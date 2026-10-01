"""Dataset B 訓練前來源準備；固定選場、保留失敗、不建立模型。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path

from abs_challenge.audit import audit_feed
from abs_challenge.abs_recovery import recover_abs_only_challenges
from abs_challenge.baseline import SavantBaseline
from abs_challenge.opportunity_coverage import inspect_population
from abs_challenge.phase1_cli import _runtime
from abs_challenge.provenance import build_file_manifest
from abs_challenge.rules import DEFAULT_RULE_CONFIG, RuleResolutionError, resolve_game_rules
from abs_challenge.savant import build_abs_csv_url, build_called_pitches_csv_url, fetch_csv_text, parse_csv_text
from abs_challenge.source_cache import SourceCache, atomic_json_new
from abs_challenge.source_eligibility import inspect_source_signals
from abs_challenge.wp_coverage import inspect_call


ROOT = Path(__file__).resolve().parents[1]


def _selected(selection: dict, sampling: dict, split: dict) -> list[dict]:
    if (selection.get("schema_version") != "dataset-b-schedule-selection-v1"
            or not selection.get("selection_complete")
            or selection.get("sampling_plan") != sampling or selection.get("split_plan") != split):
        raise ValueError("Dataset B 選場清冊與預宣告計畫不符或尚未完成")
    lock = {key: selection[key] for key in ("sampling_plan", "split_plan", "windows", "sources")}
    fingerprint = sha256(json.dumps(lock, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if fingerprint != selection["selection_sha256"]:
        raise ValueError("Dataset B 選場清冊指紋不符")
    games = [game for window in selection["windows"] for game in window["selected"]]
    ids = [game["game_pk"] for game in games]
    if (len(ids) != selection["selected_count"] or len(ids) != len(set(ids))
            or set(ids) & set(split["known_development_game_pks"])):
        raise ValueError("Dataset B 選場重複或混入已知開發場")
    for window, selected in zip(split["windows"], selection["windows"]):
        if selected["window"] != window["name"] or len(selected["selected"]) != sampling["quotas"][window["name"]]:
            raise ValueError("Dataset B 選場時間窗或配額不符")
        for row in selected["selected"]:
            if (row["window"] != window["name"] or row["split"] != window["split"]
                    or not window["start"] <= row["date"] <= window["end"]):
                raise ValueError("Dataset B 選場日期或 split 不符")
    return games


def _feed_count(text: str) -> int:
    feed = json.loads(text)
    if type(feed.get("gamePk")) is not int or not feed.get("liveData", {}).get("plays", {}).get("allPlays"):
        raise ValueError("官方 feed 缺少場次或逐球事件")
    return 1


def _pitch_count(text: str) -> int:
    rows = parse_csv_text(text)
    if not rows or not {"game_pk", "at_bat_number", "pitch_number", "inning", "balls", "strikes"}.issubset(rows[0]):
        raise ValueError("Savant 完整逐球 CSV 為空或缺少必要欄位")
    return len(rows)


def _check_feed(row: dict, feed: dict) -> tuple[dict, dict]:
    if feed["gamePk"] != row["game_pk"]:
        raise ValueError("feed game_pk 不符")
    game = feed["gameData"]
    if (game["datetime"]["officialDate"] != row["date"]
            or game["status"]["abstractGameState"] != "Final"
            or game["game"]["type"] != "R"
            or feed["liveData"]["linescore"]["scheduledInnings"] != 9):
        raise ValueError("feed 日期、終場、例行賽或原訂九局條件不符")
    for side in ("away", "home"):
        team = game["teams"][side]
        if (team["sport"]["id"] != row["sport_id"]
                or (row["league_id"] is not None and team["league"]["id"] != row["league_id"])):
            raise ValueError("feed 球隊層級或聯盟與預宣告時間窗不符")
    rules = resolve_game_rules(feed)
    if (rules.rule_status != "confirmed" or rules.initial_challenges != 2
            or rules.regime_id != row["regime"]):
        raise ValueError("逐場兩次制或 Challenge format 未確認")
    audit = audit_feed(feed, rules)
    summary = audit["summary"]
    if summary["invalid_budget_events"]:
        raise ValueError(f"Challenge 額度事件無效：{summary['invalid_budget_events']}")
    if summary["challenge_team_direction_mismatches"]:
        raise ValueError(f"Challenge 決策方與判決方向不符：{summary['challenge_team_direction_mismatches']}")
    if summary["challenger_eligibility_failures"]:
        raise ValueError(f"Challenge 發起資格無法判定：{summary['challenger_eligibility_failures']}")
    # 零挑戰場仍屬母體，不能因缺少 attempt 而事後排除。
    if (not summary["challenge_events"] and summary["official_attempts"] not in (0, None)
            and summary["official_counter_pass"] is not False):
        raise ValueError("官方有 Challenge，但 feed 未找到逐球事件")
    return audit, inspect_source_signals(feed)


def _one_feed(row: dict, cache_dir: Path, offline: bool) -> tuple[dict, dict | None, dict | None]:
    output = {key: row[key] for key in ("game_pk", "date", "split", "window", "regime")}
    url = f"https://statsapi.mlb.com/api/v1.1/game/{row['game_pk']}/feed/live"
    cache = SourceCache(cache_dir, offline=offline)
    try:
        source = cache.get(url, "mlb_stats_api_feed_json", _feed_count)
        output["feed_manifest"] = source["manifest"]
        feed = json.loads(source["text"])
        audit, signals = _check_feed(row, feed)
        summary = audit["summary"]
        mismatch = summary["official_counter_pass"] is False
        output.update(status="feed_counter_mismatch" if mismatch else "feed_pass",
                      eligibility_source_audit=signals,
                      challenge_events=audit["summary"]["challenge_events"],
                      official_counter_available=audit["summary"]["official_counter_available"],
                      official_counter_pass=audit["summary"]["official_counter_pass"],
                      actual_extra_innings=audit["game"]["extra_inning_game"])
        if mismatch:
            output["reason"] = (f"官方終場 Challenge 計數不符：feed={summary['challenge_events']}/"
                                f"{summary['overturned']}，官方={summary['official_attempts']}/"
                                f"{summary['official_overturned']}")
        return output, feed, audit
    except (OSError, KeyError, TypeError, ValueError, RuleResolutionError) as error:
        output.update(status="feed_failure", reason=str(error))
        return output, None, None


def _one_csv(day: str, level: str, cache_dir: Path, offline: bool) -> tuple[str, dict | None, str | None]:
    url = build_called_pitches_csv_url(day, level)
    cache = SourceCache(cache_dir, offline=offline, fetch=lambda address: fetch_csv_text(address, timeout=120))
    try:
        source = cache.get(url, "baseball_savant_pitch_csv", _pitch_count)
        return day, source["manifest"], None
    except (OSError, KeyError, TypeError, ValueError) as error:
        return day, None, str(error)


def _abs_source(day: str, level: str, cache_dir: Path, offline: bool) -> dict:
    url = build_abs_csv_url(day, level)
    cache = SourceCache(cache_dir, offline=offline, fetch=lambda address: fetch_csv_text(address, timeout=120))
    return cache.get(url, "baseball_savant_abs_csv", lambda text: len(parse_csv_text(text)))


def _candidate_artifact(game_row: dict, candidates: list[dict], total_pitches: int) -> dict:
    """把決策時欄位與事後標籤分艙，供後續防洩漏檢查。"""
    records = []
    if type(total_pitches) is not int or total_pitches < 1:
        raise ValueError("regulation 投球總數無效")
    next_by_team = {}
    for candidate in reversed(candidates):
        index = candidate["physical_pitch_index"]
        team = candidate["decision_team_id"]
        if type(index) is not int or not 1 <= index <= total_pitches:
            raise ValueError("候選事件的物理投球序號無效")
        next_index = next_by_team.get(team)
        gap = (next_index if next_index is not None else total_pitches) - index
        if gap < 0 or (next_index is not None and gap == 0):
            raise ValueError("候選事件順序不符")
        candidate["arrival_target"] = {"pitch_gap": gap,
                                       "next_opportunity_observed": next_index is not None,
                                       "censoring_boundary": "regulation_end" if next_index is None else None}
        if candidate["population"] == "provisional_opportunity":
            next_by_team[team] = index
    for candidate in candidates:
        records.append({"game_pk": candidate["game_pk"],
                        "at_bat_number": candidate["at_bat_number"],
                        "pitch_number": candidate["pitch_number"],
                        "physical_pitch_index": candidate["physical_pitch_index"],
                        "decision_features": {key: candidate[key] for key in (
                            "pre_pitch_state", "challenges_remaining", "original_call",
                            "decision_team_id", "decision_side")},
                        "analysis_labels": {key: candidate.get(key) for key in (
                            "actual_challenge", "population", "status", "s0", "s1", "reason")},
                        "arrival_target": candidate["arrival_target"],
                        "alignment_evidence": candidate["alignment"],
                        "source_eligibility": {key: candidate[key] for key in (
                            "abs_technical_availability", "post_replay_challenge_eligibility",
                            "source_eligibility_version")}})
    return {"schema_version": "dataset-b-provisional-candidates-v2",
            "game_pk": game_row["game_pk"], "date": game_row["date"],
            "split": game_row["split"], "window": game_row["window"],
            "feature_contract": "僅 decision_features 可作決策當下模型輸入；analysis_labels 與 alignment_evidence 禁止作 predictor",
            "source_eligibility_status": "provisional_source_limitations",
            "rows": records}


def prepare(selection: dict, sampling: dict, split: dict, *, cache_dir: Path,
            offline: bool, feeds_only: bool, baseline: SavantBaseline | None = None,
            workers: int = 6, candidates_dir: Path | None = None,
            reconcile_abs: bool = False, abs_cache_dir: Path | None = None) -> dict:
    games = _selected(selection, sampling, split)
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError("並行來源數須介於 1 與 8")
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(_one_feed, row, cache_dir, offline): row["game_pk"] for row in games}
        for future in as_completed(jobs):
            results[jobs[future]] = future.result()
            print(f"feed {len(results)}/{len(games)}", flush=True)
    rows = []
    feeds, audits = {}, {}
    for game in games:
        row, feed, audit = results[game["game_pk"]]
        rows.append(row)
        if feed is not None:
            feeds[game["game_pk"]], audits[game["game_pk"]] = feed, audit
    csv_sources, abs_sources = {}, {}
    if not feeds_only:
        if baseline is None:
            raise ValueError("完整逐球準備需要固定官方 WP baseline")
        by_date = defaultdict(list)
        for row in rows:
            if row["status"] == "feed_pass" or (reconcile_abs and row["status"] == "feed_counter_mismatch"):
                by_date[(row["date"], "mlb" if row["regime"] == "mlb-2026" else "aaa")].append(row)
        with ThreadPoolExecutor(max_workers=min(workers, 4)) as pool:
            jobs = {pool.submit(_one_csv, day, level, cache_dir, offline): (day, level)
                    for day, level in by_date}
            for future in as_completed(jobs):
                day, manifest, error = future.result()
                level = jobs[future][1]
                csv_sources[f"{level}:{day}"] = {"manifest": manifest, "error": error}
                print(f"逐球來源 {len(csv_sources)}/{len(by_date)}", flush=True)
        for (day, level), grouped in by_date.items():
            source = csv_sources[f"{level}:{day}"]
            if source["error"]:
                for row in grouped:
                    row.update(status="csv_source_failure", reason=source["error"])
                continue
            url = build_called_pitches_csv_url(day, level)
            cached = SourceCache(cache_dir, offline=True).get(url, "baseball_savant_pitch_csv", _pitch_count)
            csv_rows = parse_csv_text(cached["text"])
            for row in grouped:
                pk = row["game_pk"]
                try:
                    # 再次檢查 Challenge 與 Savant 狀態，不只確認 feed 自洽。
                    rules = resolve_game_rules(feeds[pk])
                    recovered = None
                    if row["status"] == "feed_counter_mismatch":
                        if abs_cache_dir is None:
                            raise ValueError("缺少獨立 ABS-only 來源快取")
                        abs_source = _abs_source(day, level, abs_cache_dir, offline)
                        abs_sources[f"{level}:{day}"] = abs_source["manifest"]
                        recovered = recover_abs_only_challenges(feeds[pk], csv_rows,
                                                                  parse_csv_text(abs_source["text"]))
                        row["abs_manifest"] = abs_source["manifest"]
                        row["recovery_evidence"] = recovered["evidence"]
                        row["initial_counter_mismatch"] = row.pop("reason")
                    joined = audit_feed(feeds[pk], rules, csv_rows,
                                        challenge_events=recovered["events"] if recovered else None)
                    summary = joined["summary"]
                    if (summary["official_counter_pass"] is False or summary["invalid_budget_events"]
                            or summary["challenge_team_direction_mismatches"]
                            or summary["challenger_eligibility_failures"]):
                        raise ValueError("復原後官方計數、額度或挑戰方仍不符")
                    if recovered:
                        row["initial_challenge_events"] = row["challenge_events"]
                        row["initial_official_counter_pass"] = row["official_counter_pass"]
                        row["challenge_events"] = summary["challenge_events"]
                        row["official_counter_pass"] = summary["official_counter_pass"]
                        row["official_counter_reconciled"] = True
                    if (summary["statcast_state_missing"] or summary["statcast_count_mismatches"]
                            or summary["statcast_required_state_missing"]):
                        raise ValueError("Challenge／Savant 逐球狀態未完整對齊")
                    population = inspect_population(baseline, feeds[pk], joined, csv_rows, inspect_call)
                    candidates = population["rows"]
                    artifact = _candidate_artifact(row, candidates, population["physical_regulation_pitches"])
                    if candidates_dir is not None:
                        path = candidates_dir / f"game_{pk}.json"
                        if path.exists():
                            if json.loads(path.read_text(encoding="utf-8")) != artifact:
                                raise ValueError("既有候選資料與固定來源重建結果不符，拒絕覆寫")
                        else:
                            atomic_json_new(path, artifact)
                        row["candidate_artifact"] = str(path)
                        row["candidate_manifest"] = build_file_manifest(path, source_type="dataset_b_provisional_candidates")
                    row.update(status="provisional_population_recovered" if recovered else "provisional_population_pass",
                               pitch_alignment=population["alignment"],
                               candidate_count=len(candidates),
                               population_counts=dict(sorted(Counter(item["population"] for item in candidates).items())),
                               actual_challenges=sum(item["actual_challenge"] for item in candidates),
                               source_eligibility_status="provisional_source_limitations")
                except (OSError, KeyError, TypeError, ValueError) as error:
                    row.update(status="recovery_unresolved" if row["status"] == "feed_counter_mismatch"
                               else "population_failure", reason=str(error))
    status_counts = dict(sorted(Counter(row["status"] for row in rows).items()))
    return {"schema_version": "dataset-b-pretraining-preparation-v1",
            "selection_sha256": selection["selection_sha256"], "stage": "feeds_only" if feeds_only else "population",
            "selected_games": len(games), "game_rows": rows, "status_counts": status_counts,
            "csv_sources": dict(sorted(csv_sources.items())),
            "abs_sources": dict(sorted(abs_sources.items())),
            "source_eligibility_complete": False,
            "holdout_game_lists_locked": False,
            "formal_model_evaluation_ready": False,
            "training_ready": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--sampling-plan", type=Path, default=ROOT / "config/dataset_b_sampling.json")
    parser.add_argument("--split-plan", type=Path, default=ROOT / "config/dataset_b_split_plan.json")
    parser.add_argument("--baseline", type=Path, default=ROOT / "data/processed/savant_baseline_v2_2026-09-15.json")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data/raw/dataset_b/source_cache")
    parser.add_argument("--abs-cache-dir", type=Path, default=ROOT / "data/raw/dataset_b/diagnostic_cache")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidates-dir", type=Path, default=ROOT / "data/processed/dataset_b/candidates_v4")
    parser.add_argument("--feeds-only", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--reconcile-abs", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("不得覆寫既有 Dataset B 準備報告")
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    sampling = json.loads(args.sampling_plan.read_text(encoding="utf-8"))
    split = json.loads(args.split_plan.read_text(encoding="utf-8"))
    baseline = None if args.feeds_only else SavantBaseline(json.loads(args.baseline.read_text(encoding="utf-8")))
    result = prepare(selection, sampling, split, cache_dir=args.cache_dir,
                     offline=args.offline, feeds_only=args.feeds_only, baseline=baseline,
                     workers=args.workers, candidates_dir=None if args.feeds_only else args.candidates_dir,
                     reconcile_abs=args.reconcile_abs, abs_cache_dir=args.abs_cache_dir)
    result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
        (args.selection, "dataset_b_schedule_selection"),
        (args.sampling_plan, "dataset_b_sampling_plan"),
        (args.split_plan, "dataset_b_split_plan"),
        (DEFAULT_RULE_CONFIG, "rule_regimes"),
        *(([(args.baseline, "official_wp_baseline")] if not args.feeds_only else [])))]
    result["runtime"] = _runtime()
    atomic_json_new(args.output, result)
    print(json.dumps({"selected_games": result["selected_games"],
                      "status_counts": result["status_counts"],
                      "training_ready": result["training_ready"]}, ensure_ascii=False))
    return 0 if len(result["status_counts"]) == 1 and "provisional_population_pass" in result["status_counts"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
