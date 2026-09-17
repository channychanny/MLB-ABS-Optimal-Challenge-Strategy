"""依官方比賽 metadata 解析 ABS Challenge rule regime。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .domain import GameRules


DEFAULT_RULE_CONFIG = Path(__file__).resolve().parents[2] / "config" / "rule_regimes.json"


class RuleResolutionError(ValueError):
    """比賽 metadata 無法唯一對應至完整規則時拋出。"""


def _competition_from_sport_id(sport_id: int) -> str:
    if sport_id == 1:
        return "MLB"
    if sport_id == 11:
        return "Triple-A"
    raise RuleResolutionError(f"unsupported sport id: {sport_id}")


def _has_observed_abs_challenge(feed: dict[str, Any]) -> bool:
    """Return whether the official feed contains an ABS review event."""

    all_plays = feed.get("liveData", {}).get("plays", {}).get("allPlays", [])
    return any(
        (event.get("reviewDetails") or {}).get("reviewType") == "MJ"
        for play in all_plays
        for event in play.get("playEvents", [])
    )


def resolve_game_rules(
    feed: dict[str, Any],
    *,
    config_path: Path = DEFAULT_RULE_CONFIG,
    abs_format: str | None = None,
    initial_challenges_override: int | None = None,
    extra_inning_refill_override: bool | None = None,
) -> GameRules:
    """從 feed metadata 與版本化設定解析單場比賽規則。"""

    game_data = feed.get("gameData") or {}
    teams = game_data.get("teams") or {}
    away = teams.get("away") or {}
    sport = away.get("sport") or {}
    league = away.get("league") or {}
    game = game_data.get("game") or {}
    official_date = str((game_data.get("datetime") or {}).get("officialDate") or "")
    try:
        sport_id = int(sport["id"])
        league_id = int(league["id"])
        season = int(game.get("season") or official_date[:4])
    except (KeyError, TypeError, ValueError) as error:
        raise RuleResolutionError("feed is missing sport or season metadata") from error

    competition = _competition_from_sport_id(sport_id)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    candidates = []
    for row in payload.get("regimes", []):
        if row.get("competition") != competition or int(row.get("season", -1)) != season:
            continue
        if row.get("starts_on") and official_date < row["starts_on"]:
            continue
        if row.get("ends_on") and official_date > row["ends_on"]:
            continue
        if row.get("league_ids") and league_id not in row["league_ids"]:
            continue
        candidates.append(row)
    if len(candidates) != 1:
        raise RuleResolutionError(
            f"expected one rule regime for {competition} {season}, found {len(candidates)}"
        )

    regime = candidates[0]
    format_confirmation_required = bool(regime.get("format_confirmation_required"))
    observed_abs_challenge = _has_observed_abs_challenge(feed)
    if format_confirmation_required and abs_format is None and not observed_abs_challenge:
        raise RuleResolutionError(
            f"rule regime for {competition} {season} requires explicit ABS format"
        )
    resolved_format = abs_format or regime.get("abs_format") or "challenge"
    if resolved_format != "challenge":
        raise RuleResolutionError("Full ABS games do not have Challenge ledgers")

    initial_challenges = (
        initial_challenges_override
        if initial_challenges_override is not None
        else regime.get("initial_challenges")
    )
    refill = (
        extra_inning_refill_override
        if extra_inning_refill_override is not None
        else regime.get("refill_if_empty_each_extra_inning")
    )
    if initial_challenges is None or refill is None:
        raise RuleResolutionError(
            f"rule regime for {competition} {season} is incomplete; provide an explicit override"
        )

    rule_status = str(regime.get("status") or "unknown")
    if format_confirmation_required and observed_abs_challenge:
        rule_status = "confirmed"

    return GameRules(
        initial_challenges=int(initial_challenges),
        refill_if_empty_each_extra_inning=bool(refill),
        successful_challenge_retained=bool(
            regime.get("successful_challenge_retained", True)
        ),
        rule_status=rule_status,
        extra_inning_rule_status=str(
            regime.get("extra_inning_rule_status") or "unknown"
        ),
        abs_format=resolved_format,
        regime_id=str(regime.get("id") or f"{competition.lower()}-{season}"),
        source=regime.get("source"),
    )
