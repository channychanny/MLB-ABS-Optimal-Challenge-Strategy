"""Dataset B 依場次與時間切分，既有開發場不可升格為 holdout。"""

import json
from pathlib import Path
import unittest

from abs_challenge.dataset_b_split import assign_game, assign_games, validate_plan


PLAN = json.loads((Path(__file__).resolve().parents[1] / "config" /
                   "dataset_b_split_plan.json").read_text(encoding="utf-8"))


def game(pk, date, regime="aaa-2025-il", sport=11, league=117, status="confirmed", budget=2):
    return {"game_pk": pk, "date": date, "regime": regime, "sport_id": sport,
            "league_id": league, "rule_status": status, "initial_challenges": budget}


class DatasetBSplitTests(unittest.TestCase):
    def test_known_development_games_cover_existing_cohorts(self):
        validate_plan(PLAN)
        root = Path(__file__).resolve().parents[1]
        expansion = json.loads((root / "config" / "official_wp_expansion_games.json").read_text(encoding="utf-8"))
        pilot = json.loads((root / "config" / "official_wp_coverage.json").read_text(encoding="utf-8"))
        expected = {row["game_pk"] for row in expansion["games"] + pilot["games"]}
        expected.update({721393, 723507, 723845, 751852, 753200, 753349,
                         779936, 780009, 780910})
        self.assertEqual(set(PLAN["known_development_game_pks"]), expected)
        self.assertEqual(len(expected), 39)
        self.assertEqual(assign_game(PLAN, game(780464, "2025-05-20"))["split"], "development_only")
        self.assertEqual(assign_game(PLAN, game(824087, "2026-07-20", "mlb-2026", 1, None))["split"], "development_only")

    def test_time_windows_and_regime_gate_are_disjoint(self):
        cases = [
            (game(900001, "2024-07-01", "aaa-2024-il-after-2024-06-25"), "train"),
            (game(900002, "2025-05-01"), "train"),
            (game(900003, "2025-07-01"), "validation"),
            (game(900004, "2025-09-01"), "test"),
            (game(900005, "2026-08-01", "mlb-2026", 1, None), "external"),
            (game(900006, "2025-07-01", "aaa-2025-pcl", 11, 112, budget=3), "excluded_rule_regime"),
            (game(900007, "2025-07-01", status="provisional"), "unconfirmed_rule_regime"),
            (game(900008, "2023-07-01"), "outside_predeclared_windows"),
        ]
        for entry, expected in cases:
            with self.subTest(pk=entry["game_pk"]):
                self.assertEqual(assign_game(PLAN, entry)["split"], expected)

    def test_duplicate_game_and_overlapping_windows_fail_closed(self):
        entry = game(900003, "2025-07-01")
        with self.assertRaisesRegex(ValueError, "重複"):
            assign_games(PLAN, [entry, entry])
        broken = {**PLAN, "windows": PLAN["windows"] + [dict(PLAN["windows"][2], name="duplicate")]}
        with self.assertRaisesRegex(ValueError, "重疊"):
            validate_plan(broken)


if __name__ == "__main__":
    unittest.main()
