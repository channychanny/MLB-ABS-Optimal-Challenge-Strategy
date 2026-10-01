"""按預宣告時間窗鎖定 Dataset B 賽程候選；不讀取逐球或比賽結果。"""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode

from .dataset_b_split import validate_plan as validate_split_plan
from .phase1_cli import _runtime
from .provenance import build_file_manifest
from .source_cache import SourceCache, atomic_json_new


def validate_sampling_plan(sampling: dict, split_plan: dict) -> None:
    validate_split_plan(split_plan)
    quotas = sampling.get("quotas")
    names = {row["name"] for row in split_plan["windows"]}
    if (sampling.get("schema_version") != "dataset-b-schedule-sampling-v1"
            or sampling.get("selection") != "sha256_seed_window_game_pk"
            or sampling.get("replacement") is not False
            or not isinstance(sampling.get("seed"), str) or not sampling["seed"]
            or not isinstance(quotas, dict) or set(quotas) != names
            or any(type(value) is not int or not 1 <= value <= 100 for value in quotas.values())):
        raise ValueError("Dataset B 賽程抽樣契約、時間窗或固定配額無效")


def schedule_url(window: dict) -> str:
    params = {"sportId": window["sport_id"], "startDate": window["start"],
              "endDate": window["end"], "gameType": "R", "hydrate": "team"}
    if window["league_id"] is not None:
        params["leagueId"] = window["league_id"]
    return "https://statsapi.mlb.com/api/v1/schedule?" + urlencode(params)


def schedule_count(text: str) -> int:
    return sum(len(day["games"]) for day in json.loads(text)["dates"])


def select_window(sampling: dict, split_plan: dict, window: dict, payload: dict) -> dict:
    """只以賽程資格與固定雜湊排序；不使用比分、ABS 次數或球員表現。"""
    start, end = date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
    seen, candidates, excluded = set(), [], []
    rescheduled_listings = 0
    development = set(split_plan["known_development_game_pks"])
    for day in payload["dates"]:
        day_date = date.fromisoformat(day["date"])
        if not start <= day_date <= end:
            raise ValueError("賽程回應超出預宣告時間窗")
        for game in day["games"]:
            pk = game["gamePk"]
            # Stats API 會把改期場次同時列在原排程日與正式日期。
            # 只保留 officialDate 所在的 canonical listing，避免同場重複抽樣。
            if game["officialDate"] != day["date"]:
                rescheduled_listings += 1
                continue
            if type(pk) is not int or pk <= 0 or pk in seen:
                raise ValueError("賽程 game_pk 重複或無效")
            seen.add(pk)
            played = date.fromisoformat(game["officialDate"])
            reason = None
            if not start <= played <= end:
                reason = "official_date_outside_window"
            elif game["gameType"] != "R":
                reason = "not_regular"
            elif game["status"]["abstractGameState"] != "Final":
                reason = "not_final"
            elif game.get("scheduledInnings") != 9:
                reason = "not_scheduled_nine_innings"
            elif pk in development:
                reason = "known_development_game"
            else:
                for side in ("away", "home"):
                    team = game["teams"][side]["team"]
                    if team.get("sport", {}).get("id") != window["sport_id"]:
                        reason = "sport_unknown_or_mismatch"
                        break
                    if (window["league_id"] is not None
                            and team.get("league", {}).get("id") != window["league_id"]):
                        reason = "league_unknown_or_mismatch"
                        break
            if reason:
                excluded.append({"game_pk": pk, "reason": reason})
                continue
            rank = sha256(f"{sampling['seed']}|{window['name']}|{pk}".encode()).hexdigest()
            candidates.append({"game_pk": pk, "date": played.isoformat(),
                               "split": window["split"], "window": window["name"],
                               "rank_sha256": rank, "sport_id": window["sport_id"],
                               "league_id": window["league_id"], "regime": window["regime"],
                               "feed_rule_confirmation_required": True,
                               "source_eligibility_status": "provisional_source_limitations"})
    candidates.sort(key=lambda row: (row["rank_sha256"], row["game_pk"]))
    take = sampling["quotas"][window["name"]]
    return {"window": window["name"], "split": window["split"],
            "status": "selected" if len(candidates) >= take else "shortfall",
            "eligible_count": len(candidates), "quota": take,
            "rescheduled_listings_ignored": rescheduled_listings,
            "selected": candidates[:take], "not_selected": candidates[take:],
            "excluded": sorted(excluded, key=lambda row: row["game_pk"]),
            "shortfall": max(0, take - len(candidates))}


def build_selection(sampling: dict, split_plan: dict, cache: SourceCache) -> dict:
    validate_sampling_plan(sampling, split_plan)
    windows, sources = [], []
    for window in split_plan["windows"]:
        try:
            source = cache.get(schedule_url(window), "dataset_b_schedule_json", schedule_count)
            sources.append(source["manifest"])
            windows.append(select_window(sampling, split_plan, window, json.loads(source["text"])))
        except (OSError, KeyError, TypeError, ValueError) as error:
            windows.append({"window": window["name"], "split": window["split"],
                            "status": "source_failure", "reason": str(error), "selected": [],
                            "quota": sampling["quotas"][window["name"]],
                            "shortfall": sampling["quotas"][window["name"]]})
    games = [game for item in windows for game in item["selected"]]
    if len({game["game_pk"] for game in games}) != len(games):
        raise ValueError("不同時間窗重複選到相同 game_pk")
    lock = {"sampling_plan": sampling, "split_plan": split_plan, "windows": windows, "sources": sources}
    complete = all(row["status"] == "selected" for row in windows)
    return {"schema_version": "dataset-b-schedule-selection-v1", **lock,
            "selected_count": len(games), "selection_complete": complete,
            "schedule_game_lists_locked": complete,
            "selection_sha256": sha256(json.dumps(lock, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            "holdout_game_lists_locked": False, "formal_model_evaluation_ready": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sampling-plan", type=Path, required=True)
    parser.add_argument("--split-plan", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("不得覆寫既有 Dataset B 抽樣清冊")
    sampling = json.loads(args.sampling_plan.read_text(encoding="utf-8"))
    split_plan = json.loads(args.split_plan.read_text(encoding="utf-8"))
    cache = SourceCache(args.cache_dir, offline=args.offline)
    result = build_selection(sampling, split_plan, cache)
    result["sampling_plan_manifest"] = build_file_manifest(args.sampling_plan, source_type="dataset_b_sampling_plan")
    result["split_plan_manifest"] = build_file_manifest(args.split_plan, source_type="dataset_b_split_plan")
    result["runtime"] = _runtime()
    result["cache"] = {"downloads": cache.downloads, "hits": cache.hits}
    atomic_json_new(args.output, result)
    print(json.dumps({"selected": result["selected_count"],
                      "selection_complete": result["selection_complete"],
                      "selection_sha256": result["selection_sha256"],
                      "cache": result["cache"]}, ensure_ascii=False))
    return 0 if result["selection_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
