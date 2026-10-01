"""Train-only 未來額度近似及本機表單決策介面測試。"""

import copy
import json
from pathlib import Path
import unittest

from abs_challenge.option_proxy import fit, game_labels, predict, validate_protocol
from abs_challenge.state_value import GameState
from abs_challenge.web_ui import ASSETS, evaluate_request
from baseline_support import set_wp, synthetic_snapshot


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((ROOT / "config/phase3_option_proxy_protocol.json").read_text(encoding="utf-8"))
WIN = json.loads((ROOT / "config/phase3_win_decision_protocol.json").read_text(encoding="utf-8"))


def candidate(index, population, *, supported=True, delta=0.02, team=10):
    return {"at_bat_number": index, "pitch_number": 1,
            "physical_pitch_index": index, "decision_features": {
                "decision_team_id": team, "decision_side": "batting",
                "challenges_remaining": 2 if population == "provisional_opportunity" else 0,
                "pre_pitch_state": {"inning": 5}},
            "analysis_labels": {"population": population,
                                "actual_challenge": False,
                                "s0": {"supported": supported, "wp_decision": 0.4 if supported else None},
                                "s1": {"supported": supported,
                                       "wp_decision": 0.4 + delta if supported else None}}}


class OptionProxyUiTests(unittest.TestCase):
    def test_zero_budget_future_still_counts_as_potential_opportunity(self):
        rows = [candidate(1, "provisional_opportunity"),
                candidate(2, "zero_budget"), candidate(3, "zero_budget")]
        labels = game_labels(rows, game_pk=1, split="train")
        self.assertEqual(len(labels), 1)
        self.assertTrue(labels[0]["at_least_one_future"])
        self.assertTrue(labels[0]["at_least_two_future"])
        self.assertAlmostEqual(labels[0]["first_future_positive_delta"], 0.02)

    def test_unsupported_future_is_not_zero_filled(self):
        rows = [candidate(1, "provisional_opportunity"),
                candidate(2, "zero_budget", supported=False)]
        label = game_labels(rows, game_pk=1, split="train")[0]
        self.assertTrue(label["at_least_one_future"])
        self.assertFalse(label["first_future_wp_supported"])
        self.assertIsNone(label["first_future_positive_delta"])

    def test_fit_is_train_only_and_budget_two_cost_is_smaller(self):
        train = [{"split": "train", "inning": 5, "decision_side": "batting",
                  "at_least_one_future": True, "at_least_two_future": True,
                  "first_future_wp_supported": True,
                  "first_future_positive_delta": 0.02} for _ in range(10)]
        model = fit(train, PROTOCOL)
        one = predict(model, inning=5, decision_side="batting", budget=1)
        two = predict(model, inning=5, decision_side="batting", budget=2)
        self.assertAlmostEqual(one["estimated_incremental_failure_cost"], 0.015)
        self.assertAlmostEqual(two["estimated_incremental_failure_cost"], 0.005)
        changed = copy.deepcopy(train)
        changed[0]["split"] = "test"
        with self.assertRaises(ValueError):
            fit(changed, PROTOCOL)

    def test_protocol_and_invalid_state_fail_closed(self):
        changed = copy.deepcopy(PROTOCOL)
        changed["historical_actions_not_predictors"] = False
        with self.assertRaises(ValueError):
            validate_protocol(changed)
        model = fit([{"split": "train", "inning": 5, "decision_side": "batting",
                      "at_least_one_future": True, "at_least_two_future": False,
                      "first_future_wp_supported": True,
                      "first_future_positive_delta": 0.01}], PROTOCOL)
        with self.assertRaises(ValueError):
            predict(model, inning=10, decision_side="batting", budget=1)

    def test_browser_request_returns_threshold_without_guessing_current_probability(self):
        snapshot = synthetic_snapshot()
        set_wp(snapshot, (5, "bottom", 1, 0, 0, 1), 0, 0.4)
        set_wp(snapshot, (5, "bottom", 1, 0, 1, 0), 0, 0.5)
        request = {"pre_pitch_state": GameState(5, "bottom", 1, 0, 0, 0, 0, 0).to_dict(),
                   "original_call": "strike", "challenges_remaining": 1,
                   "custom_failure_cost_pp": 20,
                   "assume_pure_called_pitch": True}
        output = evaluate_request(snapshot, WIN, request)
        self.assertEqual(output["status"], "supported")
        self.assertNotIn("assumed_overturn_probability", output)
        self.assertAlmostEqual(output["delta_wp_if_overturned"], 0.1)
        self.assertAlmostEqual(output["re_s0"], output["s0"]["re"])
        self.assertAlmostEqual(output["re_s1"], output["s1"]["re"])
        self.assertAlmostEqual(output["delta_re_decision"], output["re_s1"] - output["re_s0"])
        self.assertEqual(output["re_unit"], "expected_runs_current_half_inning")
        self.assertEqual(output["illustrative_cost_source"], "declared_not_estimated")
        self.assertEqual([row["id"] for row in output["illustrative_cost_scenarios"]],
                         ["immediate_only", "small_resource_cost", "large_resource_cost"])
        self.assertAlmostEqual(output["illustrative_cost_scenarios"][1]["threshold"]
                               ["conditional_break_even_probability"], 0.005 / 0.105)
        self.assertAlmostEqual(output["illustrative_cost_scenarios"][2]["threshold"]
                               ["conditional_break_even_probability"], 0.02 / 0.12)
        self.assertTrue(output["illustrative_threshold_range"]["not_confidence_interval"])
        self.assertAlmostEqual(output["custom_cost_threshold"]["conditional_break_even_probability"],
                               0.2 / 0.3)
        self.assertNotIn("proxy_reference", output)
        request["assumed_overturn_probability"] = 0.5
        with self.assertRaises(ValueError):
            evaluate_request(snapshot, WIN, request)
        del request["assumed_overturn_probability"]
        request["assume_pure_called_pitch"] = False
        with self.assertRaises(ValueError):
            evaluate_request(snapshot, WIN, request)

    def test_nonpositive_win_delta_has_no_fake_challenge_threshold(self):
        snapshot = synthetic_snapshot()
        set_wp(snapshot, (5, "bottom", 1, 0, 0, 1), 0, 0.5)
        set_wp(snapshot, (5, "bottom", 1, 0, 1, 0), 0, 0.4)
        request = {"pre_pitch_state": GameState(5, "bottom", 1, 0, 0, 0, 0, 0).to_dict(),
                   "original_call": "strike", "challenges_remaining": 1,
                   "custom_failure_cost_pp": None, "assume_pure_called_pitch": True}
        output = evaluate_request(snapshot, WIN, request)
        self.assertEqual(output["illustrative_cost_scenarios"][1]["threshold"]["break_even_kind"],
                         "never_strictly_challenge")
        self.assertIsNone(output["illustrative_cost_scenarios"][1]["threshold"]
                          ["conditional_break_even_probability"])
        self.assertIsNone(output["illustrative_threshold_range"])

    def test_two_remaining_uses_declared_second_budget_cost(self):
        snapshot = synthetic_snapshot()
        set_wp(snapshot, (5, "bottom", 1, 0, 0, 1), 0, 0.4)
        set_wp(snapshot, (5, "bottom", 1, 0, 1, 0), 0, 0.5)
        request = {"pre_pitch_state": GameState(5, "bottom", 1, 0, 0, 0, 0, 0).to_dict(),
                   "original_call": "strike", "challenges_remaining": 2,
                   "custom_failure_cost_pp": None, "assume_pure_called_pitch": True}
        output = evaluate_request(snapshot, WIN, request)
        self.assertAlmostEqual(output["illustrative_threshold_range"]["assumed_cost_lower_wp"],
                               0.0025)
        self.assertAlmostEqual(output["illustrative_threshold_range"]["assumed_cost_upper_wp"],
                               0.01)
        self.assertAlmostEqual(output["illustrative_threshold_range"]["lower"], 0.0025 / 0.1025)
        self.assertAlmostEqual(output["illustrative_threshold_range"]["upper"], 0.01 / 0.11)

    def test_terminal_original_call_has_no_future_budget_cost(self):
        snapshot = synthetic_snapshot()
        state = GameState(9, "bottom", 2, 0, 0, 2, 0, 1)
        request = {"pre_pitch_state": state.to_dict(), "original_call": "strike",
                   "challenges_remaining": 1, "custom_failure_cost_pp": 20,
                   "assume_pure_called_pitch": True}
        output = evaluate_request(snapshot, WIN, request)
        self.assertEqual(output["status"], "supported")
        self.assertEqual(output["s0"]["terminal"], "away_win")
        self.assertTrue(all(row["assumed_failure_cost_wp"] == 0
                            for row in output["illustrative_cost_scenarios"]))
        self.assertEqual(output["illustrative_threshold_range"]["lower"], 0)
        self.assertEqual(output["illustrative_threshold_range"]["upper"], 0)
        self.assertEqual(output["custom_cost_threshold"]["conditional_failure_cost"], 0)

    def test_re_survives_unsupported_wp_and_fielding_sign_is_reversed(self):
        snapshot = synthetic_snapshot()
        for row in snapshot["re288"]:
            key = (row["bases"], row["outs"], row["balls"], row["strikes"])
            if key == (1, 1, 0, 0):
                row["run_expectancy"] = 0.8  # 原判壞球形成保送
            elif key == (0, 1, 3, 2):
                row["run_expectancy"] = 0.3  # 翻判好球避免保送
        request = {"pre_pitch_state": GameState(5, "bottom", 1, 0, 3, 1, 7, 0).to_dict(),
                   "original_call": "ball", "challenges_remaining": 2,
                   "custom_failure_cost_pp": None, "assume_pure_called_pitch": True}
        output = evaluate_request(snapshot, WIN, request)
        self.assertEqual(output["status"], "unsupported")
        self.assertEqual(output["decision_side"], "fielding")
        self.assertIsInstance(output["re_s0"], float)
        self.assertIsInstance(output["re_s1"], float)
        self.assertAlmostEqual(output["delta_re_decision"], output["re_s0"] - output["re_s1"])
        self.assertGreater(output["delta_re_decision"], 0)
        self.assertNotIn("proxy_reference", output)
        self.assertNotIn("illustrative_cost_scenarios", output)

    def test_two_budget_symmetric_future_assumptions_are_explained(self):
        model = fit([{"split": "train", "inning": 5, "decision_side": "batting",
                      "at_least_one_future": True, "at_least_two_future": True,
                      "first_future_wp_supported": True,
                      "first_future_positive_delta": 0.02}], PROTOCOL)
        costs = [predict(model, inning=5, decision_side="batting", budget=2,
                         future_success_probability=p)["estimated_incremental_failure_cost"]
                 for p in (0.25, 0.5, 0.75)]
        self.assertAlmostEqual(costs[0], costs[2])
        self.assertGreater(costs[1], costs[0])
        html = (ASSETS / "web_ui.html").read_text(encoding="utf-8")
        self.assertIn("不是統計信賴區間", html)
        self.assertNotIn("p × (1−p)", html)
        self.assertNotIn('id="probability"', html)

    def test_ui_assets_are_local_and_chinese(self):
        for name in ("web_ui.html", "web_ui.css", "web_ui.js"):
            self.assertTrue((ASSETS / name).is_file())
        html = (ASSETS / "web_ui.html").read_text(encoding="utf-8")
        self.assertIn("查看勝率與得分影響", html)
        self.assertIn('id="re-result"', html)
        self.assertIn("原半局預期得分", html)
        self.assertIn('lang="zh-Hant"', html)


if __name__ == "__main__":
    unittest.main()
