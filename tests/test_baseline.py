"""固定來源完整度、查表視角與外部異常揭露。"""

import copy
import json
from pathlib import Path
import unittest

from abs_challenge.baseline import MissingBaselineState, SavantBaseline, build_baseline_snapshot
from abs_challenge.state_value import GameState
from abs_challenge.provenance import build_download_manifest
from baseline_support import set_wp, synthetic_bundle, synthetic_snapshot


class BaselineTests(unittest.TestCase):
    def test_imports_complete_bundle_and_preserves_separate_year_claims(self) -> None:
        bundle = synthetic_bundle()
        snapshot = build_baseline_snapshot(bundle)
        self.assertEqual(len(snapshot["re288"]), 288)
        self.assertEqual(len(snapshot["wp"]), 5184)
        self.assertEqual(snapshot["source_page_seasons"], [2016, 2025])
        self.assertEqual(snapshot["re_response_years"], [2025])
        self.assertEqual(snapshot["regulation_boundary"]["home_win_probability"], 0.5)
        self.assertEqual(build_baseline_snapshot(bundle), snapshot)

    def test_rejects_changed_source_bytes(self) -> None:
        bundle = synthetic_bundle()
        bundle["documents"]["wp_0"]["content"] += " "
        with self.assertRaisesRegex(ValueError, "hash"):
            build_baseline_snapshot(bundle)

    def test_adapter_converts_batting_score_and_probability_to_home(self) -> None:
        bundle = synthetic_bundle()
        document = bundle["documents"]["wp_0"]
        rows = json.loads(document["content"])
        row = next(row for row in rows if (row["inning"], row["bottom_top"], row["outs"], row["ball_count"], row["strike_count"]) == (4, "Top", 0, 0, 0))
        row["bat_wins_2"], row["bat_wins_minus_2"] = 0.72, 0.19
        document["content"] = json.dumps(rows)
        document["manifest"] = build_download_manifest(source_type="synthetic_fixture",
            source_url=document["manifest"]["source_url"], content=document["content"], row_count=len(rows))
        baseline = SavantBaseline(build_baseline_snapshot(bundle))
        self.assertAlmostEqual(baseline.home_wp(GameState(4, "top", 0, 0, 0, 0, 2, 0)), 0.81)
        self.assertAlmostEqual(baseline.home_wp(GameState(4, "top", 0, 0, 0, 0, 0, 2)), 0.28)

    def test_official_top_half_excerpt_has_positive_batting_challenge_value(self) -> None:
        bundle = synthetic_bundle()
        document = bundle["documents"]["wp_0"]
        rows = json.loads(document["content"])
        excerpt = json.loads((Path(__file__).parent / "fixtures" / "savant_explorer_excerpt.json").read_text(encoding="utf-8"))
        fields = ("inning", "bottom_top", "outs", "ball_count", "strike_count")
        for row in rows:
            for source in excerpt["wp_excerpt"]:
                if all(row[key] == source[key] for key in fields):
                    row.update(source)
        document["content"] = json.dumps(rows)
        document["manifest"] = build_download_manifest(source_type="synthetic_fixture",
            source_url=document["manifest"]["source_url"], content=document["content"], row_count=len(rows))
        value = SavantBaseline(build_baseline_snapshot(bundle)).value_call(GameState(4, "top", 0, 0, 0, 0, 0, 5), "strike")
        self.assertAlmostEqual(value["wp_home_stands"], 0.08)
        self.assertAlmostEqual(value["wp_home_overturned"], 0.078)
        self.assertAlmostEqual(value["delta_wp_percentage_points"], 0.2)
        self.assertFalse(value["warnings"])

    def test_row_count_manifest_mismatch_is_rejected(self) -> None:
        bundle = synthetic_bundle()
        bundle["documents"]["wp_0"]["manifest"]["row_count"] = 1
        with self.assertRaisesRegex(ValueError, "列數"):
            build_baseline_snapshot(bundle)

    def test_rejects_wrong_request_perspective(self) -> None:
        bundle = synthetic_bundle()
        bundle["documents"]["wp_0"]["manifest"]["source_url"] += "&perspective=bat"
        with self.assertRaisesRegex(ValueError, "視角"):
            build_baseline_snapshot(bundle)

    def test_rejects_missing_and_duplicate_rows(self) -> None:
        for table in ("wp", "re288"):
            for operation in ("missing", "duplicate"):
                with self.subTest(table=table, operation=operation):
                    snapshot = synthetic_snapshot()
                    if operation == "missing":
                        snapshot[table].pop()
                    else:
                        snapshot[table].append(copy.deepcopy(snapshot[table][0]))
                    with self.assertRaises(ValueError):
                        SavantBaseline(snapshot)

    def test_rejects_nonfinite_and_invalid_probabilities(self) -> None:
        for invalid in (float("nan"), float("inf"), -0.1, 1.1, True, "0.5"):
            with self.subTest(invalid=invalid):
                snapshot = synthetic_snapshot()
                snapshot["wp"][0]["home_win_probabilities"][0] = invalid
                with self.assertRaises(ValueError):
                    SavantBaseline(snapshot)
        snapshot = synthetic_snapshot()
        snapshot["re288"][0]["run_expectancy"] = -1
        with self.assertRaises(ValueError):
            SavantBaseline(snapshot)

    def test_does_not_clip_score_difference(self) -> None:
        baseline = SavantBaseline(synthetic_snapshot())
        for home, away in ((0, 6), (6, 0)):
            with self.assertRaises(MissingBaselineState):
                baseline.value_call(GameState(4, "top", 0, 0, 0, 0, home, away), "strike")

    def test_decision_team_perspective_for_all_four_call_and_half_combinations(self) -> None:
        for half, ball_wp, strike_wp in (("top", 0.4, 0.6), ("bottom", 0.6, 0.4)):
            for call in ("ball", "strike"):
                with self.subTest(half=half, call=call):
                    snapshot = synthetic_snapshot()
                    set_wp(snapshot, (4, half, 0, 0, 1, 0), 0, ball_wp)
                    set_wp(snapshot, (4, half, 0, 0, 0, 1), 0, strike_wp)
                    value = SavantBaseline(snapshot).value_call(GameState(4, half, 0, 0, 0, 0, 0, 0), call)
                    self.assertAlmostEqual(value["delta_wp_decision"], 0.2)

    def test_third_out_does_not_flip_decision_team_or_add_opponents_re(self) -> None:
        snapshot = synthetic_snapshot()
        set_wp(snapshot, (4, "bottom", 0, 0, 0, 0), 0, 0.7)
        set_wp(snapshot, (4, "top", 2, 0, 1, 2), 0, 0.6)
        value = SavantBaseline(snapshot).value_call(GameState(4, "top", 2, 0, 0, 2, 0, 0), "strike")
        self.assertAlmostEqual(value["wp_decision_stands"], 0.3)
        self.assertAlmostEqual(value["wp_decision_overturned"], 0.4)
        self.assertEqual(value["re_stands"], 0)
        self.assertEqual(value["re_overturned"], 0.5)

    def test_walkoff_and_regulation_boundary_use_explicit_terminal_values(self) -> None:
        value = SavantBaseline(synthetic_snapshot()).value_call(GameState(9, "bottom", 2, 7, 3, 2, 0, 0), "strike")
        self.assertEqual(value["wp_decision_stands"], 0.47)
        self.assertEqual(value["wp_decision_overturned"], 1.0)
        self.assertAlmostEqual(value["delta_wp_decision"], 0.53)
        self.assertTrue(value["regulation_boundary_used"])
        self.assertEqual(value["re_overturned"], 1.5)

    def test_negative_normalized_values_are_preserved_and_flagged(self) -> None:
        snapshot = synthetic_snapshot()
        set_wp(snapshot, (4, "top", 0, 0, 0, 1), -5, 0.3)
        set_wp(snapshot, (4, "top", 0, 0, 1, 0), -5, 0.4)
        value = SavantBaseline(snapshot).value_call(GameState(4, "top", 0, 0, 0, 0, 0, 5), "strike")
        self.assertAlmostEqual(value["delta_wp_percentage_points"], -10)
        self.assertTrue(value["warnings"])

    def test_obsolete_v1_snapshot_cannot_be_reused(self) -> None:
        snapshot = synthetic_snapshot()
        snapshot["schema_version"] = "savant-baseline-v1"
        with self.assertRaises(ValueError):
            SavantBaseline(snapshot)

    def test_no_budget_cost_is_hidden_in_wp_value(self) -> None:
        snapshot = synthetic_snapshot()
        for row in snapshot["re288"]:
            if (row["bases"], row["outs"], row["balls"], row["strikes"]) == (0, 0, 1, 0):
                row["run_expectancy"] = 0.8
        value = SavantBaseline(snapshot).value_call(GameState(4, "bottom", 0, 0, 0, 0, 0, 0), "strike")
        self.assertAlmostEqual(value["run_value_decision"], 0.3)
        self.assertAlmostEqual(value["savant_static_threshold"], 0.4)
        self.assertEqual(value["delta_wp_decision"], 0)
