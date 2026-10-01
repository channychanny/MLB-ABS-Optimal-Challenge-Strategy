"""九局內假設式有限視野策略；結果不可當作實證 Dynamic Policy。"""

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
from .policy_scenarios import _candidate_valuation, analyze_cohort, validate_protocol as validate_scenarios
from .provenance import build_file_manifest
from .source_cache import atomic_json_new
from .state_value import GameState
from .wp_coverage import inspect_call


ROOT = Path(__file__).resolve().parents[2]
SPLITS = ("train", "validation", "test", "external")
MODES = ("never", "fixed_confidence", "dynamic")


def _probability(value: object, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} 必須是 0–1 的有限數值")
    return float(value)


def validate_protocol(protocol: dict) -> None:
    if (protocol.get("schema_version") != "phase3-synthetic-regulation-policy-v1"
            or protocol.get("model_type") != "synthetic_wp_fractional_loss_not_empirical_transition"
            or protocol.get("future_opportunity_source") != "declared_sensitivity_not_dataset_b_arrival_hazard"
            or protocol.get("future_overturn_source") != "declared_sensitivity_not_player_confidence"
            or protocol.get("future_state_representation") != "decision_team_wp_only_no_base_out_or_score_transition"
            or protocol.get("opponent_policy") != "no_explicit_opponent_challenge_model"
            or protocol.get("unsupported_branch_handling") != "abstain_no_clipping_no_zero_fill"
            or any(protocol.get(flag) is not False for flag in (
                "formal_legal_opportunity_ready", "counterfactual_transition_ready",
                "empirical_outside_continuation_ready", "formal_policy_evaluation_ready"))):
        raise ValueError("Phase 3 原型不得冒稱經驗反事實或正式政策")
    grid = protocol.get("current_overturn_probability_grid")
    if (not isinstance(grid, list) or not grid
            or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in grid)
            or grid != sorted(set(grid))):
        raise ValueError("當前翻判率格點無效")
    if protocol.get("cohort_detail_probability") not in grid:
        raise ValueError("逐筆輸出機率必須在格點內")
    _probability(protocol.get("fixed_confidence_threshold"), "固定信心門檻")
    scenarios = protocol.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("至少需要一組未來機會情境")
    ids = []
    for scenario in scenarios:
        if not isinstance(scenario, dict) or not isinstance(scenario.get("id"), str) or not scenario["id"].strip():
            raise ValueError("情境 ID 無效")
        ids.append(scenario["id"])
        phases = scenario.get("opportunity_probability_by_phase")
        if not isinstance(phases, dict) or set(phases) != {"early", "middle", "late"}:
            raise ValueError("機會到達須指定三個局數階段")
        for phase, value in phases.items():
            _probability(value, f"{phase} 機會機率")
        _probability(scenario.get("adverse_wp_loss_fraction"), "不利判決 WP 損失比例")
        _probability(scenario.get("future_overturn_probability"), "未來翻判率")
    if len(ids) != len(set(ids)):
        raise ValueError("情境 ID 重複")


def _phase(inning: int) -> str:
    if type(inning) is not int or not 1 <= inning <= 9:
        raise ValueError("主要策略只接受第 1–9 局")
    return "early" if inning <= 3 else "middle" if inning <= 6 else "late"


def future_factors(scenario: dict, fixed_threshold: float, mode: str) -> dict[int, tuple[float, float, float]]:
    """由九局向前倒推；係數乘以當前 WP，保證所有合成葉值在 0–1。"""
    if mode not in MODES:
        raise ValueError("未來策略模式無效")
    fixed_threshold = _probability(fixed_threshold, "固定信心門檻")
    rho = _probability(scenario["adverse_wp_loss_fraction"], "不利判決 WP 損失比例")
    future_p = _probability(scenario["future_overturn_probability"], "未來翻判率")
    factors: dict[int, tuple[float, float, float]] = {10: (1.0, 1.0, 1.0)}
    for inning in range(9, 0, -1):
        q = _probability(scenario["opportunity_probability_by_phase"][_phase(inning)], "機會機率")
        after = factors[inning + 1]
        current = []
        for budget in range(3):
            save = (1 - rho) * after[budget]
            if budget == 0 or mode == "never":
                at_opportunity = save
            else:
                challenge = future_p * after[budget] + (1 - future_p) * (1 - rho) * after[budget - 1]
                if mode == "dynamic":
                    at_opportunity = max(save, challenge)
                else:
                    at_opportunity = challenge if future_p >= fixed_threshold else save
            current.append((1 - q) * after[budget] + q * at_opportunity)
        factors[inning] = tuple(current)
    return factors


def _branch_value(wp: float, terminal: bool, factors: tuple[float, float, float], budget: int) -> float:
    return wp if terminal else wp * factors[budget]


def _root_policy(wp0: float, wp1: float, *, budget: int, inning: int,
                 terminal0: bool, terminal1: bool, probability: float,
                 factors: dict[int, tuple[float, float, float]], mode: str,
                 fixed_threshold: float) -> dict:
    available = factors[inning]
    save = _branch_value(wp0, terminal0, available, budget)
    if budget == 0:
        return {"action": "save", "q_save": save, "q_challenge": None, "value": save}
    success = _branch_value(wp1, terminal1, available, budget)
    failure = _branch_value(wp0, terminal0, available, budget - 1)
    challenge = probability * success + (1 - probability) * failure
    if mode == "never":
        action = "save"
    elif mode == "fixed_confidence":
        action = "challenge" if probability >= fixed_threshold else "save"
    else:
        action = "challenge" if challenge > save + 1e-12 else "save"
    return {"action": action, "q_save": save, "q_challenge": challenge,
            "value": challenge if action == "challenge" else save}


def _synthetic_rra(wp0: float, wp1: float, inning: int, budget: int,
                   terminal0: bool, terminal1: bool,
                   factors: dict[int, tuple[float, float, float]]) -> dict:
    if budget == 0:
        return {"kind": "no_budget", "probability": None}
    available = factors[inning]
    save = _branch_value(wp0, terminal0, available, budget)
    failure = _branch_value(wp0, terminal0, available, budget - 1)
    success = _branch_value(wp1, terminal1, available, budget)
    if success <= save + 1e-12:
        return {"kind": "never_strictly_challenge", "probability": None}
    denominator = success - failure
    if denominator <= 1e-12:
        return {"kind": "never_strictly_challenge", "probability": None}
    threshold = (save - failure) / denominator
    if not 0 <= threshold < 1:
        raise ValueError("合成門檻與額度單調性不一致")
    return {"kind": "synthetic_break_even", "probability": threshold}


def solve_state(wp0: float | None, wp1: float | None, *, inning: int, budget: int,
                terminal0: bool, terminal1: bool, probability: float,
                scenario: dict, fixed_threshold: float) -> dict:
    """同一狀態輸出 V(S,0/1/2)、三種根政策與假設式門檻。"""
    _phase(inning)
    if type(budget) is not int or budget not in (1, 2):
        raise ValueError("當前額度需為 1 或 2")
    if type(terminal0) is not bool or type(terminal1) is not bool:
        raise ValueError("終局旗標無效")
    p = _probability(probability, "當前翻判率")
    threshold = _probability(fixed_threshold, "固定信心門檻")
    if wp0 is None or wp1 is None:
        return {"status": "unsupported", "model_values_by_budget": None,
                "policies": None, "synthetic_rra": None}
    wp0 = _probability(wp0, "S0 決策方 WP")
    wp1 = _probability(wp1, "S1 決策方 WP")
    factor_sets = {mode: future_factors(scenario, threshold, mode) for mode in MODES}
    policies = {mode: _root_policy(wp0, wp1, budget=budget, inning=inning,
                                   terminal0=terminal0, terminal1=terminal1,
                                   probability=p, factors=factor_sets[mode],
                                   mode=mode, fixed_threshold=threshold)
                for mode in MODES}
    values = {str(amount): _root_policy(wp0, wp1, budget=amount, inning=inning,
                                        terminal0=terminal0, terminal1=terminal1,
                                        probability=p, factors=factor_sets["dynamic"],
                                        mode="dynamic", fixed_threshold=threshold)["value"]
              for amount in range(3)}
    if not 0 <= values["0"] <= values["1"] + 1e-12 <= values["2"] + 1e-12:
        raise ValueError("合成模型違反額度單調性")
    return {"status": "supported", "scenario_id": scenario["id"],
            "probability_assumption": p, "wp_s0": wp0, "wp_s1": wp1,
            "immediate_delta_wp": wp1 - wp0,
            "future_opportunity_slots": 10 - inning,
            "model_values_by_budget": values,
            "policies": policies,
            "synthetic_rra": _synthetic_rra(wp0, wp1, inning, budget, terminal0,
                                             terminal1, factor_sets["dynamic"]),
            "formal_policy_evaluation_ready": False}


def evaluate_input_state(snapshot: dict, request: dict, protocol: dict) -> dict:
    """手填決策時 Game State；同球無其他事件須由輸入者明示承擔。"""
    validate_protocol(protocol)
    if (request.get("schema_version") != "policy-scenario-state-input-v1"
            or set(request) != {"schema_version", "pre_pitch_state", "original_call",
                                "challenges_remaining", "assume_pure_called_pitch"}
            or request["assume_pure_called_pitch"] is not True):
        raise ValueError("單一狀態輸入須明示純判決假設")
    state = GameState(**request["pre_pitch_state"])
    call = request["original_call"]
    if call not in ("ball", "strike"):
        raise ValueError("原判只接受 ball／strike")
    budget = request["challenges_remaining"]
    valuation = inspect_call(SavantBaseline(snapshot), state, call)
    branches = (valuation["s0"], valuation["s1"])
    supported = all(branch["supported"] for branch in branches)
    scenarios = {}
    for scenario in protocol["scenarios"]:
        scenarios[scenario["id"]] = {
            str(p): solve_state(branches[0]["wp_decision"] if supported else None,
                                branches[1]["wp_decision"] if supported else None,
                                inning=state.inning, budget=budget,
                                terminal0=branches[0]["terminal"] is not None,
                                terminal1=branches[1]["terminal"] is not None,
                                probability=p, scenario=scenario,
                                fixed_threshold=protocol["fixed_confidence_threshold"])
            for p in protocol["current_overturn_probability_grid"]}
    return {"schema_version": "phase3-synthetic-regulation-state-v1",
            "status": "supported" if supported else "unsupported",
            "pre_pitch_state": state.to_dict(), "original_call": call,
            "challenges_remaining": budget, "decision_side": valuation["decision_side"],
            "call_only_assumption": "no_other_same_pitch_events",
            "s0": {name: branches[0].get(name) for name in (
                "wp_decision", "re", "terminal", "supported", "missing_reason_code")},
            "s1": {name: branches[1].get(name) for name in (
                "wp_decision", "re", "terminal", "supported", "missing_reason_code")},
            "scenario_probability_results": scenarios,
            "purpose": "synthetic_sensitivity_not_empirical_policy",
            "formal_policy_evaluation_ready": False}


def analyze_population(preparation: dict, baseline_result: dict, cohort_result: dict,
                       snapshot: dict, scenario_protocol: dict, protocol: dict) -> dict:
    validate_protocol(protocol)
    validate_scenarios(scenario_protocol)
    baseline = SavantBaseline(snapshot)
    checked = analyze_cohort(preparation, baseline_result, baseline, scenario_protocol)
    if (checked["rows"] != cohort_result.get("rows")
            or checked["split_summaries"] != cohort_result.get("split_summaries")):
        raise ValueError("固定情境 cohort 與候選重算不符")
    summaries = defaultdict(lambda: {"actions": Counter(), "rra": [], "dynamic_minus_fixed": [],
                                   "dynamic_minus_never": [],
                                   "by_phase_side_budget": defaultdict(Counter)})
    records = []
    for game in preparation["game_rows"]:
        if game["status"] not in INCLUDED:
            continue
        path = Path(game["candidate_artifact"])
        if build_file_manifest(path, source_type="dataset_b_provisional_candidates") != game["candidate_manifest"]:
            raise ValueError(f"候選指紋不符：{game['game_pk']}")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact["game_pk"] != game["game_pk"] or artifact["split"] != game["split"]:
            raise ValueError("候選場次或切分不符")
        for row in artifact["rows"]:
            if row["analysis_labels"]["population"] != "provisional_opportunity":
                continue
            item = _candidate_valuation(row)
            valuation = item["valuation"]
            state = item["state"]
            if state.inning > 9:
                raise ValueError("延長賽候選不可進入主要策略")
            branches = (valuation["s0"], valuation["s1"])
            supported = all(isinstance(branch, dict) and branch.get("supported") is True
                            for branch in branches)
            record = {"game_pk": game["game_pk"], "split": game["split"],
                      "at_bat_number": row["at_bat_number"], "pitch_number": row["pitch_number"],
                      "inning": state.inning, "decision_side": valuation["decision_side"],
                      "challenges_remaining": item["budget"],
                      "status": "supported" if supported else "unsupported",
                      "valuation_status": item["status"], "scenarios": None}
            if supported:
                record["scenarios"] = {}
                for scenario in protocol["scenarios"]:
                    selected = None
                    for p in protocol["current_overturn_probability_grid"]:
                        result = solve_state(branches[0]["wp_decision"], branches[1]["wp_decision"],
                                             inning=state.inning, budget=item["budget"],
                                             terminal0=branches[0]["terminal"] is not None,
                                             terminal1=branches[1]["terminal"] is not None,
                                             probability=p, scenario=scenario,
                                             fixed_threshold=protocol["fixed_confidence_threshold"])
                        key = (game["split"], scenario["id"], str(p))
                        summary = summaries[key]
                        action = result["policies"]["dynamic"]["action"]
                        summary["actions"][action] += 1
                        summary["actions"][f"fixed_{result['policies']['fixed_confidence']['action']}"] += 1
                        if action != result["policies"]["fixed_confidence"]["action"]:
                            summary["actions"]["dynamic_fixed_disagree"] += 1
                        summary["dynamic_minus_fixed"].append(
                            result["policies"]["dynamic"]["value"]
                            - result["policies"]["fixed_confidence"]["value"])
                        summary["dynamic_minus_never"].append(
                            result["policies"]["dynamic"]["value"]
                            - result["policies"]["never"]["value"])
                        if result["synthetic_rra"]["probability"] is not None:
                            summary["rra"].append(result["synthetic_rra"]["probability"])
                        phase_key = f"{_phase(state.inning)}|{valuation['decision_side']}|{item['budget']}"
                        summary["by_phase_side_budget"][phase_key][action] += 1
                        if p == protocol["cohort_detail_probability"]:
                            selected = result
                    record["scenarios"][scenario["id"]] = {
                        "dynamic_action": selected["policies"]["dynamic"]["action"],
                        "fixed_action": selected["policies"]["fixed_confidence"]["action"],
                        "never_value": selected["policies"]["never"]["value"],
                        "fixed_value": selected["policies"]["fixed_confidence"]["value"],
                        "dynamic_value": selected["policies"]["dynamic"]["value"],
                        "model_values_by_budget": selected["model_values_by_budget"],
                        "synthetic_rra": selected["synthetic_rra"]}
                action_set = {item["dynamic_action"] for item in record["scenarios"].values()}
                record["scenario_robust_action"] = (
                    next(iter(action_set)) if len(action_set) == 1 else "scenario_sensitive")
            else:
                record["scenario_robust_action"] = "unsupported"
            records.append(record)
    split_summaries = {}
    for split in SPLITS:
        population = [row for row in records if row["split"] == split]
        expected = cohort_result["split_summaries"][split]
        if (len(population) != expected["provisional_candidates"]
                or sum(row["status"] == "supported" for row in population)
                != expected["support_counts"].get("supported", 0)):
            raise ValueError("策略母體與已核對的官方 WP 支援數不符")
        scenarios = {}
        for scenario in protocol["scenarios"]:
            by_p = {}
            for p in protocol["current_overturn_probability_grid"]:
                summary = summaries[(split, scenario["id"], str(p))]
                supported_count = expected["support_counts"].get("supported", 0)
                if summary["actions"]["challenge"] + summary["actions"]["save"] != supported_count:
                    raise ValueError("策略分母與可估值候選不符")
                by_p[str(p)] = {
                    "action_counts": dict(sorted(summary["actions"].items())),
                    "synthetic_rra_median_when_defined": median(summary["rra"]) if summary["rra"] else None,
                    "synthetic_rra_defined": len(summary["rra"]),
                    "mean_internal_dynamic_minus_fixed_value":
                        sum(summary["dynamic_minus_fixed"]) / supported_count if supported_count else None,
                    "mean_internal_dynamic_minus_never_value":
                        sum(summary["dynamic_minus_never"]) / supported_count if supported_count else None,
                    "by_game_phase_side_budget": {
                        name: dict(sorted(counts.items())) for name, counts
                        in sorted(summary["by_phase_side_budget"].items())}}
            scenarios[scenario["id"]] = by_p
        split_summaries[split] = {"games": expected["games"],
                                  "provisional_candidates": len(population),
                                  "both_wp_supported": expected["support_counts"].get("supported", 0),
                                  "unsupported": len(population) - expected["support_counts"].get("supported", 0),
                                  "scenario_robust_action_counts_at_detail_probability": dict(sorted(
                                      Counter(row["scenario_robust_action"] for row in population).items())),
                                  "scenario_probability_results": scenarios}
    return {"schema_version": "phase3-synthetic-regulation-cohort-v1",
            "purpose": "scenario_model_not_empirical_policy_evaluation",
            "scope": protocol["scope"],
            "split_summaries": split_summaries, "rows": records,
            "model_assumptions": protocol,
            "formal_legal_opportunity_ready": False,
            "counterfactual_transition_ready": False,
            "empirical_outside_continuation_ready": False,
            "formal_policy_evaluation_ready": False,
            "limitations": [
                "每個剩餘局數至多一個未來機會槽，機率和 WP 損失均為人工情境，非真實投球轉移。",
                "未來狀態僅是決策方 WP 值，不重建分差、跑壘、球數或對手挑戰。",
                "官方 WP 可已含歷史行為；人工未來損失與其是否重複計值尚未驗證。",
                "未來路徑的表外質量不能由此 WP-only 模型估計，正式 continuation 閘門保持 false。",
                "合成 RRA 與內部價值差不是球員準確率、因果增勝或樣本外政策績效。"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=ROOT / "config/phase3_synthetic_policy.json")
    parser.add_argument("--scenario-protocol", type=Path,
                        default=ROOT / "config/policy_scenario_protocol.json")
    parser.add_argument("--official-baseline", type=Path,
                        default=ROOT / "data/processed/savant_baseline_v2_2026-09-15.json")
    parser.add_argument("--state-input", type=Path)
    parser.add_argument("--preparation", type=Path)
    parser.add_argument("--baseline-result", type=Path)
    parser.add_argument("--cohort-result", type=Path)
    parser.add_argument("--phase2-closeout", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("拒絕覆寫既有 Phase 3 結果")
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    if args.state_input is not None:
        if any(value is not None for value in (
                args.preparation, args.baseline_result, args.cohort_result, args.phase2_closeout)):
            raise ValueError("單一狀態模式不可混用固定 cohort 輸入")
        result = evaluate_input_state(
            json.loads(args.official_baseline.read_text(encoding="utf-8")),
            json.loads(args.state_input.read_text(encoding="utf-8")), protocol)
        result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
            (args.protocol, "phase3_synthetic_policy_protocol"),
            (args.official_baseline, "official_wp_baseline"),
            (args.state_input, "policy_scenario_state_input"))]
        result["runtime"] = _runtime()
        atomic_json_new(args.output, result)
        return 0
    if any(value is None for value in (
            args.preparation, args.baseline_result, args.cohort_result, args.phase2_closeout)):
        raise ValueError("批次模式需提供 preparation、baseline-result、cohort-result 及 Phase 2 收尾")
    scenario_protocol = json.loads(args.scenario_protocol.read_text(encoding="utf-8"))
    preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
    baseline_result = json.loads(args.baseline_result.read_text(encoding="utf-8"))
    cohort_result = json.loads(args.cohort_result.read_text(encoding="utf-8"))
    closeout = json.loads(args.phase2_closeout.read_text(encoding="utf-8"))
    _verify_inputs(preparation, baseline_result, args.preparation)
    if (closeout.get("disposition") != "scoped_phase2_package_closed_formal_gate_not_passed"
            or closeout.get("gates", {}).get("phase3_assumption_limited_prototype_ready") is not True
            or closeout.get("gates", {}).get("formal_policy_evaluation_ready") is not False):
        raise ValueError("Phase 2 限定收尾閘門不符")
    expected = {item["source_type"]: item for item in cohort_result["input_manifests"]}
    for path, kind in ((args.preparation, "dataset_b_pretraining_preparation"),
                       (args.baseline_result, "dataset_b_observational_baseline"),
                       (args.official_baseline, "official_wp_baseline"),
                       (args.scenario_protocol, "policy_scenario_protocol")):
        if expected.get(kind) != build_file_manifest(path, source_type=kind):
            raise ValueError(f"情境 cohort 來源指紋不符：{kind}")
    closeout_inputs = {item["source_type"]: item for item in closeout["input_manifests"]}
    if closeout_inputs.get("policy_scenario_cohort") != build_file_manifest(
            args.cohort_result, source_type="policy_scenario_cohort"):
        raise ValueError("Phase 2 收尾結果與 cohort 指紋不符")
    result = analyze_population(preparation, baseline_result, cohort_result,
                                json.loads(args.official_baseline.read_text(encoding="utf-8")),
                                scenario_protocol, protocol)
    result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
        (args.protocol, "phase3_synthetic_policy_protocol"),
        (args.scenario_protocol, "policy_scenario_protocol"),
        (args.official_baseline, "official_wp_baseline"),
        (args.preparation, "dataset_b_pretraining_preparation"),
        (args.baseline_result, "dataset_b_observational_baseline"),
        (args.cohort_result, "policy_scenario_cohort"),
        (args.phase2_closeout, "phase2_closeout"))]
    result["runtime"] = _runtime()
    atomic_json_new(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
