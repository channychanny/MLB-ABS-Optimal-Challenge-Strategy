"""不可覆寫的公開來源快取：完整驗證後原子發布，失敗不污染快取。"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .provenance import build_download_manifest


def atomic_json_new(path: Path, payload: dict[str, Any]) -> None:
    """在同目錄寫暫存檔，再以硬連結原子發布；既有目標永不覆寫。"""
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".pending-", suffix=".tmp", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        # os.link 在目標已存在時失敗，不會發生先檢查再覆寫的競爭。
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def download_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 ABS-research/0.1"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def verify_source(source: dict[str, Any], url: str, kind: str,
                  count_rows: Callable[[str], int]) -> None:
    manifest = source["manifest"]
    timestamp = datetime.fromisoformat(manifest["retrieved_at_utc"].replace("Z", "+00:00"))
    if timestamp.utcoffset() is None:
        raise ValueError("來源下載時間必須含時區")
    expected = build_download_manifest(source_type=kind, source_url=url, content=source["text"],
        row_count=count_rows(source["text"]), retrieved_at_utc=manifest["retrieved_at_utc"])
    if source.get("schema_version") != "cached-public-source-v1" or manifest != expected:
        raise ValueError("來源快取的版本、URL、參數、內容指紋或列數不符；保留檔案，不自動覆寫")


class SourceCache:
    """URL 對應固定來源；只有暫時網路錯誤重試，損毀內容必須顯式處理。"""

    def __init__(self, root: Path, *, offline: bool = False,
                 fetch: Callable[[str], str] = download_text,
                 sleep: Callable[[float], None] = time.sleep,
                 attempts: int = 3):
        if type(attempts) is not int or not 1 <= attempts <= 5:
            raise ValueError("attempts 必須介於 1 與 5")
        self.root, self.offline, self.fetch, self.sleep = root, offline, fetch, sleep
        self.attempts = attempts
        self.hits = self.downloads = self.retries = 0

    def path_for(self, url: str) -> Path:
        return self.root / f"{sha256(url.encode('utf-8')).hexdigest()}.json"

    def get(self, url: str, kind: str, count_rows: Callable[[str], int]) -> dict[str, Any]:
        path = self.path_for(url)
        if path.exists():
            source = json.loads(path.read_text(encoding="utf-8"))
            verify_source(source, url, kind, count_rows)
            self.hits += 1
            return source
        if self.offline:
            raise FileNotFoundError(f"離線來源快取缺失：{url}")
        for attempt in range(self.attempts):
            try:
                text = self.fetch(url)
                break
            except (HTTPError, URLError, TimeoutError, ConnectionError) as error:
                transient = not isinstance(error, HTTPError) or error.code in {408, 429, 500, 502, 503, 504}
                if isinstance(error, HTTPError):
                    error.close()
                if not transient or attempt == self.attempts - 1:
                    raise
                self.retries += 1
                self.sleep(min(2 ** attempt, 4))
        count = count_rows(text)
        source = {"schema_version": "cached-public-source-v1", "text": text,
            "manifest": build_download_manifest(source_type=kind, source_url=url,
                content=text, row_count=count)}
        verify_source(source, url, kind, count_rows)
        try:
            atomic_json_new(path, source)
        except FileExistsError:
            # 另一程序先完成同一 URL 時採用先發布的固定快照，不混用新內容。
            source = json.loads(path.read_text(encoding="utf-8"))
            verify_source(source, url, kind, count_rows)
        self.downloads += 1
        return source
