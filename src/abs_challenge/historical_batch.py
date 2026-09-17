"""依固定清冊逐日共用來源，逐場保存 Dataset A，記錄失敗與覆蓋缺口。"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

from .historical import build_historical_dataset, content_hash, score_band, validate_contract, verify_dataset
from .savant import REQUIRED_PRE_PITCH_FIELDS, build_called_pitches_csv_url, parse_csv_text
from .source_cache import SourceCache, atomic_json_new


ALLOWED_SEASONS = {2019, 2021, 2022, 2023, 2024}


def validate_plan(plan: dict[str, Any]) -> None:
    if (plan.get("schema_version") != "historical-batch-plan-v1"
            or plan.get("purpose") != "engineering_sample"
            or plan.get("selection") != "lowest_game_pk_among_final_regular_games"):
        raise ValueError("未知批次計畫或選樣規則")
    seasons, dates, limit = plan["seasons"], plan["dates"], plan["games_per_date"]
    if (not seasons or any(type(s) is not int or s not in ALLOWED_SEASONS for s in seasons)
            or len(seasons) != len(set(seasons))):
        raise ValueError("開發批次只可使用不重複的 2019／2021–2024；2025／2026 受保留")
    if not dates or len(dates) != len(set(dates)):
        raise ValueError("必須列出不重複的確切日期，空日期不代表全季")
    parsed = [date.fromisoformat(d) for d in dates]
    if any(d.isoformat() != value for d, value in zip(parsed, dates)) or {d.year for d in parsed} != set(seasons):
        raise ValueError("抽樣日期與年度範圍不一致")
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 30):
        raise ValueError("games_per_date 必須為 1–30 或 null（指定日期全部候選場次）")


def schedule_url(season: int) -> str:
    if type(season) is not int or season not in ALLOWED_SEASONS:
        raise ValueError("批次賽程年度不在 Train／Validation 範圍")
    return "https://statsapi.mlb.com/api/v1/schedule?" + urlencode(
        {"sportId": 1, "season": season, "gameType": "R"})


def schedule_count(text: str) -> int:
    data = json.loads(text)
    count = sum(len(d["games"]) for d in data["dates"])
    if data.get("totalGames") != count:
        raise ValueError("賽程清冊回應列數不符")
    return count


def feed_count(text: str) -> int:
    data = json.loads(text)
    if type(data.get("gamePk")) is not int or "gameData" not in data or "liveData" not in data:
        raise ValueError("不是完整官方 feed JSON")
    return 1


def pitch_count(text: str) -> int:
    rows = parse_csv_text(text)
    required = set(REQUIRED_PRE_PITCH_FIELDS) | {"game_pk", "at_bat_number", "pitch_number", "game_date", "game_type"}
    if not rows or not required <= rows[0].keys():
        raise ValueError("逐球 CSV 為空或缺少欄位，不能快取錯誤頁面")
    return len(rows)


def normalize_schedule(text: str, season: int) -> dict[str, Any]:
    schedule_count(text)
    grouped = defaultdict(list)
    for day in json.loads(text)["dates"]:
        for game in day["games"]:
            game_pk = game["gamePk"]
            if type(game_pk) is not int or game_pk <= 0:
                raise ValueError("賽程 game_pk 無效")
            official_date = game["officialDate"]
            if date.fromisoformat(official_date).year != season or int(game["season"]) != season:
                raise ValueError("賽程含其他年度")
            grouped[game_pk].append({"game_pk": game_pk, "game_date": official_date,
                "schedule_date": day["date"], "season": season, "game_type": game["gameType"],
                "status": game["status"]["abstractGameState"],
                "detailed_status": game["status"].get("detailedState"),
                "scheduled_innings": game.get("scheduledInnings"),
                "home_team_id": game["teams"]["home"]["team"]["id"],
                "away_team_id": game["teams"]["away"]["team"]["id"]})
    records = []
    for game_pk, occurrences in sorted(grouped.items()):
        identity = {(g["game_date"], g["home_team_id"], g["away_team_id"], g["game_type"], g["scheduled_innings"])
                    for g in occurrences}
        # 同一比賽重列於補賽日仍只計一次；身分矛盾時不猜測。
        chosen = sorted(occurrences, key=lambda g: (g["status"] == "Final", g["schedule_date"]))[-1]
        reason = ("schedule_identity_conflict" if len(identity) != 1 else
                  "not_regular_season" if chosen["game_type"] != "R" else
                  "not_final" if chosen["status"] != "Final" else
                  "not_nine_innings" if chosen["scheduled_innings"] != 9 else None)
        records.append({**chosen, "occurrences": occurrences, "eligible": reason is None,
                        "exclusion_reason": reason})
    return {"schema_version": "historical-season-catalog-v1", "season": season,
        "raw_occurrences": sum(len(v) for v in grouped.values()), "games": records,
        "summary": {"unique_games": len(records), "eligible_games": sum(g["eligible"] for g in records),
            "excluded_by_reason": dict(Counter(g["exclusion_reason"] for g in records if not g["eligible"]))}}


def _save_fixed(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError(f"固定衍生檔案已變更，保留原檔：{path.name}")
    else:
        atomic_json_new(path, value)


def run_historical_batch(plan: dict[str, Any], contract: dict[str, Any], cache: SourceCache,
                         artifact_dir: Path, *, code_signature: str,
                         progress: Callable[[dict], None] = lambda event: None) -> dict[str, Any]:
    validate_plan(plan)
    validate_contract(contract)
    if not code_signature:
        raise ValueError("批次建置需程式內容指紋；不代表 Git commit")
    plan_hash = content_hash(plan)
    _save_fixed(artifact_dir / "plans" / f"{plan_hash}.json", plan)
    sources, catalogs, records, date_reports = {}, [], [], []
    accepted_games, coverage_rows = [], []
    used_game_ids = set()
    counters = Counter()

    def source(url, kind, count):
        item = cache.get(url, kind, count)
        sources[url] = item["manifest"]
        return item

    for season in sorted(plan["seasons"]):
        dates = sorted(d for d in plan["dates"] if date.fromisoformat(d).year == season)
        try:
            raw_schedule = source(schedule_url(season), "mlb_schedule_json", schedule_count)
            catalog = normalize_schedule(raw_schedule["text"], season)
            catalog_hash = content_hash(catalog)
            catalog_path = artifact_dir / "catalogs" / f"{season}_{catalog_hash}.json"
            _save_fixed(catalog_path, catalog)
            catalogs.append({"season": season, "relative_path": str(catalog_path.relative_to(artifact_dir)),
                             "content_sha256": catalog_hash, **catalog["summary"]})
            progress({"stage": "schedule", "season": season, **catalog["summary"]})
        except (OSError, ValueError, KeyError, TypeError) as error:
            date_reports.extend({"date": day, "status": "schedule_failed", "reason": str(error)} for day in dates)
            progress({"stage": "schedule_failed", "season": season, "reason": str(error)})
            continue
        for day in dates:
            eligible = [g for g in catalog["games"] if g["eligible"] and g["game_date"] == day]
            selected = eligible[:plan["games_per_date"]]
            day_record = {"date": day, "eligible_game_pks": [g["game_pk"] for g in eligible],
                          "selected_game_pks": [g["game_pk"] for g in selected], "status": "selected"}
            date_reports.append(day_record)
            if not selected:
                day_record["status"] = "no_eligible_games"
                continue
            try:
                csv_source = source(build_called_pitches_csv_url(day, "mlb"), "baseball_savant_pitch_csv", pitch_count)
                grouped_rows = defaultdict(list)
                for row in parse_csv_text(csv_source["text"]):
                    grouped_rows[int(row["game_pk"])].append(row)
            except (OSError, ValueError, KeyError, TypeError) as error:
                day_record["status"] = "csv_failed"
                for game in selected:
                    records.append({"game_pk": game["game_pk"], "game_date": day,
                        "status": "source_failed", "reason": str(error)})
                progress({"stage": "csv_failed", "date": day, "reason": str(error)})
                continue
            for game in selected:
                game_pk = game["game_pk"]
                if game_pk in used_game_ids:
                    raise ValueError("批次計畫重複選到同一 game_pk")
                used_game_ids.add(game_pk)
                record = {"game_pk": game_pk, "game_date": day}
                try:
                    feed_source = source(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live",
                                         "mlb_stats_api_feed_json", feed_count)
                    feed = json.loads(feed_source["text"])
                    if feed["gamePk"] != game_pk or feed["gameData"]["datetime"]["officialDate"] != day:
                        raise ValueError("feed 與選定賽程不一致")
                    for side in ("home", "away"):
                        if feed["gameData"]["teams"][side]["id"] != game[f"{side}_team_id"]:
                            raise ValueError("feed 與賽程主客隊身分不一致")
                    identity = {"feed_sha256": feed_source["manifest"]["content_sha256"],
                        "csv_sha256": csv_source["manifest"]["content_sha256"],
                        "contract_sha256": content_hash(contract), "code_signature": code_signature}
                    shard_key = content_hash(identity)
                    shard_path = artifact_dir / "shards" / f"{game_pk}_{shard_key}.json"
                    if shard_path.exists():
                        shard = json.loads(shard_path.read_text(encoding="utf-8"))
                        if shard.get("schema_version") != "historical-shard-v1" or shard["identity"] != identity:
                            raise ValueError("衍生分片來源指紋不符")
                        dataset = shard["dataset"]
                        verify_dataset(dataset)
                        counters["reused_shards"] += 1
                    else:
                        dataset = build_historical_dataset([feed], grouped_rows[game_pk], contract)
                        verify_dataset(dataset)
                        shard = {"schema_version": "historical-shard-v1", "identity": identity, "dataset": dataset}
                        atomic_json_new(shard_path, shard)
                        counters["built_shards"] += 1
                    if dataset["summary"]["input_games"] != 1 or dataset["summary"]["accepted_games"] + dataset["summary"]["excluded_games"] != 1:
                        raise ValueError("分片不是單場完整結果")
                    identities = [g["game_pk"] for g in dataset["games"] + dataset["excluded_games"]]
                    if identities != [game_pk]:
                        raise ValueError("分片場次與選定賽程不符")
                    record.update(relative_path=str(shard_path.relative_to(artifact_dir)),
                        shard_content_sha256=content_hash(shard), dataset_content_sha256=dataset["dataset_content_sha256"])
                    if dataset["games"]:
                        record["status"] = "accepted"
                        accepted_games.extend(dataset["games"])
                        # 只保留覆蓋統計所需的小欄位，不累積整批原始特徵／標籤。
                        coverage_rows.extend({"game_pk": game_pk, "date": day, "features": r["features"],
                            "re_censored": not r["sampling"]["re_half_eligible"]} for r in dataset["rows"])
                    else:
                        record.update(status="audit_excluded", reason=dataset["excluded_games"][0]["reason"])
                except (OSError, ValueError, KeyError, TypeError) as error:
                    record.update(status="source_or_build_failed", reason=str(error))
                records.append(record)
                progress({"stage": "game", **record})
    summary = _coverage_summary(records, accepted_games, coverage_rows)
    complete_sources = (all(d["status"] == "selected" for d in date_reports)
                        and len(date_reports) == len(plan["dates"])
                        and all(r["status"] in {"accepted", "audit_excluded"} for r in records))
    lock = {"schema_version": "historical-development-lock-v1", "plan_sha256": plan_hash,
        "contract_sha256": content_hash(contract), "code_signature": code_signature,
        "sources": [sources[key] for key in sorted(sources)], "catalogs": catalogs,
        "dates": date_reports, "games": records,
        "complete_selected_sources": complete_sources,
        "all_selected_games_accepted": bool(records) and complete_sources and all(r["status"] == "accepted" for r in records),
        "full_season_coverage_verified": False, "formal_training_ready": False}
    return {"schema_version": "historical-batch-report-v1", "plan": plan,
        "dataset_lock": lock, "dataset_lock_sha256": content_hash(lock), "summary": summary,
        "execution": {"cache_hits": cache.hits, "downloads": cache.downloads,
                      "retries": cache.retries, **counters},
        "status": "complete_selected_games" if lock["all_selected_games_accepted"] else "partial_or_excluded",
        "formal_training_ready": False, "formal_policy_evaluation_ready": False}


def _coverage_summary(records, games, rows):
    groups = {}
    selectors = {
        "season": lambda r: r["date"][:4], "month": lambda r: r["date"][:7],
        "score_band": lambda r: score_band(r["features"]["score_diff"]),
        "inning": lambda r: str(r["features"]["inning"]),
        "base_out": lambda r: f"{r['features']['bases']}-{r['features']['outs']}",
        "count": lambda r: f"{r['features']['balls']}-{r['features']['strikes']}",
    }
    for name, selector in selectors.items():
        counts, ids = Counter(), defaultdict(set)
        for row in rows:
            key = selector(row)
            counts[key] += 1
            ids[key].add(row["game_pk"])
        groups[name] = {k: {"pitches": counts[k], "games": len(ids[k])} for k in sorted(counts)}
    for band in ("0-5", "6-10", "11+"):
        groups["score_band"].setdefault(band, {"pitches": 0, "games": 0})
    censored = {r["game_pk"] for r in rows if r["re_censored"]}
    return {"selected_games": len(records), "accepted_games": len(games),
        "status_counts": dict(Counter(r["status"] for r in records)), "regulation_pitches": len(rows),
        "regulation_tied_games": sum(g["regulation_tied"] for g in games),
        "walkoff_censored_games": len(censored), "coverage": groups,
        "exclusion_reasons": dict(Counter(r.get("reason") for r in records if r["status"] != "accepted")),
        "note": "固定日期與編號的工程樣本，非全季、非隨機代表性抽樣；尚無分組信賴區間。"}
