from __future__ import annotations

import unittest

from abs_challenge.savant import (
    build_abs_csv_url,
    build_called_pitches_csv_url,
    index_statcast_rows,
    selected_game_state,
    selected_pre_pitch_state,
)


class SavantTests(unittest.TestCase):
    def test_minor_url_contains_abs_and_level_filters(self) -> None:
        url = build_abs_csv_url("2025-05-11", "aaa")
        self.assertIn("statcast-search-minors%2Fcsv", url.replace("/", "%2F"))
        self.assertIn("hfLevel=AAA%7C", url)
        self.assertIn("hfABSFlag=", url)

    def test_mlb_url_uses_major_endpoint(self) -> None:
        url = build_abs_csv_url("2026-03-25", "mlb")
        self.assertIn("/statcast_search/csv?", url)
        self.assertNotIn("hfLevel", url)

    def test_index_and_state_conversion(self) -> None:
        row = {
            "game_pk": "123",
            "at_bat_number": "8",
            "pitch_number": "4",
            "balls": "0",
            "strikes": "2",
            "outs_when_up": "1",
            "inning": "6",
            "home_score": "2",
            "away_score": "1",
            "bat_score": "2",
            "fld_score": "1",
            "inning_topbot": "Bot",
            "on_1b": "99",
            "on_2b": "",
            "on_3b": "",
            "plate_x": "0.8",
            "plate_z": "1.7",
            "sz_top": "3.3",
            "sz_bot": "1.6",
            "home_win_exp": "0.62",
            "bat_win_exp": "0.62",
            "delta_home_win_exp": "0.01",
            "delta_run_exp": "0.03",
            "description": "ball",
            "des": "",
        }
        self.assertIs(index_statcast_rows([row])[(123, 8, 4)], row)
        state = selected_game_state(row)
        self.assertEqual(state["balls"], 0)
        self.assertEqual(state["home_win_exp"], 0.62)
        self.assertEqual(state["on_1b"], "99")
        self.assertIsNone(state["on_2b"])

    def test_duplicate_pitch_key_is_rejected(self) -> None:
        row = {"game_pk": "123", "at_bat_number": "8", "pitch_number": "4"}

        with self.assertRaisesRegex(ValueError, "duplicate Statcast pitch key"):
            index_statcast_rows([row, dict(row)])

    def test_invalid_pitch_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid Statcast pitch key"):
            index_statcast_rows([{"game_pk": "123", "at_bat_number": "8"}])

    def test_pre_pitch_state_excludes_outcome_derived_fields(self) -> None:
        row = {
            "balls": "1",
            "strikes": "2",
            "home_win_exp": "0.62",
            "description": "called_strike",
            "delta_home_win_exp": "0.04",
            "delta_run_exp": "0.18",
            "plate_x": "0.2",
        }

        state = selected_pre_pitch_state(row)

        self.assertEqual(state["balls"], 1)
        self.assertEqual(state["home_win_exp"], 0.62)
        self.assertNotIn("description", state)
        self.assertNotIn("delta_home_win_exp", state)
        self.assertNotIn("delta_run_exp", state)
        self.assertNotIn("plate_x", state)

    def test_called_pitch_download_does_not_filter_to_actual_challenges(self) -> None:
        url = build_called_pitches_csv_url("2025-05-11", "aaa")

        self.assertIn("statcast-search-minors", url)
        self.assertNotIn("hfABSFlag", url)


if __name__ == "__main__":
    unittest.main()
