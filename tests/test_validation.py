from __future__ import annotations

import unittest

from abs_challenge.validation import (
    build_official_game_record_comparison,
    compare_official_aggregate,
    evaluate_phase0_gate,
)


class Phase0ValidationTests(unittest.TestCase):
    def test_builds_comparison_from_official_game_totals(self) -> None:
        audit = {
            "game": {"game_pk": 123},
            "summary": {"challenge_events": 5, "overturned": 2},
        }
        feed = {
            "gamePk": 123,
            "gameData": {
                "absChallenges": {
                    "hasChallenges": True,
                    "away": {"usedSuccessful": 1, "usedFailed": 1},
                    "home": {"usedSuccessful": 1, "usedFailed": 2},
                }
            },
        }

        comparison = build_official_game_record_comparison(
            scope_id="regulation-sample",
            audits=[audit],
            feeds=[feed],
        )

        self.assertEqual(comparison["game_pks"], [123])
        self.assertEqual(comparison["observed_attempts"], 5)
        self.assertEqual(comparison["observed_overturned"], 2)
        self.assertEqual(comparison["official_attempts"], 5)
        self.assertEqual(comparison["official_overturned"], 2)

    def test_official_game_comparison_rejects_different_game_sets(self) -> None:
        audit = {
            "game": {"game_pk": 123},
            "summary": {"challenge_events": 1, "overturned": 0},
        }
        feed = {"gamePk": 456, "gameData": {}}

        with self.assertRaisesRegex(ValueError, "same game_pk set"):
            build_official_game_record_comparison(
                scope_id="bad-sample",
                audits=[audit],
                feeds=[feed],
            )

    def test_missing_required_cohort_blocks_phase0_gate(self) -> None:
        audits = [
            {
                "game": {
                    "game_pk": 1,
                    "competition": "MLB",
                    "season": 2026,
                    "extra_inning_game": True,
                },
                "summary": {"phase0_game_pass": True},
            }
        ]
        requirements = {
            "required_cohorts": [
                {"competition": "Triple-A", "season": 2023, "minimum_games": 1},
                {"competition": "MLB", "season": 2026, "minimum_games": 1},
            ],
            "minimum_extra_inning_games": 1,
            "official_aggregate_comparison_required": False,
        }

        result = evaluate_phase0_gate(audits, requirements)

        self.assertFalse(result["phase0_gate_pass"])
        self.assertEqual(
            result["missing_cohorts"],
            [{"competition": "Triple-A", "season": 2023, "missing_games": 1}],
        )

    def test_official_aggregate_mismatch_is_rejected(self) -> None:
        result = compare_official_aggregate(
            scope_id="aaa-2025",
            observed_attempts=90,
            observed_overturned=36,
            official_attempts=100,
            official_overturned=50,
            maximum_attempt_relative_error=0.01,
            maximum_overturn_rate_absolute_error=0.01,
        )

        self.assertFalse(result["pass"])
        self.assertAlmostEqual(result["attempt_relative_error"], 0.1)
        self.assertAlmostEqual(result["overturn_rate_absolute_error"], 0.1)

    def test_gate_recomputes_official_comparison_with_versioned_thresholds(self) -> None:
        audits = [
            {
                "game": {
                    "game_pk": 1,
                    "competition": "MLB",
                    "season": 2026,
                    "extra_inning_game": False,
                },
                "summary": {"phase0_game_pass": True},
            }
        ]
        requirements = {
            "required_cohorts": [
                {"competition": "MLB", "season": 2026, "minimum_games": 1}
            ],
            "minimum_extra_inning_games": 0,
            "official_aggregate_comparison_required": True,
            "maximum_attempt_relative_error": 0.01,
            "maximum_overturn_rate_absolute_error": 0.01,
        }
        stale_comparison = {
            "scope_id": "mlb-2026",
            "pass": True,
            "observed_attempts": 90,
            "observed_overturned": 36,
            "official_attempts": 100,
            "official_overturned": 50,
        }

        result = evaluate_phase0_gate(
            audits, requirements, official_comparisons=[stale_comparison]
        )

        self.assertFalse(result["phase0_gate_pass"])
        self.assertFalse(result["official_aggregate_comparison_pass"])
        self.assertFalse(result["official_comparisons"][0]["pass"])

    def test_official_comparison_rejects_impossible_overturn_counts(self) -> None:
        with self.assertRaises(ValueError):
            compare_official_aggregate(
                scope_id="mlb-2026",
                observed_attempts=100,
                observed_overturned=101,
                official_attempts=100,
                official_overturned=50,
                maximum_attempt_relative_error=0.01,
                maximum_overturn_rate_absolute_error=0.01,
            )


if __name__ == "__main__":
    unittest.main()
