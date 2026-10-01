"""賽程抽樣不讀挑戰／比分，來源缺失不遞補。"""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from abs_challenge.coverage_sampling import build_selection, select_games, validate_plan
from abs_challenge.source_cache import SourceCache


def fixture():
    stratum = {"id": "test-2025", "date": "2025-07-20", "sport_id": 11, "league_id": 117, "take": 2}
    plan = {"schema_version": "wp-coverage-sampling-v1", "selection": "sha256_seed_stratum_game_pk",
            "replacement": False, "seed": "fixed", "strata": [stratum], "development_game_pks": []}
    games = [{"gamePk": pk, "officialDate": stratum["date"], "gameType": "R", "scheduledInnings": 9,
              "status": {"abstractGameState": "Final"},
              "teams": {side: {"team": {"sport": {"id": 11}, "league": {"id": 117}}}
                        for side in ("home", "away")}} for pk in (10, 11, 12)]
    return plan, stratum, {"dates": [{"date": stratum["date"], "games": games}]}


class SamplingTests(unittest.TestCase):
    def test_selection_does_not_depend_on_score_challenges_or_order(self):
        plan, stratum, payload = fixture()
        original = select_games(plan, stratum, payload)
        for game in payload["dates"][0]["games"]:
            game["absChallenges"] = {"attempts": 900}
            game["teams"]["home"]["score"] = 99
        payload["dates"][0]["games"].reverse()
        self.assertEqual(select_games(plan, stratum, payload), original)

    def test_shortfall_and_unknown_metadata_are_explicit(self):
        plan, stratum, payload = fixture()
        payload["dates"][0]["games"][0].pop("scheduledInnings")
        payload["dates"][0]["games"][1]["teams"]["home"]["team"].pop("league")
        result = select_games(plan, stratum, payload)
        self.assertEqual(result["shortfall"], 1)
        self.assertEqual(len(result["excluded"]), 2)

    def test_wrong_regime_duplicate_dates_and_replacement_rejected(self):
        for field, value in (("date", "2023-07-20"), ("league_id", 999), ("take", True)):
            plan, _, _ = fixture()
            plan["strata"][0][field] = value
            with self.assertRaises(ValueError):
                validate_plan(plan)
        plan, _, _ = fixture()
        plan["strata"].append(deepcopy(plan["strata"][0]))
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_duplicate_game_is_not_silently_deduplicated(self):
        plan, stratum, payload = fixture()
        payload["dates"][0]["games"].append(payload["dates"][0]["games"][0])
        with self.assertRaises(ValueError):
            select_games(plan, stratum, payload)

    def test_offline_replay_and_missing_source(self):
        plan, _, payload = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            live = build_selection(plan, SourceCache(root, fetch=lambda _: json.dumps(payload)))
            replay = build_selection(plan, SourceCache(root, offline=True))
            self.assertEqual(live["selection_sha256"], replay["selection_sha256"])
            self.assertTrue(live["selection_complete"])
            missing = build_selection(plan, SourceCache(root / "missing", offline=True))
            self.assertFalse(missing["selection_complete"])
            self.assertEqual(missing["strata"][0]["status"], "source_failure")
            self.assertEqual(missing["selected_count"], 0)

    def test_known_development_game_is_excluded_before_ranking(self):
        plan, stratum, payload = fixture()
        plan["development_game_pks"] = [10]
        result = select_games(plan, stratum, payload)
        self.assertNotIn(10, [g["game_pk"] for g in result["selected"]])
        self.assertEqual(result["excluded"], [{"game_pk": 10, "reason": "known_development_game"}])
