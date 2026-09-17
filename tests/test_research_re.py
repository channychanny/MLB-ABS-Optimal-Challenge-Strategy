"""Train-only RE 估計，不以測試年度或再見半局補齊表格。"""

import unittest

from abs_challenge.historical import build_historical_dataset
from abs_challenge.research_re import estimate_re_and_boundary
from historical_support import contract, game_fixture


def dataset(**kwargs):
    feed, rows = game_fixture(**kwargs)
    return build_historical_dataset([feed], rows, contract())


class ResearchRETests(unittest.TestCase):
    def test_empirical_values_and_missing_cells(self):
        result = estimate_re_and_boundary([dataset()])
        self.assertEqual(len(result["re24"]), 24)
        self.assertEqual(len(result["re288"]), 288)
        cell = result["re24"][0]
        self.assertEqual(cell["n"], 19)
        self.assertEqual(cell["run_sum"], 1)
        self.assertAlmostEqual(cell["mean"], 1 / 19)
        self.assertIsNone(result["re288"][2]["mean"])
        self.assertEqual(result["re288"][2]["n"], 0)
        self.assertIsNone(result["regulation_boundary"]["home_wp"])
        self.assertFalse(result["formal_model_ready"])

    def test_nontrain_does_not_change_estimates(self):
        train = dataset()
        before = estimate_re_and_boundary([train])
        others = [dataset(season=year, game_pk=year, away_runs=12) for year in (2024, 2025, 2026)]
        after = estimate_re_and_boundary([train, *others])
        self.assertEqual(before["re24"], after["re24"])
        self.assertEqual(before["re288"], after["re288"])
        self.assertEqual(before["regulation_boundary"], after["regulation_boundary"])
        self.assertEqual(after["summary"]["ignored_nontrain_games"], 3)

    def test_no_train_rejected(self):
        with self.assertRaisesRegex(ValueError, "Train"):
            estimate_re_and_boundary([dataset(season=2025)])

    def test_duplicate_game_across_datasets_rejected(self):
        data = dataset()
        with self.assertRaisesRegex(ValueError, "重複"):
            estimate_re_and_boundary([data, data])

    def test_boundary_uses_train_games_not_pitch_weighting(self):
        train = dataset(extra=True)
        validation = dataset(season=2024, game_pk=502, extra=True)
        result = estimate_re_and_boundary([train, validation])
        boundary = result["regulation_boundary"]
        self.assertEqual(boundary["games"], 1)
        self.assertEqual(boundary["game_pks"], [501])
        self.assertEqual(boundary["home_wp"], 0)
        self.assertEqual(result["summary"]["train_pitches"], 108)

    def test_walkoff_censored_half_not_used_for_re(self):
        result = estimate_re_and_boundary([dataset(walkoff=True)])
        self.assertEqual(result["summary"]["excluded_censored_pitches"], 2)
        self.assertEqual(sum(c["run_sum"] for c in result["re24"]), 0)


if __name__ == "__main__":
    unittest.main()
