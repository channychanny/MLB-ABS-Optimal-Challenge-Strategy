"""歷史路徑稽核不得偷換成反事實或表外補值。"""

import unittest

from abs_challenge.phase3_empirical_support import audit_game, summarize


def candidate(index, diff, *, observed, action=False, supported=True):
    return {
        "game_pk": 1, "physical_pitch_index": index,
        "decision_features": {
            "decision_team_id": 10, "challenges_remaining": 2,
            "pre_pitch_state": {"home_score": max(diff, 0), "away_score": max(-diff, 0)}},
        "analysis_labels": {
            "population": "provisional_opportunity", "actual_challenge": action,
            "s0": {"supported": supported}, "s1": {"supported": supported}},
        "arrival_target": {"next_opportunity_observed": observed},
        "source_eligibility": {"abs_technical_availability": "unknown",
                               "post_replay_challenge_eligibility": "unknown"},
    }


def episode(index, *, observed, gap=1, action=False):
    return {"game_pk": 1, "physical_pitch_index": index,
            "pre_action_budget": 2, "actual_challenge": action,
            "outcome": "next_opportunity" if observed else "regulation_end",
            "event_observed": observed, "gap": gap}


class EmpiricalSupportTests(unittest.TestCase):
    def setUp(self):
        self.rows = [candidate(1, 4, observed=True),
                     candidate(2, 7, observed=True, action=True),
                     candidate(3, 3, observed=False, supported=False)]
        self.episodes = [episode(1, observed=True),
                         episode(2, observed=True, action=True),
                         episode(3, observed=False)]

    def test_outside_then_reentry_is_observed_not_filled(self):
        rows = audit_game(self.rows, self.episodes)
        self.assertEqual([r["next_outside"] for r in rows], [True, False, None])
        self.assertTrue(rows[0]["observed_later_reentry"])
        self.assertTrue(rows[1]["observed_later_reentry"])
        result = summarize(rows)
        self.assertEqual(result["observed_inside_to_outside_next"], 1)
        self.assertEqual(result["observed_outside_to_inside_next"], 1)
        self.assertEqual(result["observed_next_wp_pair_unsupported"], 1)

    def test_action_or_arrival_mismatch_fails(self):
        changed = [dict(row) for row in self.episodes]
        changed[1]["actual_challenge"] = False
        with self.assertRaises(ValueError):
            audit_game(self.rows, changed)
        changed = [dict(row) for row in self.episodes]
        changed[0]["gap"] = 3
        with self.assertRaises(ValueError):
            audit_game(self.rows, changed)

    def test_source_must_remain_unknown_under_this_contract(self):
        changed = [dict(row) for row in self.rows]
        changed[0]["source_eligibility"] = {
            "abs_technical_availability": "available",
            "post_replay_challenge_eligibility": "unknown"}
        with self.assertRaises(ValueError):
            audit_game(changed, self.episodes)

    def test_budget_exhaustion_is_not_right_censoring(self):
        rows = [candidate(1, 0, observed=False, action=True)]
        episodes = [episode(1, observed=False, action=True)]
        episodes[0]["outcome"] = "budget_exhausted"
        result = summarize(audit_game(rows, episodes))
        self.assertEqual(result["resource_outcomes"], {"budget_exhausted": 1})
        self.assertEqual(result["observed_next"], 0)

    def test_other_team_does_not_become_next_opportunity(self):
        rows = [candidate(1, 0, observed=False), candidate(2, 7, observed=False)]
        rows[1]["decision_features"]["decision_team_id"] = 11
        episodes = [episode(1, observed=False), episode(2, observed=False)]
        result = audit_game(rows, episodes)
        self.assertEqual([row["next_outside"] for row in result], [None, None])


if __name__ == "__main__":
    unittest.main()
