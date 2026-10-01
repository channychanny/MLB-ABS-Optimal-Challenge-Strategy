"""Dataset B 賽程抽樣不以結果選場，且可由快取離線重播。"""

import json
from pathlib import Path
import tempfile
import unittest

from abs_challenge.dataset_b_sampling import (
    build_selection, schedule_url, select_window, validate_sampling_plan,
)
from abs_challenge.source_cache import SourceCache


ROOT = Path(__file__).resolve().parents[1]
SAMPLING = json.loads((ROOT / "config/dataset_b_sampling.json").read_text(encoding="utf-8"))
SPLIT = json.loads((ROOT / "config/dataset_b_split_plan.json").read_text(encoding="utf-8"))


def game(pk, date, *, sport=11, league=117, final=True):
    team = {"sport": {"id": sport}, "league": {"id": league}}
    return {"gamePk": pk, "officialDate": date, "gameType": "R",
            "status": {"abstractGameState": "Final" if final else "Preview"},
            "scheduledInnings": 9,
            "teams": {"away": {"team": team}, "home": {"team": team}}}


class DatasetBSamplingTests(unittest.TestCase):
    def test_plan_matches_all_predeclared_windows(self):
        validate_sampling_plan(SAMPLING, SPLIT)
        self.assertEqual(sum(SAMPLING["quotas"].values()), 96)
        broken = {**SAMPLING, "quotas": {"train_2024_il": 1}}
        with self.assertRaisesRegex(ValueError, "配額"):
            validate_sampling_plan(broken, SPLIT)

    def test_selection_ignores_outcome_and_excludes_development(self):
        window = SPLIT["windows"][1]
        day = "2025-05-20"
        a, b = game(900001, day), game(900002, day)
        excluded = game(780464, day)
        payload = {"dates": [{"date": day, "games": [a, b, excluded, game(900003, day, final=False)]}]}
        small = {**SAMPLING, "quotas": {**SAMPLING["quotas"], window["name"]: 1}}
        first = select_window(small, SPLIT, window, payload)
        a["teams"]["home"]["score"] = 20
        b["absChallenges"] = {"successful": 99}
        second = select_window(small, SPLIT, window, payload)
        self.assertEqual(first, second)
        self.assertEqual(first["excluded"], [
            {"game_pk": 780464, "reason": "known_development_game"},
            {"game_pk": 900003, "reason": "not_final"}])
        self.assertTrue(first["selected"][0]["feed_rule_confirmation_required"])
        self.assertEqual(first["selected"][0]["source_eligibility_status"], "provisional_source_limitations")

    def test_shortfall_and_out_of_window_response(self):
        window = SPLIT["windows"][2]
        payload = {"dates": [{"date": "2025-07-01", "games": [game(900004, "2025-07-01")]}]}
        result = select_window(SAMPLING, SPLIT, window, payload)
        self.assertEqual(result["shortfall"], 11)
        self.assertEqual(result["status"], "shortfall")
        with self.assertRaisesRegex(ValueError, "超出"):
            select_window(SAMPLING, SPLIT, window,
                          {"dates": [{"date": "2025-06-30", "games": []}]})

    def test_rescheduled_listing_does_not_duplicate_game(self):
        window = SPLIT["windows"][2]
        moved = game(900005, "2025-07-02")
        payload = {"dates": [{"date": "2025-07-01", "games": [moved]},
                             {"date": "2025-07-02", "games": [moved]}]}
        result = select_window(SAMPLING, SPLIT, window, payload)
        self.assertEqual(result["rescheduled_listings_ignored"], 1)
        self.assertEqual([row["game_pk"] for row in result["selected"]], [900005])

    def test_source_failure_keeps_readiness_false(self):
        with tempfile.TemporaryDirectory() as directory:
            result = build_selection(SAMPLING, SPLIT, SourceCache(Path(directory), offline=True))
        self.assertEqual(result["selected_count"], 0)
        self.assertFalse(result["selection_complete"])
        self.assertFalse(result["holdout_game_lists_locked"])
        self.assertTrue(all(row["status"] == "source_failure" for row in result["windows"]))

    def test_url_is_only_schedule_metadata(self):
        url = schedule_url(SPLIT["windows"][0])
        self.assertIn("startDate=2024-06-25", url)
        self.assertIn("endDate=2024-09-30", url)
        self.assertNotIn("feed", url)


if __name__ == "__main__":
    unittest.main()
