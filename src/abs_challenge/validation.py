"""彙總單場稽核，判定 Phase 0 是否符合跨年度驗收門檻。"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_PHASE0_REQUIREMENTS = (
    Path(__file__).resolve().parents[2] / "config" / "phase0_gate.json"
)


def build_official_game_record_comparison(
    *,
    scope_id: str,
    audits: list[dict[str, Any]],
    feeds: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate extracted events against official per-game ABS counters."""

    audit_by_game = {int(audit["game"]["game_pk"]): audit for audit in audits}
    feed_by_game = {int(feed["gamePk"]): feed for feed in feeds}
    if len(audit_by_game) != len(audits) or len(feed_by_game) != len(feeds):
        raise ValueError("audits and feeds must not contain duplicate game_pk values")
    if not audit_by_game or audit_by_game.keys() != feed_by_game.keys():
        raise ValueError("audits and feeds must contain the same game_pk set")

    official_attempts = 0
    official_overturned = 0
    for game_pk, feed in feed_by_game.items():
        counters = (feed.get("gameData") or {}).get("absChallenges") or {}
        if not counters.get("hasChallenges"):
            raise ValueError(f"official ABS counters unavailable for game {game_pk}")
        for side in ("away", "home"):
            side_totals = counters.get(side) or {}
            try:
                successful = int(side_totals["usedSuccessful"])
                failed = int(side_totals["usedFailed"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"official ABS counters incomplete for game {game_pk}"
                ) from error
            if successful < 0 or failed < 0:
                raise ValueError(f"official ABS counters invalid for game {game_pk}")
            official_overturned += successful
            official_attempts += successful + failed

    return {
        "schema_version": "official-game-record-comparison-input-v1",
        "scope_id": scope_id,
        "source_basis": "MLB Stats API gameData.absChallenges",
        "game_pks": sorted(audit_by_game),
        "observed_attempts": sum(
            int(audit["summary"]["challenge_events"])
            for audit in audit_by_game.values()
        ),
        "observed_overturned": sum(
            int(audit["summary"]["overturned"])
            for audit in audit_by_game.values()
        ),
        "official_attempts": official_attempts,
        "official_overturned": official_overturned,
    }


def compare_official_aggregate(
    *,
    scope_id: str,
    observed_attempts: int,
    observed_overturned: int,
    official_attempts: int,
    official_overturned: int,
    maximum_attempt_relative_error: float,
    maximum_overturn_rate_absolute_error: float,
) -> dict[str, Any]:
    """比較相同資料範圍的擷取結果與官方彙總。"""

    if observed_attempts <= 0 or official_attempts <= 0:
        raise ValueError("observed 與 official attempts 必須為正數")
    if not 0 <= observed_overturned <= observed_attempts:
        raise ValueError("observed overturned 必須介於 0 與 attempts 之間")
    if not 0 <= official_overturned <= official_attempts:
        raise ValueError("official overturned 必須介於 0 與 attempts 之間")
    if (
        maximum_attempt_relative_error < 0
        or maximum_overturn_rate_absolute_error < 0
    ):
        raise ValueError("comparison error thresholds 不得為負數")
    observed_rate = observed_overturned / observed_attempts
    official_rate = official_overturned / official_attempts
    attempt_relative_error = abs(observed_attempts - official_attempts) / official_attempts
    overturn_rate_absolute_error = abs(observed_rate - official_rate)
    comparison_pass = (
        attempt_relative_error <= maximum_attempt_relative_error
        and overturn_rate_absolute_error <= maximum_overturn_rate_absolute_error
    )
    return {
        "schema_version": "official-aggregate-comparison-v1",
        "scope_id": scope_id,
        "pass": comparison_pass,
        "observed_attempts": observed_attempts,
        "observed_overturned": observed_overturned,
        "observed_overturn_rate": observed_rate,
        "official_attempts": official_attempts,
        "official_overturned": official_overturned,
        "official_overturn_rate": official_rate,
        "attempt_relative_error": attempt_relative_error,
        "overturn_rate_absolute_error": overturn_rate_absolute_error,
        "maximum_attempt_relative_error": maximum_attempt_relative_error,
        "maximum_overturn_rate_absolute_error": (
            maximum_overturn_rate_absolute_error
        ),
    }


def evaluate_phase0_gate(
    audits: list[dict[str, Any]],
    requirements: dict[str, Any],
    official_comparisons: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """依版本化 requirements 評估 cohort、單場稽核與外部核對。"""

    game_ids = [int(audit["game"]["game_pk"]) for audit in audits]
    duplicate_game_ids = sorted(
        game_pk for game_pk, count in Counter(game_ids).items() if count > 1
    )
    cohort_counts = Counter(
        (str(audit["game"]["competition"]), int(audit["game"]["season"]))
        for audit in audits
    )
    missing_cohorts: list[dict[str, Any]] = []
    for cohort in requirements.get("required_cohorts", []):
        key = (str(cohort["competition"]), int(cohort["season"]))
        minimum_games = int(cohort["minimum_games"])
        missing_games = max(0, minimum_games - cohort_counts[key])
        if missing_games:
            missing_cohorts.append(
                {
                    "competition": key[0],
                    "season": key[1],
                    "missing_games": missing_games,
                }
            )

    failed_game_pks = [
        int(audit["game"]["game_pk"])
        for audit in audits
        if not audit.get("summary", {}).get("phase0_game_pass", False)
    ]
    extra_inning_games = sum(
        bool(audit["game"].get("extra_inning_game")) for audit in audits
    )
    minimum_extra_inning_games = int(
        requirements.get("minimum_extra_inning_games", 0)
    )
    official_required = bool(
        requirements.get("official_aggregate_comparison_required", False)
    )
    comparisons: list[dict[str, Any]] = []
    for comparison in official_comparisons or []:
        try:
            comparisons.append(
                compare_official_aggregate(
                    scope_id=str(comparison["scope_id"]),
                    observed_attempts=int(comparison["observed_attempts"]),
                    observed_overturned=int(comparison["observed_overturned"]),
                    official_attempts=int(comparison["official_attempts"]),
                    official_overturned=int(comparison["official_overturned"]),
                    maximum_attempt_relative_error=float(
                        requirements.get("maximum_attempt_relative_error", 0.0)
                    ),
                    maximum_overturn_rate_absolute_error=float(
                        requirements.get(
                            "maximum_overturn_rate_absolute_error", 0.0
                        )
                    ),
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            comparisons.append(
                {
                    "scope_id": comparison.get("scope_id"),
                    "pass": False,
                    "error": str(error),
                }
            )
    official_comparison_pass = (
        not official_required
        or bool(comparisons)
        and all(item.get("pass", False) for item in comparisons)
    )
    phase0_gate_pass = not any(
        (
            duplicate_game_ids,
            missing_cohorts,
            failed_game_pks,
            extra_inning_games < minimum_extra_inning_games,
            not official_comparison_pass,
        )
    )

    return {
        "schema_version": "phase0-gate-result-v1",
        "phase0_gate_pass": phase0_gate_pass,
        "audited_games": len(audits),
        "duplicate_game_pks": duplicate_game_ids,
        "missing_cohorts": missing_cohorts,
        "failed_game_pks": failed_game_pks,
        "extra_inning_games": extra_inning_games,
        "minimum_extra_inning_games": minimum_extra_inning_games,
        "official_aggregate_comparison_pass": official_comparison_pass,
        "official_comparisons": comparisons,
    }
