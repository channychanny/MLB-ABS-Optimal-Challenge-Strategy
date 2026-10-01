"""稽核固定候選的事前資訊與歷史後續機會；不估計最優策略。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from .option_proxy import SPLITS, load_labels
from .phase1_cli import _runtime
from .provenance import build_file_manifest
from .source_cache import atomic_json_new


ROOT = Path(__file__).resolve().parents[2]


def _delta_bin(value: float) -> str:
    """事先固定的情境勝率差級距；不是挑戰門檻。"""
    if value <= 0:
        return "nonpositive"
    if value < 0.005:
        return "positive_below_0.5pp"
    if value < 0.02:
        return "0.5pp_to_below_2pp"
    return "at_least_2pp"


def summarize(rows: list[dict]) -> dict:
    if len({(r["game_pk"], r["at_bat_number"], r["pitch_number"]) for r in rows}) != len(rows):
        raise ValueError("固定候選事件鍵重複")
    supported = [r for r in rows if r["current_wp_supported"]]
    first = [r for r in rows if r["at_least_one_future"]]
    first_supported = [r for r in first if r["first_future_wp_supported"]]
    return {
        "candidate_starts": len(rows),
        "current_wp_supported": len(supported),
        "current_wp_unsupported": len(rows) - len(supported),
        "current_hypothetical_delta_wp_bins": dict(sorted(Counter(
            _delta_bin(r["current_delta_wp"]) for r in supported).items())),
        "historical_next_adverse_call_observed": len(first),
        "historical_second_adverse_call_observed": sum(r["at_least_two_future"] for r in rows),
        "historical_no_next_observed": len(rows) - len(first),
        "next_call_wp_supported": len(first_supported),
        "next_call_wp_unsupported": len(first) - len(first_supported),
        "next_call_hypothetical_delta_wp_bins": dict(sorted(Counter(
            _delta_bin(r["first_future_positive_delta"]) for r in first_supported).items())),
    }


def analyze(preparation: dict, cohort: dict) -> dict:
    """完整保留風險集，不按實際挑戰或 ABS 正誤挑選球。"""
    by_split = load_labels(preparation, cohort)
    if set(by_split) != set(SPLITS):
        raise ValueError("固定切分不完整")
    summaries = {}
    for split in SPLITS:
        rows = by_split[split]
        expected = cohort["split_summaries"][split]["provisional_candidates"]
        if len(rows) != expected:
            raise ValueError(f"{split} 候選分母不符")
        summaries[split] = summarize(rows)
    return {
        "schema_version": "phase3-decision-time-feasibility-audit-v1",
        "population": "dataset_b_provisional_opportunity_all_adverse_calls_with_budget",
        "splits": summaries,
        "interpretation": {
            "delta_wp": "依當時 Game State 假設翻判的官方 S1 減 S0；不表示該球實際會翻判",
            "future": "沿歷史實際球序的同隊不利判決，包含後來零額度時的潛在判決；無下一筆是觀察範圍內未見，不等於沒有未來機會，亦非改變行動後的反事實到達率",
            "future_delta": "沿用既有原型的非負截斷 max(0, S1-S0)，僅供描述下一個觀察到的判決；不得當成已知翻判正誤或實際收益",
            "bins": "描述情境勝率差，不是值得挑戰的標籤或正式決策門檻",
        },
        "actual_challenge_or_overturn_used_as_filter": False,
        "formal_counterfactual_option_value_ready": False,
        "formal_policy_evaluation_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--cohort-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("拒絕覆寫既有可行性稽核結果")
    preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
    cohort = json.loads(args.cohort_result.read_text(encoding="utf-8"))
    for item in cohort["input_manifests"]:
        if item != build_file_manifest(Path(item["source_path"]), source_type=item["source_type"]):
            raise ValueError("固定 cohort 上游來源指紋不符")
    expected = next(item for item in cohort["input_manifests"]
                    if item["source_type"] == "dataset_b_pretraining_preparation")
    if expected != build_file_manifest(args.preparation, source_type=expected["source_type"]):
        raise ValueError("資料準備清冊指紋不符")
    result = analyze(preparation, cohort)
    result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
        (args.preparation, "dataset_b_pretraining_preparation"),
        (args.cohort_result, "policy_scenario_cohort"))]
    result["runtime"] = _runtime()
    atomic_json_new(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
