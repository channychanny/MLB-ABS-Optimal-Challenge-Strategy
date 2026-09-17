"""Reconstruct challenge budgets from normalized ABS challenge events."""

from __future__ import annotations

from collections.abc import Iterable

from .domain import ChallengeEvent, GameRules, LedgerEntry


def reconstruct_ledger(
    events: Iterable[ChallengeEvent],
    team_ids: Iterable[int],
    rules: GameRules,
) -> tuple[list[LedgerEntry], dict[int, int]]:
    ordered = sorted(events, key=lambda row: (row.inning, row.at_bat_index, row.play_event_index))
    budgets = {int(team_id): rules.initial_challenges for team_id in team_ids}
    rows: list[LedgerEntry] = []
    last_refill_inning = 9

    for event in ordered:
        if event.challenge_team_id not in budgets:
            budgets[event.challenge_team_id] = rules.initial_challenges

        if rules.refill_if_empty_each_extra_inning and event.inning >= 10:
            for inning in range(last_refill_inning + 1, event.inning + 1):
                if inning >= 10:
                    for team_id in budgets:
                        if budgets[team_id] == 0:
                            budgets[team_id] = 1
            last_refill_inning = max(last_refill_inning, event.inning)

        before = budgets[event.challenge_team_id]
        valid = before > 0
        retains_challenge = event.overturned and rules.successful_challenge_retained
        after = before if retains_challenge else max(0, before - 1)
        budgets[event.challenge_team_id] = after
        rows.append(
            LedgerEntry(
                event=event,
                challenges_before=before,
                challenges_after=after,
                valid_budget=valid,
            )
        )

    return rows, budgets
