"""決策隊伍勝率主線：代數、方向、終局、缺值與防洩漏。"""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from abs_challenge.baseline import SavantBaseline
from abs_challenge.policy_scenarios import analyze_cohort
from abs_challenge.provenance import build_file_manifest
from abs_challenge.state_value import GameState
from abs_challenge.win_decision import analyze_population, decide, evaluate_state, validate_protocol
from abs_challenge.wp_coverage import inspect_call
from baseline_support import set_wp, synthetic_snapshot


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((ROOT / "config/phase3_win_decision_protocol.json").read_text(encoding="utf-8"))
OLD = json.loads((ROOT / "config/policy_scenario_protocol.json").read_text(encoding="utf-8"))


class WinDecisionTests(unittest.TestCase):
    def test_gross_win_impact_and_cost_limit(self):
        result = decide(0.4, 0.5, budget=1, s0_terminal=False,
                        probability=0.5, protocol=PROTOCOL)
        self.assertAlmostEqual(result["expected_wp_without_resource_cost"], 0.45)
        self.assertAlmostEqual(result["expected_immediate_gain"], 0.05)
        self.assertAlmostEqual(result["maximum_failure_cost_for_positive_decision"]["value"], 0.1)
        self.assertEqual(result["cost_scenarios"]["large_resource_cost"]["action"], "challenge")
        self.assertAlmostEqual(result["cost_scenarios"]["large_resource_cost"]
                               ["conditional_break_even_probability"], 0.02 / 0.12)

    def test_last_budget_cost_is_higher_and_terminal_removes_it(self):
        one = decide(0.4, 0.405, budget=1, s0_terminal=False,
                     probability=0.5, protocol=PROTOCOL)
        two = decide(0.4, 0.405, budget=2, s0_terminal=False,
                     probability=0.5, protocol=PROTOCOL)
        self.assertEqual(one["cost_scenarios"]["small_resource_cost"]["action"], "tie")
        self.assertEqual(two["cost_scenarios"]["small_resource_cost"]["action"], "challenge")
        terminal = decide(0.4, 0.405, budget=1, s0_terminal=True,
                          probability=0.5, protocol=PROTOCOL)
        self.assertEqual(terminal["cost_scenarios"]["large_resource_cost"]
                         ["conditional_failure_cost"], 0)
        self.assertEqual(terminal["cost_scenarios"]["large_resource_cost"]["action"], "challenge")

    def test_zero_or_adverse_gain_cannot_be_called_beneficial(self):
        flat = decide(0.4, 0.4, budget=1, s0_terminal=False,
                      probability=0.5, protocol=PROTOCOL)
        self.assertEqual(flat["cost_scenarios"]["immediate_only"]["action"], "tie")
        self.assertEqual(flat["cost_scenarios"]["large_resource_cost"]["action"], "save")
        adverse = decide(0.4, 0.39, budget=1, s0_terminal=False,
                         probability=0.5, protocol=PROTOCOL)
        self.assertEqual(adverse["cost_scenarios"]["immediate_only"]["action"], "save")
        self.assertEqual(adverse["maximum_failure_cost_for_positive_decision"]["kind"],
                         "no_positive_gross_gain")

    def test_unsupported_and_protocol_fail_closed(self):
        self.assertEqual(decide(None, 0.5, budget=1, s0_terminal=False,
                                probability=0.5, protocol=PROTOCOL)["status"], "unsupported")
        for budget, p in ((0, 0.5), (3, 0.5), (1, -0.1), (1, float("nan"))):
            with self.subTest(budget=budget, p=p), self.assertRaises(ValueError):
                decide(0.4, 0.5, budget=budget, s0_terminal=False,
                       probability=p, protocol=PROTOCOL)
        changed = copy.deepcopy(PROTOCOL)
        changed["successful_branch_extra_shift"] = 0.005
        with self.assertRaises(ValueError):
            validate_protocol(changed)

    def test_single_state_away_perspective_and_outside(self):
        snapshot = synthetic_snapshot()
        set_wp(snapshot, (5, "top", 1, 0, 0, 1), 0, 0.6)
        set_wp(snapshot, (5, "top", 1, 0, 1, 0), 0, 0.5)
        request = {"schema_version": "policy-scenario-state-input-v1",
                   "pre_pitch_state": GameState(5, "top", 1, 0, 0, 0, 0, 0).to_dict(),
                   "original_call": "strike", "challenges_remaining": 1,
                   "assume_pure_called_pitch": True}
        result = evaluate_state(snapshot, request, PROTOCOL)
        self.assertEqual(result["decision_side"], "batting")
        self.assertAlmostEqual(result["results_by_probability"]["0.5"]["wp_s0"], 0.4)
        self.assertAlmostEqual(result["results_by_probability"]["0.5"]["wp_s1"], 0.5)
        request["pre_pitch_state"]["home_score"] = 7
        self.assertEqual(evaluate_state(snapshot, request, PROTOCOL)["status"], "unsupported")

    def test_historical_action_and_outcome_cannot_change_cohort_decision(self):
        state = GameState(5, "bottom", 1, 0, 0, 0, 0, 0)
        snapshot = synthetic_snapshot()
        set_wp(snapshot, (5, "bottom", 1, 0, 0, 1), 0, 0.4)
        set_wp(snapshot, (5, "bottom", 1, 0, 1, 0), 0, 0.5)
        baseline = SavantBaseline(snapshot)
        valuation = inspect_call(baseline, state, "strike")
        candidate = {"at_bat_number": 1, "pitch_number": 1,
                     "decision_features": {"pre_pitch_state": state.to_dict(),
                                           "challenges_remaining": 1, "original_call": "strike",
                                           "decision_team_id": 10, "decision_side": "batting"},
                     "analysis_labels": {"population": "provisional_opportunity",
                                         "status": valuation["status"], "reason": None,
                                         "s0": valuation["s0"], "s1": valuation["s1"],
                                         "actual_challenge": False}}
        with tempfile.TemporaryDirectory() as temp:
            outputs = []
            for action in (False, True):
                candidate["analysis_labels"]["actual_challenge"] = action
                candidate["analysis_labels"]["overturned"] = action
                games, manifests, evaluations = [], [], {}
                for pk, split in enumerate(("train", "validation", "test", "external"), start=1):
                    path = Path(temp) / f"candidate_{pk}.json"
                    path.write_text(json.dumps({"schema_version": "dataset-b-provisional-candidates-v2",
                                                "game_pk": pk, "split": split,
                                                "source_eligibility_status": "provisional_source_limitations",
                                                "rows": [candidate]}), encoding="utf-8")
                    manifest = build_file_manifest(path, source_type="dataset_b_provisional_candidates")
                    games.append({"game_pk": pk, "split": split,
                                  "status": "provisional_population_pass", "official_counter_pass": True,
                                  "candidate_artifact": str(path), "candidate_manifest": manifest})
                    manifests.append({"game_pk": pk, **manifest})
                    evaluations[split] = {"game_clusters": 1, "selected_model": {"episodes": 1}}
                preparation = {"game_rows": games}
                previous = {"candidate_manifests": manifests, "evaluations": evaluations}
                cohort = analyze_cohort(preparation, previous, baseline, OLD)
                outputs.append(analyze_population(preparation, previous, cohort, snapshot, OLD, PROTOCOL))
        self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
