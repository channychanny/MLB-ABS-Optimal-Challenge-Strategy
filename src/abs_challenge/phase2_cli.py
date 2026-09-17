"""Phase 2 開發命令：完整來源小樣本、Dataset A 與 Train-only RE。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .historical import build_historical_dataset
from .historical import content_hash
from .historical_batch import run_historical_batch
from .historical_sources import download_historical_bundle, read_historical_bundle
from .phase1_cli import _load, _require_new, _runtime, _write_new
from .provenance import build_file_manifest
from .research_re import estimate_re_and_boundary
from .source_cache import SourceCache, atomic_json_new


COMMANDS = {"download-historical-game", "build-historical-dataset", "estimate-re-development", "run-historical-batch"}
DEFAULT_CONTRACT = Path(__file__).resolve().parents[2] / "config" / "phase2_dataset.json"


def register_commands(subparsers: Any) -> None:
    batch = subparsers.add_parser("run-historical-batch", help="固定計畫的逐日快取、逐場稽核與可續跑開發清單")
    batch.add_argument("--plan", type=Path, required=True)
    batch.add_argument("--cache-dir", type=Path, required=True)
    batch.add_argument("--artifact-dir", type=Path, required=True)
    batch.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    batch.add_argument("--offline", action="store_true")
    batch.add_argument("--output", type=Path, required=True)
    download = subparsers.add_parser("download-historical-game", help="保存單場 MLB 完整來源小樣本")
    download.add_argument("--game-pk", type=int, required=True)
    download.add_argument("--output", type=Path, required=True)
    build = subparsers.add_parser("build-historical-dataset", help="離線建立 Dataset A 與年度切分")
    build.add_argument("--bundle", type=Path, action="append", required=True)
    build.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    build.add_argument("--output", type=Path, required=True)
    re = subparsers.add_parser("estimate-re-development", help="Train-only RE 與平手邊界開發估計，非正式模型")
    re.add_argument("--dataset", type=Path, action="append", required=True)
    re.add_argument("--output", type=Path, required=True)


def run_command(args: argparse.Namespace) -> int:
    _require_new([args.output])
    if args.command == "run-historical-batch":
        runtime = _runtime()
        code_signature = content_hash([{ "name": Path(m["source_path"]).name,
                                         "sha256": m["content_sha256"]} for m in runtime["code_manifests"]])
        result = run_historical_batch(_load(args.plan), _load(args.contract),
            SourceCache(args.cache_dir, offline=args.offline), args.artifact_dir,
            code_signature=code_signature,
            progress=lambda event: print(json.dumps(event, ensure_ascii=False), flush=True))
        result["runtime"] = runtime
        result["input_manifests"] = [build_file_manifest(args.plan, source_type="historical_batch_plan"),
                                     build_file_manifest(args.contract, source_type="phase2_dataset_contract")]
        atomic_json_new(args.output, result)
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
        return 0 if result["status"] == "complete_selected_games" else 1
    if args.command == "download-historical-game":
        bundle = download_historical_bundle(args.game_pk)
        read_historical_bundle(bundle)
        _write_new(args.output, bundle)
        print(json.dumps({"game_pk": args.game_pk, "output": str(args.output),
                          "status": "source_snapshot_only"}, ensure_ascii=False))
        return 0
    inputs = []
    if args.command == "build-historical-dataset":
        feeds, rows, csv_hashes = [], [], set()
        for path in args.bundle:
            feed, source_rows, csv_hash = read_historical_bundle(_load(path))
            feeds.append(feed)
            # 同日多份 bundle 可能攜帶同一份完整 CSV，只按來源 hash 去重。
            if csv_hash not in csv_hashes:
                rows.extend(source_rows)
                csv_hashes.add(csv_hash)
            inputs.append(build_file_manifest(path, source_type="historical_source_bundle"))
        inputs.append(build_file_manifest(args.contract, source_type="phase2_dataset_contract"))
        result = build_historical_dataset(feeds, rows, _load(args.contract))
        exit_code = 0 if result["status"] == "complete_selected_games" else 1
    else:
        result = estimate_re_and_boundary([_load(path) for path in args.dataset])
        inputs = [build_file_manifest(path, source_type="historical_dataset_a") for path in args.dataset]
        exit_code = 0
    result["input_manifests"] = inputs
    result["runtime"] = _runtime()
    _write_new(args.output, result)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return exit_code
