"""雙路徑分母、超界、終局及來源缺漏的覆蓋測試。"""

import json
from pathlib import Path
import tempfile
import unittest

from abs_challenge.baseline import SavantBaseline
from abs_challenge.state_value import GameState
from abs_challenge.wp_coverage import inspect_call, inspect_audit, summarize, run_coverage
from baseline_support import synthetic_snapshot
from test_phase1 import sample


class CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = SavantBaseline(synthetic_snapshot())

    def test_plus_five_walk_crosses_only_one_branch_and_keeps_re(self):
        result = inspect_call(self.baseline, GameState(4, "bottom", 0, 7, 3, 1, 5, 0), "strike")
        self.assertEqual(result["status"], "one_supported")
        self.assertEqual(result["s1"]["transition"]["next_state"]["home_score"], 6)
        self.assertIsNone(result["s1"]["wp_home"])
        self.assertEqual(result["s1"]["missing_reason_code"], "score_diff_out_of_range")
        self.assertEqual(result["s1"]["post_home_score_diff"], 6)
        self.assertIsNotNone(result["s1"]["re"])
        self.assertIsNone(result["delta_wp_decision"])

    def test_minus_five_away_walk_and_defending_team(self):
        result = inspect_call(self.baseline, GameState(4, "top", 0, 7, 3, 1, 0, 5), "ball")
        self.assertEqual(result["status"], "one_supported")
        self.assertFalse(result["s0"]["supported"])
        self.assertEqual(result["decision_home_away"], "home")
        self.assertEqual(result["decision_side"], "fielding")

    def test_both_outside_never_clips(self):
        result = inspect_call(self.baseline, GameState(4, "top", 0, 0, 0, 0, 0, 6), "strike")
        self.assertEqual(result["status"], "neither_supported")
        self.assertEqual([result[name]["missing_reason_code"] for name in ("s0", "s1")],
                         ["score_diff_out_of_range", "score_diff_out_of_range"])
        self.assertEqual([result[name]["post_home_score_diff"] for name in ("s0", "s1")], [-6, -6])

    def test_strikeout_switches_half_but_not_decision_team(self):
        result = inspect_call(self.baseline, GameState(4, "top", 2, 0, 0, 2, 0, 0), "strike")
        self.assertEqual(result["s0"]["transition"]["next_state"]["half"], "bottom")
        self.assertEqual(result["decision_home_away"], "away")
        self.assertEqual(result["s0"]["re"], 0)

    def test_walkoff_and_regulation_tie_use_distinct_boundaries(self):
        walk = inspect_call(self.baseline, GameState(9, "bottom", 0, 7, 3, 1, 0, 0), "strike")
        self.assertEqual(walk["s1"]["terminal"], "home_win")
        self.assertEqual(walk["s1"]["wp_home"], 1)
        tie = inspect_call(self.baseline, GameState(9, "bottom", 2, 0, 0, 2, 0, 0), "strike")
        self.assertEqual(tie["s0"]["terminal"], "regulation_tie")
        self.assertEqual(tie["s0"]["wp_home"], 0.47)

    def test_known_terminal_is_supported_even_outside_table(self):
        result = inspect_call(self.baseline, GameState(9, "bottom", 2, 0, 0, 2, 0, 6), "strike")
        self.assertEqual(result["status"], "one_supported")
        self.assertEqual(result["s0"]["wp_home"], 0)

    def test_compound_and_invalid_state_stay_in_denominator(self):
        audit, feed = sample()
        audit["rules"]["regime_id"] = "synthetic"
        audit["ledger"][0]["valid_budget"] = True
        good = inspect_audit(self.baseline, audit, feed)[0]
        feed["liveData"]["plays"]["allPlays"][0]["runners"] = [
            {"details": {"playIndex": 0}, "movement": {"start": "1B", "end": "2B"}}]
        compound = inspect_audit(self.baseline, audit, feed)[0]
        self.assertEqual(compound["status"], "unsupported_compound_event")
        audit["ledger"][0]["statcast_pre_pitch_state"] = None
        invalid = inspect_audit(self.baseline, audit, feed)[0]
        self.assertEqual(invalid["status"], "invalid_state")
        summary = summarize([good, compound, invalid, {"status": "excluded_extra_inning"}])
        self.assertEqual(summary["regulation_attempts"], 3)
        self.assertEqual(summary["both_supported_fraction"], 1 / 3)

    def test_no_post_event_observation_enters_values(self):
        audit, feed = sample()
        audit["rules"]["regime_id"] = "synthetic"
        audit["ledger"][0]["valid_budget"] = True
        expected = inspect_audit(self.baseline, audit, feed)
        audit["ledger"][0]["statcast_pitch_observation"] = {"plate_x": 999, "delta_home_win_exp": 1}
        self.assertEqual(inspect_audit(self.baseline, audit, feed), expected)

    def test_missing_sources_remain_games_and_replay_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "baseline.json").write_text(json.dumps(synthetic_snapshot()), encoding="utf-8")
            plan = {"schema_version": "official-wp-coverage-plan-v1", "population": "actual_attempts_development_only",
                    "coverage_required_fraction": 1.0, "baseline": "baseline.json",
                    "games": [{"game_pk": 123, "date": "2026-04-04"}]}
            path = root / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            first, second = run_coverage(path, root), run_coverage(path, root)
            self.assertEqual(first["selected_game_count"], 1)
            self.assertEqual(first["game_status_counts"], {"source_failure": 1})
            self.assertFalse(first["processed_regulation_attempt_denominator_complete"])
            self.assertIsNone(first["opportunity_population_coverage"])
            self.assertEqual(first["content_lock_sha256"], second["content_lock_sha256"])
            plan["games"] *= 2
            path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaises(ValueError):
                run_coverage(path, root)
