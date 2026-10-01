"""決策時情境分支、方向、缺值與防洩漏測試。"""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from abs_challenge.baseline import SavantBaseline
from abs_challenge.policy_scenarios import (
    _candidate_valuation, analyze_cohort, compare_branches, evaluate_state, evaluate_valuation,
    validate_protocol,
)
from abs_challenge.provenance import build_file_manifest
from abs_challenge.state_value import GameState
from abs_challenge.wp_coverage import inspect_call
from baseline_support import set_wp, synthetic_snapshot


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((ROOT / "config/policy_scenario_protocol.json").read_text(encoding="utf-8"))


class PolicyScenarioTests(unittest.TestCase):
    def test_budget_scarcity_changes_break_even_probability(self):
        scenario = PROTOCOL["scenarios"][2]
        one = compare_branches(0.4, 0.5, budget=1, probability=0.5, scenario=scenario)
        two = compare_branches(0.4, 0.5, budget=2, probability=0.5, scenario=scenario)
        self.assertAlmostEqual(one["break_even_probability"], 0.02 / 0.12)
        self.assertAlmostEqual(two["break_even_probability"], 0.01 / 0.11)
        self.assertGreater(one["break_even_probability"], two["break_even_probability"])
        self.assertEqual(compare_branches(0.4, 0.5, budget=1, probability=0.1,
                                          scenario=scenario)["action"], "save")
        self.assertEqual(one["action"], "challenge")

    def test_probability_and_no_positive_value_boundaries(self):
        immediate = PROTOCOL["scenarios"][0]
        self.assertEqual(compare_branches(0.4, 0.5, budget=1, probability=0,
                                          scenario=immediate)["action"], "tie")
        self.assertEqual(compare_branches(0.4, 0.5, budget=1, probability=1,
                                          scenario=immediate)["action"], "challenge")
        flat = compare_branches(0.4, 0.4, budget=1, probability=0.5, scenario=immediate)
        self.assertEqual(flat["break_even_probability_kind"], "indifferent")
        adverse = PROTOCOL["scenarios"][3]
        never = compare_branches(0.4, 0.401, budget=1, probability=1, scenario=adverse)
        self.assertEqual(never["break_even_probability_kind"], "never_strictly_challenge")
        self.assertEqual(never["action"], "save")

    def test_terminal_branches_remove_only_inapplicable_future_adjustments(self):
        scenario = PROTOCOL["scenarios"][4]
        terminal_s0 = compare_branches(0, 0.6, budget=1, probability=0.2,
                                       scenario=scenario, s0_terminal=True)
        self.assertEqual(terminal_s0["applied_failure_cost"], 0)
        self.assertEqual(terminal_s0["action"], "challenge")
        terminal_s1 = compare_branches(0.4, 1, budget=1, probability=0.2,
                                       scenario=scenario, s1_terminal=True)
        self.assertEqual(terminal_s1["applied_success_future_shift"], 0)
        self.assertEqual(terminal_s1["applied_failure_cost"], 0.01)

    def test_invalid_budget_probability_and_protocol_fail_closed(self):
        scenario = PROTOCOL["scenarios"][0]
        for budget, probability in ((0, 0.5), (3, 0.5), (1, -0.1), (1, float("nan"))):
            with self.subTest(budget=budget, probability=probability), self.assertRaises(ValueError):
                compare_branches(0.4, 0.5, budget=budget, probability=probability, scenario=scenario)
        changed = copy.deepcopy(PROTOCOL)
        changed["historical_post_action_model_as_decision_feature"] = True
        with self.assertRaises(ValueError):
            validate_protocol(changed)

    def test_unsupported_wp_retains_re_without_policy(self):
        valuation = {"s0": {"supported": True, "wp_decision": 0.4, "re": 0.3},
                     "s1": {"supported": False, "wp_decision": None, "re": 0.2,
                            "missing_reason_code": "score_diff_out_of_range"},
                     "decision_side": "batting"}
        result = evaluate_valuation(valuation, 1, PROTOCOL)
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["s1"]["re"], 0.2)
        self.assertEqual(result["s1"]["missing_reason"], "score_diff_out_of_range")
        self.assertIsNone(result["scenario_results"])
        self.assertFalse(result["formal_policy_evaluation_ready"])

    def test_official_wp_outside_table_is_not_clipped(self):
        state = GameState(5, "bottom", 1, 0, 0, 0, 7, 0)
        result = evaluate_state(SavantBaseline(synthetic_snapshot()), state,
                                "strike", 1, PROTOCOL)
        self.assertEqual(result["status"], "unsupported")
        self.assertIsNone(result["scenario_results"])
        self.assertIn("score_diff_out_of_range", result["s0"]["missing_reason"])

    def test_ninth_inning_tie_uses_regulation_boundary_without_future_shift(self):
        state = GameState(9, "bottom", 2, 0, 0, 2, 0, 0)
        baseline = SavantBaseline(synthetic_snapshot())
        result = evaluate_state(baseline, state, "ball", 1, PROTOCOL)
        self.assertEqual(result["s1"]["terminal"], "regulation_tie")
        self.assertEqual(result["s1"]["wp_decision"], 1 - baseline.boundary)
        favorable = next(item for item in result["scenario_results"]
                         if item["scenario_id"] == "favorable_success_continuation")
        self.assertEqual(favorable["applied_success_future_shift"], 0)

    def test_home_away_and_decision_side_share_one_valuation_seam(self):
        state_home = GameState(5, "bottom", 1, 0, 0, 0, 0, 0)
        snap_home = synthetic_snapshot()
        set_wp(snap_home, (5, "bottom", 1, 0, 0, 1), 0, 0.4)
        set_wp(snap_home, (5, "bottom", 1, 0, 1, 0), 0, 0.5)
        home = evaluate_state(SavantBaseline(snap_home), state_home, "strike", 1, PROTOCOL)
        self.assertEqual(home["decision_side"], "batting")
        self.assertAlmostEqual(home["immediate_delta_wp"], 0.1)

        state_away = GameState(5, "top", 1, 0, 0, 0, 0, 0)
        snap_away = synthetic_snapshot()
        set_wp(snap_away, (5, "top", 1, 0, 0, 1), 0, 0.6)
        set_wp(snap_away, (5, "top", 1, 0, 1, 0), 0, 0.5)
        away = evaluate_state(SavantBaseline(snap_away), state_away, "strike", 1, PROTOCOL)
        self.assertEqual(away["decision_side"], "batting")
        self.assertAlmostEqual(away["s0"]["wp_decision"], 0.4)
        self.assertAlmostEqual(away["immediate_delta_wp"], 0.1)

    def test_actual_challenge_label_is_not_policy_input(self):
        row = {"decision_features": {
            "pre_pitch_state": GameState(5, "top", 1, 0, 0, 0, 0, 0).to_dict(),
            "challenges_remaining": 1, "original_call": "ball",
            "decision_team_id": 10, "decision_side": "fielding"},
            "analysis_labels": {"population": "provisional_opportunity",
                                "status": "both_supported", "reason": None,
                                "actual_challenge": False,
                                "s0": {"supported": True, "wp_decision": 0.4},
                                "s1": {"supported": True, "wp_decision": 0.5}}}
        first = _candidate_valuation(row)
        row["analysis_labels"]["actual_challenge"] = True
        row["analysis_labels"]["overturned"] = True
        self.assertEqual(first, _candidate_valuation(row))
        row["decision_features"]["post_action_budget"] = 0
        with self.assertRaisesRegex(ValueError, "事後欄位"):
            _candidate_valuation(row)

    def test_cohort_keeps_same_recommendation_when_historical_action_changes(self):
        state = GameState(5, "bottom", 1, 0, 0, 0, 0, 0)
        snapshot = synthetic_snapshot()
        set_wp(snapshot, (5, "bottom", 1, 0, 0, 1), 0, 0.4)
        set_wp(snapshot, (5, "bottom", 1, 0, 1, 0), 0, 0.5)
        baseline = SavantBaseline(snapshot)
        valuation = inspect_call(baseline, state, "strike")
        candidate = {"at_bat_number": 1, "pitch_number": 1,
                     "decision_features": {"pre_pitch_state": state.to_dict(),
                                           "challenges_remaining": 1,
                                           "original_call": "strike", "decision_team_id": 10,
                                           "decision_side": "batting"},
                     "analysis_labels": {"population": "provisional_opportunity",
                                         "status": valuation["status"], "reason": None,
                                         "s0": valuation["s0"], "s1": valuation["s1"],
                                         "actual_challenge": False}}
        with tempfile.TemporaryDirectory() as temp:
            outputs = []
            for action in (False, True):
                candidate["analysis_labels"]["actual_challenge"] = action
                game_rows, manifests, evaluations = [], [], {}
                for pk, split in enumerate(("train", "validation", "test", "external"), start=1):
                    path = Path(temp) / f"candidate_{pk}.json"
                    path.write_text(json.dumps({
                        "schema_version": "dataset-b-provisional-candidates-v2",
                        "game_pk": pk, "split": split,
                        "source_eligibility_status": "provisional_source_limitations",
                        "rows": [candidate]}), encoding="utf-8")
                    manifest = build_file_manifest(path, source_type="dataset_b_provisional_candidates")
                    game_rows.append({"game_pk": pk, "split": split,
                                      "status": "provisional_population_pass",
                                      "official_counter_pass": True,
                                      "candidate_artifact": str(path),
                                      "candidate_manifest": manifest})
                    manifests.append({"game_pk": pk, **manifest})
                    evaluations[split] = {"game_clusters": 1,
                                          "selected_model": {"episodes": 1}}
                preparation = {"game_rows": game_rows}
                previous = {"candidate_manifests": manifests, "evaluations": evaluations}
                outputs.append(analyze_cohort(preparation, previous, baseline, PROTOCOL))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0]["split_summaries"]["train"]["support_counts"],
                         {"supported": 1})


if __name__ == "__main__":
    unittest.main()
