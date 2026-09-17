"""Small dependency-free client for official MLB Stats API game feeds."""

from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen


BASE_URL = "https://statsapi.mlb.com"
USER_AGENT = "mlb-abs-challenge-research/0.1"


def fetch_json(url: str, timeout: float = 30.0) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def get_live_feed(game_pk: int, timeout: float = 30.0) -> dict[str, Any]:
    if game_pk <= 0:
        raise ValueError("game_pk must be positive")
    return fetch_json(f"{BASE_URL}/api/v1.1/game/{game_pk}/feed/live", timeout)

