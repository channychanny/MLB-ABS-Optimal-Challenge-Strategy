"""以獨立 Savant 球位與官方分隊計數復原 feed 缺漏的 ABS Challenge。"""

from __future__ import annotations

from collections import Counter
from itertools import product

from .extract import _build_challenge_event, canonical_call, extract_challenge_events
from .historical_alignment import align_historical_pitches
from .savant import index_statcast_rows


def _official_counts(feed: dict) -> Counter:
    counts = feed["gameData"].get("absChallenges") or {}
    if counts.get("hasChallenges") is not True:
        raise ValueError("官方終場 Challenge 分隊計數缺失")
    result = Counter()
    for side in ("away", "home"):
        team = feed["gameData"]["teams"][side]
        for overturned, field in ((False, "usedFailed"), (True, "usedSuccessful")):
            value = counts[side][field]
            if type(value) is not int or value < 0:
                raise ValueError("官方終場 Challenge 計數無效")
            result[team["id"], overturned] = value
    return result


def recover_abs_only_challenges(feed: dict, csv_rows: list[dict], abs_rows: list[dict]) -> dict:
    """所有缺球須唯一對齊且成功／失敗分配唯一，否則整場拒絕。"""
    pk = feed["gamePk"]
    plays = feed["liveData"]["plays"]["allPlays"]
    if max(play["about"]["inning"] for play in plays) > 9:
        raise ValueError("延長賽官方計數不能用於第 1–9 局缺球推定")
    official = _official_counts(feed)
    existing = extract_challenge_events(feed)
    observed = Counter((event.challenge_team_id, event.overturned) for event in existing)
    residual = official - observed
    if any(observed[key] > official[key] for key in observed):
        raise ValueError("feed Challenge 已超過官方分隊計數")
    missing_count = sum(residual.values())
    if not 1 <= missing_count <= 8:
        raise ValueError("ABS-only 復原只接受 1–8 個官方缺漏 Challenge")

    full_rows = [row for row in csv_rows if int(row["game_pk"]) == pk and int(row["inning"]) <= 9]
    indexed = index_statcast_rows(full_rows)
    aligned, alignment = align_historical_pitches(feed, indexed)
    by_event = {(key[1], evidence["feed_event_index"]): (key, evidence)
                for key, evidence in aligned.items()}
    if len(by_event) != len(aligned):
        raise ValueError("Savant 與 feed 逐球事件對齊不唯一")
    by_pa = {play["about"]["atBatIndex"] + 1: play for play in plays}
    known = {(event.at_bat_index + 1, event.play_event_index) for event in existing}
    matched, missing, seen = set(), [], set()
    for row in abs_rows:
        if int(row["game_pk"]) != pk:
            continue
        key = (pk, int(row["at_bat_number"]), int(row["pitch_number"]))
        if key in seen:
            raise ValueError("ABS-only 同球重複，不能復原")
        seen.add(key)
        evidence = aligned.get(key)
        if evidence is None:
            raise ValueError("ABS-only 挑戰球無法嚴格對齊完整逐球來源")
        pair = (key[1], evidence["feed_event_index"])
        play = by_pa[key[1]]
        event = play["playEvents"][pair[1]]
        final_call = canonical_call(event)
        expected = {"ball": "ball", "strike": "called_strike"}.get(final_call)
        if (expected is None or row.get("description") != expected
                or indexed[key].get("description") != expected
                or event.get("reviewDetails")):
            if pair not in known:
                raise ValueError("ABS-only 判決與 feed／完整逐球不符")
        if pair in known:
            matched.add(pair)
        else:
            if event.get("reviewDetails"):
                raise ValueError("未辨識的 feed review 不能當作 ABS-only 缺球")
            missing.append((key, pair, play, event, evidence, final_call))
    if known != matched or len(missing) != missing_count:
        raise ValueError("ABS-only 與 feed／官方計數仍有缺球，拒絕猜測位置")

    possibilities = []
    for outcomes in product((False, True), repeat=len(missing)):
        allocated = Counter()
        for item, overturned in zip(missing, outcomes):
            _, _, play, _, _, final_call = item
            side = "away" if play["about"]["halfInning"] == "top" else "home"
            batting = feed["gameData"]["teams"][side]["id"]
            fielding = feed["gameData"]["teams"]["home" if side == "away" else "away"]["id"]
            original = ("ball" if final_call == "strike" else "strike") if overturned else final_call
            team = batting if original == "strike" else fielding
            allocated[team, overturned] += 1
        if allocated == residual:
            possibilities.append(outcomes)
    if len(possibilities) != 1:
        raise ValueError("ABS-only 缺球的翻判與挑戰方無法由官方計數唯一確定")

    recovered, details = [], []
    for item, overturned in zip(missing, possibilities[0]):
        key, pair, play, event, evidence, _ = item
        challenge = _build_challenge_event(feed, play, evidence["feed_pitch_number"], event,
            {"isOverturned": overturned}, review_source="savant_abs_only_counter_reconciled",
            challenge_team_source="inferred_from_call_and_half")
        recovered.append(challenge)
        details.append({"game_pk": pk, "at_bat_number": key[1], "statcast_pitch_number": key[2],
                        "feed_pitch_number": evidence["feed_pitch_number"],
                        "feed_event_index": pair[1], "overturned": overturned,
                        "challenge_team_id": challenge.challenge_team_id,
                        "alignment": evidence})
    events = sorted(existing + recovered, key=lambda row: (row.at_bat_index, row.play_event_index))
    return {"events": events, "evidence": details, "alignment_summary": alignment,
            "official_counter_reconciled": True}
