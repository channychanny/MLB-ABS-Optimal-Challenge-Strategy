"""驗證 Dataset B 限定觀察性模型輸入的固定清冊與防洩漏契約。"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from .dataset_b_sampling import validate_sampling_plan
from .phase1_cli import _runtime
from .provenance import build_file_manifest
from .source_cache import atomic_json_new


def validate_candidate_sequence(rows: list[dict], *, risk_set: str) -> None:
    """確認到達標籤只以同隊的下一個風險集候選為事件。"""
    next_by_team: dict[int, int] = {}
    previous_index = 0
    for candidate in rows:
        index = candidate["physical_pitch_index"]
        if type(index) is not int or index <= previous_index:
            raise ValueError("候選物理投球序號並非嚴格遞增")
        previous_index = index
    for candidate in reversed(rows):
        team = candidate["decision_features"]["decision_team_id"]
        index = candidate["physical_pitch_index"]
        target = candidate["arrival_target"]
        next_index = next_by_team.get(team)
        if (type(target["pitch_gap"]) is not int or target["pitch_gap"] < 0
                or type(target["next_opportunity_observed"]) is not bool):
            raise ValueError("到達或右設限標籤型別無效")
        if next_index is None:
            if target["next_opportunity_observed"] or target["censoring_boundary"] != "regulation_end":
                raise ValueError("最後一個同隊機會必須右設限")
        elif (target["next_opportunity_observed"] is not True
              or target["pitch_gap"] != next_index - index
              or target["censoring_boundary"] is not None):
            raise ValueError("下一個同隊風險集機會的到達間隔不符")
        if candidate["analysis_labels"]["population"] == risk_set:
            next_by_team[team] = index


def validate_inputs(selection: dict, preparation: dict, policy: dict) -> dict:
    if policy.get("schema_version") != "dataset-b-limited-model-input-policy-v1":
        raise ValueError("Dataset B 限定模型輸入政策版本不符")
    validate_sampling_plan(selection["sampling_plan"], selection["split_plan"])
    lock = {key: selection[key] for key in ("sampling_plan", "split_plan", "windows", "sources")}
    fingerprint = sha256(json.dumps(lock, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    selected = [row for window in selection["windows"] for row in window["selected"]]
    selected_ids = {row["game_pk"] for row in selected}
    if (selection.get("selection_complete") is not True
            or len(selected_ids) != len(selected) == policy["expected_selected_games"]
            or fingerprint != selection["selection_sha256"]
            or selected_ids & set(selection["split_plan"]["known_development_game_pks"])
            or selection["selection_sha256"] != policy["selection_sha256"]
            or preparation["selection_sha256"] != policy["selection_sha256"]):
        raise ValueError("固定選場、樣本數或來源報告指紋不符")
    game_rows = preparation["game_rows"]
    if (len(game_rows) != len(selected) or len({row["game_pk"] for row in game_rows}) != len(game_rows)
            or {row["game_pk"] for row in game_rows} != selected_ids):
        raise ValueError("準備報告缺場、重複或混入選場清冊外比賽")
    if policy["replacement"] is not False:
        raise ValueError("不得以結果替補未對齊場次")
    excluded = {row["game_pk"] for row in game_rows if row["status"] == "recovery_unresolved"}
    if excluded != set(policy["unlocalized_game_pks"]):
        raise ValueError("官方缺球排除清冊與實際失敗不一致")
    included = [row for row in game_rows if row["game_pk"] not in excluded]
    if (len(included) != policy["expected_included_games"]
            or Counter(row["split"] for row in included) != policy["expected_split_games"]
            or sum(row["status"] == "provisional_population_recovered" for row in included)
            != policy["expected_recovered_games"]):
        raise ValueError("納入場次、split 或安全復原數量不符")
    selected_by_pk = {row["game_pk"]: row for row in selected}
    feature_fields = set(policy["feature_fields"])
    target_fields = set(policy["target_fields"])
    state_fields = {"inning", "half", "outs", "bases", "balls", "strikes", "home_score", "away_score"}
    if feature_fields != {"pre_pitch_state", "challenges_remaining", "original_call",
                          "decision_team_id", "decision_side"}:
        raise ValueError("模型特徵白名單已變更，需重新審核防洩漏契約")
    if policy["risk_set_population"] != "provisional_opportunity":
        raise ValueError("Future Opportunity 風險集必須預先鎖定")
    counts = Counter()
    by_split = {split: Counter() for split in ("train", "validation", "test", "external")}
    for row in included:
        selected_row = selected_by_pk[row["game_pk"]]
        if (row["status"] not in {"provisional_population_pass", "provisional_population_recovered"}
                or row.get("official_counter_pass") is not True
                or any(row[key] != selected_row[key] for key in ("date", "split", "window", "regime"))):
            raise ValueError(f"場次 {row['game_pk']} 未通過官方計數或時間切分")
        path = Path(row["candidate_artifact"])
        if row["candidate_manifest"] != build_file_manifest(path, source_type="dataset_b_provisional_candidates"):
            raise ValueError(f"場次 {row['game_pk']} 候選檔來源指紋不符")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if (artifact.get("schema_version") != "dataset-b-provisional-candidates-v2"
                or artifact["game_pk"] != row["game_pk"] or artifact["split"] != row["split"]
                or len(artifact["rows"]) != row["candidate_count"]
                or artifact["source_eligibility_status"] != "provisional_source_limitations"):
            raise ValueError(f"場次 {row['game_pk']} 候選檔契約不符")
        previous_index = 0
        for candidate in artifact["rows"]:
            label = candidate["analysis_labels"]
            target = candidate["arrival_target"]
            if (set(candidate["decision_features"]) != feature_fields
                    or set(candidate["decision_features"]["pre_pitch_state"]) != state_fields
                    or set(target) != target_fields
                    or candidate["physical_pitch_index"] <= previous_index
                    or type(target["pitch_gap"]) is not int or target["pitch_gap"] < 0
                    or type(target["next_opportunity_observed"]) is not bool
                    or candidate["source_eligibility"]["abs_technical_availability"] != "unknown"
                    or candidate["source_eligibility"]["post_replay_challenge_eligibility"] != "unknown"):
                raise ValueError(f"場次 {row['game_pk']} 特徵、時間或來源資格契約不符")
            previous_index = candidate["physical_pitch_index"]
            counts[label["population"]] += 1
            by_split[row["split"]][label["population"]] += 1
            counts["arrival_observed" if target["next_opportunity_observed"] else "arrival_censored"] += 1
            if label["population"] == policy["risk_set_population"]:
                counts["risk_arrival_observed" if target["next_opportunity_observed"] else "risk_arrival_censored"] += 1
                by_split[row["split"]]["risk_arrival_observed" if target["next_opportunity_observed"] else "risk_arrival_censored"] += 1
        validate_candidate_sequence(artifact["rows"], risk_set=policy["risk_set_population"])
    if counts["provisional_opportunity"] == 0 or counts["risk_arrival_censored"] == 0:
        raise ValueError("觀察性候選或右設限風險集為空")
    return {"schema_version": "dataset-b-limited-model-input-gate-v1",
            "selected_games": len(selected), "included_games": len(included),
            "excluded_unlocalized_game_pks": sorted(excluded),
            "split_games": dict(sorted(Counter(row["split"] for row in included).items())),
            "candidate_counts": dict(sorted(counts.items())),
            "candidate_counts_by_split": {key: dict(sorted(value.items())) for key, value in by_split.items()},
            "limited_observational_baseline_input_ready": True,
            "formal_legal_opportunity_ready": False,
            "formal_dynamic_policy_ready": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("不得覆寫既有 Dataset B 輸入閘門報告")
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    result = validate_inputs(selection, preparation, policy)
    result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
        (args.selection, "dataset_b_schedule_selection"),
        (args.preparation, "dataset_b_pretraining_preparation"),
        (args.policy, "dataset_b_model_input_policy"))]
    result["runtime"] = _runtime()
    atomic_json_new(args.output, result)
    print(json.dumps({"included_games": result["included_games"],
                      "limited_observational_baseline_input_ready": result["limited_observational_baseline_input_ready"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
