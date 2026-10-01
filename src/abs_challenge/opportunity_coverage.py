"""完整投球對齊後的判決候選母體，保留零額度與資格未知狀態。"""

from collections import Counter

from .historical_alignment import align_historical_pitches
from .phase1 import call_only_limitation
from .savant import index_statcast_rows, selected_pre_pitch_state
from .state_value import GameState
from .source_eligibility import candidate_source_status
from .wp_coverage import grouped_summary


def pitcher_eligibility(feed, play):
    player_id = play["matchup"]["pitcher"]["id"]
    position = feed.get("gameData", {}).get("players", {}).get(f"ID{player_id}", {}).get("primaryPosition", {})
    kind, abbreviation = position.get("type"), position.get("abbreviation")
    if not kind or not abbreviation:
        return "unknown"
    if kind.lower() in {"pitcher", "two-way player"} or abbreviation in {"P", "TWP"}:
        return "pitcher"
    return "position_player"


def grouped_candidate_support(rows):
    """依候選母體分開計算分組覆蓋；零額度不進有額度分母。"""
    return {population: grouped_summary([row for row in rows if row["population"] == population])
            for population in sorted({row["population"] for row in rows})}


def candidate_missing_diagnostics(rows):
    """只匯出未雙側估值候選的事件鍵與 S0／S1 結構化原因。"""
    summaries = {population: {"candidate_count": 0, "missing_candidate_count": 0,
                 "branch_missing_reason_counts": Counter(), "not_evaluated_branch_counts": Counter()}
                 for population in sorted({row["population"] for row in rows})}
    evidence = []
    for row in rows:
        summary = summaries[row["population"]]
        summary["candidate_count"] += 1
        status = row["status"]
        if status == "both_supported":
            continue
        summary["missing_candidate_count"] += 1
        item = {name: row[name] for name in ("game_pk", "year", "regime", "at_bat_number",
            "pitch_number", "inning", "score_diff", "count", "decision_side", "population", "status")}
        item["feed_event_index"] = row["alignment"]["feed_event_index"]
        if status in {"one_supported", "neither_supported"}:
            for branch in ("s0", "s1"):
                side = row[branch]
                item[branch] = {name: side.get(name) for name in
                    ("supported", "post_home_score_diff", "terminal", "missing_reason_code")}
                if side["supported"] is False:
                    code = side.get("missing_reason_code")
                    if not code:
                        raise ValueError("未支援分支缺少結構化原因")
                    summary["branch_missing_reason_counts"][code] += 1
        else:
            item["reason"] = row.get("reason")
            summary["not_evaluated_branch_counts"][status] += 1
        evidence.append(item)
    return {"summary_by_population": {population: {
                **summary,
                "branch_missing_reason_counts": dict(sorted(summary["branch_missing_reason_counts"].items())),
                "not_evaluated_branch_counts": dict(sorted(summary["not_evaluated_branch_counts"].items())),
            } for population, summary in summaries.items()}, "rows": evidence}


def inspect_population(baseline, feed, audit, csv_rows, evaluate_call):
    """整場對齊失敗不回傳部分成功母體；不依 Reasonable 事後標籤篩選。"""
    pk = feed["gamePk"]
    if (feed["gameData"]["status"]["abstractGameState"] != "Final"
            or feed["gameData"]["game"]["type"] != "R"
            or feed["liveData"]["linescore"]["scheduledInnings"] != 9):
        raise ValueError("只接受已終場的原訂九局例行賽")
    plays = feed["liveData"]["plays"]["allPlays"]
    physical = sum(event.get("isPitch") is True for play in plays for event in play["playEvents"])
    official = sum(int(feed["liveData"]["boxscore"]["teams"][side]["teamStats"]["pitching"]["numberOfPitches"])
                   for side in ("home", "away"))
    if physical != official:
        raise ValueError("feed 實際投球數與官方總數不符")
    indexed = index_statcast_rows([row for row in csv_rows if int(row["game_pk"]) == pk and int(row["inning"]) <= 9])
    aligned, alignment = align_historical_pitches(feed, indexed)
    ledger = {(event["at_bat_index"] + 1, event["play_event_index"]): event
              for event in audit["ledger"] if event["inning"] <= 9}
    by_event = {(key[1], evidence["feed_event_index"]): (key, evidence) for key, evidence in aligned.items()}
    if set(ledger) - set(by_event):
        raise ValueError("Challenge 事件未完整對應已驗證的實際投球")
    teams = feed["gameData"]["teams"]
    budgets = {teams[side]["id"]: 2 for side in ("home", "away")}
    home_score = away_score = 0
    candidates = []
    physical_pitch_index = 0
    for play in plays:
        if play["about"]["inning"] > 9:
            continue
        pa = play["atBatIndex"] + 1
        for event in play["playEvents"]:
            event_key = (pa, event["index"])
            if event_key in by_event:
                physical_pitch_index += 1
                key, evidence = by_event[event_key]
                source = indexed[key]
                if (int(source["home_score"]), int(source["away_score"])) != (home_score, away_score):
                    raise ValueError(f"打席 {pa}：逐球前比分與跑壘重建不一致")
                code = evidence["feed_call_code"]
                challenge = ledger.get(event_key)
                if challenge is not None or code in {"B", "*B", "C"}:
                    final_call = "strike" if code == "C" else "ball"
                    original = challenge["original_call"] if challenge else final_call
                    batting = teams["home" if play["about"]["halfInning"] == "bottom" else "away"]["id"]
                    fielding = next(team for team in budgets if team != batting)
                    decision = batting if original == "strike" else fielding
                    remaining = budgets[decision]
                    if challenge and (challenge["challenges_before"] != remaining or challenge["challenge_team_id"] != decision
                                      or challenge["abs_call"] != final_call):
                        raise ValueError("對齊後的判決／額度與 Challenge ledger 不一致")
                    eligibility = pitcher_eligibility(feed, play)
                    population = ("zero_budget" if remaining == 0 else
                                  "excluded_position_player" if eligibility == "position_player" else
                                  "eligibility_unknown" if eligibility == "unknown" else "provisional_opportunity")
                    state = GameState.from_statcast(selected_pre_pitch_state(source))
                    row = {"game_pk": pk, "year": audit["game"]["season"], "regime": audit["rules"]["regime_id"],
                           "at_bat_number": pa, "pitch_number": key[2], "physical_pitch_index": physical_pitch_index,
                           "alignment": evidence,
                           "inning": state.inning, "score_diff": state.home_score - state.away_score,
                           "count": f"{state.balls}-{state.strikes}", "original_call": original,
                           "decision_side": "batting" if original == "strike" else "fielding",
                           "decision_team_id": decision, "challenges_remaining": remaining,
                           "pitcher_eligibility": eligibility, "population": population,
                           "actual_challenge": challenge is not None, "pre_pitch_state": state.to_dict(),
                           **candidate_source_status()}
                    probe = {"at_bat_index": pa - 1, "play_event_index": event["index"],
                             "pitch_number": evidence["feed_pitch_number"], "abs_call": final_call,
                             "batter_id": play["matchup"]["batter"]["id"]}
                    reason = call_only_limitation(feed, probe, state)
                    if reason:
                        row.update(status="unsupported_compound_event", reason=reason)
                    else:
                        row.update(evaluate_call(baseline, state, original))
                    candidates.append(row)
                    if challenge and not challenge["overturned"]:
                        budgets[decision] -= 1
            scores = [runner for runner in play["runners"]
                      if runner["details"]["playIndex"] == event["index"]
                      and runner["details"].get("isScoringEvent") is True
                      and runner["movement"].get("isOut") is False]
            if play["about"]["halfInning"] == "bottom":
                home_score += len(scores)
            else:
                away_score += len(scores)
        if (play["result"]["homeScore"], play["result"]["awayScore"]) != (home_score, away_score):
            raise ValueError(f"打席 {pa}：比分與打席結果不一致")
    if physical_pitch_index != len(aligned):
        raise ValueError("第 1–9 局投球序號與完整事件對齊數不一致")
    return {"status": "processed", "physical_regulation_pitches": len(aligned), "alignment": alignment,
            "candidate_count": len(candidates), "population_counts": dict(Counter(row["population"] for row in candidates)),
            "rows": candidates}
