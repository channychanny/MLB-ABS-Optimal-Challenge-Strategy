from __future__ import annotations

import unittest

from abs_challenge.extract import extract_challenge_events


def feed_with_event(
    *,
    final_code: str,
    final_description: str,
    overturned: bool,
    challenge_team_id: int,
    player: dict | None,
    half: str = "top",
    balls_after: int = 0,
    strikes_after: int = 1,
) -> dict:
    review = {
        "isOverturned": overturned,
        "challengeTeamId": challenge_team_id,
        "reviewType": "MJ",
    }
    if player is not None:
        review["player"] = player
    return {
        "gamePk": 1,
        "gameData": {
            "datetime": {"officialDate": "2026-03-25"},
            "game": {"season": "2026"},
            "teams": {
                "away": {
                    "id": 10,
                    "name": "Away",
                    "sport": {"id": 1, "name": "Major League Baseball"},
                    "league": {"id": 103, "name": "American League"},
                },
                "home": {
                    "id": 20,
                    "name": "Home",
                    "sport": {"id": 1, "name": "Major League Baseball"},
                    "league": {"id": 104, "name": "National League"},
                },
            },
        },
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "about": {"atBatIndex": 3, "inning": 4, "halfInning": half},
                        "matchup": {
                            "batter": {"id": 100, "fullName": "Batter"},
                            "pitcher": {"id": 200, "fullName": "Pitcher"},
                        },
                        "playEvents": [
                            {
                                "index": 0,
                                "type": "pitch",
                                "details": {
                                    "call": {
                                        "code": final_code,
                                        "description": final_description,
                                    },
                                    "hasReview": True,
                                },
                                "count": {
                                    "balls": balls_after,
                                    "strikes": strikes_after,
                                    "outs": 0,
                                },
                                "reviewDetails": review,
                                "pitchData": {
                                    "coordinates": {"pX": 0.1, "pZ": 2.5},
                                    "strikeZoneTop": 3.4,
                                    "strikeZoneBottom": 1.5,
                                },
                            }
                        ],
                    }
                ]
            }
        },
    }


class ExtractChallengeTests(unittest.TestCase):
    def test_confirmed_called_strike_is_batter_challenge(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        event = extract_challenge_events(feed)[0]
        self.assertEqual(event.original_call, "strike")
        self.assertEqual(event.abs_call, "strike")
        self.assertEqual(event.challenger_role, "batter")
        self.assertTrue(event.challenge_team_matches_call)
        self.assertEqual((event.balls_before, event.strikes_before), (0, 0))

    def test_overturned_feed_ball_was_originally_called_strike(self) -> None:
        feed = feed_with_event(
            final_code="B",
            final_description="Ball",
            overturned=True,
            challenge_team_id=10,
            player=None,
            balls_after=2,
            strikes_after=2,
        )
        event = extract_challenge_events(feed)[0]
        self.assertEqual(event.original_call, "strike")
        self.assertEqual(event.abs_call, "ball")
        self.assertEqual(event.challenger_role, "batter_inferred")
        self.assertEqual((event.balls_before, event.strikes_before), (1, 2))
        self.assertEqual((event.balls_after_original, event.strikes_after_original), (1, 3))
        self.assertEqual((event.balls_after_abs, event.strikes_after_abs), (2, 2))

    def test_overturned_feed_strike_was_originally_called_ball(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=True,
            challenge_team_id=20,
            player=None,
            balls_after=0,
            strikes_after=2,
        )
        event = extract_challenge_events(feed)[0]
        self.assertEqual(event.original_call, "ball")
        self.assertEqual(event.abs_call, "strike")
        self.assertEqual(event.challenger_role, "fielder_unknown")
        self.assertTrue(event.challenge_team_matches_call)

    def test_terminal_result_text_recovers_missing_pitch_review(self) -> None:
        feed = feed_with_event(
            final_code="B",
            final_description="Ball",
            overturned=False,
            challenge_team_id=20,
            player=None,
            balls_after=4,
            strikes_after=1,
        )
        play = feed["liveData"]["plays"]["allPlays"][0]
        play["playEvents"][0].pop("reviewDetails")
        play["result"] = {
            "description": (
                "Home challenged (pitch result), call on the field was upheld: "
                "Batter walks."
            )
        }
        event = extract_challenge_events(feed)[0]
        self.assertEqual(event.review_source, "play_result_description")
        self.assertEqual(event.challenge_team_source, "inferred_from_call_and_half")
        self.assertEqual(event.challenge_team_id, 20)
        self.assertEqual(event.original_call, "ball")
        self.assertFalse(event.overturned)

    def test_terminal_fallback_is_not_suppressed_by_an_earlier_review(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        play = feed["liveData"]["plays"]["allPlays"][0]
        play["playEvents"].append(
            {
                "index": 1,
                "type": "pitch",
                "details": {
                    "call": {"code": "C", "description": "Called Strike"},
                    "hasReview": True,
                },
                "count": {"balls": 0, "strikes": 2, "outs": 0},
            }
        )
        play["result"] = {
            "description": (
                "Away challenged (pitch result), call on the field was upheld: "
                "Batter strikes out."
            )
        }

        events = extract_challenge_events(feed)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[1].review_source, "play_result_description")
        self.assertEqual(events[1].play_event_index, 1)

    def test_terminal_result_accepts_confirmed_wording(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player=None,
        )
        play = feed["liveData"]["plays"]["allPlays"][0]
        play["playEvents"][0].pop("reviewDetails")
        play["result"] = {
            "description": (
                "Batter challenged (pitch result), call on the field was confirmed: "
                "Batter called out on strikes."
            )
        }

        events = extract_challenge_events(feed)

        self.assertEqual(len(events), 1)
        self.assertFalse(events[0].overturned)


if __name__ == "__main__":
    unittest.main()
