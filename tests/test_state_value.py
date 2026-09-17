"""以手算棒球情境驗證公開狀態轉移介面。"""

from dataclasses import replace
import unittest

from abs_challenge.state_value import GameState, apply_call, counterfactual_states


class StateValueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = GameState(4, "top", 0, 0, 0, 0, 0, 0)

    def test_normal_calls_produce_separate_counts(self) -> None:
        s0, s1 = counterfactual_states(self.state, "strike")
        self.assertEqual((s0.next_state.balls, s0.next_state.strikes), (0, 1))
        self.assertEqual((s1.next_state.balls, s1.next_state.strikes), (1, 0))
        self.assertEqual(self.state.balls, 0)

    def test_walk_forces_only_connected_runners_for_all_eight_base_states(self) -> None:
        # 無人→一壘；二壘單獨有人→一二壘；二三壘有人→滿壘但沒有得分。
        expected = [(1, 0), (3, 0), (3, 0), (7, 0), (5, 0), (7, 0), (7, 0), (7, 1)]
        for bases, (next_bases, runs) in enumerate(expected):
            with self.subTest(bases=bases):
                transition = apply_call(replace(self.state, bases=bases, balls=3, strikes=2), "ball")
                self.assertEqual(transition.next_state.bases, next_bases)
                self.assertEqual(transition.runs_scored, runs)
                self.assertEqual(transition.next_state.away_score, runs)
                self.assertEqual((transition.next_state.balls, transition.next_state.strikes), (0, 0))

    def test_strikeout_starts_new_count_without_erasing_runners(self) -> None:
        t = apply_call(replace(self.state, bases=6, balls=3, strikes=2), "strike")
        self.assertEqual((t.next_state.outs, t.next_state.bases, t.next_state.balls, t.next_state.strikes), (1, 6, 0, 0))

    def test_third_out_switches_half_and_clears_bases(self) -> None:
        t = apply_call(replace(self.state, bases=7, outs=2, strikes=2), "strike")
        self.assertTrue(t.half_ended)
        self.assertEqual((t.next_state.inning, t.next_state.half, t.next_state.outs, t.next_state.bases), (4, "bottom", 0, 0))
        t = apply_call(replace(self.state, half="bottom", outs=2, strikes=2), "strike")
        self.assertEqual((t.next_state.inning, t.next_state.half), (5, "top"))

    def test_ninth_top_home_lead_ends_without_bottom_half(self) -> None:
        t = apply_call(GameState(9, "top", 2, 0, 3, 2, 1, 0), "strike")
        self.assertEqual(t.terminal, "home_win")
        self.assertIsNone(t.next_state)

    def test_ninth_top_tie_still_requires_bottom_half(self) -> None:
        t = apply_call(GameState(9, "top", 2, 0, 3, 2, 0, 0), "strike")
        self.assertIsNone(t.terminal)
        self.assertEqual(t.next_state.half, "bottom")

    def test_ninth_bottom_tie_is_boundary_not_game_over(self) -> None:
        t = apply_call(GameState(9, "bottom", 2, 0, 3, 2, 0, 0), "strike")
        self.assertEqual(t.terminal, "regulation_tie")
        self.assertIsNone(t.next_state)

    def test_ninth_bottom_trailing_third_out_is_away_win(self) -> None:
        t = apply_call(GameState(9, "bottom", 2, 7, 3, 2, 0, 1), "strike")
        self.assertEqual(t.terminal, "away_win")

    def test_bases_loaded_walk_can_be_walkoff(self) -> None:
        t = apply_call(GameState(9, "bottom", 2, 7, 3, 2, 0, 0), "ball")
        self.assertEqual(t.terminal, "home_win")
        self.assertEqual(t.runs_scored, 1)

    def test_bases_loaded_tying_walk_does_not_end_game(self) -> None:
        t = apply_call(GameState(9, "bottom", 2, 7, 3, 2, 0, 1), "ball")
        self.assertIsNone(t.terminal)
        self.assertEqual((t.next_state.home_score, t.next_state.away_score), (1, 1))

    def test_rejects_invalid_states_and_non_called_pitches(self) -> None:
        for field, value in (("inning", 10), ("inning", True), ("outs", 3), ("bases", 8),
                             ("balls", 4), ("strikes", 3), ("half", "unknown"), ("away_score", -1), ("outs", 1.5)):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                replace(self.state, **{field: value})
        with self.assertRaises(ValueError):
            GameState(9, "bottom", 0, 0, 0, 0, 1, 0)
        with self.assertRaises(ValueError):
            apply_call(self.state, "foul")

    def test_missing_runner_column_is_not_empty_base(self) -> None:
        row = {"inning": 4, "inning_topbot": "Top", "outs_when_up": 0, "balls": 0, "strikes": 0,
               "home_score": 0, "away_score": 0, "on_1b": None, "on_2b": None}
        with self.assertRaises(ValueError):
            GameState.from_statcast(row)
        row["on_3b"] = "456"
        self.assertEqual(GameState.from_statcast(row).bases, 4)
        row["on_3b"] = "nan"
        with self.assertRaises(ValueError):
            GameState.from_statcast(row)
