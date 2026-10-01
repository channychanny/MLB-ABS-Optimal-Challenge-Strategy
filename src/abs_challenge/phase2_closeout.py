"""官方 WP 主線 Phase 2 的限定收尾稽核；不把未知資格升格為正式 Legal。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path

from .baseline import SavantBaseline
from .dataset_b_action_support import INCLUDED, _verify_inputs
from .phase1_cli import _runtime
from .policy_scenarios import _candidate_valuation, analyze_cohort, evaluate_valuation, validate_protocol
from .provenance import build_file_manifest
from .source_cache import atomic_json_new
from .wp_coverage import inspect_call


ROOT = Path(__file__).resolve().parents[2]
SPLITS = ("train", "validation", "test", "external")


def validate_closeout_protocol(closeout: dict, scenario_protocol: dict, baseline: SavantBaseline) -> None:
    if (closeout.get("schema_version") != "official-wp-phase2-closeout-v1"
            or closeout.get("source_unknown_not_legal") is not True
            or closeout.get("synthetic_boundary_values_not_empirical_interval") is not True
            or closeout.get("formal_legal_opportunity_ready") is not False
            or closeout.get("counterfactual_transition_ready") is not False
            or closeout.get("formal_policy_evaluation_ready") is not False):
        raise ValueError("Phase 2 收尾契約不可升格未知來源或正式策略")
    validate_protocol(scenario_protocol)
    grid = closeout.get("boundary_home_wp_sensitivity")
    reference = closeout.get("boundary_reference_home_wp")
    if (not isinstance(grid, list) or len(grid) < 3
            or any(type(value) not in (int, float) or not 0 <= value <= 1 for value in grid)
            or grid != sorted(set(grid)) or reference not in grid
            or reference != baseline.boundary):
        raise ValueError("九局平手敏感度格點或官方參考值無效")
    if closeout.get("decision_scenario_id") not in {item["id"] for item in scenario_protocol["scenarios"]}:
        raise ValueError("敏感度情境未在決策規格宣告")
    probability = closeout.get("decision_overturn_probability_assumption")
    if (type(probability) not in (int, float)
            or probability not in scenario_protocol["overturn_probability_grid"]):
        raise ValueError("敏感度成功率未在決策格點宣告")


def _alternate_baseline(snapshot: dict, value: float) -> SavantBaseline:
    alternate = deepcopy(snapshot)
    alternate["regulation_boundary"]["home_win_probability"] = value
    return SavantBaseline(alternate)


def _decision(valuation: dict, budget: int, protocol: dict, scenario_id: str,
              probability: float) -> str:
    result = evaluate_valuation(valuation, budget, protocol)
    if result["status"] != "supported":
        return "unsupported"
    scenario = next(item for item in result["scenario_results"] if item["scenario_id"] == scenario_id)
    return next(item["action"] for item in scenario["decisions"]
                if item["probability"] == probability)


def build_closeout(preparation: dict, baseline_result: dict, cohort_result: dict,
                   snapshot: dict, scenario_protocol: dict, closeout_protocol: dict) -> dict:
    baseline = SavantBaseline(snapshot)
    validate_closeout_protocol(closeout_protocol, scenario_protocol, baseline)
    verified = analyze_cohort(preparation, baseline_result, baseline, scenario_protocol)
    if (verified["split_summaries"] != cohort_result.get("split_summaries")
            or verified["rows"] != cohort_result.get("rows")):
        raise ValueError("情境 cohort 與固定候選重算結果不符")
    included = [game for game in preparation["game_rows"] if game["status"] in INCLUDED]
    excluded = [game for game in preparation["game_rows"] if game["status"] not in INCLUDED]
    if (len(preparation["game_rows"]) != 96 or len(included) != 91 or len(excluded) != 5
            or set(game["split"] for game in included) != set(SPLITS)):
        raise ValueError("固定 96 場選樣與 91／5 處置不符")
    if any(game["source_eligibility_status"] != "provisional_source_limitations"
           or game["eligibility_source_audit"]["technical_interval_coverage"] != "unknown"
           or game["eligibility_source_audit"]["post_replay_ordering_coverage"] != "unknown"
           for game in included):
        raise ValueError("來源資格證據已變動，須重新設計閘門")
    if any(game["status"] != "recovery_unresolved" for game in excluded):
        raise ValueError("五場排除原因已變動")

    baselines = {str(value): _alternate_baseline(snapshot, value)
                 for value in closeout_protocol["boundary_home_wp_sensitivity"]}
    reference_key = str(closeout_protocol["boundary_reference_home_wp"])
    scenario_id = closeout_protocol["decision_scenario_id"]
    probability = closeout_protocol["decision_overturn_probability_assumption"]
    eligibility = Counter()
    inning_range = Counter()
    tied_terminal = Counter()
    changes = defaultdict(Counter)
    support_changes = defaultdict(Counter)
    by_split = Counter()
    tie_rows = []
    for game in included:
        pk = game["game_pk"]
        artifact_path = Path(game["candidate_artifact"])
        if build_file_manifest(artifact_path, source_type="dataset_b_provisional_candidates") != game["candidate_manifest"]:
            raise ValueError(f"候選檔指紋不符：{pk}")
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        if artifact["game_pk"] != pk or artifact["split"] != game["split"]:
            raise ValueError(f"候選場次或切分不符：{pk}")
        for row in artifact["rows"]:
            if row["analysis_labels"]["population"] != "provisional_opportunity":
                continue
            info = _candidate_valuation(row)
            state = info["state"]
            if not 1 <= state.inning <= 9:
                raise ValueError(f"第十局以後候選進入主要母體：{pk}")
            inning_range[str(state.inning)] += 1
            by_split[game["split"]] += 1
            source = row["source_eligibility"]
            pair = (source["abs_technical_availability"],
                    source["post_replay_challenge_eligibility"])
            eligibility["|".join(pair)] += 1
            if pair != ("unknown", "unknown"):
                raise ValueError("逐球來源資格已變動，不能沿用未知閘門")
            if info["status"] == "unsupported_compound_event":
                continue
            original = inspect_call(baselines[reference_key], state, info["original_call"])
            is_tie = any(original[branch] and original[branch].get("terminal") == "regulation_tie"
                         for branch in ("s0", "s1"))
            if not is_tie:
                continue
            tied_terminal[game["split"]] += 1
            base_action = _decision(original, info["budget"], scenario_protocol, scenario_id, probability)
            tie_row = {"game_pk": pk, "split": game["split"],
                       "at_bat_number": row["at_bat_number"], "pitch_number": row["pitch_number"],
                       "decision_side": original["decision_side"],
                       "challenges_remaining": info["budget"],
                       "reference_action": base_action, "actions_by_home_wp": {}}
            for value, alternate in baselines.items():
                changed = inspect_call(alternate, state, info["original_call"])
                action = _decision(changed, info["budget"], scenario_protocol, scenario_id, probability)
                tie_row["actions_by_home_wp"][value] = action
                if (action == "unsupported") != (base_action == "unsupported"):
                    support_changes[value][game["split"]] += 1
                if action != base_action:
                    changes[value][game["split"]] += 1
            tie_rows.append(tie_row)
    if dict(by_split) != {split: cohort_result["split_summaries"][split]["provisional_candidates"]
                          for split in SPLITS}:
        raise ValueError("主要風險集數量與情境結果不符")
    if changes[reference_key] or support_changes[reference_key]:
        raise ValueError("參考九局平手邊界重算不一致")
    return {
        "schema_version": "official-wp-phase2-closeout-result-v1",
        "disposition": "scoped_phase2_package_closed_formal_gate_not_passed",
        "selected_games": len(preparation["game_rows"]),
        "included_games": len(included),
        "excluded_games": len(excluded),
        "excluded_game_pks": sorted(game["game_pk"] for game in excluded),
        "included_extra_inning_games": {
            split: sum(game["split"] == split and game["actual_extra_innings"] for game in included)
            for split in SPLITS},
        "regulation_candidate_counts_by_inning": dict(sorted(inning_range.items(), key=lambda item: int(item[0]))),
        "regulation_candidate_counts_by_split": {split: by_split[split] for split in SPLITS},
        "source_eligibility_pairs": dict(sorted(eligibility.items())),
        "both_sides_wp_supported": {
            split: cohort_result["split_summaries"][split]["support_counts"].get("supported", 0)
            for split in SPLITS},
        "boundary_sensitivity": {
            "reference_home_wp": baseline.boundary,
            "synthetic_home_wp_grid": closeout_protocol["boundary_home_wp_sensitivity"],
            "scenario_id": scenario_id,
            "overturn_probability_assumption": probability,
            "regulation_tie_candidate_counts_by_split": {split: tied_terminal[split] for split in SPLITS},
            "direct_regulation_tie_rows": tie_rows,
            "action_changes_from_reference_by_home_wp": {
                value: {split: changes[value][split] for split in SPLITS} for value in baselines},
            "support_changes_from_reference_by_home_wp": {
                value: {split: support_changes[value][split] for split in SPLITS} for value in baselines},
            "values_are_synthetic_stress_tests_not_confidence_bounds": True,
        },
        "gates": {
            "fixed_regulation_candidate_scope_audited": True,
            "source_eligibility_unknown_explicit": True,
            "current_s0_s1_coverage_audited": True,
            "boundary_stress_test_run": True,
            "empirical_outside_continuation_ready": False,
            "development_registry_complete": False,
            "formal_legal_opportunity_ready": False,
            "counterfactual_transition_ready": False,
            "formal_policy_evaluation_ready": False,
            "phase3_assumption_limited_prototype_ready": True,
        },
        "limitations": [
            "7 場來源比賽進入延長賽，但主要候選只含第 1–9 局；不得刪除來源稽核資料。",
            "ABS 技術停用與 replay 後資格逐球未知，不得宣稱完整 Legal Opportunity。",
            "人工九局平手邊界格點不是經驗可信區間，也不估計延長賽策略。",
            "敏感度只重算當前 S0／S1 直接接到九局平手的分支，不會傳遞至較早局數的未來政策路徑。",
            "表外未來路徑、行動依賴反事實及成功率尚未識別；不得宣稱正式 RRA。",
            "2025 Test 不是固定官方 WP 快照的完全獨立樣本外驗證。",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--baseline-result", type=Path, required=True)
    parser.add_argument("--cohort-result", type=Path, required=True)
    parser.add_argument("--official-baseline", type=Path,
                        default=ROOT / "data/processed/savant_baseline_v2_2026-09-15.json")
    parser.add_argument("--scenario-protocol", type=Path,
                        default=ROOT / "config/policy_scenario_protocol.json")
    parser.add_argument("--closeout-protocol", type=Path,
                        default=ROOT / "config/phase2_closeout_protocol.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("拒絕覆寫既有 Phase 2 收尾結果")
    preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
    baseline_result = json.loads(args.baseline_result.read_text(encoding="utf-8"))
    cohort_result = json.loads(args.cohort_result.read_text(encoding="utf-8"))
    scenario_protocol = json.loads(args.scenario_protocol.read_text(encoding="utf-8"))
    closeout_protocol = json.loads(args.closeout_protocol.read_text(encoding="utf-8"))
    _verify_inputs(preparation, baseline_result, args.preparation)
    expected = {item["source_type"]: item for item in cohort_result["input_manifests"]}
    for path, kind in ((args.preparation, "dataset_b_pretraining_preparation"),
                       (args.baseline_result, "dataset_b_observational_baseline"),
                       (args.official_baseline, "official_wp_baseline"),
                       (args.scenario_protocol, "policy_scenario_protocol")):
        if expected.get(kind) != build_file_manifest(path, source_type=kind):
            raise ValueError(f"情境原型來源指紋不符：{kind}")
    result = build_closeout(preparation, baseline_result, cohort_result,
                            json.loads(args.official_baseline.read_text(encoding="utf-8")),
                            scenario_protocol, closeout_protocol)
    result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
        (args.preparation, "dataset_b_pretraining_preparation"),
        (args.baseline_result, "dataset_b_observational_baseline"),
        (args.cohort_result, "policy_scenario_cohort"),
        (args.official_baseline, "official_wp_baseline"),
        (args.scenario_protocol, "policy_scenario_protocol"),
        (args.closeout_protocol, "phase2_closeout_protocol"))]
    result["runtime"] = _runtime()
    atomic_json_new(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
