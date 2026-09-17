"""固定選樣、逐日來源共用、跨年度隔離與續跑的行為測試。"""

from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from urllib.error import URLError

from abs_challenge.historical_batch import normalize_schedule, run_historical_batch, schedule_url, validate_plan
from abs_challenge.source_cache import SourceCache
from abs_challenge.cli import main
from historical_support import bundle_fixture, contract, game_fixture


def batch_sources(season=2019):
    games = [game_fixture(season=season, game_pk=501), game_fixture(season=season, game_pk=502)]
    entries, sources = [], {}
    all_rows = [row for feed, rows in games for row in rows]
    for feed, rows in games:
        for side, team_id in (("home", 101), ("away", 102)):
            feed["gameData"]["teams"][side]["id"] = team_id
        bundle = bundle_fixture(feed, all_rows)
        for value in (bundle["feed"], bundle["statcast"]):
            sources[value["manifest"]["source_url"]] = value["text"]
        entries.append({"gamePk": feed["gamePk"], "gameType": "R", "season": str(season),
            "officialDate": f"{season}-06-01", "scheduledInnings": 9,
            "status": {"abstractGameState": "Final"},
            "teams": {"home": {"team": {"id": 101}}, "away": {"team": {"id": 102}}}})
    schedule = {"totalGames": 2, "dates": [{"date": f"{season}-06-01", "games": entries}]}
    sources[schedule_url(season)] = json.dumps(schedule)
    return sources


def sample_plan(season=2019):
    return {"schema_version": "historical-batch-plan-v1", "purpose": "engineering_sample",
        "seasons": [season], "dates": [f"{season}-06-01"], "games_per_date": 2,
        "selection": "lowest_game_pk_among_final_regular_games"}


class HistoricalBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = batch_sources()
        self.fetch = Mock(side_effect=lambda url: self.sources[url])
        self.cache = SourceCache(self.root / "cache", fetch=self.fetch, sleep=Mock(), attempts=1)

    def run_batch(self, plan=None, code_signature="code-v1"):
        return run_historical_batch(sample_plan() if plan is None else plan, contract(), self.cache,
                                    self.root / "artifacts", code_signature=code_signature)

    def test_shared_csv_and_complete_coverage(self):
        report = self.run_batch()
        self.assertEqual(report["status"], "complete_selected_games")
        self.assertEqual(report["summary"]["accepted_games"], 2)
        self.assertEqual(self.fetch.call_count, 4)  # 一個賽程、一份日 CSV、兩份 feed。
        self.assertFalse(report["dataset_lock"]["formal_training_ready"])
        self.assertEqual(report["summary"]["coverage"]["score_band"]["11+"]["pitches"], 0)

    def test_offline_resume_identical_lock_and_no_network(self):
        before = self.run_batch()
        self.cache = SourceCache(self.root / "cache", offline=True, fetch=Mock(side_effect=AssertionError()))
        after = self.run_batch()
        self.assertEqual(before["dataset_lock_sha256"], after["dataset_lock_sha256"])
        self.assertEqual(after["execution"]["downloads"], 0)
        self.assertEqual(after["execution"]["reused_shards"], 2)

    def test_failed_feed_not_replaced_by_next_game_and_resumes(self):
        missing = "https://statsapi.mlb.com/api/v1.1/game/501/feed/live"
        self.cache.fetch = Mock(side_effect=lambda url: (_ for _ in ()).throw(URLError("中斷")) if url == missing else self.sources[url])
        first = self.run_batch()
        self.assertEqual(first["summary"]["accepted_games"], 1)
        self.assertEqual(first["summary"]["selected_games"], 2)
        self.assertFalse(first["dataset_lock"]["complete_selected_sources"])
        self.cache = SourceCache(self.root / "cache", fetch=self.fetch, attempts=1)
        second = self.run_batch()
        self.assertEqual(second["summary"]["accepted_games"], 2)
        self.assertEqual(second["execution"]["downloads"], 1)
        self.assertEqual(second["execution"]["reused_shards"], 1)

    def test_audit_excluded_kept_and_never_replaced(self):
        csv_url = next(u for u in self.sources if "statcast_search" in u)
        lines = self.sources[csv_url].splitlines()
        self.sources[csv_url] = "\n".join(lines[:-1]) + "\n"
        report = self.run_batch()
        self.assertEqual(report["summary"]["selected_games"], 2)
        self.assertEqual(report["summary"]["status_counts"]["audit_excluded"], 1)
        self.assertTrue(report["dataset_lock"]["complete_selected_sources"])
        self.assertFalse(report["dataset_lock"]["all_selected_games_accepted"])

    def test_source_or_schedule_failure_visible(self):
        self.cache.fetch = Mock(side_effect=URLError("無網路"))
        result = self.run_batch()
        self.assertEqual(result["dataset_lock"]["dates"][0]["status"], "schedule_failed")
        self.assertEqual(result["status"], "partial_or_excluded")

    def test_csv_failure_keeps_all_planned_games_visible(self):
        self.cache.fetch = Mock(side_effect=lambda url: (_ for _ in ()).throw(URLError("日資料失敗"))
                                if "statcast_search" in url else self.sources[url])
        result = self.run_batch()
        self.assertEqual(result["summary"]["selected_games"], 2)
        self.assertEqual(result["summary"]["status_counts"], {"source_failed": 2})
        self.assertFalse(result["dataset_lock"]["complete_selected_sources"])

    def test_no_games_on_requested_date_is_not_complete(self):
        plan = sample_plan()
        plan["dates"] = ["2019-06-02"]
        result = self.run_batch(plan)
        self.assertEqual(result["dataset_lock"]["dates"][0]["status"], "no_eligible_games")
        self.assertFalse(result["dataset_lock"]["all_selected_games_accepted"])
        self.fetch.assert_called_once()

    def test_wrong_feed_team_rejected(self):
        url = "https://statsapi.mlb.com/api/v1.1/game/501/feed/live"
        feed = json.loads(self.sources[url])
        feed["gameData"]["teams"]["home"]["id"] = 999
        self.sources[url] = json.dumps(feed)
        result = self.run_batch()
        self.assertEqual(result["summary"]["accepted_games"], 1)
        self.assertIn("身分不一致", result["dataset_lock"]["games"][0]["reason"])

    def test_test_external_and_2020_rejected_before_download(self):
        for season in (2020, 2025, 2026):
            with self.assertRaises(ValueError):
                self.run_batch(sample_plan(season))
        self.fetch.assert_not_called()

    def test_dates_duplicates_and_mismatched_seasons_rejected(self):
        plan = sample_plan()
        plan["dates"].append(plan["dates"][0])
        with self.assertRaises(ValueError):
            validate_plan(plan)
        plan["dates"] = ["2024-06-01"]
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_selection_is_fixed_by_id_not_order_or_outcome(self):
        raw = json.loads(self.sources[schedule_url(2019)])
        raw["dates"][0]["games"].reverse()
        self.sources[schedule_url(2019)] = json.dumps(raw)
        plan = sample_plan()
        plan["games_per_date"] = 1
        report = self.run_batch(plan)
        self.assertEqual([g["game_pk"] for g in report["dataset_lock"]["games"]], [501])

    def test_resume_under_new_code_keeps_old_shards(self):
        self.run_batch()
        result = self.run_batch(code_signature="code-v2")
        self.assertEqual(result["execution"]["built_shards"], 2)
        self.assertEqual(len(list((self.root / "artifacts" / "shards").glob("*.json"))), 4)

    def test_tampered_shard_not_rebuilt_or_accepted(self):
        result = self.run_batch()
        path = self.root / "artifacts" / result["dataset_lock"]["games"][0]["relative_path"]
        shard = json.loads(path.read_text(encoding="utf-8"))
        shard["dataset"]["rows"][0]["features"]["score_diff"] = 99
        path.write_text(json.dumps(shard), encoding="utf-8")
        before = path.read_bytes()
        after = self.run_batch()
        self.assertEqual(after["summary"]["accepted_games"], 1)
        self.assertEqual(before, path.read_bytes())

    def test_schedule_resumption_duplicates_counted_once(self):
        raw = json.loads(self.sources[schedule_url(2019)])
        duplicate = deepcopy(raw["dates"][0]["games"][0])
        raw["dates"].append({"date": "2019-06-02", "games": [duplicate]})
        raw["totalGames"] = 3
        normalized = normalize_schedule(json.dumps(raw), 2019)
        self.assertEqual(normalized["summary"]["unique_games"], 2)
        self.assertEqual(len(normalized["games"][0]["occurrences"]), 2)

    def test_conflicting_schedule_identity_excluded(self):
        raw = json.loads(self.sources[schedule_url(2019)])
        duplicate = deepcopy(raw["dates"][0]["games"][0])
        duplicate["officialDate"] = "2019-06-02"
        raw["dates"][0]["games"].append(duplicate)
        raw["totalGames"] = 3
        normalized = normalize_schedule(json.dumps(raw), 2019)
        self.assertEqual(normalized["games"][0]["exclusion_reason"], "schedule_identity_conflict")

    def test_cli_online_offline_and_no_overwrite(self):
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(sample_plan()), encoding="utf-8")
        output = self.root / "report.json"
        replay = self.root / "replay.json"
        args = ["run-historical-batch", "--plan", str(plan_path), "--cache-dir", str(self.root / "cache"),
                "--artifact-dir", str(self.root / "artifacts")]
        runtime = {"code_manifests": [{"source_path": __file__, "content_sha256": "fixed"}],
                   "formal_experiment_version_ready": False}
        factory = lambda root, offline: SourceCache(root, offline=offline, fetch=self.fetch)
        with redirect_stdout(io.StringIO()), patch("abs_challenge.phase2_cli._runtime", return_value=runtime), \
                patch("abs_challenge.phase2_cli.SourceCache", side_effect=factory):
            self.assertEqual(main(args + ["--output", str(output)]), 0)
            before = output.read_bytes()
            self.assertEqual(main(args + ["--output", str(output)]), 2)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(main(args + ["--offline", "--output", str(replay)]), 0)
        first = json.loads(output.read_text(encoding="utf-8"))
        second = json.loads(replay.read_text(encoding="utf-8"))
        self.assertEqual(first["dataset_lock_sha256"], second["dataset_lock_sha256"])
        self.assertEqual(second["execution"]["downloads"], 0)


if __name__ == "__main__":
    unittest.main()
