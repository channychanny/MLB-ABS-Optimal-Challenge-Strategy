"""九局合成模型的倒推、額度、門檻、邊界與防升格測試。"""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from abs_challenge.baseline import SavantBaseline
from abs_challenge.phase3_synthetic_policy import (
    analyze_population, evaluate_input_state, future_factors, solve_state, validate_protocol,
)
from abs_challenge.policy_scenarios import analyze_cohort
from abs_challenge.provenance import build_file_manifest
from abs_challenge.state_value import GameState
from abs_challenge.wp_coverage import inspect_call
from baseline_support import set_wp, synthetic_snapshot


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((ROOT / "config/phase3_synthetic_policy.json").read_text(encoding="utf-8"))
SCENARIO_PROTOCOL = json.loads((ROOT / "config/policy_scenario_protocol.json").read_text(encoding="utf-8"))
MODERATE = PROTOCOL["scenarios"][1]


class Phase3SyntheticPolicyTests(unittest.TestCase):
    def test_no_future_opportunities_preserves_official_branch_values(self):
        scenario = copy.deepcopy(MODERATE)
        scenario["opportunity_probability_by_phase"] = {"early": 0, "middle": 0, "late": 0}
        factors = future_factors(scenario, 0.5, "dynamic")
        self.assertEqual(factors[1], (1, 1, 1))
        result = solve_state(0.4, 0.5, inning=1, budget=1, terminal0=False,
                             terminal1=False, probability=0.5, scenario=scenario,
                             fixed_threshold=0.5)
        self.assertEqual(result["policies"]["dynamic"]["action"], "challenge")
        self.assertAlmostEqual(result["synthetic_rra"]["probability"], 0)
        self.assertAlmostEqual(result["model_values_by_budget"]["0"], 0.4)

    def test_future_budget_is_monotone_and_dynamic_does_not_lose_to_fixed(self):
        result = solve_state(0.4, 0.45, inning=3, budget=1, terminal0=False,
                             terminal1=False, probability=0.5, scenario=MODERATE,
                             fixed_threshold=0.5)
        values = result["model_values_by_budget"]
        self.assertLessEqual(values["0"], values["1"])
        self.assertLessEqual(values["1"], values["2"])
        self.assertGreaterEqual(result["policies"]["dynamic"]["value"],
                                result["policies"]["fixed_confidence"]["value"])
        self.assertGreaterEqual(result["policies"]["dynamic"]["value"],
                                result["policies"]["never"]["value"])
        self.assertEqual(result["synthetic_rra"]["kind"], "synthetic_break_even")

    def test_one_inning_bellman_and_synthetic_rra_match_hand_calculation(self):
        scenario = copy.deepcopy(MODERATE)
        scenario["opportunity_probability_by_phase"] = {"early": 0, "middle": 0, "late": 1}
        scenario["adverse_wp_loss_fraction"] = 0.2
        scenario["future_overturn_probability"] = 0.5
        factors = future_factors(scenario, 0.5, "dynamic")
        self.assertAlmostEqual(factors[9][0], 0.8)
        self.assertAlmostEqual(factors[9][1], 0.9)
        result = solve_state(0.4, 0.5, inning=9, budget=1, terminal0=False,
                             terminal1=False, probability=0.5, scenario=scenario,
                             fixed_threshold=0.5)
        self.assertAlmostEqual(result["policies"]["dynamic"]["q_save"], 0.36)
        self.assertAlmostEqual(result["policies"]["dynamic"]["q_challenge"], 0.385)
        self.assertAlmostEqual(result["synthetic_rra"]["probability"], 0.04 / 0.13)

    def test_success_retains_and_failure_loses_budget(self):
        scenario = copy.deepcopy(MODERATE)
        scenario["opportunity_probability_by_phase"] = {"early": 0, "middle": 0, "late": 1}
        scenario["adverse_wp_loss_fraction"] = 0.2
        scenario["future_overturn_probability"] = 1
        at_one = solve_state(0.4, 0.5, inning=9, budget=1, terminal0=False,
                             terminal1=False, probability=0, scenario=scenario,
                             fixed_threshold=0.5)
        at_two = solve_state(0.4, 0.5, inning=9, budget=2, terminal0=False,
                             terminal1=False, probability=0, scenario=scenario,
                             fixed_threshold=0.5)
        self.assertEqual(at_one["policies"]["dynamic"]["action"], "save")
        self.assertGreaterEqual(at_two["model_values_by_budget"]["2"],
                                at_one["model_values_by_budget"]["1"])

    def test_terminal_branch_stops_future_synthetic_opportunities(self):
        result = solve_state(0.5, 1, inning=9, budget=1, terminal0=True,
                             terminal1=True, probability=0.5, scenario=MODERATE,
                             fixed_threshold=0.5)
        self.assertAlmostEqual(result["policies"]["dynamic"]["q_save"], 0.5)
        self.assertAlmostEqual(result["policies"]["dynamic"]["q_challenge"], 0.75)
        self.assertAlmostEqual(result["synthetic_rra"]["probability"], 0)

    def test_no_positive_success_gain_has_no_rra(self):
        result = solve_state(0.6, 0.5, inning=9, budget=1, terminal0=True,
                             terminal1=True, probability=0.9, scenario=MODERATE,
                             fixed_threshold=0.5)
        self.assertEqual(result["policies"]["dynamic"]["action"], "save")
        self.assertEqual(result["synthetic_rra"]["kind"], "never_strictly_challenge")
        self.assertIsNone(result["synthetic_rra"]["probability"])

    def test_unsupported_branch_and_extra_inning_fail_closed(self):
        result = solve_state(None, 0.5, inning=7, budget=1, terminal0=False,
                             terminal1=False, probability=0.5, scenario=MODERATE,
                             fixed_threshold=0.5)
        self.assertEqual(result["status"], "unsupported")
        self.assertIsNone(result["policies"])
        with self.assertRaises(ValueError):
            solve_state(0.4, 0.5, inning=10, budget=1, terminal0=False,
                        terminal1=False, probability=0.5, scenario=MODERATE,
                        fixed_threshold=0.5)

    def test_protocol_refuses_empirical_or_formal_claims(self):
        validate_protocol(PROTOCOL)
        for field, value in (("future_opportunity_source", "dataset_b_hazard"),
                             ("counterfactual_transition_ready", True),
                             ("formal_policy_evaluation_ready", True)):
            with self.subTest(field=field):
                changed = copy.deepcopy(PROTOCOL)
                changed[field] = value
                with self.assertRaises(ValueError):
                    validate_protocol(changed)

    def test_cohort_action_and_outcome_labels_do_not_change_policy(self):
        state = GameState(5, "bottom", 1, 0, 0, 0, 0, 0)
        snapshot = synthetic_snapshot()
        set_wp(snapshot, (5, "bottom", 1, 0, 0, 1), 0, 0.4)
        set_wp(snapshot, (5, "bottom", 1, 0, 1, 0), 0, 0.5)
        baseline = SavantBaseline(snapshot)
        valuation = inspect_call(baseline, state, "strike")
        with tempfile.TemporaryDirectory() as temporary:
            results = []
            for observed_action in (False, True):
                games, manifests, evaluations = [], [], {}
                for pk, split in enumerate(("train", "validation", "test", "external"), 1):
                    candidate = {"at_bat_number": 1, "pitch_number": 1,
                                 "decision_features": {
                                     "pre_pitch_state": state.to_dict(), "challenges_remaining": 1,
                                     "original_call": "strike", "decision_team_id": 10,
                                     "decision_side": "batting"},
                                 "analysis_labels": {
                                     "population": "provisional_opportunity", "status": valuation["status"],
                                     "reason": None, "s0": valuation["s0"], "s1": valuation["s1"],
                                     "actual_challenge": observed_action,
                                     "overturned": observed_action,
                                     "post_action_budget": 1 if observed_action else 0}}
                    path = Path(temporary) / f"candidate_{observed_action}_{pk}.json"
                    path.write_text(json.dumps({
                        "schema_version": "dataset-b-provisional-candidates-v2",
                        "game_pk": pk, "split": split,
                        "source_eligibility_status": "provisional_source_limitations",
                        "rows": [candidate]}), encoding="utf-8")
                    manifest = build_file_manifest(path, source_type="dataset_b_provisional_candidates")
                    games.append({"game_pk": pk, "split": split,
                                  "status": "provisional_population_pass",
                                  "official_counter_pass": True,
                                  "candidate_artifact": str(path), "candidate_manifest": manifest})
                    manifests.append({"game_pk": pk, **manifest})
                    evaluations[split] = {"game_clusters": 1,
                                          "selected_model": {"episodes": 1}}
                preparation = {"game_rows": games}
                previous = {"candidate_manifests": manifests, "evaluations": evaluations}
                cohort = analyze_cohort(preparation, previous, baseline, SCENARIO_PROTOCOL)
                results.append(analyze_population(preparation, previous, cohort, snapshot,
                                                  SCENARIO_PROTOCOL, PROTOCOL))
        self.assertEqual(results[0]["split_summaries"], results[1]["split_summaries"])
        self.assertEqual(results[0]["rows"], results[1]["rows"])

    def test_single_state_input_has_same_official_branches_and_requires_pure_call_ack(self):
        state = GameState(5, "bottom", 1, 0, 0, 0, 0, 0)
        snapshot = synthetic_snapshot()
        set_wp(snapshot, (5, "bottom", 1, 0, 0, 1), 0, 0.4)
        set_wp(snapshot, (5, "bottom", 1, 0, 1, 0), 0, 0.5)
        request = {"schema_version": "policy-scenario-state-input-v1",
                   "pre_pitch_state": state.to_dict(), "original_call": "strike",
                   "challenges_remaining": 1, "assume_pure_called_pitch": True}
        result = evaluate_input_state(snapshot, request, PROTOCOL)
        self.assertEqual(result["status"], "supported")
        self.assertEqual(result["decision_side"], "batting")
        self.assertAlmostEqual(result["s0"]["wp_decision"], 0.4)
        self.assertAlmostEqual(result["s1"]["wp_decision"], 0.5)
        self.assertEqual(result["scenario_probability_results"]["moderate"]["0.5"]["status"],
                         "supported")
        request["assume_pure_called_pitch"] = False
        with self.assertRaisesRegex(ValueError, "純判決假設"):
            evaluate_input_state(snapshot, request, PROTOCOL)

    def test_single_state_away_perspective_and_table_outside_abstain(self):
        snapshot = synthetic_snapshot()
        set_wp(snapshot, (5, "top", 1, 0, 0, 1), 0, 0.6)
        set_wp(snapshot, (5, "top", 1, 0, 1, 0), 0, 0.5)
        request = {"schema_version": "policy-scenario-state-input-v1",
                   "pre_pitch_state": GameState(5, "top", 1, 0, 0, 0, 0, 0).to_dict(),
                   "original_call": "strike", "challenges_remaining": 1,
                   "assume_pure_called_pitch": True}
        result = evaluate_input_state(snapshot, request, PROTOCOL)
        self.assertAlmostEqual(result["s0"]["wp_decision"], 0.4)
        self.assertAlmostEqual(result["s1"]["wp_decision"], 0.5)
        request["pre_pitch_state"]["home_score"] = 8
        result = evaluate_input_state(snapshot, request, PROTOCOL)
        self.assertEqual(result["status"], "unsupported")
        self.assertFalse(result["s0"]["supported"])
        self.assertIsNone(result["scenario_probability_results"]["moderate"]["0.5"]["policies"])


if __name__ == "__main__":
    unittest.main()
