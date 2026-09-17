"""Phase 0 data-feasibility audit report generation."""

from __future__ import annotations

from typing import Any

from .domain import GameRules
from .extract import extract_challenge_events
from .ledger import reconstruct_ledger
from .savant import (
    index_statcast_rows,
    missing_pre_pitch_fields,
    selected_pitch_observation,
    selected_pre_pitch_state,
)


def _official_abs_totals(game_data: dict[str, Any]) -> tuple[int, int] | None:
    counters = game_data.get("absChallenges") or {}
    if not counters.get("hasChallenges"):
        return None
    attempts = 0
    overturned = 0
    for side in ("away", "home"):
        side_totals = counters.get(side) or {}
        try:
            successful = int(side_totals["usedSuccessful"])
            failed = int(side_totals["usedFailed"])
        except (KeyError, TypeError, ValueError):
            return None
        if successful < 0 or failed < 0:
            return None
        overturned += successful
        attempts += successful + failed
    return attempts, overturned


def audit_feed(
    feed: dict[str, Any],
    rules: GameRules,
    statcast_rows: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    game_data = feed["gameData"]
    teams = game_data["teams"]
    away_id = int(teams["away"]["id"])
    home_id = int(teams["home"]["id"])
    sport = teams["away"].get("sport") or {}
    league = teams["away"].get("league") or {}
    sport_id = int(sport.get("id", 0))
    competition = (
        "MLB"
        if sport_id == 1
        else "Triple-A"
        if sport_id == 11
        else str(sport.get("name") or "unknown")
    )
    season = int(
        (game_data.get("game") or {}).get("season")
        or str((game_data.get("datetime") or {}).get("officialDate") or "0000")[:4]
    )
    all_plays = feed.get("liveData", {}).get("plays", {}).get("allPlays", [])
    maximum_inning = max(
        (int((play.get("about") or {}).get("inning") or 0) for play in all_plays),
        default=0,
    )
    events = extract_challenge_events(feed)
    ledger, ending_budgets = reconstruct_ledger(events, (away_id, home_id), rules)
    official_totals = _official_abs_totals(game_data)
    observed_overturned = sum(row.event.overturned for row in ledger)
    official_counter_pass = (
        None
        if official_totals is None
        else official_totals == (len(ledger), observed_overturned)
    )

    direction_mismatches = [row for row in ledger if not row.event.challenge_team_matches_call]
    invalid_budgets = [row for row in ledger if not row.valid_budget]
    missing_player = [row for row in ledger if row.event.challenger_player_id is None]
    unknown_role = [
        row for row in ledger if row.event.challenger_role == "unknown"
    ]
    fielder_role_unresolved = [
        row for row in ledger if row.event.challenger_role == "fielder_unknown"
    ]
    challenger_eligibility_failures = [
        row for row in ledger if row.event.challenger_role == "unknown"
    ]
    inferred_team = [
        row for row in ledger if row.event.challenge_team_source != "feed"
    ]
    required_event_fields_complete = all(
        row.event.challenge_team_id
        and row.event.inning
        and row.event.original_call
        and row.event.abs_call
        for row in ledger
    )
    has_challenge_events = bool(ledger)
    core_ledger_pass = (
        has_challenge_events
        and required_event_fields_complete
        and not direction_mismatches
        and not invalid_budgets
    )
    statcast_index = index_statcast_rows(statcast_rows or [])
    joined_rows: list[dict[str, Any]] = []
    statcast_matches = 0
    count_mismatches = 0
    required_state_missing = 0
    for row in ledger:
        output_row = row.to_dict()
        # Savant at_bat_number is one-based; Stats API atBatIndex is zero-based.
        key = (
            row.event.game_pk,
            row.event.at_bat_index + 1,
            row.event.pitch_number,
        )
        statcast_row = statcast_index.get(key)
        if statcast_row is not None:
            statcast_matches += 1
            state = selected_pre_pitch_state(statcast_row)
            output_row["statcast_pre_pitch_state"] = state
            missing_fields = missing_pre_pitch_fields(statcast_row)
            output_row["statcast_missing_required_fields"] = list(missing_fields)
            if missing_fields:
                required_state_missing += 1
            output_row["statcast_pitch_observation"] = selected_pitch_observation(
                statcast_row
            )
            if (
                state["balls"] != row.event.balls_before
                or state["strikes"] != row.event.strikes_before
            ):
                count_mismatches += 1
        else:
            output_row["statcast_pre_pitch_state"] = None
            output_row["statcast_pitch_observation"] = None
            output_row["statcast_missing_required_fields"] = None
        joined_rows.append(output_row)

    statcast_join_pass = (
        has_challenge_events
        and statcast_matches == len(ledger)
        and count_mismatches == 0
        and required_state_missing == 0
    )
    rule_regime_pass = rules.rule_status == "confirmed"
    challenger_eligibility_pass = not challenger_eligibility_failures
    phase0_game_pass = (
        core_ledger_pass
        and statcast_join_pass
        and rule_regime_pass
        and challenger_eligibility_pass
        and official_counter_pass is not False
    )

    if not has_challenge_events:
        status = "fail_no_challenge_events"
    elif not core_ledger_pass:
        status = "fail_ledger"
    elif statcast_matches != len(ledger):
        status = "incomplete_missing_statcast"
    elif count_mismatches:
        status = "fail_statcast_count_mismatch"
    elif required_state_missing:
        status = "fail_statcast_required_state"
    elif not rule_regime_pass:
        status = "incomplete_rule_regime"
    elif not challenger_eligibility_pass:
        status = "fail_challenger_eligibility"
    elif official_counter_pass is False:
        status = "fail_official_counter_mismatch"
    elif phase0_game_pass:
        status = "pass"
    else:
        raise AssertionError("無法判定 Phase 0 單場狀態")

    return {
        "schema_version": "phase0-audit-v2",
        "game": {
            "game_pk": int(feed["gamePk"]),
            "official_date": game_data.get("datetime", {}).get("officialDate"),
            "season": season,
            "competition": competition,
            "sport_id": sport_id,
            "league_id": int(league["id"]) if league.get("id") is not None else None,
            "league_name": league.get("name"),
            "extra_inning_game": maximum_inning >= 10,
            "away_team": {"id": away_id, "name": teams["away"].get("name")},
            "home_team": {"id": home_id, "name": teams["home"].get("name")},
        },
        "rules": {
            "initial_challenges": rules.initial_challenges,
            "refill_if_empty_each_extra_inning": rules.refill_if_empty_each_extra_inning,
            "successful_challenge_retained": rules.successful_challenge_retained,
            "rule_status": rules.rule_status,
            "extra_inning_rule_status": rules.extra_inning_rule_status,
            "abs_format": rules.abs_format,
            "regime_id": rules.regime_id,
            "source": rules.source,
        },
        "summary": {
            "status": status,
            "core_ledger_pass": core_ledger_pass,
            "statcast_join_pass": statcast_join_pass,
            "rule_regime_pass": rule_regime_pass,
            "challenger_eligibility_pass": challenger_eligibility_pass,
            "official_counter_available": official_totals is not None,
            "official_counter_pass": official_counter_pass,
            "official_attempts": official_totals[0] if official_totals else None,
            "official_overturned": official_totals[1] if official_totals else None,
            "phase0_game_pass": phase0_game_pass,
            "challenge_events": len(ledger),
            "overturned": observed_overturned,
            "confirmed": sum(not row.event.overturned for row in ledger),
            "missing_challenger_player": len(missing_player),
            "unknown_challenger_role": len(unknown_role),
            "fielder_role_unresolved": len(fielder_role_unresolved),
            "challenger_eligibility_failures": len(
                challenger_eligibility_failures
            ),
            "exact_role_attribution_complete": not (
                unknown_role or fielder_role_unresolved
            ),
            "inferred_challenge_team": len(inferred_team),
            "challenge_team_direction_mismatches": len(direction_mismatches),
            "invalid_budget_events": len(invalid_budgets),
            "statcast_state_matches": statcast_matches,
            "statcast_state_missing": len(ledger) - statcast_matches,
            "statcast_count_mismatches": count_mismatches,
            "statcast_required_state_missing": required_state_missing,
            "ending_budgets": {str(key): value for key, value in ending_budgets.items()},
        },
        "limitations": [
            "Stats API event count 是 ABS 判決後狀態；判決前 count 由事件反推。",
            "完整判決前狀態（比分、出局數、跑者）必須由 Statcast join 或獨立狀態引擎取得。",
            *(
                ["一個以上的事件缺少挑戰球員身分。"]
                if missing_player
                else []
            ),
            *(
                ["一個以上的守方挑戰無法區分 pitcher 與 catcher；不影響 team-level Gate。"]
                if fielder_role_unresolved
                else []
            ),
            *(
                ["一個以上的事件無法確認挑戰者是否具備規則資格。"]
                if challenger_eligibility_failures
                else []
            ),
            *(
                ["缺少 pitch-level reviewDetails 的 terminal event，其挑戰球隊由判決方向推定。"]
                if inferred_team
                else []
            ),
        ],
        "ledger": joined_rows,
    }
