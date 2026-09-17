"""Dataset A：完整比賽核對、決策前狀態及與特徵隔離的歷史標籤。"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from hashlib import sha256
import json
from typing import Any

from .savant import REQUIRED_PRE_PITCH_FIELDS, index_statcast_rows
from .state_value import GameState, checked_int


DATASET_VERSION = "historical-dataset-a-v1"
SPLITS = {"train": [2019, 2021, 2022, 2023], "validation": [2024],
          "test": [2025], "external": [2026]}
DEVELOPMENT_GAMES = {823244, 823569, 825027}
FEATURE_NAMES = ("inning", "half", "outs", "bases", "balls", "strikes", "score_diff")


def content_hash(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def validate_contract(contract: dict[str, Any]) -> None:
    """固定研究設計，不讓命令參數靜默把 Test 改成 Train。"""
    expected = {
        "schema_version": "phase2-dataset-contract-v1", "competition": "MLB",
        "game_type": "R", "scheduled_innings": 9, "feature_innings": [1, 9],
        "splits": SPLITS, "development_external_game_pks": sorted(DEVELOPMENT_GAMES),
        "score_difference_bands": [[0, 5], [6, 10], [11, None]],
        "score_difference_clipping": False,
        "re24_sampling": "first_observed_pitch_per_plate_appearance",
        "re288_sampling": "all_observed_pitches", "re_half_policy": "three_out_halves_only",
        "boundary_fit_split": "train",
        "boundary_estimator": "empirical_home_win_fraction_without_smoothing",
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            raise ValueError(f"資料契約不符既定研究設計：{key}")


def split_for_game(season: int, game_pk: int) -> str:
    checked_int(season, "season", 1900, 2100)
    checked_int(game_pk, "game_pk", 1, 10**9)
    if game_pk in DEVELOPMENT_GAMES:
        if season != 2026:
            raise ValueError("開發稽核場次年份不一致")
        return "development_external"
    for split, years in SPLITS.items():
        if season in years:
            return split
    raise ValueError(f"年份 {season} 不在主要資料範圍；2020 不得混入")


def score_band(score_diff: int) -> str:
    return "0-5" if abs(score_diff) <= 5 else "6-10" if abs(score_diff) <= 10 else "11+"


def model_features(state: GameState) -> dict[str, Any]:
    """只從經驗證的 GameState 產生白名單，保留未截尾的真實分差。"""
    return {name: getattr(state, name) for name in FEATURE_NAMES if name != "score_diff"} | {
        "score_diff": state.home_score - state.away_score}


def _integer(value: Any, name: str, minimum: int = 0, maximum: int = 1000) -> int:
    if isinstance(value, str) and value.isascii() and value.isdigit():
        value = int(value)
    return checked_int(value, name, minimum, maximum)


def _feed_summary(feed: dict[str, Any]) -> tuple[dict[str, Any], dict, dict]:
    game_pk = _integer(feed["gamePk"], "game_pk", 1, 10**9)
    data, live = feed["gameData"], feed["liveData"]
    if data["status"].get("abstractGameState") != "Final":
        raise ValueError("比賽尚未正式結束")
    if data["game"].get("type") != "R":
        raise ValueError("只納入例行賽")
    if any(data["teams"][side].get("sport", {}).get("id") != 1 for side in ("home", "away")):
        raise ValueError("Dataset A 只納入 MLB，不以 Triple-A 訓練 MLB WP")
    line = live["linescore"]
    if line.get("scheduledInnings") != 9 or line.get("currentInning", 0) < 9:
        raise ValueError("排除七局制及未打到九局的縮短比賽")
    game_date = date.fromisoformat(data["datetime"]["officialDate"])
    season = _integer(data["game"]["season"], "season", 1900, 2100)
    if game_date.year != season:
        raise ValueError("比賽日期與球季不一致")
    split = split_for_game(season, game_pk)
    finals = {side: _integer(line["teams"][side]["runs"], f"final_{side}")
              for side in ("home", "away")}
    if finals["home"] == finals["away"]:
        raise ValueError("終場平手不能生成二元勝負標籤")
    plays = live["plays"]["allPlays"]
    if not plays or [p["about"]["atBatIndex"] for p in plays] != list(range(len(plays))):
        raise ValueError("feed 打席序號缺漏、重複或不是從零開始")
    halves: dict[tuple[int, str], list] = defaultdict(list)
    pitches = {}
    pitch_totals = {"home": 0, "away": 0}
    for play in plays:
        about = play["about"]
        if about.get("isComplete") is not True:
            raise ValueError("feed 含未完成打席")
        inning = _integer(about["inning"], "inning", 1, 100)
        half = about["halfInning"]
        if half not in {"top", "bottom"}:
            raise ValueError("無效上下半局")
        halves[inning, half].append(play)
        for event in play["playEvents"]:
            if event.get("isPitch") is not True:
                continue
            pitch_totals["home" if half == "top" else "away"] += 1
            if inning > 9:
                continue
            key = (game_pk, about["atBatIndex"] + 1,
                   _integer(event["pitchNumber"], "pitch_number", 1, 1000))
            if key in pitches:
                raise ValueError("feed 含重複投球鍵")
            pitches[key] = (inning, half)
    for side in ("home", "away"):
        official_pitches = _integer(live["boxscore"]["teams"][side]["teamStats"]["pitching"]["numberOfPitches"],
                                    "official_pitch_count", 1, 10000)
        if official_pitches != pitch_totals[side]:
            raise ValueError("逐球 feed 與官方投球總數不一致")
    ordered_halves = list(halves)
    last_inning, last_half = ordered_halves[-1]
    expected_halves = [(i, h) for i in range(1, last_inning + 1) for h in ("top", "bottom")]
    if last_half == "top":
        expected_halves.pop()
    if ordered_halves != expected_halves or last_inning != line["currentInning"]:
        raise ValueError("feed 半局序列缺漏或終局不一致")
    totals = {"home": 0, "away": 0}
    half_info = {}
    inning_lines = {item["num"]: item for item in line["innings"]}
    if len(inning_lines) != len(line["innings"]):
        raise ValueError("官方逐局比分重複")
    for half_key, half_plays in halves.items():
        inning, half = half_key
        batting = "away" if half == "top" else "home"
        start = totals.copy()
        totals[batting] += _integer(inning_lines[inning][batting]["runs"], "inning_runs")
        last = half_plays[-1]
        for side in ("home", "away"):
            if _integer(last["result"][f"{side}Score"], "half_end_score") != totals[side]:
                raise ValueError("feed 半局終點與官方逐局比分不一致")
        outs = _integer(last["count"]["outs"], "half_end_outs", 0, 3)
        complete = outs == 3
        if not complete and (half_key != ordered_halves[-1] or half != "bottom"
                             or inning < 9 or totals["home"] <= totals["away"]):
            raise ValueError("非再見半局缺少第三出局")
        half_info[half_key] = {"start": start, "end": totals.copy(), "complete": complete}
    if totals != finals:
        raise ValueError("逐局累計與官方終場比分不一致")
    if last_half == "top" and finals["home"] <= finals["away"]:
        raise ValueError("免打下半局卻非主隊領先")
    ninth = half_info.get((9, "bottom"))
    tied = bool(ninth and ninth["complete"] and ninth["end"]["home"] == ninth["end"]["away"])
    if (last_inning > 9) != tied:
        raise ValueError("九局平手狀態與後續比賽紀錄不一致")
    return {"game_pk": game_pk, "game_date": game_date.isoformat(), "season": season,
            "split": split, "home_win": int(finals["home"] > finals["away"]),
            "final_home_score": finals["home"], "final_away_score": finals["away"],
            "regulation_tied": tied, "expected_regulation_pitches": len(pitches),
            "official_pitch_counter_pass": True,
            "no_pitch_plate_appearances": sum(not any(e.get("isPitch") is True for e in p["playEvents"])
                for p in plays if p["about"]["inning"] <= 9)}, half_info, pitches


def _build_game(feed: dict[str, Any], indexed: dict) -> tuple[dict[str, Any], list]:
    game, halves, expected = _feed_summary(feed)
    if not expected or set(indexed) != set(expected):
        raise ValueError(f"完整逐球鍵不符：缺少 {len(set(expected) - set(indexed))}、"
                         f"多出 {len(set(indexed) - set(expected))}；不可用 ABS-only 資料")
    result, seen_pa = [], set()
    previous_scores = {"home": 0, "away": 0}
    for key, row in sorted(indexed.items()):
        if any(field not in row for field in REQUIRED_PRE_PITCH_FIELDS):
            raise ValueError("缺少狀態欄位；壘包缺欄不可當成空壘")
        if row.get("game_type") != "R" or row.get("game_date") != game["game_date"]:
            raise ValueError("Statcast 日期／賽事類型與官方 feed 不符")
        values = {name: row[name] for name in REQUIRED_PRE_PITCH_FIELDS}
        for name in ("inning", "outs_when_up", "balls", "strikes", "home_score", "away_score"):
            values[name] = _integer(values[name], name)
        state = GameState.from_statcast(values)
        if (state.inning, state.half) != expected[key]:
            raise ValueError("Statcast 局數與官方 feed 不符")
        half = halves[state.inning, state.half]
        batting = "away" if state.half == "top" else "home"
        for side in ("home", "away"):
            score = getattr(state, f"{side}_score")
            if not half["start"][side] <= score <= half["end"][side] or score < previous_scores[side]:
                raise ValueError("投球前比分越界或時間序列倒退")
            previous_scores[side] = score
        remaining = half["end"][batting] - getattr(state, f"{batting}_score")
        first = key[1] not in seen_pa
        seen_pa.add(key[1])
        result.append({"game_pk": game["game_pk"], "game_date": game["game_date"],
            "season": game["season"], "split": game["split"], "at_bat_number": key[1],
            "pitch_number": key[2], "pre_pitch_state": state.to_dict(),
            "features": model_features(state),
            "labels": {"home_win": game["home_win"],
                "runs_to_half_end": remaining if half["complete"] else None},
            "sampling": {"re_half_eligible": half["complete"], "re24_first_pitch": first,
                         "re_exclusion": None if half["complete"] else "walkoff_censored_half"}})
    game["regulation_pitches"] = len(result)
    return game, result


def build_historical_dataset(feeds: list[dict], statcast_rows: list[dict],
                             contract: dict[str, Any]) -> dict[str, Any]:
    validate_contract(contract)
    ids = [_integer(f["gamePk"], "game_pk", 1, 10**9) for f in feeds]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("必須提供不重複的比賽 feed")
    indexed = index_statcast_rows(statcast_rows)
    grouped = defaultdict(dict)
    excluded_extra_rows = 0
    for key, row in indexed.items():
        inning = _integer(row["inning"], "inning", 1, 100)
        if inning <= 9:
            grouped[key[0]][key] = row
        elif key[0] in ids:
            excluded_extra_rows += 1
    games, rows, excluded = [], [], []
    for feed in sorted(feeds, key=lambda f: int(f["gamePk"])):
        try:
            game, game_rows = _build_game(feed, grouped[feed["gamePk"]])
        except (KeyError, TypeError, ValueError) as error:
            excluded.append({"game_pk": feed["gamePk"], "reason": str(error)})
            continue
        games.append(game)
        rows.extend(game_rows)
    coverage = {}
    for split in (*SPLITS, "development_external"):
        selected = [r for r in rows if r["split"] == split]
        bands = {}
        for band in ("0-5", "6-10", "11+"):
            subset = [r for r in selected if score_band(r["features"]["score_diff"]) == band]
            bands[band] = {"pitches": len(subset), "games": len({r["game_pk"] for r in subset})}
        coverage[split] = {"games": len({r["game_pk"] for r in selected}), "pitches": len(selected),
            "seasons": dict(sorted(Counter(r["season"] for r in selected).items())),
            "score_bands": bands}
    result = {"schema_version": DATASET_VERSION, "contract": contract,
        "contract_sha256": content_hash(contract), "feature_names": list(FEATURE_NAMES),
        "games": games, "rows": rows, "excluded_games": excluded,
        "summary": {"input_games": len(feeds), "accepted_games": len(games),
            "excluded_games": len(excluded), "regulation_pitches": len(rows),
            "excluded_extra_inning_rows": excluded_extra_rows, "coverage": coverage,
            "unselected_csv_game_pks": sorted({key[0] for key in indexed} - set(ids))},
        "status": "complete_selected_games" if games and not excluded else "partial_or_empty",
        "full_season_coverage_verified": False, "formal_training_ready": False,
        "formal_policy_evaluation_ready": False}
    result["dataset_content_sha256"] = content_hash(result)
    return result


def verify_dataset(dataset: dict[str, Any]) -> None:
    """驗證固定衍生內容；runtime 與來源 manifests 不參與可重播內容指紋。"""
    payload = {k: v for k, v in dataset.items()
               if k not in {"dataset_content_sha256", "input_manifests", "runtime"}}
    if dataset.get("schema_version") != DATASET_VERSION or content_hash(payload) != dataset.get("dataset_content_sha256"):
        raise ValueError("Dataset A 版本或內容指紋不符")
    validate_contract(dataset["contract"])
    if content_hash(dataset["contract"]) != dataset["contract_sha256"]:
        raise ValueError("資料契約指紋不符")
    if dataset["feature_names"] != list(FEATURE_NAMES):
        raise ValueError("特徵名稱白名單不符")
    seen = set()
    row_counts = Counter()
    first_keys = {}
    games = {g["game_pk"]: g for g in dataset["games"]}
    if len(games) != len(dataset["games"]):
        raise ValueError("資料集含重複比賽")
    for game in games.values():
        if game["split"] != split_for_game(game["season"], game["game_pk"]):
            raise ValueError("場次 split 與年度不一致")
        if date.fromisoformat(game["game_date"]).year != game["season"]:
            raise ValueError("場次日期與年度不一致")
    for row in dataset["rows"]:
        key = row["game_pk"], row["at_bat_number"], row["pitch_number"]
        if key in seen:
            raise ValueError("資料集含重複逐球鍵")
        seen.add(key)
        row_counts[row["game_pk"]] += 1
        pa = key[:2]
        first_keys[pa] = min(key[2], first_keys.get(pa, key[2]))
        game = games[row["game_pk"]]
        for name in ("split", "season", "game_date"):
            if row[name] != game[name]:
                raise ValueError("同場逐球跨 split／年度／日期")
        if row["features"] != model_features(GameState(**row["pre_pitch_state"])):
            raise ValueError("特徵不符白名單或原始比分")
        if row["labels"]["home_win"] != game["home_win"] or type(game["home_win"]) is not int or game["home_win"] not in (0, 1):
            raise ValueError("同場勝負標籤不一致")
        remaining = row["labels"]["runs_to_half_end"]
        if row["sampling"]["re_half_eligible"]:
            checked_int(remaining, "runs_to_half_end", 0, 1000)
        elif remaining is not None:
            raise ValueError("未滿三出局半局不可有未截斷 RE 標籤")
    for row in dataset["rows"]:
        first = row["pitch_number"] == first_keys[row["game_pk"], row["at_bat_number"]]
        if row["sampling"]["re24_first_pitch"] is not first:
            raise ValueError("RE24 打席首球標記不符")
    for game_pk, game in games.items():
        if not row_counts[game_pk] or row_counts[game_pk] != game["expected_regulation_pitches"] or row_counts[game_pk] != game["regulation_pitches"]:
            raise ValueError("衍生資料逐球列數與場次核對結果不一致")
