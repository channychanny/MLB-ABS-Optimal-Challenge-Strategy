"""從完整逐球資料建立 Legal／Reasonable Challenge Opportunity。"""

from __future__ import annotations

from math import hypot
from typing import Any

from .domain import ChallengeOpportunity, GameRules
from .extract import BALL, STRIKE, extract_challenge_events
from .savant import selected_pitch_observation, selected_pre_pitch_state


CALLED_BALL_DESCRIPTIONS = {"ball", "blocked_ball"}
CALLED_STRIKE_DESCRIPTIONS = {"called_strike"}
ZONE_EDGE_THRESHOLD_FEET = 3 / 12
RUN_VALUE_THRESHOLD = 0.3
EXPECTED_CHALLENGE_RATE_THRESHOLD = 0.2
HALF_PLATE_WIDTH_FEET = 17 / 24
PRIMARY_MAX_INNING = 9


def _position_player_pitching(feed: dict[str, Any], at_bat_number: int) -> bool:
    """依官方名冊位置判斷該打席是否由野手登板；資料不足時不臆測。"""

    plays = feed.get("liveData", {}).get("plays", {}).get("allPlays", [])
    play = next(
        (
            candidate
            for candidate in plays
            if int((candidate.get("about") or {}).get("atBatIndex", -1)) + 1
            == at_bat_number
        ),
        None,
    )
    pitcher_id = ((play or {}).get("matchup") or {}).get("pitcher", {}).get("id")
    if pitcher_id is None:
        return False

    players = feed.get("gameData", {}).get("players", {})
    player = players.get(f"ID{pitcher_id}")
    if player is None:
        player = next(
            (
                candidate
                for candidate in players.values()
                if candidate.get("id") == pitcher_id
            ),
            None,
        )
    position = (player or {}).get("primaryPosition") or {}
    position_type = str(position.get("type") or "").lower()
    abbreviation = str(position.get("abbreviation") or "").upper()
    if not position_type and not abbreviation:
        return False
    return position_type not in {"pitcher", "two-way player"} and abbreviation not in {
        "P",
        "TWP",
    }


def _unchallenged_call(row: dict[str, str]) -> str | None:
    description = str(row.get("description") or "").lower()
    if description in CALLED_STRIKE_DESCRIPTIONS:
        return STRIKE
    if description in CALLED_BALL_DESCRIPTIONS:
        return BALL
    return None


def _float_or_none(value: str | None) -> float | None:
    return float(value) if value not in {None, ""} else None


def _distance_to_zone_edge(
    plate_x: float,
    plate_z: float,
    zone_bottom: float,
    zone_top: float,
) -> float:
    horizontal_outside = max(abs(plate_x) - HALF_PLATE_WIDTH_FEET, 0.0)
    vertical_outside = max(zone_bottom - plate_z, 0.0, plate_z - zone_top)
    if horizontal_outside or vertical_outside:
        return hypot(horizontal_outside, vertical_outside)
    return min(
        HALF_PLATE_WIDTH_FEET - abs(plate_x),
        plate_z - zone_bottom,
        zone_top - plate_z,
    )


def _reasonable_candidate(
    row: dict[str, str],
    *,
    challenged: bool,
    overturned: bool | None,
) -> tuple[bool | None, tuple[str, ...]]:
    reasons: list[str] = []
    evaluated = challenged
    if challenged and overturned:
        reasons.append("known_incorrect_original_call")

    expected_rate = _float_or_none(row.get("estimated_challenge_rate"))
    if expected_rate is not None:
        evaluated = True
        if expected_rate >= EXPECTED_CHALLENGE_RATE_THRESHOLD:
            reasons.append("high_expected_challenge_rate")

    location = tuple(
        _float_or_none(row.get(field))
        for field in ("plate_x", "plate_z", "sz_bot", "sz_top")
    )
    run_value = _float_or_none(row.get("delta_run_exp"))
    if all(value is not None for value in location) and run_value is not None:
        evaluated = True
        plate_x, plate_z, zone_bottom, zone_top = location
        assert plate_x is not None
        assert plate_z is not None
        assert zone_bottom is not None
        assert zone_top is not None
        if (
            _distance_to_zone_edge(plate_x, plate_z, zone_bottom, zone_top)
            <= ZONE_EDGE_THRESHOLD_FEET
            and abs(run_value) >= RUN_VALUE_THRESHOLD
        ):
            reasons.append("near_zone_edge_and_high_run_value")

    if reasons:
        return True, tuple(reasons)
    return (False, ()) if evaluated else (None, ())


def build_challenge_opportunities(
    feed: dict[str, Any],
    statcast_rows: list[dict[str, str]],
    rules: GameRules,
    *,
    maximum_inning: int | None = PRIMARY_MAX_INNING,
) -> list[ChallengeOpportunity]:
    """建立單場比賽中所有具有剩餘額度的 adverse called pitches。"""

    game_pk = int(feed["gamePk"])
    teams = feed["gameData"]["teams"]
    away_id = int(teams["away"]["id"])
    home_id = int(teams["home"]["id"])
    budgets = {away_id: rules.initial_challenges, home_id: rules.initial_challenges}
    events = {
        (event.game_pk, event.at_bat_index + 1, event.pitch_number): event
        for event in extract_challenge_events(feed)
    }
    game_rows = [row for row in statcast_rows if int(row.get("game_pk", -1)) == game_pk]
    game_rows.sort(
        key=lambda row: (
            int(row.get("inning") or 0),
            int(row["at_bat_number"]),
            int(row["pitch_number"]),
        )
    )

    opportunities: list[ChallengeOpportunity] = []
    last_refill_inning = 9
    for row in game_rows:
        key = (game_pk, int(row["at_bat_number"]), int(row["pitch_number"]))
        event = events.get(key)
        inning = int(row.get("inning") or (event.inning if event else 0))
        if maximum_inning is not None and inning > maximum_inning:
            continue
        if rules.refill_if_empty_each_extra_inning and inning >= 10:
            for extra_inning in range(last_refill_inning + 1, inning + 1):
                if extra_inning >= 10:
                    for team_id in budgets:
                        if budgets[team_id] == 0:
                            budgets[team_id] = 1
            last_refill_inning = max(last_refill_inning, inning)

        original_call = event.original_call if event else _unchallenged_call(row)
        if original_call is None:
            continue
        half = str(
            row.get("inning_topbot") or (event.half_inning if event else "")
        ).lower()
        if half == "top":
            batting_team_id, fielding_team_id = away_id, home_id
        elif half == "bottom":
            batting_team_id, fielding_team_id = home_id, away_id
        else:
            raise ValueError(f"unsupported inning half: {half!r}")
        decision_team_id = (
            batting_team_id if original_call == STRIKE else fielding_team_id
        )
        challenges_remaining = budgets[decision_team_id]
        legal_pitcher = not _position_player_pitching(feed, key[1])
        if challenges_remaining > 0 and legal_pitcher:
            reasonable_candidate, reasonable_reasons = _reasonable_candidate(
                row,
                challenged=event is not None,
                overturned=event.overturned if event else None,
            )
            opportunities.append(
                ChallengeOpportunity(
                    game_pk=game_pk,
                    at_bat_number=key[1],
                    pitch_number=key[2],
                    inning=inning,
                    half_inning=half,
                    decision_team_id=decision_team_id,
                    original_call=original_call,
                    challenges_remaining=challenges_remaining,
                    actual_challenge=event is not None,
                    overturned=event.overturned if event else None,
                    reasonable_candidate=reasonable_candidate,
                    reasonable_reasons=reasonable_reasons,
                    pre_pitch_state=selected_pre_pitch_state(row),
                    pitch_observation=selected_pitch_observation(row),
                )
            )

        if event is not None and (
            not event.overturned or not rules.successful_challenge_retained
        ):
            budgets[event.challenge_team_id] = max(
                0, budgets[event.challenge_team_id] - 1
            )

    return opportunities
