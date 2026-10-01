"""離線比較相同固定樣本的兩版批次，核對來源並重算 Train-only RE 開發統計。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from abs_challenge.historical import content_hash, verify_dataset
from abs_challenge.provenance import build_file_manifest
from abs_challenge.research_re import estimate_re_and_boundary
from abs_challenge.source_cache import atomic_json_new


def load_batch(report_path, artifact_dir):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    lock = report["dataset_lock"]
    if content_hash(lock) != report["dataset_lock_sha256"]:
        raise ValueError("批次 lock 指紋不符")
    datasets = {}
    for game in lock["games"]:
        path = artifact_dir / game["relative_path"]
        if not path.resolve().is_relative_to(artifact_dir.resolve()):
            raise ValueError("分片路徑超出指定資料目錄")
        shard = json.loads(path.read_text(encoding="utf-8"))
        if content_hash(shard) != game["shard_content_sha256"]:
            raise ValueError("批次分片指紋不符")
        dataset = shard["dataset"]
        verify_dataset(dataset)
        if dataset["dataset_content_sha256"] != game["dataset_content_sha256"]:
            raise ValueError("批次資料內容指紋不符")
        datasets[game["game_pk"]] = dataset
    return report, datasets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for prefix in ("before", "after"):
        parser.add_argument(f"--{prefix}-report", type=Path, required=True)
        parser.add_argument(f"--{prefix}-artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("保留既有比較報告，請指定新的輸出路徑")
    before, old = load_batch(args.before_report, args.before_artifacts)
    after, new = load_batch(args.after_report, args.after_artifacts)
    if before["plan"] != after["plan"] or set(old) != set(new):
        raise ValueError("兩版不是相同固定選樣，不可作本次比較")
    if before["dataset_lock"]["sources"] != after["dataset_lock"]["sources"]:
        raise ValueError("兩版原始來源 manifests 不一致")
    unchanged, changed, recovered, lost = [], [], [], []
    game_deltas = []
    for game_pk in sorted(old):
        a, b = old[game_pk], new[game_pk]
        if a["games"] and b["games"]:
            previous = [{k: v for k, v in row.items() if k != "alignment"} for row in a["rows"]]
            stripped = [{k: v for k, v in row.items() if k != "alignment"} for row in b["rows"]]
            (unchanged if previous == stripped else changed).append(game_pk)
        elif b["games"]:
            recovered.append(game_pk)
        elif a["games"]:
            lost.append(game_pk)
        game_deltas.append({"game_pk": game_pk, "before_pitches": len(a["rows"]),
            "after_pitches": len(b["rows"]), "alignment": b["games"][0]["alignment"] if b["games"] else None})
    estimates = {}
    for label, datasets in (("before", old), ("after", new)):
        re = estimate_re_and_boundary(list(datasets.values()))
        estimates[label] = {"summary": re["summary"], "regulation_boundary": re["regulation_boundary"],
            "re24_samples": sum(cell["n"] for cell in re["re24"]),
            "re288_samples": sum(cell["n"] for cell in re["re288"]),
            "re24": re["re24"], "re288": re["re288"]}
    result = {"schema_version": "historical-alignment-comparison-v1", "same_plan_and_sources": True,
        "before_lock_sha256": before["dataset_lock_sha256"], "after_lock_sha256": after["dataset_lock_sha256"],
        "unchanged_existing_games": unchanged, "changed_existing_games": changed,
        "recovered_games": recovered, "lost_games": lost, "games": game_deltas,
        "before_summary": before["summary"], "after_summary": after["summary"], "re_development": estimates,
        "after_runtime": after["runtime"], "formal_training_ready": False,
        "input_manifests": [build_file_manifest(path, source_type="historical_batch_report")
                            for path in (args.before_report, args.after_report)],
        "script_manifest": build_file_manifest(Path(__file__), source_type="python_validation_script")}
    atomic_json_new(args.output, result)
    print(json.dumps({"unchanged_existing_games": unchanged, "changed_existing_games": changed,
        "recovered_games": recovered, "lost_games": lost,
        "re": {k: {"summary": v["summary"], "re24_samples": v["re24_samples"],
                    "re288_samples": v["re288_samples"], "boundary": v["regulation_boundary"]}
               for k, v in estimates.items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
