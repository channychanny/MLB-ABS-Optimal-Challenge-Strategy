"""Dataset B 準備階段不得把候選賽程直接升格為訓練資料。"""

import json
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from scripts.prepare_dataset_b import _candidate_artifact, _selected, prepare


ROOT = Path(__file__).resolve().parents[1]


class DatasetBPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sampling = json.loads((ROOT / "config/dataset_b_sampling.json").read_text(encoding="utf-8"))
        cls.split = json.loads((ROOT / "config/dataset_b_split_plan.json").read_text(encoding="utf-8"))
        windows = []
        for index, window in enumerate(cls.split["windows"]):
            selected = [{"game_pk": 900000 + index * 100 + n, "date": window["start"],
                         "window": window["name"], "split": window["split"],
                         "regime": window["regime"]}
                        for n in range(cls.sampling["quotas"][window["name"]])]
            windows.append({"window": window["name"], "selected": selected})
        lock = {"sampling_plan": cls.sampling, "split_plan": cls.split,
                "windows": windows, "sources": []}
        cls.selection = {"schema_version": "dataset-b-schedule-selection-v1", **lock,
                         "selection_complete": True, "selected_count": 96,
                         "selection_sha256": sha256(json.dumps(lock, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}

    def test_locked_selection_is_verified_before_sources(self):
        self.assertEqual(len(_selected(self.selection, self.sampling, self.split)), 96)
        altered = {**self.selection, "selection_sha256": "wrong"}
        with self.assertRaisesRegex(ValueError, "指紋"):
            _selected(altered, self.sampling, self.split)

    def test_missing_offline_sources_remain_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            report = prepare(self.selection, self.sampling, self.split,
                             cache_dir=Path(directory), offline=True, feeds_only=True, workers=2)
        self.assertEqual(report["selected_games"], 96)
        self.assertEqual(report["status_counts"], {"feed_failure": 96})
        self.assertFalse(report["training_ready"])
        self.assertFalse(report["holdout_game_lists_locked"])

    def test_candidate_artifact_separates_decision_features_and_labels(self):
        candidate = {"game_pk": 900001, "at_bat_number": 1, "pitch_number": 2,
                     "physical_pitch_index": 2,
                     "pre_pitch_state": {"balls": 1}, "challenges_remaining": 2,
                     "original_call": "strike", "decision_team_id": 10,
                     "decision_side": "batting", "actual_challenge": True,
                     "population": "provisional_opportunity", "status": "both_supported",
                     "s0": {"wp": 0.4}, "s1": {"wp": 0.6},
                     "alignment": {"feed_event_index": 1},
                     "abs_technical_availability": "unknown",
                     "post_replay_challenge_eligibility": "unknown",
                     "source_eligibility_version": "abs-source-eligibility-evidence-v1"}
        artifact = _candidate_artifact({"game_pk": 900001, "date": "2025-07-01",
                                        "split": "validation", "window": "validation_2025_il"}, [candidate], 10)
        record = artifact["rows"][0]
        self.assertEqual(set(record["decision_features"]), {
            "pre_pitch_state", "challenges_remaining", "original_call",
            "decision_team_id", "decision_side"})
        self.assertNotIn("actual_challenge", record["decision_features"])
        self.assertNotIn("alignment_evidence", record["decision_features"])
        self.assertTrue(record["analysis_labels"]["actual_challenge"])
        self.assertNotIn("arrival_target", record["decision_features"])
        self.assertEqual(record["arrival_target"], {"pitch_gap": 8,
            "next_opportunity_observed": False, "censoring_boundary": "regulation_end"})

    def test_next_opportunity_target_is_team_specific(self):
        base = {"game_pk": 900001, "at_bat_number": 1, "pitch_number": 1,
                "pre_pitch_state": {}, "challenges_remaining": 2,
                "original_call": "strike", "decision_side": "batting",
                "actual_challenge": False, "population": "provisional_opportunity",
                "status": "both_supported", "alignment": {},
                "abs_technical_availability": "unknown",
                "post_replay_challenge_eligibility": "unknown",
                "source_eligibility_version": "abs-source-eligibility-evidence-v1"}
        candidates = [{**base, "physical_pitch_index": 2, "decision_team_id": 10},
                      {**base, "physical_pitch_index": 5, "decision_team_id": 20},
                      {**base, "physical_pitch_index": 8, "decision_team_id": 10}]
        artifact = _candidate_artifact({"game_pk": 900001, "date": "2025-07-01",
                                        "split": "validation", "window": "validation_2025_il"}, candidates, 10)
        targets = [row["arrival_target"] for row in artifact["rows"]]
        self.assertEqual([(row["pitch_gap"], row["next_opportunity_observed"]) for row in targets],
                         [(6, True), (5, False), (2, False)])

    def test_next_opportunity_skips_zero_budget_and_position_player(self):
        base = {"game_pk": 900001, "at_bat_number": 1, "pitch_number": 1,
                "pre_pitch_state": {}, "challenges_remaining": 2,
                "original_call": "strike", "decision_side": "batting",
                "decision_team_id": 10, "actual_challenge": False,
                "status": "both_supported", "alignment": {},
                "abs_technical_availability": "unknown",
                "post_replay_challenge_eligibility": "unknown",
                "source_eligibility_version": "abs-source-eligibility-evidence-v1"}
        candidates = [{**base, "physical_pitch_index": 2, "population": "provisional_opportunity"},
                      {**base, "physical_pitch_index": 5, "population": "zero_budget"},
                      {**base, "physical_pitch_index": 8, "population": "excluded_position_player"},
                      {**base, "physical_pitch_index": 10, "population": "provisional_opportunity"}]
        artifact = _candidate_artifact({"game_pk": 900001, "date": "2025-07-01",
                                        "split": "validation", "window": "validation_2025_il"}, candidates, 12)
        targets = [row["arrival_target"] for row in artifact["rows"]]
        self.assertEqual(targets[0]["pitch_gap"], 8)
        self.assertTrue(targets[0]["next_opportunity_observed"])
        self.assertEqual(targets[1]["pitch_gap"], 5)
        self.assertEqual(targets[2]["pitch_gap"], 2)
        self.assertFalse(targets[3]["next_opportunity_observed"])


if __name__ == "__main__":
    unittest.main()
