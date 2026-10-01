"""Dataset A 專用事件序列對齊；不改動 Phase 0 的 Challenge 串接。"""

from __future__ import annotations

from collections import defaultdict

from .state_value import checked_int


ALIGNMENT_VERSION = "historical-event-alignment-v1"
AUTOMATIC_CALLS = {"V": "automatic_ball", "VB": "automatic_ball",
                   "VP": "automatic_ball", "AC": "automatic_strike",
                   "AB": "automatic_strike"}
# 固定樣本核對過的來源判決碼；未支援碼須新增來源證據與測試後才能納入。
PHYSICAL_CALLS = {"B": "ball", "*B": "blocked_ball", "C": "called_strike", "F": "foul",
    "S": "swinging_strike", "W": "swinging_strike_blocked", "T": "foul_tip",
    "L": "foul_bunt", "O": "bunt_foul_tip", "H": "hit_by_pitch", "M": "missed_bunt",
    "X": "hit_into_play", "D": "hit_into_play", "E": "hit_into_play", "P": "pitchout"}
BASES = ("1B", "2B", "3B")


def _feed_only_non_pitch(event):
    """固定來源的 N 事件無 CSV 列；跑壘仍交由完整事件狀態重建。"""
    details = event.get("details", {})
    return (event.get("type") == "no_pitch" and event.get("isPitch") is False
            and details.get("code") == "N" and details.get("call") is None
            and event.get("pitchNumber") is None and not event.get("pitchData")
            and type(details.get("isOut")) is bool
            and not details.get("isBall") and not details.get("isStrike"))


def _integer(value, name, maximum=1000):
    if isinstance(value, str) and value.isascii() and value.isdigit():
        value = int(value)
    return checked_int(value, name, 0, maximum)


def _event_states(feed):
    """從半局起點與 runner movement 重建事件前狀態，不讀 Statcast 作答案。"""
    states, bases, half_key, outs = {}, {}, None, 0
    for play in feed["liveData"]["plays"]["allPlays"]:
        about = play["about"]
        if about["inning"] > 9:
            continue
        current_half = (about["inning"], about["halfInning"])
        if current_half != half_key:
            bases, outs, half_key = {}, 0, current_half
        pa = about["atBatIndex"] + 1
        movements = defaultdict(list)
        indices = {event["index"] for event in play["playEvents"]}
        for runner in play["runners"]:
            index = runner["details"]["playIndex"]
            if index not in indices:
                raise ValueError(f"打席 {pa}：跑者移動沒有對應事件")
            movements[index].append(runner)
        for event in play["playEvents"]:
            index = event["index"]
            states[pa, index] = {"inning": about["inning"], "half": about["halfInning"],
                "outs": outs, "bases": sum(1 << i for i, base in enumerate(BASES) if base in bases),
                "runner_ids": [bases.get(base) for base in BASES]}
            next_bases = bases.copy()
            if (event.get("isSubstitution") is True
                    and event.get("position", {}).get("code") == "12"):
                base_number = _integer(event["base"], "pinch_runner_base", 3)
                if base_number < 1:
                    raise ValueError(f"打席 {pa}：代跑壘位不合法")
                base = BASES[base_number - 1]
                if bases.get(base) != event["replacedPlayer"]["id"]:
                    raise ValueError(f"打席 {pa}：代跑者與原跑者不一致")
                next_bases[base] = event["player"]["id"]
            paths = defaultdict(list)
            for runner in movements[index]:
                paths[runner["details"]["runner"]["id"]].append(runner["movement"])
            destinations = {}
            for runner_id, segments in paths.items():
                position = next((base for base, occupant in bases.items() if occupant == runner_id), None)
                for base, occupant in bases.items():
                    if occupant == runner_id:
                        next_bases.pop(base, None)
                # feed 可附帶同跑者的全空佔位列；只在另有實際移動證據時忽略。
                pending = [m for m in segments if any(m.get(name) is not None for name in
                    ("originBase", "start", "end", "outBase", "isOut", "outNumber"))]
                if not pending:
                    raise ValueError(f"打席 {pa}：只有空跑者移動，證據不足")
                if any(type(m["isOut"]) is not bool for m in pending):
                    raise ValueError(f"打席 {pa}：跑者出局狀態不明")
                while pending:
                    candidates = [m for m in pending if m["start"] == position]
                    if len(candidates) != 1:
                        raise ValueError(f"打席 {pa}：跑者移動路徑不唯一或起點不符")
                    movement = candidates[0]
                    pending.remove(movement)
                    position = movement["end"]
                    if pending and (movement["isOut"] or position not in BASES):
                        raise ValueError(f"打席 {pa}：跑者終止後仍有移動")
                destinations[runner_id] = movement
            terminal_outs = max([outs, _integer(event["count"]["outs"], "outs", 3)] +
                [_integer(m["outNumber"], "out_number", 3) for m in destinations.values() if m["isOut"]])
            for runner_id, movement in destinations.items():
                if movement["isOut"]:
                    outs = max(outs, _integer(movement["outNumber"], "out_number", 3))
                elif movement["end"] in BASES:
                    # 第三出局後沒有可延續的壘包狀態；feed 未必記錄其他跑者續跑。
                    if terminal_outs == 3:
                        continue
                    end = movement["end"]
                    if end in next_bases:
                        raise ValueError(f"打席 {pa}：同壘有多位跑者")
                    next_bases[end] = runner_id
                elif movement["end"] not in {None, "score", "4B"}:
                    raise ValueError(f"打席 {pa}：未知跑者終點")
            bases = {} if terminal_outs == 3 else next_bases
            outs = terminal_outs
        if outs != _integer(play["count"]["outs"], "play_outs", 3):
            raise ValueError(f"打席 {pa}：跑者移動與打席終點出局數不一致")
        if outs < 3:
            matchup = play["matchup"]
            official = {base: matchup[name]["id"] for base, name in zip(BASES,
                ("postOnFirst", "postOnSecond", "postOnThird")) if matchup.get(name)}
            if bases != official:
                raise ValueError(f"打席 {pa}：跑者移動與打席終點壘包不一致")
    return states


def align_historical_pitches(feed, indexed):
    """每個打席依事件順序及球數核對，一對一留下實際投球與來源證據。"""
    grouped = defaultdict(list)
    for key, row in sorted(indexed.items()):
        if row.get("game_type") != "R" or row.get("game_date") != feed["gameData"]["datetime"]["officialDate"]:
            raise ValueError("Statcast 日期／賽事類型與官方 feed 不符")
        grouped[key[1]].append((key, row))
    states = _event_states(feed)
    aligned, excluded, visited, feed_only = {}, [], set(), []
    for play in feed["liveData"]["plays"]["allPlays"]:
        about = play["about"]
        if about["inning"] > 9:
            continue
        pa = about["atBatIndex"] + 1
        visited.add(pa)
        events = play["playEvents"]
        indices = [e["index"] for e in events]
        if indices != list(range(len(events))):
            raise ValueError(f"打席 {pa}：feed 事件序號不連續")
        observed = [e for e in events if (e.get("isPitch") is True or e.get("type") == "no_pitch")
                    and not _feed_only_non_pitch(e)]
        rows = grouped[pa]
        if len(rows) != len(observed):
            raise ValueError(f"打席 {pa}：完整事件鍵不符：缺少 {max(0, len(observed) - len(rows))}、"
                             f"多出 {max(0, len(rows) - len(observed))}")
        if [key[2] for key, _ in rows] != list(range(1, len(rows) + 1)):
            raise ValueError(f"打席 {pa}：Statcast 事件編號缺漏或不是從一開始")
        balls = strikes = cursor = 0
        for event in events:
            after = (_integer(event["count"]["balls"], "balls", 4),
                     _integer(event["count"]["strikes"], "strikes", 3))
            if _feed_only_non_pitch(event):
                if after != (balls, strikes):
                    raise ValueError(f"打席 {pa}：N 非投球事件不可改變球數")
                runner_out = any(r["details"]["playIndex"] == event["index"]
                                 and r["movement"].get("isOut") is True for r in play["runners"])
                if event["details"]["isOut"] != runner_out:
                    raise ValueError(f"打席 {pa}：N 非投球出局旗標與跑者證據不一致")
                before = states[pa, event["index"]]
                feed_only.append({"at_bat_number": pa, "feed_event_index": event["index"],
                    "kind": "feed_only_no_pitch", "feed_call_code": "N",
                    "balls_before": balls, "strikes_before": strikes,
                    "balls_after": after[0], "strikes_after": after[1],
                    "outs_before": before["outs"], "bases_before": before["bases"],
                    "runner_ids_before": before["runner_ids"], "event_is_out": event["details"]["isOut"],
                    "state_checks_pass": True})
                continue
            physical = event.get("isPitch") is True
            automatic = event.get("type") == "no_pitch"
            if not physical and not automatic:
                if after != (balls, strikes):
                    raise ValueError(f"打席 {pa}：未支援的非投球球數變化")
                continue
            key, row = rows[cursor]
            cursor += 1
            code = event["details"]["call"]["code"]
            if physical and (automatic or code in AUTOMATIC_CALLS
                             or row.get("description") in set(AUTOMATIC_CALLS.values())):
                raise ValueError(f"打席 {pa}：實際投球與自動判決類型不一致")
            if physical and (code not in PHYSICAL_CALLS or row.get("description") != PHYSICAL_CALLS[code]):
                raise ValueError(f"打席 {pa}：未支援判決碼或兩來源判決類型不一致")
            if physical:
                # 固定 feed 的觸身球 H 也將 balls 加一；這是來源計數語意，不是 ABS 判決。
                expected_after = ((balls + 1, strikes) if code in {"B", "*B", "H", "P"} else
                    (balls, min(strikes + 1, 2)) if code == "F" else
                    (balls, strikes + 1) if code in {"C", "S", "W", "T", "L", "O", "M"} else
                    (balls, strikes))
                if after != expected_after:
                    raise ValueError(f"打席 {pa}：投球後球數與判決不一致")
            if (_integer(row["balls"], "balls", 3), _integer(row["strikes"], "strikes", 2)) != (balls, strikes):
                raise ValueError(f"打席 {pa}／事件 {event['index']}：投球前球數不一致")
            before = states[pa, event["index"]]
            if any(name not in row for name in ("on_1b", "on_2b", "on_3b")):
                raise ValueError("缺少壘包欄位；缺欄不可當成空壘")
            runners = [None if row[name] in {None, "", "null", "nan"} else
                       _integer(row[name], name, 10**9) for name in ("on_1b", "on_2b", "on_3b")]
            if (_integer(row["outs_when_up"], "outs", 2) != before["outs"]
                    or runners != before["runner_ids"]):
                raise ValueError(f"打席 {pa}／事件 {event['index']}：投球前出局／壘包狀態不一致")
            if (_integer(row["inning"], "inning", 9) != before["inning"]
                    or row["inning_topbot"] != ("Top" if before["half"] == "top" else "Bot")):
                raise ValueError(f"打席 {pa}：Statcast 局數與官方 feed 不符")
            evidence = {"schema_version": ALIGNMENT_VERSION,
                "feed_event_index": event["index"], "feed_pitch_number": event["pitchNumber"],
                "statcast_pitch_number": key[2], "feed_call_code": code,
                "balls_before": balls, "strikes_before": strikes,
                "balls_after": after[0], "strikes_after": after[1],
                "outs_before": before["outs"], "bases_before": before["bases"],
                "runner_ids_before": before["runner_ids"], "state_checks_pass": True}
            if automatic:
                kind = AUTOMATIC_CALLS.get(code)
                expected = (balls + 1, strikes) if kind == "automatic_ball" else (balls, strikes + 1)
                batter_timeout_evidence = (code != "AB" or
                    (event.get("isPitch") is False
                     and event["details"].get("call", {}).get("description") ==
                         "Automatic Strike - Batter Timeout Violation"
                     and isinstance(event["details"].get("violation"), dict)
                     and event["details"]["violation"].get("type") == "batter_timeout"
                     and event["details"].get("isStrike") is True
                     and event["details"].get("isBall") is False))
                if (physical or kind is None or not batter_timeout_evidence
                        or row.get("description") != kind or after != expected):
                    raise ValueError(f"打席 {pa}：自動判決證據或球數變化不一致")
                excluded.append({"at_bat_number": pa, "kind": kind, **evidence})
            else:
                aligned[key] = evidence
            balls, strikes = after
    if set(grouped) - visited:
        raise ValueError("Statcast 包含 feed 沒有的打席")
    return aligned, {"schema_version": ALIGNMENT_VERSION, "physical_pitch_rows": len(aligned),
        "non_pitch_rows": len(excluded), "non_pitch_events": excluded,
        **({"feed_only_events": feed_only} if feed_only else {}),
        "renumbered_pitch_rows": sum(key[2] != value["feed_pitch_number"] for key, value in aligned.items())}
