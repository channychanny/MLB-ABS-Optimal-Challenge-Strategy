"""執行已固定清冊的一個月；逐來源檢查剩餘空間，保留可續跑分片。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from abs_challenge.historical import content_hash
from abs_challenge.historical_batch import run_historical_batch
from abs_challenge.phase1_cli import _runtime
from abs_challenge.provenance import build_file_manifest
from abs_challenge.source_cache import SourceCache, atomic_json_new
from plan_historical_seasons import build_campaign


RESERVE_BYTES = 5 * 1024**3


class CapacityLimitedCache(SourceCache):
    """在每次來源讀取／下載前檢查空間；不足時停止，不刪除既有資料。"""

    def check_space(self):
        if shutil.disk_usage(self.root.resolve()).free < RESERVE_BYTES:
            raise RuntimeError("剩餘空間低於 5 GiB 保留額，已停止；既有快取與分片可供續跑")

    def get(self, url, kind, count_rows):
        self.check_space()
        return super().get(url, kind, count_rows)


def run_month(document, month, cache, artifact_dir, contract, runtime, progress):
    campaign = document["campaign"]
    if content_hash(campaign) != document["campaign_sha256"]:
        raise ValueError("取得計畫指紋不符")
    # 僅讀固定快取重新產生清冊，確認清冊／選樣均未更換，再允許下載逐球來源。
    fixed = build_campaign(SourceCache(cache.root, offline=True))
    if fixed != campaign:
        raise ValueError("固定官方清冊或月計畫已變更，不能混入本次取得計畫")
    matches = [batch for batch in campaign["months"] if batch["month"] == month]
    if len(matches) != 1:
        raise ValueError("月份不在固定 Train／Validation 計畫")
    batch = matches[0]
    signature = content_hash([{"name": Path(m["source_path"]).name, "sha256": m["content_sha256"]}
                              for m in runtime["code_manifests"]])
    result = run_historical_batch(batch["plan"], contract, cache, artifact_dir,
                                  code_signature=signature, progress=progress)
    selected = sorted(g["game_pk"] for g in result["dataset_lock"]["games"])
    if selected != batch["expected_game_pks"]:
        raise ValueError("實際選定場次與固定月清冊不符，不能發布為完成報告")
    result.update(runtime=runtime, campaign_sha256=document["campaign_sha256"], month=month,
                  expected_game_pks=batch["expected_game_pks"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--month", required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("月報不覆寫，請指定新輸出檔名")
    # 原始來源與分片都限定專案磁碟，避免只量測來源磁碟卻寫到另一磁碟。
    if args.artifact_dir.resolve().anchor != args.cache_dir.resolve().anchor:
        raise ValueError("此執行器要求來源與分片在同一磁碟")
    cache = CapacityLimitedCache(args.cache_dir, offline=args.offline)
    cache.check_space()
    root = Path(__file__).resolve().parents[1]
    contract_path = root / "config" / "phase2_dataset.json"
    result = run_month(json.loads(args.campaign.read_text(encoding="utf-8")), args.month, cache,
        args.artifact_dir, json.loads(contract_path.read_text(encoding="utf-8")), _runtime(),
        lambda event: print(json.dumps(event, ensure_ascii=False), flush=True))
    cache.check_space()
    result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
        (args.campaign, "historical_acquisition_campaign"), (contract_path, "phase2_dataset_contract"),
        (Path(__file__), "campaign_runner"), (Path(__file__).with_name("plan_historical_seasons.py"), "campaign_planner"))]
    atomic_json_new(args.output, result)
    print(json.dumps({"month": args.month, "summary": result["summary"],
                      "execution": result["execution"]}, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "complete_selected_games" else 1


if __name__ == "__main__":
    raise SystemExit(main())
