"""Extract normalized ABS challenge events from MLB Stats API live feeds."""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any

from .domain import ChallengeEvent


BALL = "ball"
STRIKE = "strike"
RESULT_CHALLENGE_PATTERN = re.compile(
    r"challenged \(pitch result\), call on the field was "
    r"(?P<outcome>upheld|confirmed|overturned):",
    re.IGNORECASE,
)


def opposite_call(call: str) -> str:
    if call == BALL:
        return STRIKE
    if call == STRIKE:
        return BALL
    raise ValueError(f"unsupported called-pitch result: {call!r}")


def canonical_call(event: dict[str, Any]) -> str | None:
    """Return the feed's final ABS call for a reviewed called pitch."""

    details = event.get("details") or {}
    call = details.get("call") or {}
    code = call.get("code") or details.get("code")
    description = str(call.get("description") or details.get("description") or "")
    if code == "B" or description in {"Ball", "Ball In Dirt"}:
        return BALL
    if code == "C" or description == "Called Strike":
        return STRIKE
    return None


def _post_count_from_pre(call: str, balls: int, strikes: int) -> tuple[int, int]:
    if call == BALL:
        return balls + 1, strikes
    if call == STRIKE:
        return balls, strikes + 1
    raise ValueError(f"unsupported call: {call!r}")


def _pre_count(final_call: str, event: dict[str, Any]) -> tuple[int, int]:
    count = event.get("count") or {}
    balls_after = int(count.get("balls", 0))
    strikes_after = int(count.get("strikes", 0))
    if final_call == BALL:
        if balls_after < 1:
            raise ValueError("reviewed ball has an impossible post-call ball count")
        return balls_after - 1, strikes_after
    if strikes_after < 1:
        raise ValueError("reviewed strike has an impossible post-call strike count")
    return balls_after, strikes_after - 1


def _team_context(feed: dict[str, Any], half_inning: str) -> tuple[int, int]:
    teams = feed["gameData"]["teams"]
    away_id = int(teams["away"]["id"])
    home_id = int(teams["home"]["id"])
    if half_inning.lower() == "top":
        return away_id, home_id
    if half_inning.lower() == "bottom":
        return home_id, away_id
    raise ValueError(f"unsupported half inning: {half_inning!r}")


def _challenger_role(
    original_call: str,
    player_id: int | None,
    batter_id: int | None,
    pitcher_id: int | None,
) -> str:
    if original_call == STRIKE:
        if player_id is None:
            return "batter_inferred"
        return "batter" if player_id == batter_id else "unknown"

    if player_id is None:
        return "fielder_unknown"
    if player_id == pitcher_id:
        return "pitcher"
    return "catcher"


def _pitch_events(play_events: Iterable[dict[str, Any]]) -> Iterable[tuple[int, dict[str, Any]]]:
    pitch_number = 0
    for event in play_events:
        if event.get("type") == "pitch":
            pitch_number += 1
            yield pitch_number, event


def _build_challenge_event(
    feed: dict[str, Any],
    play: dict[str, Any],
    pitch_number: int,
    event: dict[str, Any],
    review: dict[str, Any],
    *,
    review_source: str,
    challenge_team_source: str,
) -> ChallengeEvent:
    game_pk = int(feed["gamePk"])
    game_date = (feed.get("gameData") or {}).get("datetime", {}).get("officialDate")
    about = play.get("about") or {}
    matchup = play.get("matchup") or {}
    batter = matchup.get("batter") or {}
    pitcher = matchup.get("pitcher") or {}
    half = str(about.get("halfInning") or "").lower()
    batting_team_id, fielding_team_id = _team_context(feed, half)
    final_call = canonical_call(event)
    if final_call is None:
        raise ValueError("review event is not a called ball or called strike")

    overturned = bool(review.get("isOverturned"))
    original_call = opposite_call(final_call) if overturned else final_call
    expected_team_id = batting_team_id if original_call == STRIKE else fielding_team_id
    challenge_team_id = int(review.get("challengeTeamId", expected_team_id))
    player = review.get("player") or {}
    player_id = player.get("id")
    batter_id = batter.get("id")
    pitcher_id = pitcher.get("id")
    balls_before, strikes_before = _pre_count(final_call, event)
    balls_after_original, strikes_after_original = _post_count_from_pre(
        original_call, balls_before, strikes_before
    )
    balls_after_abs, strikes_after_abs = _post_count_from_pre(
        final_call, balls_before, strikes_before
    )
    count = event.get("count") or {}
    pitch_data = event.get("pitchData") or {}
    coordinates = pitch_data.get("coordinates") or {}

    return ChallengeEvent(
        game_pk=game_pk,
        game_date=game_date,
        at_bat_index=int(about.get("atBatIndex", -1)),
        pitch_number=pitch_number,
        play_event_index=int(event.get("index", -1)),
        inning=int(about["inning"]),
        half_inning=half,
        batter_id=int(batter_id) if batter_id is not None else None,
        batter_name=batter.get("fullName"),
        pitcher_id=int(pitcher_id) if pitcher_id is not None else None,
        pitcher_name=pitcher.get("fullName"),
        challenge_team_id=challenge_team_id,
        challenge_team_source=challenge_team_source,
        expected_challenge_team_id=expected_team_id,
        challenge_team_matches_call=challenge_team_id == expected_team_id,
        review_source=review_source,
        challenger_player_id=int(player_id) if player_id is not None else None,
        challenger_player_name=player.get("fullName"),
        challenger_role=_challenger_role(
            original_call,
            int(player_id) if player_id is not None else None,
            int(batter_id) if batter_id is not None else None,
            int(pitcher_id) if pitcher_id is not None else None,
        ),
        original_call=original_call,
        abs_call=final_call,
        overturned=overturned,
        balls_before=balls_before,
        strikes_before=strikes_before,
        balls_after_original=balls_after_original,
        strikes_after_original=strikes_after_original,
        balls_after_abs=balls_after_abs,
        strikes_after_abs=strikes_after_abs,
        outs_after_feed=(int(count["outs"]) if count.get("outs") is not None else None),
        plate_x=coordinates.get("pX"),
        plate_z=coordinates.get("pZ"),
        strike_zone_top=pitch_data.get("strikeZoneTop"),
        strike_zone_bottom=pitch_data.get("strikeZoneBottom"),
    )


def extract_challenge_events(feed: dict[str, Any]) -> list[ChallengeEvent]:
    """Extract reviewed called pitches and normalize original/ABS calls.

    The live feed mutates an overturned pitch's stored call to the corrected ABS
    result. Consequently, an overturned event's original umpire call is the
    opposite of the stored call.
    """

    all_plays = feed.get("liveData", {}).get("plays", {}).get("allPlays", [])
    events: list[ChallengeEvent] = []

    for play in all_plays:
        about = play.get("about") or {}
        half = str(about.get("halfInning") or "").lower()
        if half not in {"top", "bottom"}:
            continue
        pitch_events = list(_pitch_events(play.get("playEvents") or []))
        reviewed_event_indexes: set[int] = set()

        for pitch_number, event in pitch_events:
            review = event.get("reviewDetails")
            if not review:
                continue
            final_call = canonical_call(event)
            if final_call is None:
                continue
            reviewed_event_indexes.add(int(event.get("index", -1)))
            events.append(
                _build_challenge_event(
                    feed,
                    play,
                    pitch_number,
                    event,
                    review,
                    review_source="pitch_review_details",
                    challenge_team_source="feed",
                )
            )

        # Terminal called pitches are sometimes recorded only in the plate-
        # appearance result text, with no pitch-level reviewDetails object.
        # Recover those events so the team ledger is not silently incomplete.
        result_description = str((play.get("result") or {}).get("description") or "")
        match = RESULT_CHALLENGE_PATTERN.search(result_description)
        if match:
            terminal = next(
                (
                    (pitch_number, event)
                    for pitch_number, event in reversed(pitch_events)
                    if canonical_call(event) is not None
                ),
                None,
            )
            if (
                terminal is not None
                and int(terminal[1].get("index", -1)) not in reviewed_event_indexes
            ):
                pitch_number, event = terminal
                events.append(
                    _build_challenge_event(
                        feed,
                        play,
                        pitch_number,
                        event,
                        {"isOverturned": match.group("outcome").lower() == "overturned"},
                        review_source="play_result_description",
                        challenge_team_source="inferred_from_call_and_half",
                    )
                )

    return sorted(events, key=lambda row: (row.at_bat_index, row.play_event_index))
