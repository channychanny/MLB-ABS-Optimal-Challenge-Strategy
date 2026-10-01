"""取得鎖定官方 WP 工程 cohort 的 feed 與逐球來源，並重建逐場診斷。"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import tempfile

from abs_challenge.audit import audit_feed
from abs_challenge.baseline import SavantBaseline
from abs_challenge.opportunity_coverage import candidate_missing_diagnostics, grouped_candidate_support, inspect_population
from abs_challenge.provenance import build_download_manifest, build_file_manifest
from abs_challenge.rules import DEFAULT_RULE_CONFIG, resolve_game_rules
from abs_challenge.savant import (
    build_abs_csv_url,
    build_called_pitches_csv_url,
    parse_csv_text,
)
from abs_challenge.source_cache import atomic_json_new
from abs_challenge.source_eligibility import inspect_source_signals, summarize_source_audits
from abs_challenge.wp_coverage import inspect_call, summarize


ROOT = Path(__file__).resolve().parents[1]
SELECTION_PATH = ROOT / "data" / "processed" / "wp_expansion_selection_2026-09-23.json"
LOCKED_GAMES_PATH = ROOT / "config" / "official_wp_expansion_games.json"
PLAN_PATH = ROOT / "config" / "official_wp_expansion.json"
BASELINE_PATH = ROOT / "data" / "processed" / "savant_baseline_v2_2026-09-15.json"
RAW_DIR = ROOT / "data" / "raw" / "wp_expansion"
OUTPUT_PATH = ROOT / "data" / "processed" / "wp_expansion_acquisition_2026-09-23-v6.json"


def _publish_new(path: Path, content: bytes) -> None:
    """Atomic create-only publication; never replace an existing artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".pending-", suffix=".tmp", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _save_source(path: Path, text: str, *, kind: str, url: str, row_count: int) -> dict:
    manifest_path = Path(f"{path}.manifest.json")
    encoded = text.encode("utf-8")
    if path.exists() or manifest_path.exists():
        if not path.exists() or not manifest_path.exists():
            raise FileExistsError(f"來源與 manifest 不完整，保留既有檔案：{path}")
        actual = path.read_bytes()
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = build_download_manifest(
            source_type=kind, source_url=url, content=text, row_count=row_count,
            retrieved_at_utc=saved.get("retrieved_at_utc"),
        )
        if actual != encoded or saved != expected:
            raise ValueError(f"既有來源與本次固定快照不符，拒絕覆寫：{path}")
        return saved
    manifest = build_download_manifest(source_type=kind, source_url=url, content=text, row_count=row_count)
    _publish_new(path, encoded)
    try:
        atomic_json_new(manifest_path, manifest)
    except Exception:
        # Keep the source if manifest publication fails; next run reports the partial pair.
        raise
    return manifest


def _feed_count(text: str) -> int:
    feed = json.loads(text)
    if not isinstance(feed, dict) or not isinstance(feed.get("gamePk"), int):
        raise ValueError("官方 feed JSON 格式不符")
    return 1


def _pitch_count(text: str) -> int:
    rows = parse_csv_text(text)
    if not rows:
        raise ValueError("Savant 完整逐球 CSV 沒有資料列")
    required = {"game_pk", "at_bat_number", "pitch_number", "inning", "inning_topbot",
                "outs_when_up", "balls", "strikes", "home_score", "away_score",
                "on_1b", "on_2b", "on_3b"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"Savant 完整逐球 CSV 缺欄：{sorted(missing)}")
    return len(rows)


def _challenge_count(text: str) -> int:
    rows = parse_csv_text(text)
    header_line = text.lstrip("\ufeff").splitlines()[0] if text.strip() else ""
    header = next(csv.reader(io.StringIO(header_line)), [])
    if "game_pk" not in header:
        raise ValueError("Savant ABS-only CSV 缺少 game_pk 標頭")
    if rows and not {"at_bat_number", "pitch_number", "description"}.issubset(rows[0]):
        raise ValueError("Savant ABS-only CSV 欄位不完整")
    return len(rows)


def _get_feed(game_pk: int, *, offline: bool) -> tuple[dict, str, dict]:
    from abs_challenge.source_cache import SourceCache
    from abs_challenge.mlb_api import BASE_URL

    url = f"{BASE_URL}/api/v1.1/game/{game_pk}/feed/live"
    cache = SourceCache(RAW_DIR / "source_cache", offline=offline)
    source = cache.get(url, "mlb_stats_api_feed_json", _feed_count)
    return json.loads(source["text"]), source["text"], source["manifest"]


def _get_pitch_csv(day: str, level: str, *, offline: bool) -> tuple[str, list[dict[str, str]], dict]:
    from abs_challenge.source_cache import SourceCache

    url = build_called_pitches_csv_url(day, level)
    cache = SourceCache(RAW_DIR / "source_cache", offline=offline)
    source = cache.get(url, "baseball_savant_pitch_csv", _pitch_count)
    return source["text"], parse_csv_text(source["text"]), source["manifest"]


def _get_abs_csv(day: str, level: str, *, offline: bool) -> tuple[str, list[dict[str, str]], dict]:
    from abs_challenge.source_cache import SourceCache

    url = build_abs_csv_url(day, level)
    cache = SourceCache(RAW_DIR / "source_cache", offline=offline)
    source = cache.get(url, "baseball_savant_abs_csv", _challenge_count)
    return source["text"], parse_csv_text(source["text"]), source["manifest"]


def run(*, offline: bool = False, output_path: Path = OUTPUT_PATH) -> dict:
    if output_path.exists():
        raise FileExistsError(f"拒絕覆寫既有執行報告：{output_path}")
    selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    locked = json.loads(LOCKED_GAMES_PATH.read_text(encoding="utf-8"))
    if not selection.get("selection_complete") or selection["selection_sha256"] != locked["selection_sha256"]:
        raise ValueError("選樣 lock 不符或抽樣未完整，停止下載")
    games = locked["games"]
    selected_ids = {game["game_pk"] for stratum in selection["strata"] for game in stratum["selected"]}
    if selected_ids != {row["game_pk"] for row in games}:
        raise ValueError("選樣輸出與已鎖定 game_pk 清冊不符")
    baseline = SavantBaseline(json.loads(BASELINE_PATH.read_text(encoding="utf-8")))
    pitch_sources = {}
    challenge_sources = {}
    levels_by_date = {}
    for row in games:
        previous = levels_by_date.setdefault(row["date"], row["level"])
        if previous != row["level"]:
            raise ValueError("同日出現不同聯盟層級，不能合併逐球來源")
    sources: dict[str, dict] = {}
    for day, level in sorted(levels_by_date.items()):
        text, rows, manifest = _get_pitch_csv(day, level, offline=offline)
        path = RAW_DIR / f"savant_{level}_{day}_pitches.csv"
        _save_source(path, text, kind="baseball_savant_pitch_csv",
                     url=build_called_pitches_csv_url(day, level), row_count=len(rows))
        sources[f"{level}:{day}"] = manifest
        pitch_sources[f"{level}:{day}"] = (rows, path)
        abs_text, abs_rows, abs_manifest = _get_abs_csv(day, level, offline=offline)
        abs_path = RAW_DIR / f"savant_{level}_{day}_abs.csv"
        _save_source(abs_path, abs_text, kind="baseball_savant_abs_csv",
                     url=build_abs_csv_url(day, level), row_count=len(abs_rows))
        sources[f"{level}:{day}:abs"] = abs_manifest
        challenge_sources[f"{level}:{day}"] = (abs_rows, abs_path)

    game_results, all_candidates = [], []
    for item in games:
        game = {**item, "acquisition_status": "source_failure"}
        try:
            feed, feed_text, feed_manifest = _get_feed(item["game_pk"], offline=offline)
            feed_path = RAW_DIR / f"game_{item['game_pk']}.json"
            _save_source(feed_path, feed_text, kind="mlb_stats_api_feed_json",
                         url=feed_manifest["source_url"], row_count=1)
            if (feed["gamePk"] != item["game_pk"]
                    or feed["gameData"]["datetime"]["officialDate"] != item["date"]):
                raise ValueError("feed game_pk／官方日期與鎖定清冊不符")
            level_key = f"{item['level']}:{item['date']}"
            day_rows, pitch_path = pitch_sources[level_key]
            game_rows = [row for row in day_rows if int(row["game_pk"]) == item["game_pk"]]
            if not game_rows:
                raise ValueError("完整逐球來源沒有此 game_pk 的資料列")
            abs_rows, abs_path = challenge_sources[level_key]
            game_abs_rows = [row for row in abs_rows if int(row["game_pk"]) == item["game_pk"]]
            rules = resolve_game_rules(feed)
            audit = audit_feed(feed, rules, game_abs_rows)
            game["eligibility_source_audit"] = inspect_source_signals(feed)
            game.update(regime=rules.regime_id, rule_status=rules.rule_status,
                        rule_source=rules.source, initial_challenges=rules.initial_challenges,
                        scheduled_innings=feed["liveData"]["linescore"].get("scheduledInnings"),
                        final=feed["gameData"]["status"].get("abstractGameState") == "Final",
                        statcast_pitch_rows=len(game_rows), attempt_count=len(audit["ledger"]),
                        audit_status=audit["summary"]["status"],
                        official_counter_pass=audit["summary"].get("official_counter_pass"),
                        statcast_join_pass=audit["summary"].get("statcast_join_pass"),
                        phase0_game_pass=audit["summary"].get("phase0_game_pass"),
                        audit_summary=audit["summary"],
                        feed_sha256=feed_manifest["content_sha256"],
                        abs_csv_rows=len(game_abs_rows),
                        abs_csv_sha256=build_file_manifest(abs_path, source_type="baseball_savant_abs_csv")["content_sha256"],
                        pitch_csv_sha256=build_file_manifest(pitch_path, source_type="baseball_savant_pitch_csv")["content_sha256"])
            if not game["final"] or game["scheduled_innings"] != 9 or rules.rule_status != "confirmed":
                game["acquisition_status"] = "acquired_but_ineligible_for_primary_checks"
                game["skip_reason"] = "feed/status/format-regime gate failed"
            elif rules.initial_challenges == 2:
                game["acquisition_status"] = "acquired"
                if audit["summary"].get("official_counter_pass") is False:
                    game["opportunity_status"] = "blocked_official_counter_mismatch"
                else:
                    try:
                        population = inspect_population(baseline, feed, audit, day_rows, inspect_call)
                        candidates = population.pop("rows")
                        game["opportunity_status"] = "provisional_source_limitations"
                        game["physical_regulation_pitches"] = population["physical_regulation_pitches"]
                        game["alignment"] = population["alignment"]
                        game["candidate_count"] = population["candidate_count"]
                        game["population_counts"] = population["population_counts"]
                        game["both_supported"] = sum(row["status"] == "both_supported" for row in candidates)
                        game["one_supported"] = sum(row["status"] == "one_supported" for row in candidates)
                        game["neither_supported"] = sum(row["status"] == "neither_supported" for row in candidates)
                        game["unsupported_compound_event"] = sum(row["status"] == "unsupported_compound_event" for row in candidates)
                        all_candidates.extend(candidates)
                    except (KeyError, TypeError, ValueError, IndexError) as error:
                        game["opportunity_status"] = "population_alignment_failure"
                        game["opportunity_reason"] = f"{type(error).__name__}: {error}"
            else:
                game["acquisition_status"] = "acquired_engineering_only"
                game["opportunity_status"] = "not_evaluated_three_challenge_regime"
        except Exception as error:  # preserve every selected game and its failure reason
            game["reason"] = f"{type(error).__name__}: {error}"
        game_results.append(game)

    processed_primary = [g for g in game_results if g.get("opportunity_status") == "provisional_source_limitations"]
    populations = sorted({row["population"] for row in all_candidates})
    candidate_population_support = {
        population: {
            "candidate_count": sum(row["population"] == population for row in all_candidates),
            **{status: sum(row["population"] == population and row.get("status") == status
                           for row in all_candidates)
               for status in ("both_supported", "one_supported", "neither_supported",
                              "unsupported_compound_event", "invalid_state", "excluded_extra_inning")},
        }
        for population in populations
    }
    report = {
        "schema_version": "wp-expansion-acquisition-report-v1",
        "selection_sha256": locked["selection_sha256"],
        "purpose": locked["purpose"],
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "locked_games_manifest": build_file_manifest(LOCKED_GAMES_PATH, source_type="locked_game_manifest"),
        "baseline_manifest": build_file_manifest(BASELINE_PATH, source_type="official_baseline_snapshot"),
        "rule_config_manifest": build_file_manifest(DEFAULT_RULE_CONFIG, source_type="rule_regime_config"),
        "sources": sources,
        "selected_game_count": len(games),
        "game_status_counts": {status: sum(g.get("acquisition_status") == status for g in game_results)
                                for status in sorted({g.get("acquisition_status") for g in game_results})},
        "primary_two_challenge_games": sum(g.get("initial_challenges") == 2 for g in game_results),
        "primary_opportunity_games_processed": len(processed_primary),
        "primary_opportunity_game_denominator_complete": len(processed_primary) == sum(g.get("initial_challenges") == 2 for g in game_results),
        "primary_candidate_count": len(all_candidates),
        "candidate_population_support": candidate_population_support,
        "candidate_grouped_support": grouped_candidate_support(all_candidates),
        "candidate_missing_diagnostics": candidate_missing_diagnostics(all_candidates),
        "eligibility_source_audit_summary": summarize_source_audits(game_results),
        "candidate_source_status_counts": {
            "abs_technical_availability_unknown": sum(row["abs_technical_availability"] == "unknown"
                                                      for row in all_candidates),
            "post_replay_challenge_eligibility_unknown": sum(
                row["post_replay_challenge_eligibility"] == "unknown" for row in all_candidates),
        },
        "candidate_wp_support": {status: sum(row.get("status") == status for row in all_candidates)
                                 for status in ("both_supported", "one_supported", "neither_supported", "unsupported_compound_event", "invalid_state", "excluded_extra_inning")},
        "all_candidate_wp_support_fraction_including_zero_budget": (
            sum(row.get("status") == "both_supported" for row in all_candidates) / len(all_candidates)
            if all_candidates else None),
        "provisional_opportunity_both_supported_fraction": (
            candidate_population_support.get("provisional_opportunity", {}).get("both_supported", 0)
            / candidate_population_support["provisional_opportunity"]["candidate_count"]
            if candidate_population_support.get("provisional_opportunity", {}).get("candidate_count", 0) else None),
        "challenge_attempt_count_in_primary_games": sum(int(g.get("attempt_count") or 0)
                                                        for g in game_results if g.get("initial_challenges") == 2),
        "phase0_game_pass_count": sum(g.get("phase0_game_pass") is True for g in game_results),
        "legal_opportunity_status": "provisional_source_limitations",
        "formal_policy_evaluation_ready": False,
        "games": game_results,
    }
    report["offline_replay"] = offline
    atomic_json_new(output_path, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="只使用固定的本機公開來源快取")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    result = run(offline=args.offline, output_path=args.output)
    print(json.dumps({key: result[key] for key in (
        "selected_game_count", "game_status_counts", "primary_two_challenge_games",
        "primary_opportunity_games_processed", "primary_candidate_count", "candidate_wp_support",
        "all_candidate_wp_support_fraction_including_zero_budget",
        "provisional_opportunity_both_supported_fraction", "formal_policy_evaluation_ready")}, ensure_ascii=False, indent=2))
