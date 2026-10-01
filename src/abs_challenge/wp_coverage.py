"""固定開發 cohort 的雙路徑 WP 支援性；不冒充完整機會母體。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

from .audit import audit_feed
from .baseline import MissingBaselineState, SavantBaseline
from .phase1 import call_only_limitation
from .phase1_cli import _runtime, _write_new
from .provenance import build_file_manifest
from .rules import DEFAULT_RULE_CONFIG, resolve_game_rules
from .savant import build_called_pitches_csv_url, parse_csv_text
from .state_value import GameState, counterfactual_states


def inspect_call(baseline: SavantBaseline, state: GameState, original_call: str) -> dict[str, Any]:
    """獨立檢查兩側，保留超界時仍存在的 RE 與另一側 WP。"""
    result: dict[str, Any] = {}
    decision_home = (state.half == "bottom") == (original_call == "strike")
    for name, transition in zip(("s0", "s1"), counterfactual_states(state, original_call)):
        next_state = transition.next_state
        post_diff = next_state.home_score - next_state.away_score if next_state else None
        side = {"transition": transition.to_dict(), "re": baseline.transition_re(transition),
                "terminal": transition.terminal, "wp_home": None, "wp_decision": None,
                "post_home_score_diff": post_diff}
        try:
            value = baseline.transition_home_wp(transition)
            side.update(supported=True, wp_home=value, wp_decision=value if decision_home else 1 - value)
        except MissingBaselineState as error:
            side.update(supported=False, reason=str(error),
                        missing_reason_code=("score_diff_out_of_range"
                            if post_diff is not None and not -5 <= post_diff <= 5
                            else "baseline_state_unavailable"))
        result[name] = side
    supported = sum(result[name]["supported"] for name in ("s0", "s1"))
    result["status"] = ("neither_supported", "one_supported", "both_supported")[supported]
    result["decision_side"] = "batting" if original_call == "strike" else "fielding"
    result["decision_home_away"] = "home" if decision_home else "away"
    result["delta_wp_decision"] = (
        result["s1"]["wp_decision"] - result["s0"]["wp_decision"] if supported == 2 else None)
    result["negative_value_warning"] = supported == 2 and result["delta_wp_decision"] < 0
    return result


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """分母包含資料／轉移問題；延長賽另列，不混入主要比例。"""
    counts = Counter(row["status"] for row in rows)
    denominator = len(rows) - counts["excluded_extra_inning"]
    return {"rows": len(rows), "regulation_attempts": denominator,
            "status_counts": dict(sorted(counts.items())),
            "both_supported_fraction": counts["both_supported"] / denominator if denominator else None,
            "terminal_branches": dict(Counter(
                row[name]["terminal"] for row in rows for name in ("s0", "s1")
                if name in row and row[name]["terminal"] is not None)),
            "negative_value_warnings": sum(bool(row.get("negative_value_warning")) for row in rows)}


def inspect_audit(baseline: SavantBaseline, audit: dict, feed: dict) -> list[dict]:
    """輸入由 runner 重新稽核；不修改既有 Phase 1 估值介面。"""
    rows = []
    for event in audit["ledger"]:
        row = {"game_pk": audit["game"]["game_pk"], "year": audit["game"]["season"],
               "regime": audit["rules"]["regime_id"], "inning": event["inning"],
               "at_bat_number": event["at_bat_index"] + 1, "pitch_number": event["pitch_number"],
               "decision_side": "batting" if event["original_call"] == "strike" else "fielding",
               "original_call": event["original_call"], "status": "invalid_state",
               "score_diff": "unknown", "count": "unknown"}
        rows.append(row)
        if event["inning"] > 9:
            row["status"] = "excluded_extra_inning"
            continue
        try:
            state = GameState.from_statcast(event["statcast_pre_pitch_state"])
            row.update(pre_pitch_state=state.to_dict(), score_diff=state.home_score - state.away_score,
                       count=f"{state.balls}-{state.strikes}")
            if (state.inning, state.half, state.balls, state.strikes) != (
                    event["inning"], event["half_inning"], event["balls_before"], event["strikes_before"]):
                raise ValueError("feed 與判決前狀態不一致")
            if event["challenges_before"] not in (1, 2) or not event["valid_budget"]:
                raise ValueError("決策額度無效")
            reason = call_only_limitation(feed, event, state)
            if reason:
                row.update(status="unsupported_compound_event", reason=reason)
            else:
                row.update(inspect_call(baseline, state, event["original_call"]))
        except (KeyError, TypeError, ValueError) as error:
            row.update(status="invalid_state", reason=str(error))
    return rows


def grouped_summary(rows: list[dict]) -> dict:
    result = {}
    for field in ("year", "regime", "game_pk", "decision_side", "inning", "score_diff", "count"):
        groups = defaultdict(list)
        for row in rows:
            groups[str(row[field])].append(row)
        result[field] = {key: summarize(values) for key, values in sorted(groups.items())}
    return result


def run_coverage(plan_path: Path, root: Path) -> dict:
    """離線重建 audit；所有選定場次均列出，失敗不會消失。"""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if (plan.get("schema_version") != "official-wp-coverage-plan-v1"
            or plan.get("population") != "actual_attempts_development_only"
            or plan.get("coverage_required_fraction") != 1.0):
        raise ValueError("不支援的覆蓋計畫或母體／門檻")
    entries = plan["games"]
    ids = [entry["game_pk"] for entry in entries]
    if not ids or len(ids) != len(set(ids)) or any(type(pk) is not int for pk in ids):
        raise ValueError("cohort 場次必須非空、唯一且為整數")
    baseline_path = root / plan["baseline"]
    baseline = SavantBaseline(json.loads(baseline_path.read_text(encoding="utf-8")))
    inputs = [build_file_manifest(plan_path, source_type="coverage_plan"),
              build_file_manifest(baseline_path, source_type="savant_baseline_snapshot"),
              build_file_manifest(DEFAULT_RULE_CONFIG, source_type="rule_regime_config")]
    games, rows, opportunity_rows = [], [], []
    for entry in entries:
        game = {**entry, "status": "source_failure", "attempt_count": None,
                "opportunity_population_status": "not_evaluated_missing_full_pitch_sources"}
        games.append(game)
        try:
            feed_path = root / "data" / "raw" / f"game_{entry['game_pk']}.json"
            csv_path = root / "data" / "raw" / f"savant_mlb_{entry['date']}_abs.csv"
            for path, kind in ((feed_path, "mlb_stats_api_feed_json"), (csv_path, "baseball_savant_abs_csv")):
                inputs.append(build_file_manifest(path, source_type=kind))
            feed = json.loads(feed_path.read_text(encoding="utf-8"))
            if feed["gamePk"] != entry["game_pk"] or feed["gameData"]["datetime"]["officialDate"] != entry["date"]:
                raise ValueError("cohort 日期／比賽 ID 與 feed 不一致")
            if feed["gameData"]["teams"]["away"]["sport"]["id"] != 1:
                raise ValueError("本 runner 只接受 MLB 開發 cohort，不能套用至 Triple-A")
            # 規則依固定設定重新解析，不相信舊 audit 的 pass 旗標。
            game["status"] = "rule_unresolved"
            rules = resolve_game_rules(feed)
            game["regime"] = rules.regime_id
            game["rule_source"] = rules.source
            if (rules.rule_status != "confirmed" or rules.initial_challenges != 2
                    or rules.abs_format != "challenge" or not rules.successful_challenge_retained):
                game["status"] = "excluded_rule_regime"
                continue
            game["status"] = "audit_failure"
            audit = audit_feed(feed, rules, parse_csv_text(csv_path.read_text(encoding="utf-8-sig")))
            game["audit_summary"] = audit["summary"]
            game["attempt_count"] = len(audit["ledger"])
            if not audit["ledger"]:
                # 無挑戰不是無機會，仍保留在場次分母；官方 counter 不符亦不能通過。
                game["status"] = "zero_attempts" if audit["summary"].get("official_counter_pass") is True else "audit_failure"
                if game["status"] != "zero_attempts":
                    continue
            if audit["ledger"] and not audit["summary"]["phase0_game_pass"]:
                continue
            game_rows = inspect_audit(baseline, audit, feed)
            rows.extend(game_rows)
            game.update(status="processed" if audit["ledger"] else "zero_attempts", summary=summarize(game_rows))
            if plan.get("evaluate_opportunities") is True:
                from .opportunity_coverage import inspect_population
                game["opportunity_population_status"] = "source_or_alignment_failure"
                try:
                    full_path = root / "data" / "raw" / f"savant_mlb_{entry['date']}_pitches.csv"
                    manifest_path = Path(str(full_path) + ".manifest.json")
                    full_manifest = build_file_manifest(full_path, source_type="baseball_savant_pitch_csv")
                    inputs.extend([full_manifest, build_file_manifest(manifest_path, source_type="download_manifest")])
                    downloaded = json.loads(manifest_path.read_text(encoding="utf-8"))
                    full_text = full_path.read_text(encoding="utf-8-sig")
                    full_rows = parse_csv_text(full_text)
                    # 舊 CLI 在 Windows 寫入時轉為 CRLF，下載 manifest 記錄原始文字。
                    # 同時保存實體檔 hash；只接受原 bytes 或還原換行後完全相符的內容。
                    source_variants = [full_path.read_bytes(), full_text.encode("utf-8")]
                    source_matches = any(sha256(content).hexdigest() == downloaded.get("content_sha256")
                                         and len(content) == downloaded.get("byte_length") for content in source_variants)
                    if (downloaded.get("source_type") != "baseball_savant_pitch_csv"
                            or downloaded.get("source_url") != build_called_pitches_csv_url(entry["date"], "mlb")
                            or not source_matches
                            or downloaded.get("row_count") != len(full_rows)
                            or not downloaded.get("retrieved_at_utc")):
                        raise ValueError("完整逐球來源 manifest 不符")
                    population = inspect_population(baseline, feed, audit, full_rows, inspect_call)
                    opportunity_rows.extend(population.pop("rows"))
                    game["opportunity_population"] = population
                    game["opportunity_population_status"] = "provisional_source_limitations"
                except (OSError, KeyError, TypeError, ValueError, IndexError) as error:
                    game["opportunity_population_error"] = str(error)
        except (OSError, KeyError, TypeError, ValueError) as error:
            game["reason"] = str(error)
    summary = summarize(rows)
    processing_complete = all(game["status"] in {"processed", "zero_attempts"} for game in games)
    result = {"schema_version": "official-wp-coverage-report-v1", "cohort": plan,
              "input_manifests": inputs, "games": games, "summary": summary,
              "selected_game_count": len(games), "game_status_counts": dict(Counter(g["status"] for g in games)),
              "processed_regulation_attempt_denominator_complete": processing_complete,
              "selected_cohort_attempts_all_supported": processing_complete and summary["both_supported_fraction"] == 1.0,
              "opportunity_population_coverage": None,
              "legal_opportunity_status": "provisional_source_limitations",
              "research_support_gate_pass": False, "formal_policy_evaluation_ready": False,
              "groups": grouped_summary(rows), "rows": rows}
    if plan.get("evaluate_opportunities") is True:
        def candidate_summary(values):
            summary = summarize(values)
            summary["regulation_candidates"] = summary.pop("regulation_attempts")
            return summary
        def candidate_groups(values):
            groups = grouped_summary(values)
            for group in groups.values():
                for value in group.values():
                    value["regulation_candidates"] = value.pop("regulation_attempts")
            return groups
        populations = sorted({row["population"] for row in opportunity_rows})
        result["opportunity_report"] = {
            "legal_opportunity_status": "provisional_source_limitations",
            "selected_game_denominator_complete": all(g["opportunity_population_status"] == "provisional_source_limitations" for g in games),
            "selected_games_processed": sum(g["opportunity_population_status"] == "provisional_source_limitations" for g in games),
            "candidate_summary": candidate_summary(opportunity_rows),
            "populations": {name: candidate_summary([row for row in opportunity_rows if row["population"] == name])
                            for name in populations},
            "groups": candidate_groups(opportunity_rows),
            "groups_by_population": {name: candidate_groups([row for row in opportunity_rows if row["population"] == name])
                                     for name in populations},
            "rows": opportunity_rows}
    # 排除執行時間／路徑等 runtime 差異；來源內容與分組結果共同形成重播指紋。
    lock = {"cohort": plan, "games": games, "rows": rows,
            "source_hashes": [item["content_sha256"] for item in inputs]}
    if plan.get("evaluate_opportunities") is True:
        lock["opportunity_rows"] = opportunity_rows
    result["content_lock_sha256"] = sha256(json.dumps(lock, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    result["runtime"] = _runtime()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="固定開發樣本的官方 WP 雙路徑覆蓋檢查")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise FileExistsError("輸出已存在，請使用新的檔名")
        result = run_coverage(args.plan, Path(__file__).resolve().parents[2])
        result["command"] = ["python", "-m", "abs_challenge.wp_coverage", *(argv if argv is not None else sys.argv[1:])]
        _write_new(args.output, result)
        print(json.dumps({"games": result["game_status_counts"], "summary": result["summary"],
                          "content_lock_sha256": result["content_lock_sha256"]}, ensure_ascii=False, indent=2))
        # 開發子母體報告不等於整體研究閘門通過。
        return 1
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
