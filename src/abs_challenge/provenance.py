"""建立可驗證的外部資料來源 manifest。"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit


def build_download_manifest(
    *,
    source_type: str,
    source_url: str,
    content: str,
    row_count: int,
    retrieved_at_utc: str | None = None,
) -> dict[str, Any]:
    """記錄下載內容、來源與查詢參數，供後續重播及驗證。"""

    encoded = content.encode("utf-8")
    retrieved_at = retrieved_at_utc or datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    return {
        "schema_version": "source-manifest-v1",
        "source_type": source_type,
        "source_url": source_url,
        "request_parameters": dict(parse_qsl(urlsplit(source_url).query)),
        "retrieved_at_utc": retrieved_at,
        "content_sha256": sha256(encoded).hexdigest(),
        "byte_length": len(encoded),
        "row_count": row_count,
    }


def build_file_manifest(path: Path, *, source_type: str) -> dict[str, Any]:
    """為本機輸入檔建立內容指紋，不依賴檔名判定內容。"""

    content = path.read_bytes()
    return {
        "schema_version": "file-manifest-v1",
        "source_type": source_type,
        "source_path": str(path.resolve()),
        "content_sha256": sha256(content).hexdigest(),
        "byte_length": len(content),
    }
