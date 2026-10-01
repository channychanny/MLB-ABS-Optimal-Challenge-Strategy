"""從固定官方清冊建立逐月全季取得計畫；容量估計不代表資料已下載。"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
import statistics

from abs_challenge.historical import content_hash, verify_dataset
from abs_challenge.historical_batch import (
    ALLOWED_SEASONS, feed_count, normalize_schedule, pitch_count, schedule_count,
    schedule_url, validate_plan,
)
from abs_challenge.provenance import build_file_manifest
from abs_challenge.source_cache import SourceCache, atomic_json_new


def build_campaign(cache):
    """完整列出五年度所有候選及清冊排除，依月份切分而不抽樣。"""
    months, sources, summaries, excluded = defaultdict(list), [], [], []
    seen_games = set()
    for season in sorted(ALLOWED_SEASONS):
        source = cache.get(schedule_url(season), "mlb_schedule_json", schedule_count)
        catalog = normalize_schedule(source["text"], season)
        sources.append(source["manifest"])
        summaries.append({"season": season, **catalog["summary"], "catalog_sha256": content_hash(catalog)})
        for game in catalog["games"]:
            if game["game_pk"] in seen_games:
                raise ValueError("不同年度清冊重複包含同一 game_pk")
            seen_games.add(game["game_pk"])
            if game["eligible"]:
                months[game["game_date"][:7]].append(game)
            else:
                excluded.append(game)
    batches = []
    for month, games in sorted(months.items()):
        plan = {"schema_version": "historical-batch-plan-v1", "purpose": "engineering_sample",
            "seasons": [int(month[:4])], "dates": sorted({g["game_date"] for g in games}),
            "games_per_date": None, "selection": "lowest_game_pk_among_final_regular_games",
            "notes": "全季取得計畫的單月工程批次：取固定清冊所有候選，非正式訓練資料鎖定。"}
        validate_plan(plan)
        batches.append({"month": month, "plan": plan, "plan_sha256": content_hash(plan),
                        "expected_game_pks": sorted(g["game_pk"] for g in games)})
    return {"schema_version": "historical-acquisition-campaign-v1", "seasons": sorted(ALLOWED_SEASONS),
        "schedule_sources": sources, "catalog_summaries": summaries,
        "catalog_excluded_games": excluded, "months": batches,
        "expected_games": sum(len(b["expected_game_pks"]) for b in batches),
        "expected_dates": sum(len(b["plan"]["dates"]) for b in batches),
        "formal_training_ready": False, "full_season_coverage_verified": False}


def measure_storage(reference, artifacts, cache, campaign):
    """核對參考批次後，以快取實際檔案大小估計一版全季空間。"""
    lock = reference["dataset_lock"]
    if content_hash(lock) != reference["dataset_lock_sha256"]:
        raise ValueError("參考批次 lock 不符")
    counters = {"mlb_schedule_json": schedule_count, "mlb_stats_api_feed_json": feed_count,
                "baseball_savant_pitch_csv": pitch_count}
    sizes = defaultdict(list)
    for manifest in lock["sources"]:
        url, kind = manifest["source_url"], manifest["source_type"]
        source = cache.get(url, kind, counters[kind])
        if source["manifest"] != manifest:
            raise ValueError("參考批次來源已變更")
        sizes[kind].append(cache.path_for(url).stat().st_size)
    for game in lock["games"]:
        path = artifacts / game["relative_path"]
        if not path.resolve().is_relative_to(artifacts.resolve()):
            raise ValueError("分片路徑超出資料目錄")
        shard = json.loads(path.read_text(encoding="utf-8"))
        if content_hash(shard) != game["shard_content_sha256"]:
            raise ValueError("參考分片指紋不符")
        verify_dataset(shard["dataset"])
        sizes["shard"].append(path.stat().st_size)
    counts = {"mlb_schedule_json": len(campaign["seasons"]),
              "mlb_stats_api_feed_json": campaign["expected_games"],
              "baseball_savant_pitch_csv": campaign["expected_dates"], "shard": campaign["expected_games"]}
    measurements = {kind: {"sample_files": len(values), "mean_bytes": statistics.mean(values),
                           "sample_max_bytes": max(values), "target_files": counts[kind]}
                    for kind, values in sizes.items()}
    if set(measurements) != set(counts):
        raise ValueError("容量估計缺少來源種類")
    return {"measurements": measurements,
        "estimated_total_bytes_at_sample_mean": int(sum(v["mean_bytes"] * v["target_files"] for v in measurements.values())),
        "estimated_total_bytes_at_sample_max": sum(v["sample_max_bytes"] * v["target_files"] for v in measurements.values()),
        "free_bytes_at_planning": shutil.disk_usage(cache.root.resolve()).free,
        "minimum_free_reserve_bytes": 5 * 1024**3,
        "note": "只估一版來源及分片，含已有來源，未扣重用；樣本最大值不是上界。未含重建多版本、訓練產物及其他磁碟使用。"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--reference-report", type=Path, required=True)
    parser.add_argument("--reference-artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("計畫不覆寫，請指定新檔名")
    cache = SourceCache(args.cache_dir, offline=True)
    campaign = build_campaign(cache)
    reference = json.loads(args.reference_report.read_text(encoding="utf-8"))
    result = {"campaign": campaign, "campaign_sha256": content_hash(campaign),
        "storage": measure_storage(reference, args.reference_artifacts, cache, campaign),
        "script_manifest": build_file_manifest(Path(__file__), source_type="campaign_planner"),
        "reference_manifest": build_file_manifest(args.reference_report, source_type="historical_batch_report")}
    atomic_json_new(args.output, result)
    print(json.dumps({"campaign_sha256": result["campaign_sha256"], "months": len(campaign["months"]),
        "expected_games": campaign["expected_games"], "expected_dates": campaign["expected_dates"],
        "storage": result["storage"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
