from __future__ import annotations

import unittest
from dataclasses import replace

from abs_challenge.domain import GameRules
from abs_challenge.extract import extract_challenge_events
from abs_challenge.ledger import reconstruct_ledger
from test_extract import feed_with_event


class LedgerTests(unittest.TestCase):
    def _event(self, *, overturned: bool, inning: int = 4):
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=overturned,
            challenge_team_id=10 if not overturned else 20,
            player=None,
        )
        event = extract_challenge_events(feed)[0]
        return replace(event, inning=inning)

    def test_failed_challenge_consumes_budget(self) -> None:
        event = self._event(overturned=False)
        rows, budgets = reconstruct_ledger([event], [10, 20], GameRules(2))
        self.assertEqual(rows[0].challenges_before, 2)
        self.assertEqual(rows[0].challenges_after, 1)
        self.assertEqual(budgets[10], 1)

    def test_successful_challenge_retains_budget(self) -> None:
        event = self._event(overturned=True)
        rows, budgets = reconstruct_ledger([event], [10, 20], GameRules(2))
        self.assertEqual(rows[0].challenges_before, 2)
        self.assertEqual(rows[0].challenges_after, 2)
        self.assertEqual(budgets[20], 2)

    def test_successful_challenge_consumes_budget_when_rule_disables_retention(self) -> None:
        event = self._event(overturned=True)
        rules = GameRules(2, successful_challenge_retained=False)

        rows, budgets = reconstruct_ledger([event], [10, 20], rules)

        self.assertEqual(rows[0].challenges_before, 2)
        self.assertEqual(rows[0].challenges_after, 1)
        self.assertEqual(budgets[20], 1)

    def test_empty_budget_refills_at_extra_inning_start(self) -> None:
        failed_one = self._event(overturned=False)
        failed_two = replace(failed_one, at_bat_index=4)
        extra_failed = replace(failed_one, inning=10, at_bat_index=70)
        rows, budgets = reconstruct_ledger(
            [failed_one, failed_two, extra_failed],
            [10, 20],
            GameRules(2, refill_if_empty_each_extra_inning=True),
        )
        self.assertEqual([row.challenges_before for row in rows], [2, 1, 1])
        self.assertEqual(budgets[10], 0)

    def test_attempt_without_remaining_budget_is_invalid(self) -> None:
        failed_one = self._event(overturned=False)
        failed_two = replace(failed_one, at_bat_index=4)

        rows, budgets = reconstruct_ledger(
            [failed_one, failed_two], [10, 20], GameRules(1)
        )

        self.assertTrue(rows[0].valid_budget)
        self.assertFalse(rows[1].valid_budget)
        self.assertEqual(rows[1].challenges_before, 0)
        self.assertEqual(budgets[10], 0)


if __name__ == "__main__":
    unittest.main()
