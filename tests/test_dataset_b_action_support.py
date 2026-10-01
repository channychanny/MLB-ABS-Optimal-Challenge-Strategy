"""行動支持與額度耗盡設限的契約測試。"""

import json
from pathlib import Path
import tempfile
import unittest

from abs_challenge.dataset_b_action_support import analyze, load_action_rows
from abs_challenge.provenance import build_file_manifest


PROTOCOL = {
    "schema_version": "dataset-b-action-support-protocol-v1",
    "scope": "測試",
    "risk_set_population": "provisional_opportunity",
    "training_split": "train",
    "evaluation_splits": ["validation", "test", "external"],
    "game_phase_innings": {"early": [1, 3], "middle": [4, 6], "late": [7, 9]},
    "minimum_train_challenges_per_stratum": 20,
    "minimum_train_saves_per_stratum": 20,
    "minimum_train_challenge_games_per_stratum": 5,
    "minimum_train_save_games_per_stratum": 5,
    "minimum_train_action_fraction": 0.01,
    "maximum_train_action_fraction": 0.99,
    "limitations": [],
}


def _candidate(index, population, *, budget, challenge=False, observed=False,
               gap=0, boundary="regulation_end", team=10):
    return {
        "physical_pitch_index": index,
        "decision_features": {
            "pre_pitch_state": {"inning": 5}, "decision_team_id": team,
            "decision_side": "fielding", "challenges_remaining": budget,
        },
        "analysis_labels": {"population": population, "actual_challenge": challenge},
        "arrival_target": {"pitch_gap": gap, "next_opportunity_observed": observed,
                           "censoring_boundary": boundary},
    }


class DatasetBActionSupportTests(unittest.TestCase):
    def _load(self, directory: Path, rows):
        path = directory / "game_1.json"
        path.write_text(json.dumps({
            "schema_version": "dataset-b-provisional-candidates-v2", "game_pk": 1,
            "split": "train", "source_eligibility_status": "provisional_source_limitations",
            "rows": rows,
        }), encoding="utf-8")
        manifest = build_file_manifest(path, source_type="dataset_b_provisional_candidates")
        preparation = {"game_rows": [{"game_pk": 1, "split": "train",
                                      "status": "provisional_population_pass",
                                      "candidate_artifact": str(path), "candidate_manifest": manifest}]}
        baseline = {"candidate_manifests": [{"game_pk": 1, **manifest}],
                    "evaluations": {"train": {"selected_model": {
                        "episodes": sum(r["analysis_labels"]["population"] == "provisional_opportunity"
                                        for r in rows)}}}}
        return load_action_rows(preparation, baseline, PROTOCOL)["train"]

    def test_zero_budget_after_last_challenge_proves_budget_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            rows = self._load(Path(temp), [
                _candidate(3, "provisional_opportunity", budget=1, challenge=True,
                           observed=False, gap=7),
                _candidate(5, "zero_budget", budget=0, gap=5),
            ])
        self.assertEqual(rows[0]["reclassified_boundary"], "budget_exhaustion_evidenced")

    def test_last_challenge_without_later_candidate_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as temp:
            rows = self._load(Path(temp), [
                _candidate(3, "provisional_opportunity", budget=1, challenge=True, gap=7)])
        self.assertEqual(rows[0]["reclassified_boundary"], "budget_or_regulation_unresolved")

    def test_zero_budget_evidence_requires_last_budget_challenge(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "額度耗盡證據與最後風險集行動不一致"):
                self._load(Path(temp), [
                    _candidate(3, "provisional_opportunity", budget=1, challenge=False, gap=7),
                    _candidate(5, "zero_budget", budget=0, gap=5),
                ])

    def test_next_opportunity_ignores_zero_budget_and_checks_gap(self):
        candidates = [
            _candidate(2, "provisional_opportunity", budget=2, observed=True,
                       gap=5, boundary=None),
            _candidate(4, "zero_budget", budget=0),
            _candidate(7, "provisional_opportunity", budget=1, gap=3),
        ]
        with tempfile.TemporaryDirectory() as temp:
            rows = self._load(Path(temp), candidates)
        self.assertEqual(rows[0]["next_challenges_remaining"], 1)
        self.assertEqual(rows[0]["pitch_gap"], 5)
        candidates[0]["arrival_target"]["pitch_gap"] = 2
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "下一同隊機會標籤不一致"):
                self._load(Path(temp), candidates)

    def test_support_gate_and_censoring_gate_fail_closed(self):
        action_row = {"game_pk": 1, "game_phase": "early", "decision_side": "fielding",
                      "challenges_remaining": 1, "actual_challenge": True,
                      "next_opportunity_observed": False, "pitch_gap": 4,
                      "reclassified_boundary": "budget_exhaustion_evidenced",
                      "next_decision_side": None, "next_challenges_remaining": None}
        save_row = {**action_row, "actual_challenge": False,
                    "reclassified_boundary": "regulation_end_without_budget_evidence"}
        result = analyze({"train": [action_row, save_row], "validation": [save_row],
                          "test": [save_row], "external": [save_row]}, PROTOCOL)
        self.assertEqual(result["train_strata_passing"], 0)
        self.assertFalse(result["historical_action_overlap_gate_pass"])
        self.assertFalse(result["arrival_baseline_censoring_contract_valid"])
        self.assertFalse(result["counterfactual_transition_ready"])


if __name__ == "__main__":
    unittest.main()
