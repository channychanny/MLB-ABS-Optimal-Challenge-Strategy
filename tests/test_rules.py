from __future__ import annotations

import unittest

from abs_challenge.rules import RuleResolutionError, resolve_game_rules


def game_metadata_feed(
    *,
    date: str,
    sport_id: int,
    sport_name: str,
    league_id: int,
    league_name: str,
) -> dict:
    team = {
        "id": 10,
        "sport": {"id": sport_id, "name": sport_name},
        "league": {"id": league_id, "name": league_name},
    }
    return {
        "gameData": {
            "datetime": {"officialDate": date},
            "game": {"season": date[:4]},
            "teams": {"away": team, "home": dict(team)},
        }
    }


class RuleResolutionTests(unittest.TestCase):
    def test_observed_abs_challenge_event_confirms_2023_game_format(self) -> None:
        feed = game_metadata_feed(
            date="2023-07-15",
            sport_id=11,
            sport_name="Triple-A",
            league_id=117,
            league_name="International League",
        )
        feed["liveData"] = {
            "plays": {
                "allPlays": [
                    {
                        "playEvents": [
                            {"reviewDetails": {"reviewType": "MJ"}}
                        ]
                    }
                ]
            }
        }

        rules = resolve_game_rules(feed)

        self.assertEqual(rules.abs_format, "challenge")
        self.assertEqual(rules.rule_status, "confirmed")

    def test_explicit_format_without_feed_evidence_remains_provisional(self) -> None:
        feed = game_metadata_feed(
            date="2023-07-15",
            sport_id=11,
            sport_name="Triple-A",
            league_id=117,
            league_name="International League",
        )

        rules = resolve_game_rules(feed, abs_format="challenge")

        self.assertEqual(rules.rule_status, "provisional_format_selection")

    def test_2026_mlb_rules_resolve_from_feed_metadata(self) -> None:
        feed = game_metadata_feed(
            date="2026-04-01",
            sport_id=1,
            sport_name="Major League Baseball",
            league_id=103,
            league_name="American League",
        )

        rules = resolve_game_rules(feed)

        self.assertEqual(rules.initial_challenges, 2)
        self.assertTrue(rules.refill_if_empty_each_extra_inning)
        self.assertEqual(rules.rule_status, "confirmed")
        self.assertEqual(rules.extra_inning_rule_status, "confirmed")
        self.assertEqual(rules.abs_format, "challenge")

    def test_2024_international_league_after_june_25_uses_two_challenges(self) -> None:
        feed = game_metadata_feed(
            date="2024-07-01",
            sport_id=11,
            sport_name="Triple-A",
            league_id=117,
            league_name="International League",
        )

        rules = resolve_game_rules(feed)

        self.assertEqual(rules.initial_challenges, 2)
        self.assertEqual(rules.regime_id, "aaa-2024-il-after-2024-06-25")
        self.assertEqual(rules.rule_status, "confirmed")
        self.assertEqual(
            rules.extra_inning_rule_status, "provisional_not_primary_scope"
        )

    def test_2024_pacific_coast_league_after_june_25_uses_three_challenges(self) -> None:
        feed = game_metadata_feed(
            date="2024-07-01",
            sport_id=11,
            sport_name="Triple-A",
            league_id=112,
            league_name="Pacific Coast League",
        )

        rules = resolve_game_rules(feed)

        self.assertEqual(rules.initial_challenges, 3)
        self.assertEqual(rules.regime_id, "aaa-2024-pcl-after-2024-06-25")
        self.assertEqual(rules.rule_status, "confirmed")

    def test_2024_before_june_25_requires_explicit_abs_format(self) -> None:
        feed = game_metadata_feed(
            date="2024-05-01",
            sport_id=11,
            sport_name="Triple-A",
            league_id=112,
            league_name="Pacific Coast League",
        )

        with self.assertRaisesRegex(RuleResolutionError, "explicit ABS format"):
            resolve_game_rules(feed)

    def test_2023_triple_a_requires_explicit_abs_format(self) -> None:
        feed = game_metadata_feed(
            date="2023-07-01",
            sport_id=11,
            sport_name="Triple-A",
            league_id=117,
            league_name="International League",
        )

        with self.assertRaisesRegex(RuleResolutionError, "explicit ABS format"):
            resolve_game_rules(feed)

    def test_2025_triple_a_resolves_to_two_challenges(self) -> None:
        feed = game_metadata_feed(
            date="2025-05-11",
            sport_id=11,
            sport_name="Triple-A",
            league_id=112,
            league_name="Pacific Coast League",
        )

        rules = resolve_game_rules(feed)

        self.assertEqual(rules.initial_challenges, 2)
        self.assertEqual(rules.regime_id, "aaa-2025")
        self.assertEqual(rules.rule_status, "confirmed")
        self.assertEqual(rules.extra_inning_rule_status, "confirmed")


if __name__ == "__main__":
    unittest.main()
