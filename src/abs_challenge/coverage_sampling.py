"""先鎖定賽程樣本，再取得逐球結果；不依 ABS 行為選場。"""

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode

from .phase1_cli import _runtime
from .provenance import build_file_manifest
from .source_cache import SourceCache, atomic_json_new


def schedule_url(stratum):
    params = {"sportId": stratum["sport_id"], "date": stratum["date"], "gameType": "R", "hydrate": "team"}
    if stratum["league_id"] is not None:
        params["leagueId"] = stratum["league_id"]
    return "https://statsapi.mlb.com/api/v1/schedule?" + urlencode(params)


def schedule_count(text):
    return sum(len(day["games"]) for day in json.loads(text)["dates"])


def validate_plan(plan):
    if (plan.get("schema_version") != "wp-coverage-sampling-v1"
            or plan.get("selection") != "sha256_seed_stratum_game_pk" or plan.get("replacement") is not False
            or not isinstance(plan.get("seed"), str) or not plan["seed"]):
        raise ValueError("抽樣契約不符")
    seen = set()
    seen_queries = set()
    for stratum in plan["strata"]:
        when = date.fromisoformat(stratum["date"])
        sport, league = stratum["sport_id"], stratum["league_id"]
        allowed = ((when.year == 2024 and when >= date(2024, 6, 25) and sport == 11 and league == 117)
                   or (when.year == 2025 and sport == 11 and league in {117, 112})
                   or (when.year == 2026 and sport == 1 and league is None))
        query = (sport, league, stratum["date"])
        if (not allowed or stratum["id"] in seen or query in seen_queries
                or type(stratum["take"]) is not int or not 1 <= stratum["take"] <= 10):
            raise ValueError("抽樣分層重複、額度制度／日期或場次數無效")
        seen.add(stratum["id"])
        seen_queries.add(query)
    if not seen:
        raise ValueError("抽樣分層不可為空")


def select_games(plan, stratum, payload):
    """只讀資格 metadata；排序不讀比分、投球或挑戰結果。"""
    candidates, excluded, seen = [], [], set()
    for day in payload["dates"]:
        if day["date"] != stratum["date"]:
            raise ValueError("賽程回應日期不符")
        for game in day["games"]:
            pk = game["gamePk"]
            if type(pk) is not int or pk <= 0 or pk in seen:
                raise ValueError("賽程 game_pk 重複或無效")
            seen.add(pk)
            reason = None
            if game["officialDate"] != stratum["date"]:
                reason = "official_date_mismatch"
            elif game["gameType"] != "R":
                reason = "not_regular"
            elif game["status"]["abstractGameState"] != "Final":
                reason = "not_final"
            elif game.get("scheduledInnings") != 9:
                reason = "not_confirmed_nine_innings"
            elif pk in plan.get("development_game_pks", []):
                reason = "known_development_game"
            else:
                for side in ("away", "home"):
                    team = game["teams"][side]["team"]
                    if team.get("sport", {}).get("id") != stratum["sport_id"]:
                        reason = "sport_unknown_or_mismatch"
                    if stratum["league_id"] is not None and team.get("league", {}).get("id") != stratum["league_id"]:
                        reason = "league_unknown_or_mismatch"
            if reason:
                excluded.append({"game_pk": pk, "reason": reason})
                continue
            rank = sha256(f"{plan['seed']}|{stratum['id']}|{pk}".encode()).hexdigest()
            candidates.append({"game_pk": pk, "date": stratum["date"], "rank_sha256": rank,
                               "sport_id": stratum["sport_id"], "league_id": stratum["league_id"],
                               "feed_rule_confirmation_required": True})
    candidates.sort(key=lambda row: (row["rank_sha256"], row["game_pk"]))
    return {"stratum": stratum, "status": "selected" if len(candidates) >= stratum["take"] else "shortfall",
            "eligible_count": len(candidates), "selected": candidates[:stratum["take"]],
            "not_selected": candidates[stratum["take"]:], "excluded": sorted(excluded, key=lambda row: row["game_pk"]),
            "shortfall": max(0, stratum["take"] - len(candidates))}


def build_selection(plan, cache):
    validate_plan(plan)
    strata, sources = [], []
    for stratum in plan["strata"]:
        try:
            source = cache.get(schedule_url(stratum), "abs_coverage_schedule_json", schedule_count)
            sources.append(source["manifest"])
            strata.append(select_games(plan, stratum, json.loads(source["text"])))
        except (OSError, KeyError, TypeError, ValueError) as error:
            strata.append({"stratum": stratum, "status": "source_failure", "reason": str(error),
                           "selected": [], "shortfall": stratum["take"]})
    games = [row for item in strata for row in item["selected"]]
    if len({row["game_pk"] for row in games}) != len(games):
        raise ValueError("不同分層出現重複比賽，不能重複加權")
    lock = {"plan": plan, "strata": strata, "sources": sources}
    return {"schema_version": "wp-coverage-selection-v1", **lock,
            "selected_count": len(games), "selection_complete": all(row["status"] == "selected" for row in strata),
            "selection_sha256": sha256(json.dumps(lock, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            "coverage_evaluated": False, "formal_policy_evaluation_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("不得覆寫既有抽樣清冊")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    cache = SourceCache(args.cache_dir, offline=args.offline)
    result = build_selection(plan, cache)
    result["plan_manifest"] = build_file_manifest(args.plan, source_type="coverage_sampling_plan")
    result["runtime"] = _runtime()
    result["cache"] = {"downloads": cache.downloads, "hits": cache.hits}
    atomic_json_new(args.output, result)
    print(json.dumps({"selected": result["selected_count"], "selection_complete": result["selection_complete"],
                      "selection_sha256": result["selection_sha256"], "cache": result["cache"]}, ensure_ascii=False))
    return 0 if result["selection_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
