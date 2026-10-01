"""核對批次分片，按年度／月份量化排除及稀有狀態，重算 Train-only 開發 RE。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from abs_challenge.historical import content_hash, score_band, verify_dataset
from abs_challenge.historical_batch import validate_plan
from abs_challenge.provenance import build_file_manifest
from abs_challenge.research_re import estimate_re_and_boundary
from abs_challenge.source_cache import atomic_json_new


def summarize(report, artifact_dir):
    """只接受可核對的開發批次；缺來源仍列入分母，不以成功場次取代。"""
    lock = report["dataset_lock"]
    if content_hash(lock) != report["dataset_lock_sha256"]:
        raise ValueError("批次 lock 指紋不符")
    validate_plan(report["plan"])
    if content_hash(report["plan"]) != lock["plan_sha256"]:
        raise ValueError("批次計畫與 lock 不符")
    records = lock["games"]
    ids = [r["game_pk"] for r in records]
    selected = [pk for day in lock["dates"] for pk in day.get("selected_game_pks", [])]
    if len(ids) != len(set(ids)) or sorted(ids) != sorted(selected):
        raise ValueError("選定場次與逐場結果不一致或重複")
    groups = {"season": defaultdict(Counter), "month": defaultdict(Counter)}
    reasons = Counter()
    datasets, games, rows = [], [], []
    for record in records:
        for name, key in (("season", record["game_date"][:4]), ("month", record["game_date"][:7])):
            groups[name][key]["selected"] += 1
            groups[name][key][record["status"]] += 1
        if record["status"] != "accepted":
            reasons[re.sub(r"打席 \d+：", "打席：", record.get("reason", "未提供原因"))] += 1
        if "relative_path" not in record:
            if record["status"] in {"accepted", "audit_excluded"}:
                raise ValueError("已稽核場次缺少分片")
            continue
        path = artifact_dir / record["relative_path"]
        if not path.resolve().is_relative_to(artifact_dir.resolve()):
            raise ValueError("分片路徑超出資料目錄")
        shard = json.loads(path.read_text(encoding="utf-8"))
        if content_hash(shard) != record["shard_content_sha256"]:
            raise ValueError("分片指紋不符")
        dataset = shard["dataset"]
        verify_dataset(dataset)
        if dataset["dataset_content_sha256"] != record["dataset_content_sha256"]:
            raise ValueError("資料內容指紋不符")
        members = dataset["games"] + dataset["excluded_games"]
        if [g["game_pk"] for g in members] != [record["game_pk"]]:
            raise ValueError("分片不是指定的單場結果")
        if bool(dataset["games"]) != (record["status"] == "accepted"):
            raise ValueError("納入狀態與分片不一致")
        if any(g["split"] not in {"train", "validation"} for g in dataset["games"]):
            raise ValueError("工程覆蓋不得納入 Test／External")
        datasets.append(dataset)
        games.extend(dataset["games"])
        rows.extend(dataset["rows"])
    coverage = {}
    for name, values in groups.items():
        coverage[name] = {key: {**dict(count),
            "not_accepted_fraction": 1 - count["accepted"] / count["selected"]}
            for key, count in sorted(values.items())}
    split_coverage = {}
    for split in ("train", "validation"):
        selected_rows = [row for row in rows if row["split"] == split]
        bands = {}
        for band in ("0-5", "6-10", "11+"):
            observed = [row for row in selected_rows if score_band(row["features"]["score_diff"]) == band]
            bands[band] = {"pitches": len(observed),
                "game_pks": sorted({row["game_pk"] for row in observed})}
        differences = [r["features"]["score_diff"] for r in selected_rows]
        split_coverage[split] = {"score_bands": bands,
            "score_diff_min": min(differences) if differences else None,
            "score_diff_max": max(differences) if differences else None,
            "walkoff_censored_game_pks": sorted({r["game_pk"] for r in selected_rows
                if not r["sampling"]["re_half_eligible"]})}
    ties = [{k: game[k] for k in ("game_pk", "season", "split", "home_win")}
            for game in games if game["regulation_tied"]]
    estimates = estimate_re_and_boundary(datasets) if any(g["split"] == "train" for g in games) else None
    return {"schema_version": "historical-coverage-review-v1",
        "dataset_lock_sha256": report["dataset_lock_sha256"],
        "runtime": report.get("runtime"), "date_status_counts": dict(Counter(d["status"] for d in lock["dates"])),
        "empty_or_failed_dates": [d for d in lock["dates"] if d["status"] != "selected"],
        "selected_games": len(records), "accepted_games": len(games), "regulation_pitches": len(rows),
        "coverage": coverage, "split_coverage": split_coverage,
        "grouped_exclusion_reasons": dict(reasons),
        "not_accepted_games": [r for r in records if r["status"] != "accepted"],
        "regulation_tied_games": ties, "re_development": estimates,
        "formal_training_ready": False, "formal_policy_evaluation_ready": False,
        "limitations": ["固定工程樣本非機率抽樣，排除比例只描述本次樣本，不推論全季。",
            "分差組場次可能重疊；投球非獨立樣本，不能用球數冒充有效場次。",
            "九局平手依年度列出；混合年度及少數比賽的平均不作正式邊界。",
            "未估計 WP 或其不確定性；大比分數值範圍及格子有觀測不代表估值可靠。"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("保留既有覆蓋報告，請指定新輸出檔名")
    result = summarize(json.loads(args.report.read_text(encoding="utf-8")), args.artifacts)
    result["input_manifest"] = build_file_manifest(args.report, source_type="historical_batch_report")
    result["script_manifest"] = build_file_manifest(Path(__file__), source_type="python_validation_script")
    atomic_json_new(args.output, result)
    print(json.dumps({key: value for key, value in result.items()
                     if key not in {"re_development", "not_accepted_games"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
