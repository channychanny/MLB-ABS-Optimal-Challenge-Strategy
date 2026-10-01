"""限定觀察性模型輸入閘門的到達標籤與防洩漏測試。"""

import unittest

from abs_challenge.dataset_b_readiness import validate_candidate_sequence


class DatasetBReadinessTests(unittest.TestCase):
    def _candidate(self, index, population, observed, gap, boundary=None, team=10):
        return {"physical_pitch_index": index,
                "decision_features": {"decision_team_id": team},
                "analysis_labels": {"population": population},
                "arrival_target": {"pitch_gap": gap,
                                   "next_opportunity_observed": observed,
                                   "censoring_boundary": boundary}}

    def test_zero_budget_cannot_end_arrival_interval(self):
        rows = [self._candidate(2, "provisional_opportunity", True, 8),
                self._candidate(5, "zero_budget", True, 5),
                self._candidate(10, "provisional_opportunity", False, 2, "regulation_end")]
        validate_candidate_sequence(rows, risk_set="provisional_opportunity")
        rows[0]["arrival_target"]["pitch_gap"] = 3
        with self.assertRaisesRegex(ValueError, "到達間隔"):
            validate_candidate_sequence(rows, risk_set="provisional_opportunity")

    def test_other_team_is_not_next_arrival(self):
        rows = [self._candidate(2, "provisional_opportunity", True, 8),
                self._candidate(5, "provisional_opportunity", False, 7, "regulation_end", team=20),
                self._candidate(10, "provisional_opportunity", False, 2, "regulation_end")]
        validate_candidate_sequence(rows, risk_set="provisional_opportunity")
        rows[0]["arrival_target"]["pitch_gap"] = 3
        with self.assertRaisesRegex(ValueError, "到達間隔"):
            validate_candidate_sequence(rows, risk_set="provisional_opportunity")

    def test_last_arrival_must_be_censored(self):
        rows = [self._candidate(2, "provisional_opportunity", True, 8)]
        with self.assertRaisesRegex(ValueError, "右設限"):
            validate_candidate_sequence(rows, risk_set="provisional_opportunity")


if __name__ == "__main__":
    unittest.main()
