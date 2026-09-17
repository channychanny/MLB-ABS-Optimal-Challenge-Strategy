from __future__ import annotations

import unittest

from abs_challenge.domain import GameRules
from abs_challenge.opportunities import build_challenge_opportunities
from test_extract import feed_with_event


class OpportunityTests(unittest.TestCase):
    def test_all_adverse_called_pitches_are_included_not_only_challenges(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        play = feed["liveData"]["plays"]["allPlays"][0]
        challenged_pitch = play["playEvents"][0]
        challenged_pitch["index"] = 1
        challenged_pitch["count"]["strikes"] = 2
        play["playEvents"].insert(
            0,
            {
                "index": 0,
                "type": "pitch",
                "details": {
                    "call": {"code": "C", "description": "Called Strike"}
                },
                "count": {"balls": 0, "strikes": 1, "outs": 0},
            },
        )
        statcast_rows = [
            {
                "game_pk": "1",
                "at_bat_number": "4",
                "pitch_number": "1",
                "inning": "4",
                "inning_topbot": "Top",
                "balls": "0",
                "strikes": "0",
                "description": "called_strike",
            },
            {
                "game_pk": "1",
                "at_bat_number": "4",
                "pitch_number": "2",
                "inning": "4",
                "inning_topbot": "Top",
                "balls": "0",
                "strikes": "1",
                "description": "called_strike",
            },
        ]

        rows = build_challenge_opportunities(
            feed,
            statcast_rows,
            GameRules(2, rule_status="confirmed"),
        )

        self.assertEqual(len(rows), 2)
        self.assertFalse(rows[0].actual_challenge)
        self.assertTrue(rows[1].actual_challenge)
        self.assertEqual(rows[0].decision_team_id, 10)
        self.assertEqual(rows[0].challenges_remaining, 2)
        self.assertEqual(rows[1].challenges_remaining, 2)

    def test_near_edge_high_value_pitch_is_a_reasonable_candidate(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        feed["liveData"]["plays"]["allPlays"][0]["playEvents"][0].pop(
            "reviewDetails"
        )
        statcast_rows = [
            {
                "game_pk": "1",
                "at_bat_number": "4",
                "pitch_number": "1",
                "inning": "4",
                "inning_topbot": "Top",
                "balls": "0",
                "strikes": "0",
                "description": "called_strike",
                "plate_x": "0.72",
                "plate_z": "2.50",
                "sz_bot": "1.50",
                "sz_top": "3.50",
                "delta_run_exp": "0.35",
            }
        ]

        row = build_challenge_opportunities(
            feed,
            statcast_rows,
            GameRules(2, rule_status="confirmed"),
        )[0]

        self.assertTrue(row.reasonable_candidate)
        self.assertIn("near_zone_edge_and_high_run_value", row.reasonable_reasons)

    def test_position_player_pitching_is_not_a_legal_opportunity(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        play = feed["liveData"]["plays"]["allPlays"][0]
        play["playEvents"][0].pop("reviewDetails")
        feed["gameData"]["players"] = {
            "ID200": {
                "id": 200,
                "primaryPosition": {"type": "Infielder", "abbreviation": "1B"},
            }
        }
        statcast_rows = [
            {
                "game_pk": "1",
                "at_bat_number": "4",
                "pitch_number": "1",
                "inning": "4",
                "inning_topbot": "Top",
                "balls": "0",
                "strikes": "0",
                "description": "called_strike",
            }
        ]

        rows = build_challenge_opportunities(
            feed,
            statcast_rows,
            GameRules(2, rule_status="confirmed"),
        )

        self.assertEqual(rows, [])

    def test_primary_dataset_excludes_extra_inning_opportunities(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        play = feed["liveData"]["plays"]["allPlays"][0]
        play["about"]["inning"] = 10
        play["playEvents"][0].pop("reviewDetails")
        statcast_rows = [
            {
                "game_pk": "1",
                "at_bat_number": "4",
                "pitch_number": "1",
                "inning": "10",
                "inning_topbot": "Top",
                "balls": "0",
                "strikes": "0",
                "description": "called_strike",
            }
        ]

        rows = build_challenge_opportunities(
            feed,
            statcast_rows,
            GameRules(2, rule_status="confirmed"),
        )

        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
