"""完整逐球母體的完整性、額度及未知資格防護。"""

import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from abs_challenge.baseline import SavantBaseline
from abs_challenge.opportunity_coverage import candidate_missing_diagnostics, grouped_candidate_support, inspect_population
from abs_challenge.provenance import build_download_manifest
from abs_challenge.savant import build_called_pitches_csv_url
from abs_challenge.wp_coverage import inspect_call, run_coverage
from baseline_support import synthetic_snapshot
from historical_support import game_fixture


def fixture():
    feed, rows = game_fixture(season=2026)
    for side, team in (("away", 10), ("home", 20)):
        feed["gameData"]["teams"][side].update(id=team, league={"id": 103})
    feed["gameData"]["players"] = {"ID900": {"primaryPosition": {"type": "Pitcher", "abbreviation": "P"}}}
    feed["gameData"]["absChallenges"] = {"hasChallenges": True,
        "home": {"usedSuccessful": 0, "usedFailed": 0}, "away": {"usedSuccessful": 0, "usedFailed": 0}}
    for play in feed["liveData"]["plays"]["allPlays"]:
        play["atBatIndex"] = play["about"]["atBatIndex"]
        play["matchup"]["pitcher"] = {"id": 900}
        for event in play["playEvents"]:
            event["details"]["description"] = "Ball" if event["details"]["call"]["code"] == "B" else "In play"
        for runner in play["runners"]:
            runner["details"]["isScoringEvent"] = runner["movement"]["end"] == "score"
    audit = {"game": {"season": 2026}, "rules": {"regime_id": "mlb-2026"}, "ledger": []}
    return feed, rows, audit


class PopulationTests(unittest.TestCase):
    def test_missing_diagnostics_keep_branch_reason_and_population(self):
        common = {"game_pk": 501, "at_bat_number": 2, "pitch_number": 1,
                  "alignment": {"feed_event_index": 0}, "year": 2025, "regime": "aaa-2025-il",
                  "inning": 4, "score_diff": 6, "count": "1-2", "decision_side": "fielding"}
        supported = {"supported": True, "post_home_score_diff": 5, "terminal": None}
        missing = {"supported": False, "missing_reason_code": "score_diff_out_of_range",
                   "post_home_score_diff": 6, "terminal": None}
        rows = [
            {**common, "population": "provisional_opportunity", "status": "both_supported",
             "s0": supported, "s1": supported},
            {**common, "pitch_number": 2, "population": "provisional_opportunity",
             "status": "one_supported", "s0": supported, "s1": missing},
            {**common, "pitch_number": 3, "population": "provisional_opportunity",
             "status": "neither_supported", "s0": missing, "s1": missing},
            {**common, "pitch_number": 4, "population": "provisional_opportunity",
             "status": "unsupported_compound_event", "reason": "同球有額外跑壘"},
            {**common, "pitch_number": 5, "population": "zero_budget", "status": "one_supported",
             "s0": missing, "s1": supported},
        ]
        result = candidate_missing_diagnostics(rows)
        self.assertEqual(len(result["rows"]), 4)
        provisional = result["summary_by_population"]["provisional_opportunity"]
        self.assertEqual(provisional["candidate_count"], 4)
        self.assertEqual(provisional["missing_candidate_count"], 3)
        self.assertEqual(provisional["branch_missing_reason_counts"], {"score_diff_out_of_range": 3})
        self.assertEqual(provisional["not_evaluated_branch_counts"], {"unsupported_compound_event": 1})
        self.assertEqual(result["summary_by_population"]["zero_budget"]["branch_missing_reason_counts"],
                         {"score_diff_out_of_range": 1})
        one = next(row for row in result["rows"] if row["pitch_number"] == 2)
        self.assertEqual(one["s1"]["post_home_score_diff"], 6)
        self.assertNotIn("s0", result["rows"][2])

    def test_grouped_support_keeps_budget_populations_and_missing_states_separate(self):
        common = {"year": 2025, "regime": "aaa-2025-il", "game_pk": 501,
                  "decision_side": "batting", "inning": 4, "score_diff": 6, "count": "1-2"}
        rows = [
            {**common, "population": "provisional_opportunity", "status": "both_supported"},
            {**common, "population": "provisional_opportunity", "status": "neither_supported"},
            {**common, "population": "provisional_opportunity", "status": "unsupported_compound_event"},
            {**common, "population": "zero_budget", "status": "both_supported"},
        ]
        result = grouped_candidate_support(rows)
        provisional = result["provisional_opportunity"]["regime"]["aaa-2025-il"]
        self.assertEqual(provisional["rows"], 3)
        self.assertEqual(provisional["status_counts"], {"both_supported": 1,
            "neither_supported": 1, "unsupported_compound_event": 1})
        self.assertEqual(provisional["both_supported_fraction"], 1 / 3)
        self.assertEqual(result["provisional_opportunity"]["score_diff"]["6"]["rows"], 3)
        self.assertEqual(result["zero_budget"]["game_pk"]["501"]["rows"], 1)

    @classmethod
    def setUpClass(cls):
        cls.baseline = SavantBaseline(synthetic_snapshot())

    def test_unchallenged_pitches_are_included(self):
        feed, rows, audit = fixture()
        result = inspect_population(self.baseline, feed, audit, rows, inspect_call)
        self.assertEqual(result["candidate_count"], 55)
        self.assertFalse(any(row["actual_challenge"] for row in result["rows"]))
        self.assertEqual({row["abs_technical_availability"] for row in result["rows"]}, {"unknown"})
        self.assertEqual({row["post_replay_challenge_eligibility"] for row in result["rows"]}, {"unknown"})

    def test_zero_budget_is_preserved(self):
        feed, rows, audit = fixture()
        audit["ledger"] = [{"inning": 1, "at_bat_index": n, "play_event_index": 0,
            "original_call": "ball", "abs_call": "ball", "challenges_before": 2 - n,
            "challenge_team_id": 20, "overturned": False} for n in (0, 1)]
        result = inspect_population(self.baseline, feed, audit, rows, inspect_call)
        self.assertGreater(result["population_counts"]["zero_budget"], 0)
        self.assertEqual(result["candidate_count"], 55)
        self.assertEqual(sum(row["actual_challenge"] for row in result["rows"]), 2)

    def test_unknown_and_position_player_are_not_silently_eligible(self):
        feed, rows, audit = fixture()
        feed["gameData"]["players"] = {}
        result = inspect_population(self.baseline, feed, audit, rows, inspect_call)
        self.assertEqual(result["population_counts"], {"eligibility_unknown": 55})
        feed["gameData"]["players"] = {"ID900": {"primaryPosition": {"type": "Infielder", "abbreviation": "SS"}}}
        result = inspect_population(self.baseline, feed, audit, rows, inspect_call)
        self.assertEqual(result["population_counts"], {"excluded_position_player": 55})

    def test_missing_pitch_and_wrong_score_fail_entire_game(self):
        feed, rows, audit = fixture()
        with self.assertRaises(ValueError):
            inspect_population(self.baseline, feed, audit, rows[1:], inspect_call)
        rows[0]["home_score"] = "2"
        with self.assertRaisesRegex(ValueError, "比分"):
            inspect_population(self.baseline, feed, audit, rows, inspect_call)

    def test_zero_attempt_game_runs_population_and_checks_manifest(self):
        feed, rows, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "data" / "raw"
            raw.mkdir(parents=True)
            (raw / "game_501.json").write_text(json.dumps(feed), encoding="utf-8")
            (root / "baseline.json").write_text(json.dumps(synthetic_snapshot()), encoding="utf-8")
            (raw / "savant_mlb_2026-06-01_abs.csv").write_text("game_pk,at_bat_number,pitch_number\n", encoding="utf-8")
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            text = buffer.getvalue()
            csv_path = raw / "savant_mlb_2026-06-01_pitches.csv"
            # 明確模擬 Windows 舊下載器的換行轉換。
            csv_path.write_bytes(text.replace("\n", "\r\n").encode())
            manifest = build_download_manifest(source_type="baseball_savant_pitch_csv",
                source_url=build_called_pitches_csv_url("2026-06-01", "mlb"), content=text, row_count=len(rows))
            Path(str(csv_path) + ".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            plan = {"schema_version": "official-wp-coverage-plan-v1", "population": "actual_attempts_development_only",
                    "coverage_required_fraction": 1.0, "baseline": "baseline.json", "evaluate_opportunities": True,
                    "games": [{"game_pk": 501, "date": "2026-06-01"}]}
            path = root / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            result = run_coverage(path, root)
            self.assertEqual(result["game_status_counts"], {"zero_attempts": 1})
            self.assertEqual(result["opportunity_report"]["selected_games_processed"], 1)
            self.assertEqual(result["opportunity_report"]["candidate_summary"]["regulation_candidates"], 55)
            csv_path.write_bytes(csv_path.read_bytes() + b"\n")
            result = run_coverage(path, root)
            self.assertEqual(result["opportunity_report"]["selected_games_processed"], 0)
            self.assertIn("manifest", result["games"][0]["opportunity_population_error"])
