"""額度感知 episode 與事後條件到達模型的邊界測試。"""

import unittest

from abs_challenge.dataset_b_resource_aware import build_game_episodes, evaluate_contract


GAME = {"game_pk": 1, "split": "train"}


def _row(index, budget, *, action=False, population="provisional_opportunity",
         observed=False, gap=5, team=10, at_bat=1):
    return {"at_bat_number": at_bat, "pitch_number": index,
            "physical_pitch_index": index,
            "alignment_evidence": {"feed_event_index": index},
            "decision_features": {"decision_team_id": team,
                                  "decision_side": "fielding",
                                  "challenges_remaining": budget,
                                  "pre_pitch_state": {"inning": 5, "balls": 1, "strikes": 1}},
            "analysis_labels": {"actual_challenge": action, "population": population},
            "arrival_target": {"pitch_gap": gap, "next_opportunity_observed": observed,
                               "censoring_boundary": None if observed else "regulation_end"}}


class ResourceAwareTests(unittest.TestCase):
    def test_failed_last_challenge_terminates_at_action_not_regulation(self):
        rows = [_row(3, 1, action=True, gap=7),
                _row(5, 0, population="zero_budget", gap=5)]
        episodes = build_game_episodes(GAME, rows, {(1, 3): (False, 10)})
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]["outcome"], "budget_exhausted")
        self.assertEqual(episodes[0]["gap"], 0)
        self.assertEqual(episodes[0]["post_action_budget"], 0)
        self.assertFalse(episodes[0]["regulation_end_coincident"])

    def test_exhaustion_on_last_pitch_records_both_boundaries(self):
        episodes = build_game_episodes(GAME, [_row(3, 1, action=True, gap=0)],
                                       {(1, 3): (False, 10)})
        self.assertEqual(episodes[0]["outcome"], "budget_exhausted")
        self.assertTrue(episodes[0]["regulation_end_coincident"])

    def test_final_success_remains_regulation_censor_without_future_candidate(self):
        episodes = build_game_episodes(GAME, [_row(3, 1, action=True, gap=7)],
                                       {(1, 3): (True, 10)})
        self.assertEqual(episodes[0]["outcome"], "regulation_end")
        self.assertEqual(episodes[0]["post_action_budget"], 1)
        self.assertEqual(episodes[0]["challenge_overturned"], True)
        self.assertEqual(episodes[0]["gap"], 7)

    def test_failed_challenge_with_two_left_uses_post_action_budget(self):
        rows = [_row(3, 2, action=True, observed=True, gap=4),
                _row(7, 1, gap=3)]
        episodes = build_game_episodes(GAME, rows, {(1, 3): (False, 10)})
        self.assertEqual(episodes[0]["outcome"], "next_opportunity")
        self.assertEqual(episodes[0]["post_action_budget"], 1)
        self.assertEqual(episodes[0]["gap"], 4)

    def test_inconsistent_budget_and_missing_challenge_fail_closed(self):
        rows = [_row(3, 1, action=True, observed=True, gap=4),
                _row(7, 1, gap=3)]
        with self.assertRaisesRegex(ValueError, "額度轉移不一致"):
            build_game_episodes(GAME, rows, {(1, 3): (False, 10)})
        with self.assertRaisesRegex(ValueError, "一對一對齊"):
            build_game_episodes(GAME, rows, {})

    def test_wrong_challenge_team_and_future_after_exhaustion_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "挑戰方與決策隊伍不一致"):
            build_game_episodes(GAME, [_row(3, 1, action=True)], {(1, 3): (False, 20)})
        rows = [_row(3, 1, action=True, observed=True, gap=4),
                _row(7, 0, population="zero_budget", gap=3),
                _row(8, 0, population="provisional_opportunity", gap=2)]
        with self.assertRaises(ValueError):
            build_game_episodes(GAME, rows, {(1, 3): (False, 10)})

    def test_challenge_outside_risk_set_is_not_silently_ignored(self):
        with self.assertRaisesRegex(ValueError, "歷史挑戰行動或額度無效"):
            build_game_episodes(GAME, [
                _row(3, 1, action=True, population="excluded_position_player")],
                {(1, 3): (False, 10)})

    def test_terminal_excluded_from_conditional_hazard_fit(self):
        protocol = {"schema_version": "dataset-b-resource-aware-arrival-protocol-v1",
                    "estimand": "測試", "training_split": "train",
                    "selection_split": "validation", "held_out_splits": ["test", "external"],
                    "forecast_horizons_pitches": [5],
                    "smoothing_prior_pitch_exposures": [25],
                    "selection_metric": "negative_log_likelihood_per_pitch_exposure",
                    "primary_metric": "negative_log_likelihood_per_pitch_exposure",
                    "secondary_metric": "negative_log_likelihood_per_episode",
                    "bootstrap_replicates": 2, "bootstrap_seed": 1, "limitations": []}
        sample = [
            {"game_pk": 1, "outcome": "next_opportunity", "post_action_budget": 1,
             "balls": 1, "strikes": 1, "gap": 2, "event_observed": True},
            {"game_pk": 1, "outcome": "regulation_end", "post_action_budget": 1,
             "balls": 1, "strikes": 1, "gap": 4, "event_observed": False},
            {"game_pk": 1, "outcome": "budget_exhausted", "post_action_budget": 0,
             "balls": 1, "strikes": 1, "gap": 0, "event_observed": False},
        ]
        result = evaluate_contract({split: sample for split in (
            "train", "validation", "test", "external")}, protocol)
        self.assertEqual(result["training_fit"]["episodes"], 2)
        self.assertEqual(result["outcome_counts_by_split"]["train"]["budget_exhausted"], 1)
        self.assertFalse(result["decision_time_counterfactual_ready"])
        self.assertFalse(result["formal_dynamic_policy_ready"])


if __name__ == "__main__":
    unittest.main()
