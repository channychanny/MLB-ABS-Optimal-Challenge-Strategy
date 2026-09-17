"""Phase 1 命令；下載與估值分離、預設不覆寫任何既有輸出。"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .baseline import SavantBaseline, build_baseline_snapshot, download_baseline_bundle
from .dynamic_prototype import build_dynamic_demo
from .phase1 import value_audited_challenges
from .provenance import build_file_manifest
from .validation import evaluate_phase0_gate


COMMANDS = {"download-baseline", "build-baseline", "value-challenges", "run-dynamic-prototype"}


def register_commands(subparsers: Any) -> None:
    download = subparsers.add_parser("download-baseline", help="下載官方 RE288／WP 與來源快照")
    download.add_argument("--raw-output", type=Path, required=True)
    download.add_argument("--output", type=Path, required=True)
    build = subparsers.add_parser("build-baseline", help="離線重播官方原始快照")
    build.add_argument("--bundle", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    values = subparsers.add_parser("value-challenges", help="對通過 Gate 的兩次制度樣本估值")
    values.add_argument("--baseline", type=Path, required=True)
    values.add_argument("--phase0-gate", type=Path, required=True)
    values.add_argument("--audit", type=Path, action="append", required=True)
    values.add_argument("--feed-json", type=Path, action="append", required=True)
    values.add_argument("--output", type=Path, required=True)
    demo = subparsers.add_parser("run-dynamic-prototype", help="執行合成兩次額度決策流程，不作正式回測")
    demo.add_argument("--baseline", type=Path, required=True)
    demo.add_argument("--output", type=Path, required=True)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_new(paths: list[Path]) -> None:
    resolved = [path.resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("原始與衍生輸出不能是同一檔案")
    for path in resolved:
        if path.exists():
            raise FileExistsError(f"保留既有檔案，請使用新的輸出路徑：{path}")


def _write_new(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def _runtime() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    commit, clean = None, False
    try:
        options = {"cwd": root, "capture_output": True, "text": True,
                   "encoding": "utf-8", "errors": "replace", "timeout": 5}
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], **options)
        # 不能誤把使用者家目錄的其他 repository commit 當作本專案版本。
        if top.returncode == 0 and Path(top.stdout.strip()).resolve() == root:
            result = subprocess.run(["git", "rev-parse", "HEAD"], **options)
            commit = result.stdout.strip() if result.returncode == 0 else None
            status = subprocess.run(["git", "status", "--porcelain"], **options)
            clean = status.returncode == 0 and not status.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        commit = None
    return {"python_version": platform.python_version(), "dependencies": "standard_library_only",
        "commit_sha": commit, "worktree_clean": clean,
        "formal_experiment_version_ready": commit is not None and clean,
        "version_note": "程式檔 hash 只供原型重播，不能取代正式專案 commit。",
        "code_manifests": [build_file_manifest(path, source_type="python_source")
                           for path in sorted((root / "src" / "abs_challenge").glob("*.py"))]}


def _verified_gate(path: Path) -> tuple[dict[str, Any], set[str]]:
    """重驗 Gate 全部依賴的內容指紋，再重算 Gate，不只信任 pass 布林。"""
    gate = _load(path)
    if gate.get("schema_version") != "phase0-gate-result-v1" or gate.get("phase0_gate_pass") is not True:
        raise ValueError("跨年度 Phase 0 Gate 尚未通過")
    audits, comparisons, requirements, audit_hashes = [], [], [], set()
    for item in gate["input_manifests"]:
        source_path = Path(item["source_path"])
        manifest = build_file_manifest(source_path, source_type=item["source_type"])
        if manifest["content_sha256"] != item["content_sha256"]:
            raise ValueError(f"Gate 依賴內容已變更：{source_path.name}")
        if item["source_type"] == "phase0_game_audit":
            audits.append(_load(source_path))
            audit_hashes.add(item["content_sha256"])
        elif item["source_type"] == "phase0_gate_requirements":
            requirements.append(_load(source_path))
        elif item["source_type"] == "official_aggregate_comparison":
            comparisons.append(_load(source_path))
    if len(requirements) != 1 or not evaluate_phase0_gate(audits, requirements[0], comparisons)["phase0_gate_pass"]:
        raise ValueError("重算 Phase 0 Gate 未通過")
    return gate, audit_hashes


def run_command(args: argparse.Namespace) -> int:
    paths = [args.output] + ([args.raw_output] if args.command == "download-baseline" else [])
    _require_new(paths)
    if args.command in {"download-baseline", "build-baseline"}:
        bundle = download_baseline_bundle() if args.command == "download-baseline" else _load(args.bundle)
        snapshot = build_baseline_snapshot(bundle)
        if args.command == "download-baseline":
            _write_new(args.raw_output, bundle)
        _write_new(args.output, snapshot)
        print(json.dumps({"re_states": len(snapshot["re288"]), "wp_count_states": len(snapshot["wp"]),
                          "regulation_boundary": snapshot["regulation_boundary"], "output": str(args.output)}, ensure_ascii=False))
        return 0
    baseline = SavantBaseline(_load(args.baseline))
    inputs = [build_file_manifest(args.baseline, source_type="savant_baseline_snapshot")]
    if args.command == "run-dynamic-prototype":
        result = build_dynamic_demo(baseline)
        exit_code = 0
    else:
        _, allowed_hashes = _verified_gate(args.phase0_gate)
        inputs.append(build_file_manifest(args.phase0_gate, source_type="phase0_gate_result"))
        audits = []
        feed_hashes = set()
        canonical_feed_hashes = set()
        for path in args.feed_json:
            manifest = build_file_manifest(path, source_type="mlb_stats_api_feed_json")
            inputs.append(manifest)
            feed_hashes.add(manifest["content_sha256"])
            # Phase 0 即時下載模式記錄的是排序後 JSON；本機模式則記錄檔案 bytes。
            canonical = json.dumps(_load(path), ensure_ascii=False, sort_keys=True).encode("utf-8")
            canonical_feed_hashes.add(sha256(canonical).hexdigest())
        for path in args.audit:
            manifest = build_file_manifest(path, source_type="phase0_game_audit")
            if manifest["content_sha256"] not in allowed_hashes:
                raise ValueError("估值 audit 不屬於通過 Gate 的固定 snapshot")
            audit = _load(path)
            sources = [item for item in audit["input_manifests"] if item["source_type"] == "mlb_stats_api_feed_json"]
            source_match = any(item["content_sha256"] in (
                canonical_feed_hashes if item["schema_version"] == "source-manifest-v1" else feed_hashes
            ) for item in sources)
            if not source_match:
                raise ValueError("官方 feed 與 audit 來源 hash 不一致")
            audits.append(audit)
            inputs.append(manifest)
        result = value_audited_challenges(baseline, audits, [_load(path) for path in args.feed_json])
        exit_code = 0 if result["status"] == "complete_smoke_test" else 1
    result["input_manifests"] = inputs
    result["baseline_metadata"] = {key: baseline.snapshot[key] for key in (
        "schema_version", "source_url", "source_page_seasons", "re_response_years", "regulation_boundary")}
    result["runtime"] = _runtime()
    _write_new(args.output, result)
    print(json.dumps(result.get("summary", result.get("results")), ensure_ascii=False, indent=2))
    return exit_code
