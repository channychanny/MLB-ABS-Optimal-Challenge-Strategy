"""Phase 1 真實小樣本估值；保守排除尚未定義的反事實跑壘。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .baseline import MissingBaselineState, SavantBaseline
from .state_value import GameState, apply_call


def call_only_limitation(feed: dict[str, Any], row: dict[str, Any], state: GameState) -> str | None:
    """檢查同球額外事件；沒有旗標不代表正式 Legal population 已確認。"""
    plays = [play for play in feed["liveData"]["plays"]["allPlays"]
             if play["atBatIndex"] == row["at_bat_index"]]
    if len(plays) != 1:
        return "無法唯一找到官方打席"
    play = plays[0]
    events = play.get("playEvents", [])
    pitches = [event for event in events if event["index"] == row["play_event_index"]]
    if len(pitches) != 1 or pitches[0].get("pitchNumber") != row["pitch_number"]:
        return "無法唯一找到官方逐球事件"
    pitch = pitches[0]
    if pitch.get("details", {}).get("description") not in {"Ball", "Called Strike"}:
        return "不是純 called ball／strike（可能有 blocked ball 或額外動作）"
    actual = apply_call(state, row["abs_call"])
    expected_outs = 3 if actual.half_ended else actual.re_outs
    if pitch.get("count", {}).get("outs") != expected_outs:
        return "官方球後出局數與純判決不符"
    is_walk = row["abs_call"] == "ball" and state.balls == 3
    is_strikeout = row["abs_call"] == "strike" and state.strikes == 2
    later_pitches = [e["index"] for e in events if e.get("isPitch") and e["index"] > pitch["index"]]
    next_pitch_index = min(later_pitches, default=float("inf"))
    # 打席終局若不是單純 BB／K，不推定不死三振或複合出局的另一條路徑。
    if next_pitch_index == float("inf") and (is_walk or is_strikeout):
        expected_type = "walk" if is_walk else "strikeout"
        if play.get("result", {}).get("eventType") != expected_type:
            return "終局事件不是單純保送／三振"
    for runner in play.get("runners", []):
        details = runner.get("details", {})
        index = details.get("playIndex")
        if index is None:
            return "官方跑壘缺少事件索引"
        if not pitch["index"] <= index < next_pitch_index:
            continue
        movement = runner.get("movement", {})
        start, end = movement.get("start"), movement.get("end")
        runner_id = (details.get("runner") or {}).get("id")
        if is_walk and details.get("eventType") == "walk" and not movement.get("isOut"):
            expected = {None: "1B"}
            if state.bases & 1:
                expected["1B"] = "2B"
            if state.bases & 3 == 3:
                expected["2B"] = "3B"
            if state.bases == 7:
                expected["3B"] = "score"
            if start in expected and end == expected[start]:
                if start is not None or runner_id == row["batter_id"]:
                    continue
        if (is_strikeout and details.get("eventType") == "strikeout"
                and runner_id == row["batter_id"] and movement.get("isOut") is True):
            continue
        return "同球有非單純保送強迫進壘／三振的跑壘事件"
    return None


def value_audited_challenges(
    baseline: SavantBaseline, audits: list[dict[str, Any]], feeds: list[dict[str, Any]],
) -> dict[str, Any]:
    """估值 actual attempts 樣本，不將其視為完整機會母體或 policy evaluation。"""
    feed_index = {feed["gamePk"]: feed for feed in feeds}
    game_ids = [audit["game"]["game_pk"] for audit in audits]
    if (not audits or len(set(game_ids)) != len(game_ids) or len(feed_index) != len(feeds)
            or set(feed_index) != set(game_ids)):
        raise ValueError("audit／feed 場次必須非空、唯一且完全對應")
    rows = []
    for audit in audits:
        if audit["summary"].get("phase0_game_pass") is not True:
            raise ValueError("單場 Phase 0 未通過")
        rules = audit["rules"]
        if (rules.get("initial_challenges") != 2 or rules.get("successful_challenge_retained") is not True
                or rules.get("abs_format") != "challenge" or rules.get("rule_status") != "confirmed"):
            raise ValueError("Phase 1 主要原型只接受已確認的成功保留／兩次額度制度")
        game_pk = audit["game"]["game_pk"]
        for row in audit["ledger"]:
            output: dict[str, Any] = {"game_pk": game_pk, "at_bat_number": row["at_bat_index"] + 1,
                "pitch_number": row["pitch_number"], "original_call": row["original_call"],
                "decision_team_id": row["challenge_team_id"], "challenges_remaining": row["challenges_before"]}
            rows.append(output)
            if row["inning"] > 9:
                output.update(status="excluded_extra_inning", reason="第 10 局以後不在主要研究範圍")
                continue
            try:
                state = GameState.from_statcast(row["statcast_pre_pitch_state"])
                if (state.inning != row["inning"] or state.half != row["half_inning"]
                        or state.balls != row["balls_before"] or state.strikes != row["strikes_before"]):
                    raise ValueError("audit 事件與判決前狀態不一致")
                if type(row["challenges_before"]) is not int or row["challenges_before"] not in {1, 2}:
                    raise ValueError("決策當下沒有有效的一或兩次額度")
                batting_id = audit["game"]["home_team" if state.half == "bottom" else "away_team"]["id"]
                fielding_id = audit["game"]["away_team" if state.half == "bottom" else "home_team"]["id"]
                if row["challenge_team_id"] != (batting_id if row["original_call"] == "strike" else fielding_id):
                    raise ValueError("Decision Team 與不利判決方向不一致")
                reason = call_only_limitation(feed_index[game_pk], row, state)
                if reason:
                    output.update(status="unsupported_compound_event", reason=reason)
                    continue
                value = baseline.value_call(state, row["original_call"])
                output.update(status="valued", pre_pitch_state=state.to_dict(), valuation=value)
            except MissingBaselineState as error:
                output.update(status="missing_baseline_state", reason=str(error))
            except (KeyError, TypeError, ValueError) as error:
                output.update(status="invalid_state", reason=str(error))
    counts = Counter(row["status"] for row in rows)
    valued = [row["valuation"]["delta_wp_percentage_points"] for row in rows if row["status"] == "valued"]
    warnings = sum(bool(row["valuation"]["warnings"]) for row in rows if row["status"] == "valued")
    complete = bool(valued) and len(valued) + counts["excluded_extra_inning"] == len(rows) and not warnings
    return {
        "schema_version": "phase1-counterfactual-report-v1",
        "status": "complete_smoke_test" if complete else "partial_smoke_test",
        "formal_policy_evaluation_ready": False,
        "population": "phase0_verified_actual_attempts_only",
        "legal_opportunity_status": "provisional_source_limitations",
        "summary": {"games": len(audits), "attempts": len(rows), "status_counts": dict(counts),
            "valuation_warnings": warnings, "maximum_delta_wp_percentage_points": max(valued, default=None),
            "minimum_delta_wp_percentage_points": min(valued, default=None)},
        "limitations": [
            "少量實際挑戰樣本只驗證資料流程，不估計全部機會分布或策略成效。",
            "兩條路徑均假定沒有額外跑壘；官方同球有複合事件者不估值。",
            "官方資料窗口可能涵蓋測試年度，只能稱作外部原型。",
            "Technical outage／post-replay-review 排除及正式 commit 基準仍未完成。",
        ],
        "rows": rows,
    }
