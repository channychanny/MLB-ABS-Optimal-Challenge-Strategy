"""以決策隊伍的官方 S0／S1 WP 為核心，輸出條件式挑戰勝率決策表。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
from statistics import median

from .baseline import SavantBaseline
from .dataset_b_action_support import INCLUDED, _verify_inputs
from .phase1_cli import _runtime
from .policy_scenarios import _candidate_valuation, analyze_cohort
from .provenance import build_file_manifest
from .source_cache import atomic_json_new
from .state_value import GameState
from .wp_coverage import inspect_call


ROOT = Path(__file__).resolve().parents[2]
SPLITS = ("train", "validation", "test", "external")


def _number(value: object, name: str, low: float = 0, high: float = 1) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} 必須是 {low}–{high} 的有限數值")
    return float(value)


def validate_protocol(protocol: dict) -> None:
    if (protocol.get("schema_version") != "phase3-decision-team-win-impact-v1"
            or protocol.get("objective") != "決策隊伍預期勝率；RE 僅作輔助說明"
            or protocol.get("probability_source") != "declared_sensitivity_not_estimated_player_confidence"
            or protocol.get("resource_cost_source") != "declared_incremental_sensitivity_not_empirical_option_value"
            or protocol.get("successful_branch_extra_shift") != 0
            or protocol.get("formal_policy_evaluation_ready") is not False):
        raise ValueError("主線勝率決策規格不可混入人工成功位移或正式策略宣稱")
    ps = protocol.get("overturn_probability_grid")
    if (not isinstance(ps, list) or not ps
            or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 < p < 1 for p in ps)
            or ps != sorted(set(ps)) or protocol.get("detail_probability") not in ps):
        raise ValueError("成功率格點須為排序、唯一且位於 0–1 之內")
    costs = protocol.get("cost_scenarios")
    if (not isinstance(costs, list) or [item.get("id") for item in costs]
            != ["immediate_only", "small_resource_cost", "large_resource_cost"]):
        raise ValueError("成本敏感度情境不完整或順序錯誤")
    for item in costs:
        by_budget = item.get("failure_cost_by_budget")
        if not isinstance(by_budget, dict) or set(by_budget) != {"1", "2"}:
            raise ValueError("成本須明確列出剩餘 1／2 次額度")
        one = _number(by_budget["1"], "最後一次額度成本")
        two = _number(by_budget["2"], "第二次額度成本")
        if two > one:
            raise ValueError("最後一次額度的成本不得低於第二次")
    if (any(costs[0]["failure_cost_by_budget"][key] != 0 for key in ("1", "2"))
            or any(costs[1]["failure_cost_by_budget"][key]
                   > costs[2]["failure_cost_by_budget"][key] for key in ("1", "2"))):
        raise ValueError("零成本與成本遞增契約不符")
    _number(protocol.get("action_tie_tolerance"), "平手容差", 0, 1e-9)


def assess_incremental_cost(delta_wp: float, probability: float, cost: float,
                            *, tolerance: float = 1e-12) -> dict:
    """給定主觀成功率和失敗額度成本的相對決策；不將結果冒稱校準勝率。"""
    delta = _number(delta_wp, "翻判 WP 差", -1, 1)
    p = _number(probability, "翻判成功率")
    failure_cost = _number(cost, "失敗額度成本")
    tolerance = _number(tolerance, "平手容差", 0, 1e-9)
    net = p * delta - (1 - p) * failure_cost
    action = "challenge" if net > tolerance else "save" if net < -tolerance else "tie"
    threshold_result = required_success_probability(delta, failure_cost, tolerance=tolerance)
    return {"conditional_failure_cost": failure_cost,
            "net_relative_decision_score": net,
            "action": action,
            **threshold_result}


def required_success_probability(delta_wp: float, cost: float,
                                 *, tolerance: float = 1e-12) -> dict:
    """只算當下翻判把握門檻；不假裝知道球員對這一球的主觀把握。"""
    delta = _number(delta_wp, "翻判 WP 差", -1, 1)
    failure_cost = _number(cost, "失敗額度成本")
    tolerance = _number(tolerance, "平手容差", 0, 1e-9)
    if delta > tolerance:
        threshold, kind = failure_cost / (delta + failure_cost), "conditional_break_even"
    elif abs(delta) <= tolerance and failure_cost <= tolerance:
        threshold, kind = None, "indifferent"
    else:
        threshold, kind = None, "never_strictly_challenge"
    return {"conditional_failure_cost": failure_cost,
            "conditional_break_even_probability": threshold,
            "break_even_kind": kind}


def decide(wp0: float | None, wp1: float | None, *, budget: int,
           s0_terminal: bool, probability: float, protocol: dict) -> dict:
    """官方 WP 只處理當下 S0／S1；未來額度價值僅以明示成本測試。"""
    validate_protocol(protocol)
    if type(budget) is not int or budget not in (1, 2) or type(s0_terminal) is not bool:
        raise ValueError("決策額度或 S0 終局旗標無效")
    p = _number(probability, "翻判成功率", 0, 1)
    if wp0 is None or wp1 is None:
        return {"status": "unsupported", "wp_s0": wp0, "wp_s1": wp1,
                "expected_wp_without_resource_cost": None, "cost_scenarios": None}
    w0, w1 = _number(wp0, "S0 決策隊伍 WP"), _number(wp1, "S1 決策隊伍 WP")
    delta = w1 - w0
    gross = p * delta
    if delta > 0 and p == 1:
        cost_limit = {"kind": "unbounded_when_failure_impossible", "value": None}
    elif gross > 0 and p < 1:
        cost_limit = {"kind": "finite", "value": gross / (1 - p)}
    else:
        cost_limit = {"kind": "no_positive_gross_gain", "value": None}
    outcomes = {}
    tolerance = protocol["action_tie_tolerance"]
    for scenario in protocol["cost_scenarios"]:
        cost = 0.0 if s0_terminal else scenario["failure_cost_by_budget"][str(budget)]
        outcomes[scenario["id"]] = assess_incremental_cost(
            delta, p, cost, tolerance=tolerance)
    return {
        "status": "supported", "wp_s0": w0, "wp_s1": w1,
        "delta_wp_if_overturned": delta,
        "probability_assumption": p,
        "expected_wp_without_resource_cost": w0 + gross,
        "expected_immediate_gain": gross,
        "maximum_failure_cost_for_positive_decision": cost_limit,
        "cost_scenarios": outcomes,
        "interpretation": "條件式勝率決策，非已驗證的全場最適政策",
    }


def evaluate_state(snapshot: dict, request: dict, protocol: dict) -> dict:
    validate_protocol(protocol)
    if (request.get("schema_version") != "policy-scenario-state-input-v1"
            or set(request) != {"schema_version", "pre_pitch_state", "original_call",
                                "challenges_remaining", "assume_pure_called_pitch"}
            or request["assume_pure_called_pitch"] is not True):
        raise ValueError("單一狀態須明示純判決假設")
    state = GameState(**request["pre_pitch_state"])
    if state.inning > 9 or request["original_call"] not in ("ball", "strike"):
        raise ValueError("主研究只接受第 1–9 局的 ball／strike 原判")
    valuation = inspect_call(SavantBaseline(snapshot), state, request["original_call"])
    s0, s1 = valuation["s0"], valuation["s1"]
    supported = (isinstance(s0, dict) and isinstance(s1, dict)
                 and s0.get("supported") is True and s1.get("supported") is True)
    results = {str(p): decide(s0["wp_decision"] if supported else None,
                              s1["wp_decision"] if supported else None,
                              budget=request["challenges_remaining"],
                              s0_terminal=bool(s0 and s0["terminal"] is not None),
                              probability=p, protocol=protocol)
               for p in protocol["overturn_probability_grid"]}
    return {
        "schema_version": "phase3-decision-team-win-impact-state-v1",
        "status": "supported" if supported else "unsupported",
        "pre_pitch_state": state.to_dict(), "original_call": request["original_call"],
        "decision_side": valuation["decision_side"],
        "challenges_remaining": request["challenges_remaining"],
        "s0": {name: s0.get(name) if s0 else None for name in (
            "wp_decision", "re", "terminal", "supported", "missing_reason_code")},
        "s1": {name: s1.get(name) if s1 else None for name in (
            "wp_decision", "re", "terminal", "supported", "missing_reason_code")},
        "results_by_probability": results,
        "call_only_assumption": "no_other_same_pitch_events",
        "formal_policy_evaluation_ready": False,
    }


def analyze_population(preparation: dict, baseline_result: dict, cohort_result: dict,
                       snapshot: dict, old_protocol: dict, protocol: dict) -> dict:
    validate_protocol(protocol)
    verified = analyze_cohort(preparation, baseline_result, SavantBaseline(snapshot), old_protocol)
    if (verified["rows"] != cohort_result.get("rows")
            or verified["split_summaries"] != cohort_result.get("split_summaries")):
        raise ValueError("舊固定 cohort 與官方 S0／S1 重算結果不符")
    expected = {(row["game_pk"], row["at_bat_number"], row["pitch_number"]): row
                for row in verified["rows"]}
    if len(expected) != len(verified["rows"]):
        raise ValueError("舊 cohort 事件鍵重複")
    records = []
    for game in preparation["game_rows"]:
        if game["status"] not in INCLUDED:
            continue
        path = Path(game["candidate_artifact"])
        if build_file_manifest(path, source_type="dataset_b_provisional_candidates") != game["candidate_manifest"]:
            raise ValueError("固定候選指紋不符")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact["game_pk"] != game["game_pk"] or artifact["split"] != game["split"]:
            raise ValueError("候選場次或切分不符")
        for row in artifact["rows"]:
            if row["analysis_labels"]["population"] != "provisional_opportunity":
                continue
            item = _candidate_valuation(row)
            key = (game["game_pk"], row["at_bat_number"], row["pitch_number"])
            reference = expected.pop(key, None)
            if (reference is None or reference["split"] != game["split"]
                    or reference["challenges_remaining"] != item["budget"]):
                raise ValueError("主線 cohort 事件鍵、切分或額度不一致")
            valuation = item["valuation"]
            s0, s1 = valuation["s0"], valuation["s1"]
            supported = reference["status"] == "supported"
            if supported != (isinstance(s0, dict) and isinstance(s1, dict)
                             and s0.get("supported") is True and s1.get("supported") is True):
                raise ValueError("官方 WP 支援狀態不一致")
            wp0, wp1 = (s0["wp_decision"], s1["wp_decision"]) if supported else (None, None)
            if supported and abs((wp1 - wp0) - reference["immediate_delta_wp"]) > 1e-12:
                raise ValueError("官方決策方 WP 差值與固定 cohort 不一致")
            by_p = {str(p): decide(wp0, wp1, budget=item["budget"],
                                    s0_terminal=bool(s0 and s0.get("terminal") is not None),
                                    probability=p, protocol=protocol)
                    for p in protocol["overturn_probability_grid"]}
            records.append({
                "game_pk": game["game_pk"], "split": game["split"],
                "at_bat_number": row["at_bat_number"], "pitch_number": row["pitch_number"],
                "decision_side": reference["decision_side"], "game_phase": reference["game_phase"],
                "challenges_remaining": item["budget"], "status": reference["status"],
                "wp_s0": wp0, "wp_s1": wp1,
                "re_s0": s0.get("re") if isinstance(s0, dict) else None,
                "re_s1": s1.get("re") if isinstance(s1, dict) else None,
                "missing_reason_s0": reference["s0_missing_reason"],
                "missing_reason_s1": reference["s1_missing_reason"],
                "s0_terminal": bool(s0 and s0.get("terminal") is not None),
                "results_by_probability": by_p,
            })
    if expected:
        raise ValueError("主線 cohort 有未核對的候選")
    split_summaries = {}
    for split in SPLITS:
        rows = [row for row in records if row["split"] == split]
        supported = [row for row in rows if row["status"] == "supported"]
        previous = cohort_result["split_summaries"][split]
        if len(rows) != previous["provisional_candidates"] or len(supported) != previous["support_counts"]["supported"]:
            raise ValueError("固定切分候選分母不一致")
        by_p = {}
        for p in protocol["overturn_probability_grid"]:
            selected = [row["results_by_probability"][str(p)] for row in supported]
            costs = {}
            for scenario in protocol["cost_scenarios"]:
                name = scenario["id"]
                counts = Counter(result["cost_scenarios"][name]["action"] for result in selected)
                cells = defaultdict(Counter)
                for row in supported:
                    action = row["results_by_probability"][str(p)]["cost_scenarios"][name]["action"]
                    cells[f"{row['game_phase']}|{row['decision_side']}|{row['challenges_remaining']}"][action] += 1
                costs[name] = {"action_counts": dict(sorted(counts.items())),
                               "by_phase_side_budget": {key: dict(sorted(value.items()))
                                                        for key, value in sorted(cells.items())}}
            limits = [result["maximum_failure_cost_for_positive_decision"]["value"]
                      for result in selected
                      if result["maximum_failure_cost_for_positive_decision"]["kind"] == "finite"]
            by_p[str(p)] = {"cost_scenarios": costs,
                            "median_gross_gain_wp": median(result["expected_immediate_gain"] for result in selected)
                            if selected else None,
                            "finite_cost_limit_count": len(limits),
                            "median_maximum_failure_cost_when_finite": median(limits) if limits else None}
        split_summaries[split] = {"games": previous["games"],
                                  "provisional_candidates": len(rows),
                                  "supported": len(supported),
                                  "unsupported": len(rows) - len(supported),
                                  "by_probability": by_p}
    detail_p = protocol["detail_probability"]
    compact_rows = []
    for row in records:
        detail = row["results_by_probability"][str(detail_p)]
        compact_rows.append({key: value for key, value in row.items()
                             if key != "results_by_probability"}
                            | {"detail_probability": detail_p,
                               "expected_wp_without_resource_cost": detail["expected_wp_without_resource_cost"],
                               "expected_immediate_gain": detail.get("expected_immediate_gain"),
                               "maximum_failure_cost_for_positive_decision": detail.get(
                                   "maximum_failure_cost_for_positive_decision"),
                               "detail_cost_scenarios": detail["cost_scenarios"]})
    return {"schema_version": "phase3-decision-team-win-impact-cohort-v1",
            "scope": protocol["scope"],
            "estimand": "指定翻判成功率與增量失敗額度成本下，已可挑戰情境的決策隊伍預期勝率比較",
            "costs_are_assumptions_not_estimates": True,
            "synthetic_future_model_is_not_primary": True,
            "source_eligibility_unknown_is_scope_limitation_not_decision_gate": True,
            "split_summaries": split_summaries, "rows": compact_rows,
            "formal_policy_evaluation_ready": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=ROOT / "config/phase3_win_decision_protocol.json")
    parser.add_argument("--official-baseline", type=Path,
                        default=ROOT / "data/processed/savant_baseline_v2_2026-09-15.json")
    parser.add_argument("--state-input", type=Path)
    parser.add_argument("--preparation", type=Path)
    parser.add_argument("--baseline-result", type=Path)
    parser.add_argument("--cohort-result", type=Path)
    parser.add_argument("--scenario-protocol", type=Path, default=ROOT / "config/policy_scenario_protocol.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("拒絕覆寫既有勝率決策結果")
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    if args.state_input is not None:
        if any(value is not None for value in (args.preparation, args.baseline_result, args.cohort_result)):
            raise ValueError("單一狀態不可混用 cohort 輸入")
        result = evaluate_state(json.loads(args.official_baseline.read_text(encoding="utf-8")),
                                json.loads(args.state_input.read_text(encoding="utf-8")), protocol)
        paths = ((args.protocol, "phase3_win_decision_protocol"),
                 (args.official_baseline, "official_wp_baseline"),
                 (args.state_input, "policy_scenario_state_input"))
    else:
        if any(value is None for value in (args.preparation, args.baseline_result, args.cohort_result)):
            raise ValueError("批次需提供固定 preparation、baseline-result 與 cohort-result")
        preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
        baseline_result = json.loads(args.baseline_result.read_text(encoding="utf-8"))
        cohort_result = json.loads(args.cohort_result.read_text(encoding="utf-8"))
        _verify_inputs(preparation, baseline_result, args.preparation)
        expected = {item["source_type"]: item for item in cohort_result["input_manifests"]}
        for path, kind in ((args.preparation, "dataset_b_pretraining_preparation"),
                           (args.baseline_result, "dataset_b_observational_baseline"),
                           (args.official_baseline, "official_wp_baseline"),
                           (args.scenario_protocol, "policy_scenario_protocol")):
            if expected.get(kind) != build_file_manifest(path, source_type=kind):
                raise ValueError(f"固定 cohort 上游指紋不符：{kind}")
        result = analyze_population(
            preparation, baseline_result, cohort_result,
            json.loads(args.official_baseline.read_text(encoding="utf-8")),
            json.loads(args.scenario_protocol.read_text(encoding="utf-8")), protocol)
        paths = ((args.protocol, "phase3_win_decision_protocol"),
                 (args.scenario_protocol, "policy_scenario_protocol"),
                 (args.official_baseline, "official_wp_baseline"),
                 (args.preparation, "dataset_b_pretraining_preparation"),
                 (args.baseline_result, "dataset_b_observational_baseline"),
                 (args.cohort_result, "policy_scenario_cohort"))
    result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in paths]
    result["runtime"] = _runtime()
    atomic_json_new(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
