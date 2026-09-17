"""Domain objects for ABS challenge extraction and ledger reconstruction."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class GameRules:
    """Challenge rules that must be selected for a game or competition."""

    initial_challenges: int
    refill_if_empty_each_extra_inning: bool = True
    successful_challenge_retained: bool = True
    rule_status: str = "manual"
    abs_format: str = "challenge"
    regime_id: str = "manual"
    source: str | None = None
    extra_inning_rule_status: str = "manual"

    def __post_init__(self) -> None:
        if self.initial_challenges < 1:
            raise ValueError("initial_challenges must be positive")


@dataclass(frozen=True)
class ChallengeEvent:
    """A normalized ABS challenge event extracted from a live game feed."""

    game_pk: int
    game_date: str | None
    at_bat_index: int
    pitch_number: int
    play_event_index: int
    inning: int
    half_inning: str
    batter_id: int | None
    batter_name: str | None
    pitcher_id: int | None
    pitcher_name: str | None
    challenge_team_id: int
    challenge_team_source: str
    expected_challenge_team_id: int
    challenge_team_matches_call: bool
    review_source: str
    challenger_player_id: int | None
    challenger_player_name: str | None
    challenger_role: str
    original_call: str
    abs_call: str
    overturned: bool
    balls_before: int
    strikes_before: int
    balls_after_original: int
    strikes_after_original: int
    balls_after_abs: int
    strikes_after_abs: int
    outs_after_feed: int | None
    plate_x: float | None
    plate_z: float | None
    strike_zone_top: float | None
    strike_zone_bottom: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LedgerEntry:
    """Challenge event augmented with team budget before and after the action."""

    event: ChallengeEvent
    challenges_before: int
    challenges_after: int
    valid_budget: bool

    def to_dict(self) -> dict[str, Any]:
        row = self.event.to_dict()
        row.update(
            challenges_before=self.challenges_before,
            challenges_after=self.challenges_after,
            valid_budget=self.valid_budget,
        )
        return row


@dataclass(frozen=True)
class ChallengeOpportunity:
    """一顆在當下可合法提出 Challenge 的 adverse called pitch。"""

    game_pk: int
    at_bat_number: int
    pitch_number: int
    inning: int
    half_inning: str
    decision_team_id: int
    original_call: str
    challenges_remaining: int
    actual_challenge: bool
    overturned: bool | None
    reasonable_candidate: bool | None
    reasonable_reasons: tuple[str, ...]
    pre_pitch_state: dict[str, Any]
    pitch_observation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
