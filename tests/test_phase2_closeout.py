"""Phase 2 收尾契約：固定來源、不升格未知資格、平手邊界敏感度。"""

import copy
import json
from pathlib import Path
import unittest

from abs_challenge.baseline import SavantBaseline
from abs_challenge.phase2_closeout import _alternate_baseline, _decision, validate_closeout_protocol
from abs_challenge.state_value import GameState
from abs_challenge.wp_coverage import inspect_call
from baseline_support import synthetic_snapshot


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = json.loads((ROOT / "config/policy_scenario_protocol.json").read_text(encoding="utf-8"))
CLOSEOUT = json.loads((ROOT / "config/phase2_closeout_protocol.json").read_text(encoding="utf-8"))


class Phase2CloseoutTests(unittest.TestCase):
    def test_unknown_source_and_formal_gates_cannot_be_promoted(self):
        snapshot = synthetic_snapshot()
        snapshot["regulation_boundary"]["home_win_probability"] = 0.5
        baseline = SavantBaseline(snapshot)
        validate_closeout_protocol(CLOSEOUT, SCENARIOS, baseline)
        for field, value in (("source_unknown_not_legal", False),
                             ("formal_legal_opportunity_ready", True),
                             ("counterfactual_transition_ready", True),
                             ("formal_policy_evaluation_ready", True)):
            with self.subTest(field=field):
                changed = copy.deepcopy(CLOSEOUT)
                changed[field] = value
                with self.assertRaises(ValueError):
                    validate_closeout_protocol(changed, SCENARIOS, baseline)

    def test_boundary_grid_is_ordered_and_contains_official_reference(self):
        snapshot = synthetic_snapshot()
        snapshot["regulation_boundary"]["home_win_probability"] = 0.5
        baseline = SavantBaseline(snapshot)
        for grid in ([0.4, 0.6], [0.5, 0.4, 0.6], [0.4, 0.5, 0.5, 0.6]):
            with self.subTest(grid=grid):
                changed = copy.deepcopy(CLOSEOUT)
                changed["boundary_home_wp_sensitivity"] = grid
                with self.assertRaises(ValueError):
                    validate_closeout_protocol(changed, SCENARIOS, baseline)

    def test_alternate_boundary_only_changes_tie_terminal_and_does_not_mutate_source(self):
        snapshot = synthetic_snapshot()
        snapshot["regulation_boundary"]["home_win_probability"] = 0.5
        original = SavantBaseline(snapshot)
        alternate = _alternate_baseline(snapshot, 0.75)
        state = GameState(inning=9, half="bottom", outs=2, bases=0, balls=3,
                          strikes=2, home_score=0, away_score=0)
        reference = inspect_call(original, state, "strike")
        stressed = inspect_call(alternate, state, "strike")
        self.assertEqual(snapshot["regulation_boundary"]["home_win_probability"], 0.5)
        self.assertEqual(reference["s0"]["terminal"], "regulation_tie")
        self.assertAlmostEqual(reference["s0"]["wp_decision"], 0.5)
        self.assertAlmostEqual(stressed["s0"]["wp_decision"], 0.75)
        self.assertEqual(reference["s1"]["wp_decision"], stressed["s1"]["wp_decision"])
        self.assertIn(_decision(stressed, 1, SCENARIOS, "large_resource_cost", 0.5),
                      {"challenge", "save", "tie"})


if __name__ == "__main__":
    unittest.main()
