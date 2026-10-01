"""決策時 ABS 情境比較；只求明示假設下的相對價值，不冒充正式策略。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

from .baseline import SavantBaseline
from .dataset_b_action_support import INCLUDED, _verify_inputs
from .phase1_cli import _runtime
from .provenance import build_file_manifest
from .source_cache import atomic_json_new
from .state_value import GameState
from .wp_coverage import inspect_call


ROOT = Path(__file__).resolve().parents[2]
FEATURE_FIELDS = {"pre_pitch_state", "challenges_remaining", "original_call",
                  "decision_team_id", "decision_side"}


def _number(value: Any, name: str, minimum: float, maximum: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} 必須是 {minimum}–{maximum} 的有限數值")
    return float(value)


def validate_protocol(protocol: dict) -> None:
    if (protocol.get("schema_version") != "decision-time-policy-scenarios-v1"
            or protocol.get("probability_source") != "synthetic_sensitivity_not_player_confidence"
            or protocol.get("future_value_source") != "synthetic_increment_not_empirical_transition"
            or protocol.get("historical_post_action_model_as_decision_feature") is not False
            or protocol.get("formal_legal_opportunity_ready") is not False
            or protocol.get("formal_policy_evaluation_ready") is not False):
        raise ValueError("情境規格不得宣稱經驗成功率或正式策略")
    probabilities = protocol.get("overturn_probability_grid")
    if (not isinstance(probabilities, list) or not probabilities
            or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
                   for p in probabilities)
            or probabilities != sorted(set(probabilities))):
        raise ValueError("成功率格點必須有限、排序且唯一")
    scenarios = protocol.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("至少需要一組明示未來成本情境")
    ids = []
    for scenario in scenarios:
        name = scenario.get("id")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("情境 ID 不可為空")
        ids.append(name)
        costs = scenario.get("failed_challenge_option_cost_by_budget")
        if not isinstance(costs, dict) or set(costs) != {"1", "2"}:
            raise ValueError("成本需分別指定剩餘 1／2 次額度")
        one = _number(costs["1"], "額度 1 失敗成本", 0, 1)
        two = _number(costs["2"], "額度 2 失敗成本", 0, 1)
        if two > one:
            raise ValueError("本原型要求剩餘 1 次時的成本不低於 2 次")
        _number(scenario.get("successful_branch_future_shift"), "成功後續位移", -1, 1)
    if len(ids) != len(set(ids)):
        raise ValueError("情境 ID 重複")
    _number(protocol.get("action_tie_tolerance"), "平手容差", 0, 1e-9)
    if (protocol.get("risk_set_population") != "provisional_opportunity"
            or protocol.get("supported_valuation_status") != "both_supported"):
        raise ValueError("只接受有額度暫定機會母體")
    phases = protocol.get("game_phase_innings")
    if not isinstance(phases, dict) or set(phases) != {"early", "middle", "late"}:
        raise ValueError("局數階段需完整且不重疊")
    coverage = []
    for bounds in phases.values():
        if (not isinstance(bounds, list) or len(bounds) != 2
                or any(type(value) is not int for value in bounds)
                or not 1 <= bounds[0] <= bounds[1] <= 9):
            raise ValueError("局數階段範圍無效")
        coverage.extend(range(bounds[0], bounds[1] + 1))
    if sorted(coverage) != list(range(1, 10)):
        raise ValueError("局數階段需恰好覆蓋 1–9 局")


def _phase(inning: int, protocol: dict) -> str:
    for name, bounds in protocol["game_phase_innings"].items():
        if bounds[0] <= inning <= bounds[1]:
            return name
    raise ValueError("局數不在主要研究範圍")


def _branch(valuation: dict, name: str) -> tuple[float | None, str | None, str | None]:
    side = valuation.get(name)
    if side is None:
        return None, None, valuation.get("reason") or "not_evaluated"
    if not isinstance(side, dict):
        raise ValueError(f"缺少 {name} 官方估值分支")
    terminal = side.get("terminal")
    if terminal not in (None, "home_win", "away_win", "regulation_tie"):
        raise ValueError(f"{name} 終局型態不支援")
    if side.get("supported") is not True:
        return None, terminal, side.get("missing_reason_code") or side.get("reason") or "unsupported"
    wp = _number(side.get("wp_decision"), f"{name} 決策方 WP", 0, 1)
    return wp, terminal, None


def compare_branches(wp0: float, wp1: float, *, budget: int, probability: float,
                     scenario: dict, s0_terminal: bool = False,
                     s1_terminal: bool = False, tolerance: float = 1e-12) -> dict:
    """一個深介面：把額度、終局、情境與成功率映成可稽核的相對決策。"""
    wp0 = _number(wp0, "S0 決策方 WP", 0, 1)
    wp1 = _number(wp1, "S1 決策方 WP", 0, 1)
    if type(budget) is not int or budget not in (1, 2):
        raise ValueError("決策當下額度只接受 1 或 2")
    p = _number(probability, "主觀翻判成功率情境", 0, 1)
    if type(s0_terminal) is not bool or type(s1_terminal) is not bool:
        raise ValueError("終局旗標必須是布林值")
    tolerance = _number(tolerance, "平手容差", 0, 1e-9)
    costs = scenario["failed_challenge_option_cost_by_budget"]
    cost = 0.0 if s0_terminal else _number(costs[str(budget)], "失敗額度成本", 0, 1)
    shift = 0.0 if s1_terminal else _number(
        scenario["successful_branch_future_shift"], "成功後續位移", -1, 1)
    immediate = wp1 - wp0
    success_advantage = immediate + shift
    advantage = p * success_advantage - (1 - p) * cost
    if advantage > tolerance:
        action = "challenge"
    elif advantage < -tolerance:
        action = "save"
    else:
        action = "tie"
    if success_advantage > tolerance:
        threshold_kind = "break_even"
        threshold = cost / (success_advantage + cost)
    elif abs(success_advantage) <= tolerance and cost <= tolerance:
        threshold_kind, threshold = "indifferent", None
    else:
        threshold_kind, threshold = "never_strictly_challenge", None
    return {"scenario_id": scenario["id"], "probability_assumption": p,
            "wp_s0": wp0, "wp_s1": wp1,
            "immediate_delta_wp": immediate,
            "applied_failure_cost": cost, "applied_success_future_shift": shift,
            "relative_challenge_advantage": advantage,
            "break_even_probability_kind": threshold_kind,
            "break_even_probability": threshold,
            "action": action,
            "terminal_adjustment_applied": bool(s0_terminal or s1_terminal)}


def evaluate_valuation(valuation: dict, budget: int, protocol: dict) -> dict:
    """只讀 S0／S1 靜態估值；不讀實際行動、翻判結果或事後額度。"""
    validate_protocol(protocol)
    if type(budget) is not int or budget not in (1, 2):
        raise ValueError("決策當下額度只接受 1 或 2")
    wp0, terminal0, reason0 = _branch(valuation, "s0")
    wp1, terminal1, reason1 = _branch(valuation, "s1")
    decision_side = valuation.get("decision_side")
    if decision_side not in (None, "batting", "fielding"):
        raise ValueError("Decision Side 無效")
    response = {"schema_version": "decision-time-policy-scenario-result-v1",
                "status": "supported" if wp0 is not None and wp1 is not None else "unsupported",
                "challenges_remaining": budget,
                "decision_side": decision_side,
                "s0": {"wp_decision": wp0, "terminal": terminal0, "missing_reason": reason0,
                       "re": valuation["s0"].get("re") if isinstance(valuation["s0"], dict) else None},
                "s1": {"wp_decision": wp1, "terminal": terminal1, "missing_reason": reason1,
                       "re": valuation["s1"].get("re") if isinstance(valuation["s1"], dict) else None},
                "scenario_source": "synthetic_sensitivity_not_empirical_policy",
                "formal_policy_evaluation_ready": False}
    if wp0 is None or wp1 is None:
        response.update(immediate_delta_wp=None, re_difference=None,
                        scenario_results=None, robust_action="unsupported")
        return response
    if type(response["s0"]["re"]) in (int, float) and type(response["s1"]["re"]) in (int, float):
        re_delta = response["s1"]["re"] - response["s0"]["re"]
    else:
        re_delta = None
    scenario_results = []
    actions = set()
    for scenario in protocol["scenarios"]:
        results = [compare_branches(wp0, wp1, budget=budget, probability=p,
                                    scenario=scenario, s0_terminal=terminal0 is not None,
                                    s1_terminal=terminal1 is not None,
                                    tolerance=protocol["action_tie_tolerance"])
                   for p in protocol["overturn_probability_grid"]]
        actions.update(item["action"] for item in results)
        scenario_results.append({"scenario_id": scenario["id"],
                                 "break_even_probability_kind": results[0]["break_even_probability_kind"],
                                 "break_even_probability": results[0]["break_even_probability"],
                                 "applied_failure_cost": results[0]["applied_failure_cost"],
                                 "applied_success_future_shift": results[0]["applied_success_future_shift"],
                                 "decisions": [{"probability": item["probability_assumption"],
                                                "action": item["action"],
                                                "relative_challenge_advantage": item["relative_challenge_advantage"]}
                                               for item in results]})
    response.update(immediate_delta_wp=wp1 - wp0, re_difference=re_delta,
                    scenario_results=scenario_results,
                    robust_action=next(iter(actions)) if len(actions) == 1 else "scenario_sensitive")
    return response


def evaluate_state(baseline: SavantBaseline, state: GameState, original_call: str,
                   budget: int, protocol: dict) -> dict:
    """單一決策時狀態入口；主客與進攻／防守視角由現有估值模組統一處理。"""
    if original_call not in ("ball", "strike"):
        raise ValueError("原判只接受 ball／strike")
    valuation = inspect_call(baseline, state, original_call)
    result = evaluate_valuation(valuation, budget, protocol)
    result.update(pre_pitch_state=state.to_dict(), original_call=original_call,
                  call_only_assumption="no_other_same_pitch_events")
    return result


def _candidate_valuation(row: dict) -> dict:
    features = row["decision_features"]
    labels = row["analysis_labels"]
    if set(features) != FEATURE_FIELDS:
        raise ValueError("候選決策特徵欄位不符，拒絕額外事後欄位")
    state = GameState(**features["pre_pitch_state"])
    call = features["original_call"]
    expected_side = "batting" if call == "strike" else "fielding" if call == "ball" else None
    if expected_side is None or features["decision_side"] != expected_side:
        raise ValueError("原判方向與 Decision Side 不符")
    if features["challenges_remaining"] not in (1, 2):
        raise ValueError("候選額度必須為 1 或 2")
    if labels["population"] != "provisional_opportunity":
        raise ValueError("只有有額度暫定候選可進策略情境")
    status = labels["status"]
    if status == "unsupported_compound_event":
        if labels["s0"] is not None or labels["s1"] is not None:
            raise ValueError("非純判決候選不得偷帶兩側估值")
    elif status in {"both_supported", "one_supported", "neither_supported"}:
        observed = sum(side.get("supported") is True for side in (labels["s0"], labels["s1"]))
        if observed != {"both_supported": 2, "one_supported": 1,
                        "neither_supported": 0}[status]:
            raise ValueError("兩側支援狀態與標籤不一致")
    else:
        raise ValueError("候選估值狀態不支援")
    valuation = {"s0": labels["s0"], "s1": labels["s1"], "decision_side": expected_side,
                 "reason": labels.get("reason")}
    return {"state": state, "original_call": call,
            "valuation": valuation, "budget": features["challenges_remaining"], "status": status}


def analyze_cohort(preparation: dict, baseline_result: dict,
                   official_baseline: SavantBaseline, protocol: dict) -> dict:
    validate_protocol(protocol)
    archived = {item["game_pk"]: item for item in baseline_result["candidate_manifests"]}
    games = [game for game in preparation["game_rows"] if game["status"] in INCLUDED]
    if len(games) != len(archived):
        raise ValueError("候選場次與已核對清冊不符")
    split_summaries = {}
    detail_rows = []
    for game in games:
        pk = game["game_pk"]
        if game.get("official_counter_pass") is not True:
            raise ValueError(f"官方挑戰計數未通過：{pk}")
        path = Path(game["candidate_artifact"])
        manifest = build_file_manifest(path, source_type="dataset_b_provisional_candidates")
        if manifest != game["candidate_manifest"] or archived.get(pk) != {"game_pk": pk, **manifest}:
            raise ValueError(f"候選指紋不符：{pk}")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if (artifact.get("schema_version") != "dataset-b-provisional-candidates-v2"
                or artifact.get("game_pk") != pk or artifact.get("split") != game["split"]
                or artifact.get("source_eligibility_status") != "provisional_source_limitations"):
            raise ValueError(f"候選資料契約不符：{pk}")
        for candidate in artifact["rows"]:
            if candidate["analysis_labels"]["population"] != protocol["risk_set_population"]:
                continue
            item = _candidate_valuation(candidate)
            if item["status"] != "unsupported_compound_event":
                reference = inspect_call(official_baseline, item["state"], item["original_call"])
                if reference["status"] != item["status"]:
                    raise ValueError(f"官方估值支援狀態與固定候選不符：{pk}")
                for branch in ("s0", "s1"):
                    actual = item["valuation"][branch]
                    expected = reference[branch]
                    if any(actual.get(field) != expected.get(field) for field in (
                            "supported", "wp_decision", "re", "terminal")):
                        raise ValueError(f"官方 S0／S1 估值與固定候選不符：{pk} {branch}")
            result = evaluate_valuation(item["valuation"], item["budget"], protocol)
            detail_rows.append({"game_pk": pk, "split": game["split"],
                                "at_bat_number": candidate["at_bat_number"],
                                "pitch_number": candidate["pitch_number"],
                                "decision_side": result["decision_side"],
                                "game_phase": _phase(item["state"].inning, protocol),
                                "challenges_remaining": item["budget"],
                                "status": result["status"],
                                "valuation_status": item["status"],
                                "immediate_delta_wp": result.get("immediate_delta_wp"),
                                "s0_missing_reason": result["s0"]["missing_reason"],
                                "s1_missing_reason": result["s1"]["missing_reason"],
                                "robust_action": result["robust_action"],
                                "scenario_results": result["scenario_results"]})
    grouped = defaultdict(list)
    for row in detail_rows:
        grouped[row["split"]].append(row)
    if set(grouped) != {"train", "validation", "test", "external"}:
        raise ValueError("固定 Train／Validation／Test／External 場次不完整")
    for split, rows in grouped.items():
        reference = baseline_result["evaluations"][split]
        if (len(rows) != reference["selected_model"]["episodes"]
                or len({row["game_pk"] for row in rows}) != reference["game_clusters"]):
            raise ValueError(f"固定 {split} 候選數或場次與已核對清冊不符")
    for split, rows in grouped.items():
        support = Counter(row["status"] for row in rows)
        valuation_statuses = Counter(row["valuation_status"] for row in rows)
        robust = Counter(row["robust_action"] for row in rows)
        scenarios = {}
        for scenario in protocol["scenarios"]:
            by_p = {}
            for p in protocol["overturn_probability_grid"]:
                counts = Counter()
                by_side_budget = defaultdict(Counter)
                by_phase_side_budget = defaultdict(Counter)
                for row in rows:
                    if row["status"] != "supported":
                        continue
                    choice = next(item for item in row["scenario_results"]
                                  if item["scenario_id"] == scenario["id"])
                    decision = next(item["action"] for item in choice["decisions"]
                                    if item["probability"] == p)
                    counts[decision] += 1
                    by_side_budget[f"{row['decision_side']}|{row['challenges_remaining']}"][decision] += 1
                    by_phase_side_budget[
                        f"{row['game_phase']}|{row['decision_side']}|{row['challenges_remaining']}"][decision] += 1
                by_p[str(p)] = {"action_counts": dict(sorted(counts.items())),
                                "by_decision_side_and_budget": {
                                    key: dict(sorted(value.items()))
                                    for key, value in sorted(by_side_budget.items())},
                                "by_game_phase_side_and_budget": {
                                    key: dict(sorted(value.items()))
                                    for key, value in sorted(by_phase_side_budget.items())}}
            thresholds = {}
            for budget in (1, 2):
                matching = [next(item for item in row["scenario_results"]
                                 if item["scenario_id"] == scenario["id"])
                            for row in rows if row["status"] == "supported"
                            and row["challenges_remaining"] == budget]
                kinds = Counter(item["break_even_probability_kind"] for item in matching)
                finite = [item["break_even_probability"] for item in matching
                          if item["break_even_probability"] is not None]
                thresholds[str(budget)] = {
                    "supported_candidates": len(matching),
                    "threshold_kind_counts": dict(sorted(kinds.items())),
                    "break_even_median_when_defined": median(finite) if finite else None}
            scenarios[scenario["id"]] = {"by_probability": by_p,
                                          "thresholds_by_budget": thresholds}
        split_summaries[split] = {"games": len({row["game_pk"] for row in rows}),
                                  "provisional_candidates": len(rows),
                                  "support_counts": dict(sorted(support.items())),
                                  "valuation_status_counts": dict(sorted(valuation_statuses.items())),
                                  "robust_action_counts": dict(sorted(robust.items())),
                                  "scenario_decisions": scenarios}
    compact_rows = []
    for row in detail_rows:
        compact_rows.append({key: value for key, value in row.items() if key != "scenario_results"}
                            | {"break_even_by_scenario": {
                                item["scenario_id"]: {"kind": item["break_even_probability_kind"],
                                                      "probability": item["break_even_probability"]}
                                for item in row["scenario_results"]} if row["scenario_results"] else None})
    return {"schema_version": "decision-time-policy-scenario-cohort-v1",
            "scope": protocol["scope"],
            "population": "provisional_opportunity",
            "probability_source": protocol["probability_source"],
            "future_value_source": protocol["future_value_source"],
            "scenario_grid": {"probabilities": protocol["overturn_probability_grid"],
                              "scenarios": protocol["scenarios"]},
            "split_summaries": split_summaries,
            "rows": compact_rows,
            "formal_legal_opportunity_ready": False,
            "formal_policy_evaluation_ready": False,
            "limitations": protocol["limitations"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=ROOT / "config/policy_scenario_protocol.json")
    parser.add_argument("--official-baseline", type=Path,
                        default=ROOT / "data/processed/savant_baseline_v2_2026-09-15.json")
    parser.add_argument("--state-input", type=Path)
    parser.add_argument("--preparation", type=Path)
    parser.add_argument("--baseline-result", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    if args.state_input is not None:
        if args.preparation or args.baseline_result:
            raise ValueError("單一狀態查詢不可混用固定 cohort 參數")
        request = json.loads(args.state_input.read_text(encoding="utf-8"))
        if (request.get("schema_version") != "policy-scenario-state-input-v1"
                or set(request) != {"schema_version", "pre_pitch_state", "original_call",
                                    "challenges_remaining", "assume_pure_called_pitch"}
                or request.get("assume_pure_called_pitch") is not True):
            raise ValueError("單一狀態輸入規格版本不符")
        baseline = SavantBaseline(json.loads(args.official_baseline.read_text(encoding="utf-8")))
        result = evaluate_state(baseline, GameState(**request["pre_pitch_state"]),
                                request["original_call"], request["challenges_remaining"], protocol)
        result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
            (args.official_baseline, "savant_baseline_snapshot"),
            (args.protocol, "policy_scenario_protocol"),
            (args.state_input, "policy_scenario_state_input"))]
    else:
        if args.preparation is None or args.baseline_result is None:
            raise ValueError("批次需提供 preparation 與 baseline-result")
        baseline_result = json.loads(args.baseline_result.read_text(encoding="utf-8"))
        preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
        _verify_inputs(preparation, baseline_result, args.preparation)
        official_manifest = next((item for item in preparation["input_manifests"]
                                  if item["source_type"] == "official_wp_baseline"), None)
        if (official_manifest is None or official_manifest != build_file_manifest(
                args.official_baseline, source_type="official_wp_baseline")):
            raise ValueError("官方 WP 快照與候選建置來源指紋不符")
        official_baseline = SavantBaseline(json.loads(args.official_baseline.read_text(encoding="utf-8")))
        result = analyze_cohort(preparation, baseline_result, official_baseline, protocol)
        result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
            (args.preparation, "dataset_b_pretraining_preparation"),
            (args.baseline_result, "dataset_b_observational_baseline"),
            (args.official_baseline, "official_wp_baseline"),
            (args.protocol, "policy_scenario_protocol"))]
    result["runtime"] = _runtime()
    if args.output:
        if args.output.exists():
            raise FileExistsError("拒絕覆寫既有策略情境結果")
        atomic_json_new(args.output, result)
    else:
        if args.state_input is None:
            raise ValueError("批次結果需提供 output，以便保留可重播來源")
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
