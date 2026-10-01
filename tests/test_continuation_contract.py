"""合成有限視野契約；不將人工分支當成實際比賽反事實。"""

import unittest

from abs_challenge.baseline import SavantBaseline
from abs_challenge.continuation_contract import (
    BoundedLeaf, ChanceNode, ChallengeDecision, StateStep,
    regulation_tie_leaf, solve_finite_horizon, terminal_leaf,
)
from baseline_support import synthetic_snapshot


class ContinuationContractTests(unittest.TestCase):
    def test_outside_then_reentry_keeps_branch_probability_and_value(self):
        root = ChanceNode(((0.4, StateStep(6, StateStep(5, BoundedLeaf(0.7, 0.7)))),
                           (0.6, BoundedLeaf(0.3, 0.3))))
        result = solve_finite_horizon(root, 0)
        self.assertAlmostEqual(result["value_interval"][0], 0.46)
        self.assertEqual(result["outside_mass_interval"], [0.4, 0.4])
        self.assertEqual(result["reentry_mass_interval"], [0.4, 0.4])
        self.assertEqual(result["unresolved_mass_interval"], [0.0, 0.0])
        self.assertFalse(result["formal_policy_evaluation_ready"])

    def test_actions_have_distinct_outside_mass_and_unknown_value(self):
        root = ChallengeDecision(0.5, BoundedLeaf(0.4, 0.4),
                                 StateStep(6, BoundedLeaf(0.0, 1.0, "未知跨界延續")))
        result = solve_finite_horizon(root, 1)
        self.assertEqual(result["q_save"]["outside_mass_interval"], [0.0, 0.0])
        self.assertEqual(result["q_challenge"]["outside_mass_interval"], [0.5, 0.5])
        self.assertEqual(result["q_challenge"]["unresolved_mass_interval"], [0.5, 0.5])
        self.assertEqual(result["q_challenge"]["value_interval"], [0.2, 0.7])
        self.assertEqual(result["action"], "undetermined")
        self.assertEqual(solve_finite_horizon(root, 0)["action"], "save")

    def test_budget_retention_can_change_root_action(self):
        later = ChallengeDecision(0.5, BoundedLeaf(0.2, 0.2), BoundedLeaf(1.0, 1.0))
        root = ChallengeDecision(0.5, later, BoundedLeaf(0.8, 0.8))
        self.assertEqual(solve_finite_horizon(root, 1)["action"], "save")
        self.assertEqual(solve_finite_horizon(root, 2)["action"], "challenge")

    def test_regulation_tie_uses_versioned_boundary_not_extra_inning_policy(self):
        baseline = SavantBaseline(synthetic_snapshot())
        leaf = regulation_tie_leaf(baseline, decision_home=False)
        result = solve_finite_horizon(leaf, 2)
        self.assertEqual(result["value_interval"], [1 - baseline.boundary] * 2)
        self.assertIn("savant-regulation-tie-home-v1", leaf.assumption)
        self.assertFalse(result["extra_inning_policy_modeled"])
        outside_win = solve_finite_horizon(
            StateStep(6, terminal_leaf("home_win", baseline, decision_home=True)), 0)
        self.assertEqual(outside_win["value_interval"], [1.0, 1.0])
        self.assertEqual(outside_win["outside_mass_interval"], [1.0, 1.0])

    def test_invalid_probability_and_silent_unknown_are_rejected(self):
        with self.assertRaises(ValueError):
            ChanceNode(((0.4, BoundedLeaf(0.2, 0.2)),))
        with self.assertRaises(ValueError):
            BoundedLeaf(0.0, 1.0)
        with self.assertRaises(ValueError):
            solve_finite_horizon(BoundedLeaf(0.5, 0.5), 3)
        with self.assertRaisesRegex(ValueError, "表外終點"):
            solve_finite_horizon(StateStep(6, BoundedLeaf(0.9, 0.9)), 0)
        with self.assertRaisesRegex(ValueError, "表外終點"):
            solve_finite_horizon(StateStep(6, StateStep(5, StateStep(7, BoundedLeaf(0.9, 0.9)))), 0)

    def test_explicit_outside_sensitivity_can_change_action(self):
        def scenario(lower, upper):
            return ChallengeDecision(1.0, BoundedLeaf(0.4, 0.4),
                StateStep(6, BoundedLeaf(lower, upper, "人工跨界敏感度")))
        self.assertEqual(solve_finite_horizon(scenario(0.0, 1.0), 1)["action"], "undetermined")
        self.assertEqual(solve_finite_horizon(scenario(0.5, 0.8), 1)["action"], "challenge")
        self.assertEqual(solve_finite_horizon(scenario(0.1, 0.3), 1)["action"], "save")


if __name__ == "__main__":
    unittest.main()
