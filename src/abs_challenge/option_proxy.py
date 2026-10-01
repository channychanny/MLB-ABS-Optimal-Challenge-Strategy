"""Train-only 的兩個未來同隊不利判決額度價值近似；不是反事實轉移。"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

from .dataset_b_action_support import INCLUDED, _verify_inputs
from .phase1_cli import _runtime
from .provenance import build_file_manifest
from .source_cache import atomic_json_new
from .win_decision import assess_incremental_cost


ROOT = Path(__file__).resolve().parents[2]
SPLITS = ("train", "validation", "test", "external")


def validate_protocol(protocol: dict) -> None:
    if (protocol.get("schema_version") != "phase3-two-future-opportunity-proxy-v1"
            or protocol.get("training_split") != "train"
            or protocol.get("evaluation_splits") != ["validation", "test", "external"]
            or protocol.get("stratum_fields") != ["inning", "decision_side"]
            or protocol.get("unsupported_future_value_handling") != "excluded_from_mean_and_reported_not_zero_filled"
            or protocol.get("historical_actions_not_predictors") is not True
            or protocol.get("formal_counterfactual_option_value_ready") is not False):
        raise ValueError("未來額度近似的訓練／限制契約不符")
    alpha = protocol.get("smoothing_pseudo_candidates")
    if type(alpha) is not int or not 1 <= alpha <= 10000:
        raise ValueError("收縮候選數無效")
    ps = protocol.get("future_success_probability_sensitivity")
    reference = protocol.get("future_success_probability_reference")
    if (not isinstance(ps, list) or len(ps) < 3 or ps != sorted(set(ps))
            or reference not in ps or any(type(p) not in (int, float) or not 0 < p < 1 for p in ps)):
        raise ValueError("未來成功率敏感度格點無效")
    current_ps = protocol.get("current_success_probability_grid")
    if (not isinstance(current_ps, list) or not current_ps
            or current_ps != sorted(set(current_ps))
            or protocol.get("cohort_detail_current_probability") not in current_ps
            or any(type(p) not in (int, float) or not 0 < p < 1 for p in current_ps)):
        raise ValueError("當下成功率評估格點無效")


def _potential_value(row: dict) -> tuple[bool, float | None]:
    labels = row["analysis_labels"]
    s0, s1 = labels.get("s0"), labels.get("s1")
    if (not isinstance(s0, dict) or not isinstance(s1, dict)
            or s0.get("supported") is not True or s1.get("supported") is not True):
        return False, None
    w0, w1 = s0.get("wp_decision"), s1.get("wp_decision")
    if (type(w0) not in (int, float) or type(w1) not in (int, float)
            or not math.isfinite(w0) or not math.isfinite(w1)
            or not 0 <= w0 <= 1 or not 0 <= w1 <= 1):
        raise ValueError("後續候選的官方決策方 WP 無效")
    return True, max(0.0, w1 - w0)


def game_labels(rows: list[dict], *, game_pk: int, split: str) -> list[dict]:
    """後續資訊只產生監督標籤；服務時不讀該場未來球序。"""
    if any(a["physical_pitch_index"] >= b["physical_pitch_index"] for a, b in zip(rows, rows[1:])):
        raise ValueError("候選物理投球序列不遞增")
    by_team: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        if row["analysis_labels"]["population"] in ("provisional_opportunity", "zero_budget"):
            by_team[row["decision_features"]["decision_team_id"]].append(row)
    output = []
    for team_rows in by_team.values():
        for index, row in enumerate(team_rows):
            if row["analysis_labels"]["population"] != "provisional_opportunity":
                continue
            features = row["decision_features"]
            state = features["pre_pitch_state"]
            if not 1 <= state["inning"] <= 9 or features["decision_side"] not in ("batting", "fielding"):
                raise ValueError("主線候選局數或決策方無效")
            next_rows = team_rows[index + 1:index + 3]
            first = _potential_value(next_rows[0]) if next_rows else (False, None)
            current_supported, _ = _potential_value(row)
            current_delta = (row["analysis_labels"]["s1"]["wp_decision"]
                             - row["analysis_labels"]["s0"]["wp_decision"]
                             if current_supported else None)
            budget = features["challenges_remaining"]
            if type(budget) is not int or budget not in (1, 2):
                raise ValueError("當前風險集額度無效")
            output.append({
                "game_pk": game_pk, "split": split,
                "at_bat_number": row["at_bat_number"], "pitch_number": row["pitch_number"],
                "inning": state["inning"], "decision_side": features["decision_side"],
                "budget": budget,
                "current_wp_supported": current_supported,
                "current_delta_wp": current_delta,
                "s0_terminal": bool(current_supported and row["analysis_labels"]["s0"].get("terminal") is not None),
                "at_least_one_future": len(next_rows) >= 1,
                "at_least_two_future": len(next_rows) >= 2,
                "first_future_wp_supported": first[0] if next_rows else None,
                "first_future_positive_delta": first[1],
            })
    return output


def load_labels(preparation: dict, cohort_result: dict) -> dict[str, list[dict]]:
    expected = {(row["game_pk"], row["at_bat_number"], row["pitch_number"]): row
                for row in cohort_result["rows"]}
    if len(expected) != len(cohort_result["rows"]):
        raise ValueError("固定 cohort 事件鍵重複")
    by_split = defaultdict(list)
    included = [game for game in preparation["game_rows"] if game["status"] in INCLUDED]
    if len(included) != 91:
        raise ValueError("固定 91 場清冊不符")
    for game in included:
        path = Path(game["candidate_artifact"])
        if build_file_manifest(path, source_type="dataset_b_provisional_candidates") != game["candidate_manifest"]:
            raise ValueError("候選來源指紋不符")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact["game_pk"] != game["game_pk"] or artifact["split"] != game["split"]:
            raise ValueError("候選場次／切分不符")
        rows = game_labels(artifact["rows"], game_pk=game["game_pk"], split=game["split"])
        for row in rows:
            key = (row["game_pk"], row["at_bat_number"], row["pitch_number"])
            old = expected.pop(key, None)
            if (old is None or old["split"] != game["split"]
                    or old["decision_side"] != row["decision_side"]
                    or old["challenges_remaining"] != row["budget"]
                    or (old["status"] == "supported") != row["current_wp_supported"]
                    or (row["current_wp_supported"] and abs(
                        old["immediate_delta_wp"] - row["current_delta_wp"]) > 1e-12)):
                raise ValueError("未來機會起點與固定 cohort 不符")
        by_split[game["split"]].extend(rows)
    if expected or set(by_split) != set(SPLITS):
        raise ValueError("固定 cohort 有未核對的起點或切分")
    return dict(by_split)


def _stratum(row: dict) -> str:
    return f"{row['inning']}|{row['decision_side']}"


def _sufficient(rows: list[dict]) -> dict:
    supported = [row["first_future_positive_delta"] for row in rows
                 if row["first_future_positive_delta"] is not None]
    return {"starts": len(rows),
            "one": sum(row["at_least_one_future"] for row in rows),
            "two": sum(row["at_least_two_future"] for row in rows),
            "first_future_wp_supported": len(supported),
            "first_future_wp_unsupported": sum(
                row["at_least_one_future"] and row["first_future_wp_supported"] is False for row in rows),
            "positive_delta_sum": sum(supported)}


def fit(train: list[dict], protocol: dict) -> dict:
    validate_protocol(protocol)
    if not train or any(row["split"] != "train" for row in train):
        raise ValueError("只能使用非空 Train 標籤擬合")
    global_stats = _sufficient(train)
    if not global_stats["first_future_wp_supported"]:
        raise ValueError("Train 未來 WP 無可估值機會")
    global_q1 = global_stats["one"] / global_stats["starts"]
    global_q2 = global_stats["two"] / global_stats["starts"]
    global_delta = global_stats["positive_delta_sum"] / global_stats["first_future_wp_supported"]
    alpha = protocol["smoothing_pseudo_candidates"]
    strata = {}
    for inning in range(1, 10):
        for side in ("batting", "fielding"):
            key = f"{inning}|{side}"
            stats = _sufficient([row for row in train if _stratum(row) == key])
            n = stats["starts"]
            m = stats["first_future_wp_supported"]
            strata[key] = {"starts": n, "first_future_wp_supported": m,
                           "q_at_least_one": (stats["one"] + alpha * global_q1) / (n + alpha),
                           "q_at_least_two": (stats["two"] + alpha * global_q2) / (n + alpha),
                           "mean_positive_delta": (stats["positive_delta_sum"] + alpha * global_delta) / (m + alpha)}
    return {"schema_version": "phase3-two-future-opportunity-proxy-fit-v1",
            "training_split": "train", "features": ["inning", "decision_side"],
            "train_global": {**global_stats, "q_at_least_one": global_q1,
                             "q_at_least_two": global_q2, "mean_positive_delta": global_delta},
            "strata": strata, "smoothing_pseudo_candidates": alpha,
            "future_success_probability_reference": protocol["future_success_probability_reference"],
            "future_success_probability_sensitivity": protocol["future_success_probability_sensitivity"],
            "formal_counterfactual_option_value_ready": False}


def predict(model: dict, *, inning: int, decision_side: str, budget: int,
            future_success_probability: float | None = None) -> dict:
    if model.get("schema_version") != "phase3-two-future-opportunity-proxy-fit-v1":
        raise ValueError("未來額度模型版本不符")
    if (type(inning) is not int or not 1 <= inning <= 9
            or decision_side not in ("batting", "fielding")
            or type(budget) is not int or budget not in (1, 2)):
        raise ValueError("只接受九局內、有額度且攻守方明確的決策")
    p = (model["future_success_probability_reference"] if future_success_probability is None
         else future_success_probability)
    if type(p) not in (int, float) or not math.isfinite(p) or not 0 < p < 1:
        raise ValueError("未來翻判成功率須介於 0 與 1")
    params = model["strata"][f"{inning}|{decision_side}"]
    q1, q2, delta = (params["q_at_least_one"], params["q_at_least_two"],
                     params["mean_positive_delta"])
    # 同質兩機會有限樹：1 次額度在第一球成功後仍可用於第二球；
    # 第 2 次額度的邊際價值只在第一球失敗、且第二球存在時顯現。
    cost = (p * delta * (q1 + p * q2) if budget == 1
            else q2 * (1 - p) * p * delta)
    if cost > 1:
        raise ValueError("額度近似超出勝率機率單位，拒絕靜默截尾")
    return {"model_kind": "historical_exogenous_two_opportunity_proxy",
            "inning": inning, "decision_side": decision_side, "budget": budget,
            "future_success_probability_assumption": p,
            "q_at_least_one": q1, "q_at_least_two": q2,
            "mean_positive_delta_from_supported_first_future": delta,
            "estimated_incremental_failure_cost": cost,
            "train_stratum_starts": params["starts"],
            "train_stratum_first_future_wp_supported": params["first_future_wp_supported"],
            "not_counterfactual_or_calibrated_win_gain": True}


def evaluate(labels: dict[str, list[dict]], model: dict) -> dict:
    output = {}
    pooled = model["train_global"]
    for split in SPLITS:
        rows = labels[split]
        stats = _sufficient(rows)
        predictions = [model["strata"][_stratum(row)] for row in rows]
        q1_brier = sum((pred["q_at_least_one"] - row["at_least_one_future"]) ** 2
                       for pred, row in zip(predictions, rows)) / len(rows)
        q2_brier = sum((pred["q_at_least_two"] - row["at_least_two_future"]) ** 2
                       for pred, row in zip(predictions, rows)) / len(rows)
        supported = [(pred, row) for pred, row in zip(predictions, rows)
                     if row["first_future_positive_delta"] is not None]
        delta_mae = (sum(abs(pred["mean_positive_delta"] - row["first_future_positive_delta"])
                         for pred, row in supported) / len(supported) if supported else None)
        pooled_delta_mae = (sum(abs(pooled["mean_positive_delta"] - row["first_future_positive_delta"])
                                for _, row in supported) / len(supported) if supported else None)
        output[split] = {"games": len({row["game_pk"] for row in rows}), **stats,
                         "observed_one_rate": stats["one"] / stats["starts"],
                         "observed_two_rate": stats["two"] / stats["starts"],
                         "q1_brier": q1_brier, "q2_brier": q2_brier,
                         "pooled_q1_brier": sum((pooled["q_at_least_one"] - row["at_least_one_future"]) ** 2
                                                for row in rows) / len(rows),
                         "pooled_q2_brier": sum((pooled["q_at_least_two"] - row["at_least_two_future"]) ** 2
                                                for row in rows) / len(rows),
                         "first_future_supported_delta_mae": delta_mae,
                         "pooled_first_future_supported_delta_mae": pooled_delta_mae}
    return output


def analyze(preparation: dict, cohort_result: dict, protocol: dict) -> dict:
    labels = load_labels(preparation, cohort_result)
    model = fit(labels["train"], protocol)
    diagnostics = evaluate(labels, model)
    for split in SPLITS:
        if diagnostics[split]["starts"] != cohort_result["split_summaries"][split]["provisional_candidates"]:
            raise ValueError("未來價值近似與固定候選分母不符")
    decisions = {}
    for split in SPLITS:
        by_probability = {}
        for p in protocol["current_success_probability_grid"]:
            counts = {"challenge": 0, "save": 0, "tie": 0, "unsupported": 0}
            by_phase_side_budget = defaultdict(lambda: {"challenge": 0, "save": 0, "tie": 0})
            for row in labels[split]:
                if not row["current_wp_supported"]:
                    counts["unsupported"] += 1
                    continue
                estimated = predict(model, inning=row["inning"], decision_side=row["decision_side"],
                                    budget=row["budget"])
                cost = 0.0 if row["s0_terminal"] else estimated["estimated_incremental_failure_cost"]
                action = assess_incremental_cost(row["current_delta_wp"], p, cost)["action"]
                counts[action] += 1
                phase = "early" if row["inning"] <= 3 else "middle" if row["inning"] <= 6 else "late"
                by_phase_side_budget[f"{phase}|{row['decision_side']}|{row['budget']}"][action] += 1
            if sum(counts.values()) != diagnostics[split]["starts"]:
                raise ValueError("條件式建議分母不符")
            by_probability[str(p)] = {"action_counts": counts,
                                      "by_phase_side_budget": dict(sorted(by_phase_side_budget.items()))}
        decisions[split] = by_probability
    return {"schema_version": "phase3-two-future-opportunity-proxy-result-v1",
            "model": model, "split_diagnostics": diagnostics,
            "conditional_decision_counts": decisions,
            "estimand": "歷史路徑中未來至多兩個同隊不利判決的 Train-only 有限視野額度成本近似",
            "limitations": protocol["limitations"],
            "formal_counterfactual_option_value_ready": False,
            "formal_policy_evaluation_ready": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=ROOT / "config/phase3_option_proxy_protocol.json")
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--baseline-result", type=Path, required=True)
    parser.add_argument("--cohort-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("拒絕覆寫既有未來額度近似結果")
    preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
    baseline_result = json.loads(args.baseline_result.read_text(encoding="utf-8"))
    cohort_result = json.loads(args.cohort_result.read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    _verify_inputs(preparation, baseline_result, args.preparation)
    expected = {item["source_type"]: item for item in cohort_result["input_manifests"]}
    if any(item != build_file_manifest(Path(item["source_path"]), source_type=item["source_type"])
           for item in cohort_result["input_manifests"]):
        raise ValueError("固定官方 WP cohort 的上游來源指紋已變更")
    for path, kind in ((args.preparation, "dataset_b_pretraining_preparation"),
                       (args.baseline_result, "dataset_b_observational_baseline")):
        if expected.get(kind) != build_file_manifest(path, source_type=kind):
            raise ValueError("固定 cohort 上游指紋不符")
    result = analyze(preparation, cohort_result, protocol)
    result["official_baseline_manifest"] = expected["official_wp_baseline"]
    result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
        (args.protocol, "phase3_option_proxy_protocol"),
        (args.preparation, "dataset_b_pretraining_preparation"),
        (args.baseline_result, "dataset_b_observational_baseline"),
        (args.cohort_result, "policy_scenario_cohort"))]
    result["runtime"] = _runtime()
    atomic_json_new(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
