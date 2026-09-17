"""Baseball Savant CSV access and challenge-state joins."""

from __future__ import annotations

import csv
import io
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SAVANT_BASE = "https://baseballsavant.mlb.com"
USER_AGENT = "mlb-abs-challenge-research/0.1"
ABS_CHALLENGE_FILTER = r"is\.\.challengeabs\.\.review|"
REQUIRED_PRE_PITCH_FIELDS = (
    "balls",
    "strikes",
    "outs_when_up",
    "inning",
    "inning_topbot",
    "home_score",
    "away_score",
    "on_1b",
    "on_2b",
    "on_3b",
)
NULLABLE_PRE_PITCH_FIELDS = {"on_1b", "on_2b", "on_3b"}


def _build_csv_url(game_date: str, level: str, *, challenges_only: bool) -> str:
    normalized_level = level.lower()
    if normalized_level == "aaa":
        endpoint = "/statcast-search-minors/csv"
        params = {"minors": "true", "hfLevel": "AAA|"}
    elif normalized_level == "mlb":
        endpoint = "/statcast_search/csv"
        params = {}
    else:
        raise ValueError("level must be 'mlb' or 'aaa'")

    params.update(
        {
            "all": "true",
            "type": "details",
            "player_type": "pitcher",
            "hfGT": "R|",
            "game_date_gt": game_date,
            "game_date_lt": game_date,
            "group_by": "name-date",
            "min_pitches": "0",
            "min_results": "0",
            "min_pas": "0",
        }
    )
    if challenges_only:
        params["hfABSFlag"] = ABS_CHALLENGE_FILTER
    return f"{SAVANT_BASE}{endpoint}?{urlencode(params)}"


def build_abs_csv_url(game_date: str, level: str) -> str:
    """Build a one-day, pitch-level ABS challenge CSV URL."""

    return _build_csv_url(game_date, level, challenges_only=True)


def build_called_pitches_csv_url(game_date: str, level: str) -> str:
    """建立包含所有逐球資料的下載網址，供 Legal Opportunity 篩選。"""

    return _build_csv_url(game_date, level, challenges_only=False)


def fetch_csv_text(url: str, timeout: float = 120.0) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8-sig")


def parse_csv_text(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))


def fetch_abs_rows(game_date: str, level: str) -> tuple[str, list[dict[str, str]]]:
    url = build_abs_csv_url(game_date, level)
    text = fetch_csv_text(url)
    return text, parse_csv_text(text)


def fetch_called_pitch_rows(
    game_date: str, level: str
) -> tuple[str, list[dict[str, str]]]:
    """下載整日逐球資料，供 Challenge Opportunity 母體建構。"""

    url = build_called_pitches_csv_url(game_date, level)
    text = fetch_csv_text(url)
    return text, parse_csv_text(text)


def index_statcast_rows(rows: list[dict[str, str]]) -> dict[tuple[int, int, int], dict[str, str]]:
    index: dict[tuple[int, int, int], dict[str, str]] = {}
    for row_number, row in enumerate(rows, start=1):
        try:
            key = (
                int(row["game_pk"]),
                int(row["at_bat_number"]),
                int(row["pitch_number"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"invalid Statcast pitch key at row {row_number}"
            ) from error
        if key in index:
            raise ValueError(f"duplicate Statcast pitch key: {key!r}")
        index[key] = row
    return index


def selected_pre_pitch_state(row: dict[str, str]) -> dict[str, Any]:
    """只回傳決策當下可用的賽況欄位，排除結果衍生資料。"""

    integer_fields = (
        "balls",
        "strikes",
        "outs_when_up",
        "inning",
        "home_score",
        "away_score",
        "bat_score",
        "fld_score",
    )
    float_fields = ("home_win_exp", "bat_win_exp")
    state: dict[str, Any] = {
        "inning_topbot": row.get("inning_topbot") or None,
        "on_1b": row.get("on_1b") or None,
        "on_2b": row.get("on_2b") or None,
        "on_3b": row.get("on_3b") or None,
    }
    for field in integer_fields:
        value = row.get(field)
        state[field] = int(value) if value not in {None, ""} else None
    for field in float_fields:
        value = row.get(field)
        state[field] = float(value) if value not in {None, ""} else None
    return state


def missing_pre_pitch_fields(row: dict[str, str]) -> tuple[str, ...]:
    """列出 Phase 0 所需但未出現在來源列的賽前欄位。"""

    return tuple(
        field
        for field in REQUIRED_PRE_PITCH_FIELDS
        if field not in row
        or (field not in NULLABLE_PRE_PITCH_FIELDS and row.get(field) in {None, ""})
    )


def selected_pitch_observation(row: dict[str, str]) -> dict[str, Any]:
    """回傳投球發生後才可確認的觀測值與結果衍生欄位。"""

    float_fields = (
        "plate_x",
        "plate_z",
        "sz_top",
        "sz_bot",
        "delta_home_win_exp",
        "delta_run_exp",
    )
    observation: dict[str, Any] = {
        "description": row.get("description") or None,
        "des": row.get("des") or None,
    }
    for field in float_fields:
        value = row.get(field)
        observation[field] = float(value) if value not in {None, ""} else None
    return observation


def selected_game_state(row: dict[str, str]) -> dict[str, Any]:
    """Select pre-pitch state and official baseline fields from a CSV row."""

    integer_fields = (
        "balls",
        "strikes",
        "outs_when_up",
        "inning",
        "home_score",
        "away_score",
        "bat_score",
        "fld_score",
    )
    float_fields = (
        "plate_x",
        "plate_z",
        "sz_top",
        "sz_bot",
        "home_win_exp",
        "bat_win_exp",
        "delta_home_win_exp",
        "delta_run_exp",
    )
    state: dict[str, Any] = {
        "inning_topbot": row.get("inning_topbot") or None,
        "on_1b": row.get("on_1b") or None,
        "on_2b": row.get("on_2b") or None,
        "on_3b": row.get("on_3b") or None,
        "description": row.get("description") or None,
        "des": row.get("des") or None,
    }
    for field in integer_fields:
        value = row.get(field)
        state[field] = int(value) if value not in {None, ""} else None
    for field in float_fields:
        value = row.get(field)
        state[field] = float(value) if value not in {None, ""} else None
    return state
