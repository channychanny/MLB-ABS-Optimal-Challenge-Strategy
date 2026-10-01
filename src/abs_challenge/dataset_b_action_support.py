"""稽核 Dataset B 歷史行動重疊與額度耗盡；不估計反事實效果。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import median

from .phase1_cli import _runtime
from .provenance import build_file_manifest
from .source_cache import atomic_json_new


ROOT = Path(__file__).resolve().parents[2]
INCLUDED = {"provisional_population_pass", "provisional_population_recovered"}


def _phase(inning: int, protocol: dict) -> str:
    for name, bounds in protocol["game_phase_innings"].items():
        if bounds[0] <= inning <= bounds[1]:
            return name
    raise ValueError(f"局數不在研究範圍：{inning}")


def _verify_inputs(preparation: dict, baseline: dict, preparation_path: Path) -> None:
    if (baseline.get("schema_version") != "dataset-b-observational-baseline-results-v1"
            or baseline.get("observational_baseline_evaluation_completed") is not True):
        raise ValueError("到達基線版本或狀態不符")
    manifest = build_file_manifest(preparation_path, source_type="dataset_b_pretraining_preparation")
    if manifest not in baseline.get("input_manifests", []):
        raise ValueError("資料準備清冊與到達基線指紋不符")
    for item in baseline["input_manifests"]:
        if item != build_file_manifest(Path(item["source_path"]), source_type=item["source_type"]):
            raise ValueError("到達基線來源指紋不符")


def load_action_rows(preparation: dict, baseline: dict, protocol: dict) -> dict[str, list[dict]]:
    """重新核對候選指紋和下一同隊機會，僅提取稽核所需欄位。"""
    archived = {item["game_pk"]: item for item in baseline["candidate_manifests"]}
    games = [game for game in preparation["game_rows"] if game["status"] in INCLUDED]
    if len(games) != len(archived):
        raise ValueError("候選場次與基線清冊不符")
    output: dict[str, list[dict]] = defaultdict(list)
    for game in games:
        pk = game["game_pk"]
        path = Path(game["candidate_artifact"])
        manifest = build_file_manifest(path, source_type="dataset_b_provisional_candidates")
        if (manifest != game["candidate_manifest"]
                or archived.get(pk) != {"game_pk": pk, **manifest}):
            raise ValueError(f"候選來源指紋不符：{pk}")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if (artifact.get("schema_version") != "dataset-b-provisional-candidates-v2"
                or artifact.get("game_pk") != pk or artifact.get("split") != game["split"]
                or artifact.get("source_eligibility_status") != "provisional_source_limitations"):
            raise ValueError(f"候選契約不符：{pk}")
        rows = artifact["rows"]
        if any(a["physical_pitch_index"] >= b["physical_pitch_index"]
               for a, b in zip(rows, rows[1:])):
            raise ValueError(f"候選物理投球序列不遞增：{pk}")
        next_risk: dict[int, dict] = {}
        later_zero_budget: set[int] = set()
        game_output = []
        for row in reversed(rows):
            features = row["decision_features"]
            labels = row["analysis_labels"]
            team = features["decision_team_id"]
            population = labels["population"]
            if population == "zero_budget":
                if features["challenges_remaining"] != 0:
                    raise ValueError(f"零額度標籤不一致：{pk}")
                later_zero_budget.add(team)
                continue
            if population != protocol["risk_set_population"]:
                continue
            if features["challenges_remaining"] not in (1, 2):
                raise ValueError(f"風險集額度不一致：{pk}")
            action = labels["actual_challenge"]
            if type(action) is not bool:
                raise ValueError(f"歷史行動標籤缺失：{pk}")
            target = row["arrival_target"]
            next_row = next_risk.get(team)
            observed = next_row is not None
            if (target["next_opportunity_observed"] is not observed
                    or target["censoring_boundary"] != (None if observed else "regulation_end")
                    or (observed and target["pitch_gap"] !=
                        next_row["physical_pitch_index"] - row["physical_pitch_index"])):
                raise ValueError(f"下一同隊機會標籤不一致：{pk}")
            if not observed and team in later_zero_budget:
                if not action or features["challenges_remaining"] != 1:
                    raise ValueError(f"額度耗盡證據與最後風險集行動不一致：{pk}")
                boundary = "budget_exhaustion_evidenced"
            elif not observed and action and features["challenges_remaining"] == 1:
                boundary = "budget_or_regulation_unresolved"
            elif not observed:
                boundary = "regulation_end_without_budget_evidence"
            else:
                boundary = None
            game_output.append({
                "game_pk": pk,
                "game_phase": _phase(features["pre_pitch_state"]["inning"], protocol),
                "decision_side": features["decision_side"],
                "challenges_remaining": features["challenges_remaining"],
                "actual_challenge": action,
                "next_opportunity_observed": observed,
                "pitch_gap": target["pitch_gap"],
                "reclassified_boundary": boundary,
                "next_decision_side": next_row["decision_features"]["decision_side"] if observed else None,
                "next_challenges_remaining": next_row["decision_features"]["challenges_remaining"] if observed else None,
            })
            next_risk[team] = row
        output[game["split"]].extend(reversed(game_output))
    if sum(map(len, output.values())) != sum(
            baseline["evaluations"][split]["selected_model"]["episodes"] for split in output):
        raise ValueError("風險集筆數與基線不符")
    return dict(output)


def _summarize_action(rows: list[dict]) -> dict:
    observed = [row for row in rows if row["next_opportunity_observed"]]
    gaps = sorted(row["pitch_gap"] for row in observed)
    boundaries = Counter(row["reclassified_boundary"] for row in rows if not row["next_opportunity_observed"])
    return {"episodes": len(rows),
            "games": len({row["game_pk"] for row in rows}),
            "next_observed": len(observed),
            "observed_next_fraction": len(observed) / len(rows) if rows else None,
            "observed_next_pitch_gap_median": median(gaps) if gaps else None,
            "next_side_counts": dict(sorted(Counter(row["next_decision_side"] for row in observed).items())),
            "next_budget_counts": dict(sorted(Counter(row["next_challenges_remaining"] for row in observed).items())),
            "censoring_boundary_counts": dict(sorted(boundaries.items()))}


def analyze(rows_by_split: dict[str, list[dict]], protocol: dict) -> dict:
    if protocol.get("schema_version") != "dataset-b-action-support-protocol-v1":
        raise ValueError("行動支持規格版本不符")
    required = {protocol["training_split"], *protocol["evaluation_splits"]}
    if set(rows_by_split) != required:
        raise ValueError("訓練／驗證／測試切分不完整")
    split_summaries = {}
    for split, rows in rows_by_split.items():
        arms = {"challenge": _summarize_action([r for r in rows if r["actual_challenge"]]),
                "save": _summarize_action([r for r in rows if not r["actual_challenge"]])}
        split_summaries[split] = {"episodes": len(rows), "actions": arms}
    train_rows = rows_by_split[protocol["training_split"]]
    strata = defaultdict(list)
    for row in train_rows:
        key = (row["game_phase"], row["decision_side"], row["challenges_remaining"])
        strata[key].append(row)
    support = []
    for phase in protocol["game_phase_innings"]:
        for side in ("batting", "fielding"):
            for budget in (1, 2):
                key = (phase, side, budget)
                group = strata[key]
                challenged = [r for r in group if r["actual_challenge"]]
                saved = [r for r in group if not r["actual_challenge"]]
                rate = len(challenged) / len(group) if group else None
                pass_gate = (len(challenged) >= protocol["minimum_train_challenges_per_stratum"]
                             and len(saved) >= protocol["minimum_train_saves_per_stratum"]
                             and len({r["game_pk"] for r in challenged}) >=
                             protocol["minimum_train_challenge_games_per_stratum"]
                             and len({r["game_pk"] for r in saved}) >=
                             protocol["minimum_train_save_games_per_stratum"]
                             and rate is not None
                             and protocol["minimum_train_action_fraction"] <= rate <=
                             protocol["maximum_train_action_fraction"])
                support.append({"game_phase": phase, "decision_side": side,
                                "challenges_remaining": budget, "challenge_episodes": len(challenged),
                                "save_episodes": len(saved),
                                "challenge_games": len({r["game_pk"] for r in challenged}),
                                "save_games": len({r["game_pk"] for r in saved}),
                                "challenge_fraction": rate, "support_gate_pass": pass_gate})
    return {"schema_version": "dataset-b-action-support-results-v1",
            "scope": protocol["scope"],
            "split_summaries": split_summaries,
            "train_support_strata": support,
            "train_strata_passing": sum(row["support_gate_pass"] for row in support),
            "train_strata_total": len(support),
            "historical_action_overlap_gate_pass": all(row["support_gate_pass"] for row in support),
            "arrival_baseline_censoring_contract_valid": not any(
                r["reclassified_boundary"] == "budget_exhaustion_evidenced"
                for rows in rows_by_split.values() for r in rows),
            "formal_legal_opportunity_ready": False,
            "counterfactual_transition_ready": False,
            "formal_dynamic_policy_ready": False,
            "limitations": protocol["limitations"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--preparation", required=True, type=Path)
    parser.add_argument("--protocol", type=Path, default=ROOT / "config/dataset_b_action_support_protocol.json")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("拒絕覆寫既有行動支持稽核結果")
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    _verify_inputs(preparation, baseline, args.preparation)
    result = analyze(load_action_rows(preparation, baseline, protocol), protocol)
    result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
        (args.baseline, "dataset_b_observational_baseline"),
        (args.preparation, "dataset_b_pretraining_preparation"),
        (args.protocol, "dataset_b_action_support_protocol"))]
    result["candidate_manifests"] = baseline["candidate_manifests"]
    result["runtime"] = _runtime()
    atomic_json_new(args.output, result)
    print(json.dumps({"train_strata_passing": result["train_strata_passing"],
                      "train_strata_total": result["train_strata_total"],
                      "arrival_baseline_censoring_contract_valid": result["arrival_baseline_censoring_contract_valid"],
                      "formal_dynamic_policy_ready": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
