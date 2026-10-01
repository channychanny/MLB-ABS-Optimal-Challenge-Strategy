"""下一機會的同隊配對、右設限與 WP 價值邊界。"""

import json
from pathlib import Path
import tempfile
import unittest

from abs_challenge.dataset_b_followup import _value_category, load_observed_paths
from abs_challenge.provenance import build_file_manifest


class DatasetBFollowupTests(unittest.TestCase):
    def _load_two_opportunities(self, directory: Path, first_gap: int):
        rows = []
        for index, population, side, observed, gap in (
                (2, "provisional_opportunity", "fielding", True, first_gap),
                (4, "zero_budget", "fielding", False, 6),
                (7, "provisional_opportunity", "batting", False, 3)):
            rows.append({"physical_pitch_index": index,
                         "decision_features": {
                             "pre_pitch_state": {"inning": 8, "balls": 1, "strikes": 1,
                                                 "bases": 0, "outs": 1,
                                                 "half": "top", "home_score": 0, "away_score": 0},
                             "decision_team_id": 10, "decision_side": side,
                             "challenges_remaining": 1 if index == 4 else 2,
                             "original_call": "ball" if side == "fielding" else "strike"},
                         "analysis_labels": {
                             "population": population,
                             "s0": {"supported": True, "wp_decision": 0.501},
                             "s1": {"supported": True, "wp_decision": 0.506}},
                         "arrival_target": {"pitch_gap": gap,
                                            "next_opportunity_observed": observed,
                                            "censoring_boundary": None if observed else "regulation_end"}})
        artifact_path = directory / "game_1.json"
        artifact_path.write_text(json.dumps({"game_pk": 1, "split": "train", "rows": rows}), encoding="utf-8")
        manifest = build_file_manifest(artifact_path, source_type="dataset_b_provisional_candidates")
        preparation = {"game_rows": [{"game_pk": 1, "date": "2025-04-01", "split": "train",
                                      "status": "provisional_population_pass",
                                      "candidate_artifact": str(artifact_path),
                                      "candidate_manifest": manifest}]}
        prep_path = directory / "preparation.json"
        prep_path.write_text(json.dumps(preparation), encoding="utf-8")
        baseline = {"schema_version": "dataset-b-observational-baseline-results-v1",
                    "observational_baseline_evaluation_completed": True,
                    "input_manifests": [build_file_manifest(
                        prep_path, source_type="dataset_b_pretraining_preparation")],
                    "candidate_manifests": [{"game_pk": 1, **manifest}],
                    "evaluations": {"train": {"selected_model": {"episodes": 2, "events": 1}}}}
        protocol = {"excluded_unlocalized_game_pks": [],
                    "risk_set_population": "provisional_opportunity",
                    "wp_value_breaks": [0.0, 0.005, 0.02]}
        return load_observed_paths(preparation, baseline, protocol)

    def test_next_event_skips_zero_budget_candidate_and_keeps_last_censored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._load_two_opportunities(Path(temp_dir), first_gap=5)
        self.assertEqual(len(paths["train"]), 2)
        first, last = paths["train"]
        self.assertEqual(first["gap"], 5)
        self.assertEqual(first["future"]["next_decision_side"], "batting")
        self.assertEqual(first["future"]["next_wp_value_category"], "up_to_0_5_pp")
        self.assertIsNone(last["future"])

    def test_mismatched_gap_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "間隔不一致"):
                self._load_two_opportunities(Path(temp_dir), first_gap=4)

    def test_wp_threshold_rounding_and_missing_support(self):
        candidate = {"analysis_labels": {"s0": {"supported": True, "wp_decision": 0.501},
                                         "s1": {"supported": True, "wp_decision": 0.506}}}
        self.assertEqual(_value_category(candidate, [0.0, 0.005, 0.02]), ("up_to_0_5_pp", 0.005))
        candidate["analysis_labels"]["s1"]["supported"] = False
        self.assertEqual(_value_category(candidate, [0.0, 0.005, 0.02]), ("unsupported", None))


if __name__ == "__main__":
    unittest.main()
