"""Dataset A 的小樣本來源快照；逐日全季排程另行建置。"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any
from urllib.request import Request, urlopen

from .historical import _feed_summary
from .mlb_api import BASE_URL
from .provenance import build_download_manifest
from .savant import build_called_pitches_csv_url, parse_csv_text


BUNDLE_VERSION = "historical-source-bundle-v1"


def _download(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 ABS-research/0.1"})
    with urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8-sig")


def _source(url: str, text: str, kind: str, count: int) -> dict[str, Any]:
    return {"text": text, "manifest": build_download_manifest(
        source_type=kind, source_url=url, content=text, row_count=count)}


def download_historical_bundle(game_pk: int) -> dict[str, Any]:
    """保存一場 feed 與其比賽日完整 MLB CSV，不觸碰既有快照。"""
    if type(game_pk) is not int or game_pk <= 0:
        raise ValueError("game_pk 必須是正整數")
    url = f"{BASE_URL}/api/v1.1/game/{game_pk}/feed/live"
    text = _download(url)
    feed = json.loads(text)
    if feed.get("gamePk") != game_pk:
        raise ValueError("下載 feed 與要求的 game_pk 不一致")
    game, _, _ = _feed_summary(feed)
    csv_url = build_called_pitches_csv_url(game["game_date"], "mlb")
    csv_text = _download(csv_url)
    return {"schema_version": BUNDLE_VERSION, "feed": _source(url, text, "mlb_stats_api_feed_json", 1),
            "statcast": _source(csv_url, csv_text, "baseball_savant_pitch_csv", len(parse_csv_text(csv_text)))}


def read_historical_bundle(bundle: dict[str, Any]) -> tuple[dict, list[dict], str]:
    """重驗原始文字、來源查詢與列數，拒絕改造為 ABS-only 的來源。"""
    if bundle.get("schema_version") != BUNDLE_VERSION:
        raise ValueError("未知歷史來源 bundle 版本")
    for name in ("feed", "statcast"):
        source = bundle[name]
        raw = source["text"].encode("utf-8")
        manifest = source["manifest"]
        if (manifest.get("schema_version") != "source-manifest-v1"
                or sha256(raw).hexdigest() != manifest.get("content_sha256")
                or len(raw) != manifest.get("byte_length")
                or not manifest.get("retrieved_at_utc")):
            raise ValueError("原始來源 manifest 指紋或必要欄位不符")
    feed = json.loads(bundle["feed"]["text"])
    game_date = feed["gameData"]["datetime"]["officialDate"]
    expected_urls = {
        "feed": f"{BASE_URL}/api/v1.1/game/{feed['gamePk']}/feed/live",
        "statcast": build_called_pitches_csv_url(game_date, "mlb"),
    }
    rows = parse_csv_text(bundle["statcast"]["text"])
    for name, kind, count in (("feed", "mlb_stats_api_feed_json", 1),
                               ("statcast", "baseball_savant_pitch_csv", len(rows))):
        original = bundle[name]["manifest"]
        expected = build_download_manifest(source_type=kind, source_url=expected_urls[name],
            content=bundle[name]["text"], row_count=count,
            retrieved_at_utc=original["retrieved_at_utc"])
        if any(original.get(k) != v for k, v in expected.items()):
            raise ValueError("來源 URL、類型、查詢參數或列數不符")
    return feed, rows, bundle["statcast"]["manifest"]["content_sha256"]
