"""事前候選與事後標籤的隔離測試。"""

import copy
import unittest

from abs_challenge.decision_time_audit import summarize
from abs_challenge.option_proxy import game_labels


def candidate(index, *, population="provisional_opportunity", supported=True, team=1):
    return {
        "physical_pitch_index": index, "at_bat_number": index, "pitch_number": 1,
        "decision_features": {
            "decision_team_id": team, "decision_side": "batting",
            "challenges_remaining": 2 if population == "provisional_opportunity" else 0,
            "pre_pitch_state": {"inning": 5},
        },
        "analysis_labels": {
            "population": population, "actual_challenge": False,
            "s0": {"supported": supported, "wp_decision": 0.4 if supported else None},
            "s1": {"supported": supported, "wp_decision": 0.41 if supported else None},
        },
    }


class DecisionTimeAuditTests(unittest.TestCase):
    def test_outcome_and_action_mutations_do_not_select_candidates(self):
        rows = [candidate(1), candidate(2, population="zero_budget"), candidate(3)]
        original = game_labels(rows, game_pk=9, split="train")
        changed = copy.deepcopy(rows)
        for row in changed:
            row["analysis_labels"].update(actual_challenge=True, overturned=True,
                                          reasonable_candidate=False,
                                          pitch_observation={"plate_x": 99},
                                          post_action_budget=-1)
        self.assertEqual(original, game_labels(changed, game_pk=9, split="train"))
        self.assertEqual(len(original), 2)
        self.assertEqual(summarize(original)["historical_next_adverse_call_observed"], 1)

    def test_missing_wp_is_reported_not_zero_filled_or_dropped(self):
        rows = [candidate(1, supported=False), candidate(2),
                candidate(3, population="zero_budget", supported=False)]
        summary = summarize(game_labels(rows, game_pk=9, split="test"))
        self.assertEqual(summary["candidate_starts"], 2)
        self.assertEqual(summary["current_wp_unsupported"], 1)
        self.assertEqual(summary["historical_next_adverse_call_observed"], 2)
        self.assertEqual(summary["next_call_wp_unsupported"], 1)

    def test_future_opportunity_is_not_filtered_by_wp_value(self):
        rows = [candidate(1), candidate(2, population="zero_budget")]
        rows[1]["analysis_labels"]["s1"]["wp_decision"] = 0.4
        summary = summarize(game_labels(rows, game_pk=9, split="validation"))
        self.assertEqual(summary["historical_next_adverse_call_observed"], 1)
        self.assertEqual(summary["next_call_hypothetical_delta_wp_bins"], {"nonpositive": 1})


if __name__ == "__main__":
    unittest.main()
