"""來源訊號不等於逐球資格證明。"""

import unittest

from abs_challenge.source_eligibility import candidate_source_status, inspect_source_signals, summarize_source_audits


class SourceEligibilityTests(unittest.TestCase):
    def test_abs_review_alone_does_not_prove_full_game_availability(self):
        feed = {"gamePk": 123, "liveData": {"plays": {"allPlays": [
            {"atBatIndex": 0, "playEvents": [
                {"index": 0, "type": "pitch", "reviewDetails": {"reviewType": "MJ"},
                 "details": {"description": "Called Strike"}},
            ]},
        ]}}}
        audit = inspect_source_signals(feed)
        self.assertEqual(audit["abs_review_events"], 1)
        self.assertEqual(audit["technical_interval_coverage"], "unknown")
        self.assertEqual(audit["post_replay_ordering_coverage"], "unknown")
        self.assertEqual(audit["hints"], [])
        self.assertEqual(candidate_source_status()["abs_technical_availability"], "unknown")

    def test_replay_and_technical_text_remain_hints_not_eligibility(self):
        feed = {"gamePk": 456, "liveData": {"plays": {"allPlays": [
            {"atBatIndex": 2, "playEvents": [
                {"index": 0, "type": "action", "details": {"description": "Replay Review"},
                 "reviewDetails": {"reviewType": "other"}},
                {"index": 1, "type": "action", "details": {"description": "ABS technical issue"}},
            ]},
        ]}}}
        audit = inspect_source_signals(feed)
        self.assertEqual({hint["signal_type"] for hint in audit["hints"]},
                         {"non_abs_review_type", "replay_text_hint", "technical_text_hint"})
        self.assertTrue(all(hint["at_bat_number"] == 3 for hint in audit["hints"]))
        self.assertEqual(audit["technical_interval_coverage"], "unknown")
        self.assertEqual(audit["post_replay_ordering_coverage"], "unknown")

    def test_summary_keeps_missing_feed_in_denominator(self):
        audit = {"abs_review_events": 2, "hints": [],
                 "technical_interval_coverage": "unknown",
                 "post_replay_ordering_coverage": "unknown"}
        result = summarize_source_audits([{"eligibility_source_audit": audit}, {}])
        self.assertEqual(result["selected_games"], 2)
        self.assertEqual(result["games_with_feed_audit"], 1)
        self.assertEqual(result["games_without_feed_audit"], 1)
        self.assertEqual(result["abs_review_events"], 2)
        self.assertEqual(result["hint_events"], 0)
        self.assertFalse(result["complete_eligibility_evidence"])


if __name__ == "__main__":
    unittest.main()
