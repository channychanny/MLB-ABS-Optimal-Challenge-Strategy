from __future__ import annotations

import json
from pathlib import Path
import unittest

from abs_challenge.audit import audit_feed
from abs_challenge.domain import GameRules
from abs_challenge.rules import resolve_game_rules
from test_extract import feed_with_event


class AuditTests(unittest.TestCase):
    def test_game_without_challenge_events_cannot_pass_phase0(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player=None,
        )
        feed["liveData"]["plays"]["allPlays"] = []

        report = audit_feed(feed, GameRules(2), statcast_rows=[])

        self.assertFalse(report["summary"]["phase0_game_pass"])
        self.assertEqual(report["summary"]["status"], "fail_no_challenge_events")

    def test_game_without_statcast_match_cannot_pass_phase0(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )

        report = audit_feed(feed, GameRules(2), statcast_rows=[])

        self.assertTrue(report["summary"]["core_ledger_pass"])
        self.assertFalse(report["summary"]["phase0_game_pass"])
        self.assertEqual(report["summary"]["status"], "incomplete_missing_statcast")

    def test_provisional_rule_regime_cannot_pass_phase0(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        statcast_row = {
            "game_pk": "1",
            "at_bat_number": "4",
            "pitch_number": "1",
            "balls": "0",
            "strikes": "0",
            "outs_when_up": "0",
            "inning": "4",
            "inning_topbot": "Top",
            "home_score": "0",
            "away_score": "0",
            "on_1b": "",
            "on_2b": "",
            "on_3b": "",
        }

        report = audit_feed(
            feed,
            GameRules(2, rule_status="provisional_pending_validation"),
            statcast_rows=[statcast_row],
        )

        self.assertFalse(report["summary"]["phase0_game_pass"])
        self.assertFalse(report["summary"]["rule_regime_pass"])
        self.assertEqual(report["summary"]["status"], "incomplete_rule_regime")

    def test_audit_separates_pre_pitch_features_from_outcome_fields(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        statcast_row = {
            "game_pk": "1",
            "at_bat_number": "4",
            "pitch_number": "1",
            "balls": "0",
            "strikes": "0",
            "description": "called_strike",
            "delta_home_win_exp": "0.04",
            "delta_run_exp": "0.18",
            "plate_x": "0.2",
        }

        report = audit_feed(
            feed,
            GameRules(2, rule_status="confirmed"),
            statcast_rows=[statcast_row],
        )
        row = report["ledger"][0]

        self.assertNotIn("delta_home_win_exp", row["statcast_pre_pitch_state"])
        self.assertEqual(
            row["statcast_pitch_observation"]["delta_home_win_exp"], 0.04
        )

    def test_missing_required_pre_pitch_field_cannot_pass_phase0(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        statcast_row = {
            "game_pk": "1",
            "at_bat_number": "4",
            "pitch_number": "1",
            "balls": "0",
            "strikes": "0",
            "inning": "4",
            "inning_topbot": "Top",
            "home_score": "0",
            "away_score": "0",
            "on_1b": "",
            "on_2b": "",
            "on_3b": "",
        }

        report = audit_feed(
            feed,
            GameRules(2, rule_status="confirmed"),
            statcast_rows=[statcast_row],
        )

        self.assertFalse(report["summary"]["phase0_game_pass"])
        self.assertEqual(
            report["summary"]["status"], "fail_statcast_required_state"
        )
        self.assertEqual(report["summary"]["statcast_required_state_missing"], 1)

    def test_statcast_count_mismatch_cannot_pass_phase0(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        statcast_row = {
            "game_pk": "1",
            "at_bat_number": "4",
            "pitch_number": "1",
            "balls": "1",
            "strikes": "0",
            "outs_when_up": "0",
            "inning": "4",
            "inning_topbot": "Top",
            "home_score": "0",
            "away_score": "0",
            "on_1b": "",
            "on_2b": "",
            "on_3b": "",
        }

        report = audit_feed(
            feed,
            GameRules(2, rule_status="confirmed"),
            statcast_rows=[statcast_row],
        )

        self.assertFalse(report["summary"]["phase0_game_pass"])
        self.assertEqual(
            report["summary"]["status"], "fail_statcast_count_mismatch"
        )
        self.assertEqual(report["summary"]["statcast_count_mismatches"], 1)

    def test_official_abs_counter_mismatch_cannot_pass_phase0(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        feed["gameData"]["absChallenges"] = {
            "hasChallenges": True,
            "away": {"usedSuccessful": 0, "usedFailed": 2},
            "home": {"usedSuccessful": 0, "usedFailed": 0},
        }
        statcast_row = {
            "game_pk": "1",
            "at_bat_number": "4",
            "pitch_number": "1",
            "balls": "0",
            "strikes": "0",
            "outs_when_up": "0",
            "inning": "4",
            "inning_topbot": "Top",
            "home_score": "0",
            "away_score": "0",
            "on_1b": "",
            "on_2b": "",
            "on_3b": "",
        }

        report = audit_feed(
            feed,
            GameRules(2, rule_status="confirmed"),
            statcast_rows=[statcast_row],
        )

        self.assertFalse(report["summary"]["phase0_game_pass"])
        self.assertFalse(report["summary"]["official_counter_pass"])
        self.assertEqual(report["summary"]["status"], "fail_official_counter_mismatch")

    def test_unresolved_pitcher_or_catcher_role_does_not_block_team_level_gate(
        self,
    ) -> None:
        feed = feed_with_event(
            final_code="B",
            final_description="Ball",
            overturned=False,
            challenge_team_id=20,
            player=None,
            balls_after=1,
            strikes_after=0,
        )
        statcast_row = {
            "game_pk": "1",
            "at_bat_number": "4",
            "pitch_number": "1",
            "balls": "0",
            "strikes": "0",
            "outs_when_up": "0",
            "inning": "4",
            "inning_topbot": "Top",
            "home_score": "0",
            "away_score": "0",
            "on_1b": "",
            "on_2b": "",
            "on_3b": "",
        }

        report = audit_feed(
            feed,
            GameRules(2, rule_status="confirmed"),
            statcast_rows=[statcast_row],
        )

        self.assertTrue(report["summary"]["phase0_game_pass"])
        self.assertTrue(report["summary"]["challenger_eligibility_pass"])
        self.assertEqual(report["summary"]["unknown_challenger_role"], 0)
        self.assertEqual(report["summary"]["fielder_role_unresolved"], 1)
        self.assertFalse(report["summary"]["exact_role_attribution_complete"])

    def test_ineligible_or_unexplained_challenger_still_blocks_gate(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 999, "fullName": "Unexpected Player"},
        )
        statcast_row = {
            "game_pk": "1",
            "at_bat_number": "4",
            "pitch_number": "1",
            "balls": "0",
            "strikes": "0",
            "outs_when_up": "0",
            "inning": "4",
            "inning_topbot": "Top",
            "home_score": "0",
            "away_score": "0",
            "on_1b": "",
            "on_2b": "",
            "on_3b": "",
        }

        report = audit_feed(
            feed,
            GameRules(2, rule_status="confirmed"),
            statcast_rows=[statcast_row],
        )

        self.assertFalse(report["summary"]["phase0_game_pass"])
        self.assertFalse(report["summary"]["challenger_eligibility_pass"])
        self.assertEqual(report["summary"]["challenger_eligibility_failures"], 1)
        self.assertEqual(
            report["summary"]["status"], "fail_challenger_eligibility"
        )

    def test_audit_records_cohort_and_extra_inning_metadata(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        play = feed["liveData"]["plays"]["allPlays"][0]
        play["about"]["inning"] = 10

        report = audit_feed(feed, GameRules(2), statcast_rows=[])

        self.assertEqual(report["game"]["competition"], "MLB")
        self.assertEqual(report["game"]["season"], 2026)
        self.assertTrue(report["game"]["extra_inning_game"])

    def test_official_2026_extra_inning_fixture_matches_recorded_ledger(self) -> None:
        fixture_path = (
            Path(__file__).parent / "fixtures" / "official_game_823488_excerpt.json"
        )
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        rules = resolve_game_rules(fixture["feed"])

        report = audit_feed(fixture["feed"], rules, fixture["statcast_rows"])

        self.assertTrue(report["summary"]["phase0_game_pass"])
        self.assertEqual(report["summary"]["challenge_events"], 5)
        self.assertEqual(
            [row["inning"] for row in report["ledger"]], [4, 8, 10, 10, 10]
        )
        self.assertEqual(report["summary"]["ending_budgets"], {"140": 1, "143": 0})


if __name__ == "__main__":
    unittest.main()
