"""Dataset B 預先宣告的場次時間窗；未鎖 game_pk 前不聲稱 holdout 完成。"""

from __future__ import annotations

from collections import Counter
from datetime import date


def _day(value: str) -> date:
    if not isinstance(value, str):
        raise ValueError("比賽日期必須為 ISO 日期字串")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("比賽日期格式無效") from error


def validate_plan(plan: dict) -> None:
    if (plan.get("schema_version") != "dataset-b-split-plan-v1"
            or plan.get("status") != "rules_predeclared_game_lists_pending"
            or plan.get("formal_model_evaluation_ready") is not False):
        raise ValueError("Dataset B 切分計畫版本或 readiness 無效")
    ids = plan.get("known_development_game_pks")
    if (not isinstance(ids, list) or not ids or len(ids) != len(set(ids))
            or any(type(pk) is not int or pk <= 0 for pk in ids)):
        raise ValueError("開發場次清冊必須非空、唯一且為正整數")
    windows = plan.get("windows")
    if not isinstance(windows, list) or not windows:
        raise ValueError("必須預先宣告時間窗")
    names = set()
    parsed = []
    for window in windows:
        name = window["name"]
        if name in names or window["split"] not in {"train", "validation", "test", "external"}:
            raise ValueError("時間窗名稱重複或切分名稱無效")
        names.add(name)
        start, end = _day(window["start"]), _day(window["end"])
        if start > end or type(window["sport_id"]) is not int or type(window["regime"]) is not str:
            raise ValueError("時間窗範圍或制度條件無效")
        parsed.append((window, start, end))
    for index, (first, start, end) in enumerate(parsed):
        for second, other_start, other_end in parsed[index + 1:]:
            same_regime = all(first[key] == second[key] for key in ("sport_id", "league_id", "regime"))
            if same_regime and start <= other_end and other_start <= end:
                raise ValueError("同制度時間窗重疊，可能使同場跨 split")
    split_ranges = {split: [(start, end) for window, start, end in parsed if window["split"] == split]
                    for split in ("train", "validation", "test", "external")}
    if any(not ranges for ranges in split_ranges.values()):
        raise ValueError("Train／Validation／Test／External 時間窗不完整")
    for earlier, later in (("train", "validation"), ("validation", "test"), ("test", "external")):
        if max(end for _, end in split_ranges[earlier]) >= min(start for start, _ in split_ranges[later]):
            raise ValueError("時間切分順序不可逆轉或交疊")


def assign_game(plan: dict, game: dict) -> dict:
    """開發場次優先隔離；規則不明或制度不符不會偷進任何 split。"""
    validate_plan(plan)
    pk = game["game_pk"]
    if type(pk) is not int or pk <= 0:
        raise ValueError("game_pk 必須為正整數")
    played = _day(game["date"])
    result = {"game_pk": pk, "date": game["date"], "split": None, "window": None,
              "source_eligibility_status": "provisional_source_limitations"}
    if pk in plan["known_development_game_pks"]:
        result["split"] = "development_only"
    elif game.get("rule_status") != "confirmed":
        result["split"] = "unconfirmed_rule_regime"
    elif game.get("initial_challenges") != 2:
        result["split"] = "excluded_rule_regime"
    else:
        matches = [window for window in plan["windows"]
                   if (_day(window["start"]) <= played <= _day(window["end"])
                       and game.get("sport_id") == window["sport_id"]
                       and game.get("league_id") == window["league_id"]
                       and game.get("regime") == window["regime"])]
        if len(matches) > 1:
            raise ValueError("同場符合多個切分時間窗")
        if matches:
            result.update(split=matches[0]["split"], window=matches[0]["name"])
        else:
            result["split"] = "outside_predeclared_windows"
    return result


def assign_games(plan: dict, games: list[dict]) -> dict:
    validate_plan(plan)
    ids = [game["game_pk"] for game in games]
    if len(ids) != len(set(ids)):
        raise ValueError("同一 game_pk 重複，不能跨 split")
    rows = [assign_game(plan, game) for game in games]
    return {"schema_version": "dataset-b-split-assignment-v1", "rows": rows,
            "split_counts": dict(sorted(Counter(row["split"] for row in rows).items())),
            "holdout_game_lists_locked": False, "formal_model_evaluation_ready": False}
