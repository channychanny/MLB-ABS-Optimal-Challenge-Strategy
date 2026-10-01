"""Savant 有挑戰球、官方有計數，但 feed 漏掉 review 時的復原測試。"""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from abs_challenge.abs_recovery import recover_abs_only_challenges
from abs_challenge.audit import _official_abs_totals, audit_feed
from abs_challenge.rules import resolve_game_rules
from historical_support import game_fixture
from scripts.prepare_dataset_b import _one_feed


def missing_review_fixture():
    feed, rows = game_fixture(season=2025, game_pk=501)
    for side, team_id in (("away", 10), ("home", 20)):
        feed["gameData"]["teams"][side].update(id=team_id,
            sport={"id": 11}, league={"id": 117})
    feed["gameData"]["absChallenges"] = {"hasChallenges": True,
        "away": {"usedSuccessful": 0, "usedFailed": 0},
        "home": {"usedSuccessful": 1, "usedFailed": 0}}
    for play in feed["liveData"]["plays"]["allPlays"]:
        play["atBatIndex"] = play["about"]["atBatIndex"]
    pitch = feed["liveData"]["plays"]["allPlays"][0]["playEvents"][0]
    pitch["details"] = {"call": {"code": "C", "description": "Called Strike"},
                        "description": "Called Strike", "isBall": False, "isStrike": True, "isInPlay": False}
    pitch["count"] = {"balls": 0, "strikes": 1, "outs": 0}
    rows[0].update(balls="0", strikes="0", description="called_strike")
    feed["liveData"]["plays"]["allPlays"][0]["playEvents"][1]["count"] = {
        "balls": 0, "strikes": 1, "outs": 0}
    rows[1].update(balls="0", strikes="1")
    abs_rows = [{"game_pk": "501", "at_bat_number": "1", "pitch_number": "1",
                 "description": "called_strike", "des": ""}]
    return feed, rows, abs_rows


class AbsRecoveryTests(unittest.TestCase):
    def test_explicit_zero_official_counters_confirm_zero_attempts(self):
        counters = {"hasChallenges": False,
                    "home": {"usedSuccessful": 0, "usedFailed": 0},
                    "away": {"usedSuccessful": 0, "usedFailed": 0}}
        self.assertEqual(_official_abs_totals({"absChallenges": counters}), (0, 0))
        self.assertIsNone(_official_abs_totals({"absChallenges": {"hasChallenges": False}}))

    def test_missing_review_requires_abs_pitch_alignment_and_official_team_counter(self):
        feed, rows, abs_rows = missing_review_fixture()
        rules = resolve_game_rules(feed)
        self.assertFalse(audit_feed(feed, rules)["summary"]["official_counter_pass"])
        recovered = recover_abs_only_challenges(feed, rows, abs_rows)
        self.assertEqual(len(recovered["events"]), 1)
        self.assertEqual(recovered["evidence"][0]["at_bat_number"], 1)
        self.assertEqual(recovered["events"][0].review_source, "savant_abs_only_counter_reconciled")
        self.assertEqual(recovered["events"][0].original_call, "ball")
        self.assertEqual(recovered["events"][0].challenge_team_id, 20)
        self.assertTrue(audit_feed(feed, rules, challenge_events=recovered["events"])["summary"]["official_counter_pass"])

    def test_missing_abs_row_or_wrong_official_team_does_not_invent_event(self):
        feed, rows, abs_rows = missing_review_fixture()
        with self.assertRaisesRegex(ValueError, "ABS-only"):
            recover_abs_only_challenges(feed, rows, [])
        feed["gameData"]["absChallenges"]["home"]["usedSuccessful"] = 0
        feed["gameData"]["absChallenges"]["away"]["usedSuccessful"] = 1
        with self.assertRaisesRegex(ValueError, "唯一"):
            recover_abs_only_challenges(feed, rows, abs_rows)

    def test_preparation_preserves_counter_mismatch_for_later_recovery(self):
        feed, _, _ = missing_review_fixture()
        selected = {"game_pk": 501, "date": "2025-06-01", "split": "train",
                    "window": "train_2025_il_early", "regime": "aaa-2025-il",
                    "sport_id": 11, "league_id": 117}
        with patch("scripts.prepare_dataset_b.SourceCache.get", return_value={
                "text": json.dumps(feed), "manifest": {"source_type": "fixture"}}):
            row, retained_feed, _ = _one_feed(selected, Path("unused"), True)
        self.assertEqual(row["status"], "feed_counter_mismatch", row)
        self.assertEqual(row["official_counter_pass"], False)
        self.assertEqual(retained_feed["gamePk"], 501)


if __name__ == "__main__":
    unittest.main()
