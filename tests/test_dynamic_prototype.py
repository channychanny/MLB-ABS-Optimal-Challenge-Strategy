"""手算有限樹，驗證額度保留而非只搜尋固定門檻。"""

import unittest

from abs_challenge.dynamic_prototype import ChallengeNode, ValueLeaf, build_dynamic_demo, solve_scenario
from abs_challenge.baseline import SavantBaseline
from baseline_support import synthetic_snapshot


class DynamicPrototypeTests(unittest.TestCase):
    def test_last_opportunity_challenges_when_positive(self) -> None:
        root = ChallengeNode(0.5, ValueLeaf(0.4), ValueLeaf(0.8))
        self.assertEqual(solve_scenario(root, 0)["action"], "save")
        self.assertAlmostEqual(solve_scenario(root, 1)["value"], 0.6)

    def test_saving_one_challenge_can_dominate_but_two_changes_decision(self) -> None:
        later = ChallengeNode(0.5, ValueLeaf(0.2), ValueLeaf(1.0))
        root = ChallengeNode(0.5, later, ValueLeaf(0.8))
        one, two = solve_scenario(root, 1), solve_scenario(root, 2)
        self.assertAlmostEqual(one["q_save"], 0.6)
        self.assertAlmostEqual(one["q_challenge"], 0.5)
        self.assertEqual(one["action"], "save")
        self.assertAlmostEqual(two["q_challenge"], 0.7)
        self.assertEqual(two["action"], "challenge")

    def test_success_retains_budget_for_success_branch(self) -> None:
        later = ChallengeNode(1.0, ValueLeaf(0.2), ValueLeaf(0.9))
        root = ChallengeNode(1.0, ValueLeaf(0.1), later)
        self.assertEqual(solve_scenario(root, 1)["value"], 0.9)

    def test_zero_probability_and_ties_do_not_consume_budget(self) -> None:
        result = solve_scenario(ChallengeNode(0.0, ValueLeaf(0.4), ValueLeaf(0.9)), 1)
        self.assertEqual(result["action"], "save")
        self.assertEqual(result["value"], 0.4)

    def test_rejects_three_challenges_and_invalid_probabilities(self) -> None:
        for budget in (-1, 3, True, 1.5):
            with self.assertRaises(ValueError):
                solve_scenario(ValueLeaf(0.5), budget)
        for p in (-0.1, 1.1, float("nan"), True):
            with self.assertRaises(ValueError):
                ChallengeNode(p, ValueLeaf(0.2), ValueLeaf(0.8))

    def test_demo_explicitly_not_formal_evaluation(self) -> None:
        demo = build_dynamic_demo(SavantBaseline(synthetic_snapshot()))
        self.assertFalse(demo["formal_policy_evaluation_ready"])
        self.assertEqual(demo["assumptions"]["opponent_policy"], "never_challenge")
        self.assertEqual(demo["assumptions"]["probability_source"], "assumed_not_fitted")
        self.assertEqual([r["challenges_remaining"] for r in demo["results"]], [0, 1, 2])
