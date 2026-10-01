"""透過 Dataset A 公開建置介面驗證事件對齊，不依賴本機下載資料。"""

from copy import deepcopy
import unittest

from abs_challenge.historical import build_historical_dataset, content_hash, verify_dataset
from historical_support import contract, game_fixture


def starting_automatic_strike():
    """首個打席先判自動好球，再投壞球、擊出全壘打；實際投球仍只有兩球。"""
    feed, rows = game_fixture()
    play = feed["liveData"]["plays"]["allPlays"][0]
    play["playEvents"].insert(0, {"index": 0, "type": "no_pitch", "isPitch": False,
        "pitchNumber": 0, "count": {"balls": 0, "strikes": 1, "outs": 0},
        "details": {"call": {"code": "AC"}, "isBall": False, "isStrike": True}})
    for index, event in enumerate(play["playEvents"]):
        event["index"] = index
        event["count"]["strikes"] = 1
    play["runners"][0]["details"]["playIndex"] = 2
    play["count"].update(balls=1, strikes=1)
    automatic = dict(rows[0], description="automatic_strike")
    for row in rows[:2]:
        row["pitch_number"] = str(int(row["pitch_number"]) + 1)
        row["strikes"] = "1"
    rows.insert(0, automatic)
    return feed, rows


def runner_chain_fixture():
    """首打者上一壘，次打席同事件先推進二壘再得分，不能誤認重複資料。"""
    feed, rows = game_fixture()
    first, second = feed["liveData"]["plays"]["allPlays"][:2]
    first["result"]["awayScore"] = 0
    first["runners"][0]["movement"]["end"] = "1B"
    first["matchup"]["postOnFirst"] = {"id": 1000}
    for row in rows[2:4]:
        row.update(on_1b="1000", away_score="0")
    for start, end in (("1B", "2B"), ("2B", "score")):
        second["runners"].append({"movement": {"start": start, "end": end,
            "isOut": False, "outNumber": None},
            "details": {"runner": {"id": 1000}, "playIndex": 1}})
    return feed, rows


def intentional_walk_fixture(physical_balls=0):
    """同一保送可整打席無投球，或投兩球後才敬遠；都不增加實際投球數。"""
    feed, rows = runner_chain_fixture()
    play = feed["liveData"]["plays"]["allPlays"][0]
    template = dict(rows[0])
    events, walk_rows = [], []
    for number in range(1, 5):
        physical = number <= physical_balls
        events.append({"index": number - 1, "type": "pitch" if physical else "no_pitch",
            "isPitch": physical, "pitchNumber": number if physical else physical_balls,
            "count": {"balls": number, "strikes": 0, "outs": 0},
            "details": {"call": {"code": "B" if physical else "V"}, "isBall": True, "isStrike": False}})
        walk_rows.append(dict(template, pitch_number=str(number), balls=str(number - 1),
                              description="ball" if physical else "automatic_ball"))
    play["playEvents"] = events
    play["count"].update(balls=4, strikes=0)
    play["runners"][0]["details"]["playIndex"] = 3
    feed["liveData"]["boxscore"]["teams"]["home"]["teamStats"]["pitching"]["numberOfPitches"] += physical_balls - 2
    return feed, walk_rows + rows[2:]


def third_out_fixture():
    """一局上六個打席；第三出局的封殺只記二壘跑者出局，無後續有效壘位。"""
    feed, rows = game_fixture()
    template = deepcopy(rows[0])
    plays = feed["liveData"]["plays"]["allPlays"]
    specifications = [
        (0, {}, 0, [(1001, None, "1B", None)], {"1B": 1001}, 0),
        (0, {"1B": 1001}, 0, [(1002, None, "1B", None), (1001, "1B", "2B", None)], {"1B": 1002, "2B": 1001}, 0),
        (0, {"1B": 1002, "2B": 1001}, 0, [(1003, None, None, 1)], {"1B": 1002, "2B": 1001}, 1),
        (1, {"1B": 1002, "2B": 1001}, 0, [(1004, None, "1B", None), (1002, "1B", "2B", None), (1001, "2B", "score", None)], {"1B": 1004, "2B": 1002}, 1),
        (1, {"1B": 1004, "2B": 1002}, 1, [(1005, None, None, 2)], {"1B": 1004, "2B": 1002}, 2),
        (2, {"1B": 1004, "2B": 1002}, 1, [(1002, "2B", None, 3), (1006, None, "1B", None)], {}, 3),
    ]
    new_plays, new_rows = [], []
    for index, (outs, bases, score, movements, final_bases, final_outs) in enumerate(specifications):
        event = {"index": 0, "type": "pitch", "isPitch": True, "pitchNumber": 1,
            "count": {"balls": 0, "strikes": 0, "outs": outs},
            "details": {"call": {"code": "X"}, "isInPlay": True, "isBall": False, "isStrike": False}}
        matchup = {name: {"id": final_bases[base]} for base, name in
                   zip(("1B", "2B", "3B"), ("postOnFirst", "postOnSecond", "postOnThird")) if base in final_bases}
        new_plays.append({"about": {"atBatIndex": index, "inning": 1, "halfInning": "top", "isComplete": True},
            "count": {"outs": final_outs}, "result": {"homeScore": 0, "awayScore": int(index >= 3)},
            "playEvents": [event], "matchup": matchup,
            "runners": [{"movement": {"start": start, "end": end, "isOut": number is not None, "outNumber": number},
                "details": {"runner": {"id": runner}, "playIndex": 0}} for runner, start, end, number in movements]})
        new_rows.append(dict(template, at_bat_number=str(index + 1), pitch_number="1", description="hit_into_play",
            balls="0", strikes="0", outs_when_up=str(outs), away_score=str(score),
            **{field: str(bases[base]) if base in bases else "" for base, field in
               zip(("1B", "2B", "3B"), ("on_1b", "on_2b", "on_3b"))}))
    for play in plays[4:]:
        play["about"]["atBatIndex"] += 2
    for row in rows[8:]:
        row["at_bat_number"] = str(int(row["at_bat_number"]) + 2)
    feed["liveData"]["plays"]["allPlays"] = new_plays + plays[4:]
    feed["liveData"]["boxscore"]["teams"]["home"]["teamStats"]["pitching"]["numberOfPitches"] -= 2
    return feed, new_rows + rows[8:]


def feed_only_marker_fixture():
    """首球前無投球標記不新增 CSV 列，也不改變球數。"""
    feed, rows = game_fixture()
    play = feed["liveData"]["plays"]["allPlays"][0]
    play["playEvents"].insert(0, {"index": 0, "type": "no_pitch", "isPitch": False,
        "count": {"balls": 0, "strikes": 0, "outs": 0},
        "details": {"code": "N", "isOut": False}})
    for index, event in enumerate(play["playEvents"]):
        event["index"] = index
    play["runners"][0]["details"]["playIndex"] = 2
    return feed, rows


class HistoricalAlignmentTests(unittest.TestCase):
    def test_feed_only_out_flag_requires_runner_out_evidence(self):
        feed, rows = feed_only_marker_fixture()
        feed["liveData"]["plays"]["allPlays"][0]["playEvents"][0]["details"]["isOut"] = True
        data = build_historical_dataset([feed], rows, contract())
        self.assertFalse(data["rows"])
        self.assertEqual(data["summary"]["excluded_games"], 1)

    def test_feed_only_third_out_has_no_pitch_or_re_sample(self):
        feed, rows = third_out_fixture()
        play = feed["liveData"]["plays"]["allPlays"][5]
        play["playEvents"] = [{"index": 0, "type": "no_pitch", "isPitch": False,
            "count": {"balls": 0, "strikes": 0, "outs": 2},
            "details": {"code": "N", "isOut": True}}]
        play["runners"] = [play["runners"][0]]
        rows.pop(5)
        feed["liveData"]["boxscore"]["teams"]["home"]["teamStats"]["pitching"]["numberOfPitches"] -= 1
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        verify_dataset(data)
        self.assertFalse(any(r["at_bat_number"] == 6 for r in data["rows"]))
        self.assertEqual(data["games"][0]["no_pitch_plate_appearances"], 1)
        self.assertEqual(data["rows"][5]["features"]["outs"], 0)
        self.assertEqual(data["rows"][5]["features"]["bases"], 0)
        self.assertTrue(data["games"][0]["alignment"]["feed_only_events"][0]["event_is_out"])

    def test_feed_only_unknown_or_conflicting_events_are_not_discarded(self):
        for scenario in ("unknown_code", "count_change", "call", "pitch_number", "physical", "extra_csv", "missing_pitch"):
            with self.subTest(scenario=scenario):
                feed, rows = feed_only_marker_fixture()
                event = feed["liveData"]["plays"]["allPlays"][0]["playEvents"][0]
                if scenario == "unknown_code":
                    event["details"]["code"] = "UNKNOWN"
                elif scenario == "count_change":
                    event["count"]["balls"] = 1
                elif scenario == "call":
                    event["details"]["call"] = {"code": "AC"}
                elif scenario == "pitch_number":
                    event["pitchNumber"] = 0
                elif scenario == "physical":
                    event["isPitch"] = True
                elif scenario == "extra_csv":
                    rows.insert(2, dict(rows[1], pitch_number="3"))
                else:
                    rows.pop(0)
                data = build_historical_dataset([feed], rows, contract())
                self.assertFalse(data["rows"])
                self.assertEqual(data["summary"]["excluded_games"], 1)

    def test_feed_only_evidence_cannot_change_count_after_rehash(self):
        feed, rows = feed_only_marker_fixture()
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        data["games"][0]["alignment"]["feed_only_events"][0]["balls_after"] = 1
        data["dataset_content_sha256"] = content_hash({k: v for k, v in data.items()
                                                       if k != "dataset_content_sha256"})
        with self.assertRaisesRegex(ValueError, "非投球"):
            verify_dataset(data)

    def test_feed_only_non_pitch_preserves_runner_movement_without_csv_row(self):
        feed, rows = runner_chain_fixture()
        play = feed["liveData"]["plays"]["allPlays"][1]
        play["playEvents"].insert(1, {"index": 1, "type": "no_pitch", "isPitch": False,
            "count": {"balls": 1, "strikes": 0, "outs": 0},
            "details": {"code": "N", "isOut": False}})
        play["playEvents"][2]["index"] = 2
        play["runners"][0]["details"]["playIndex"] = 2
        play["runners"][1]["details"]["playIndex"] = 1
        play["runners"][2]["details"]["playIndex"] = 2
        rows[3].update(on_1b="", on_2b="1000")
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        verify_dataset(data)
        self.assertEqual(len(data["rows"]), 110)
        self.assertEqual([r["features"]["bases"] for r in data["rows"][2:5]], [1, 2, 0])
        alignment = data["games"][0]["alignment"]
        self.assertEqual(alignment["non_pitch_rows"], 0)
        self.assertEqual(alignment["feed_only_events"][0]["feed_event_index"], 1)
        self.assertEqual(alignment["feed_only_events"][0]["bases_before"], 1)

    def test_missed_bunt_adds_strike_and_keeps_physical_pitch(self):
        feed, rows = game_fixture()
        play = feed["liveData"]["plays"]["allPlays"][0]
        play["playEvents"][0]["details"].update(call={"code": "M"}, isBall=False, isStrike=True)
        for event in play["playEvents"]:
            event["count"].update(balls=0, strikes=1)
        rows[0]["description"] = "missed_bunt"
        rows[1].update(balls="0", strikes="1")
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        verify_dataset(data)
        self.assertEqual(len(data["rows"]), 110)
        self.assertEqual(data["rows"][1]["features"]["strikes"], 1)

    def test_pitchout_remains_a_physical_ball(self):
        feed, rows = game_fixture()
        first = feed["liveData"]["plays"]["allPlays"][0]["playEvents"][0]
        first["details"]["call"]["code"] = "P"
        rows[0]["description"] = "pitchout"
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        verify_dataset(data)
        self.assertEqual(len(data["rows"]), 110)
        self.assertEqual(data["rows"][1]["features"]["balls"], 1)
        self.assertEqual(data["games"][0]["alignment"]["non_pitch_rows"], 0)

    def test_nonempty_runner_movement_requires_explicit_out_status(self):
        feed, rows = runner_chain_fixture()
        feed["liveData"]["plays"]["allPlays"][0]["runners"][0]["movement"]["isOut"] = None
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["summary"]["accepted_games"], 0)

    def test_runner_movement_between_pitches_changes_only_following_state(self):
        feed, rows = runner_chain_fixture()
        play = feed["liveData"]["plays"]["allPlays"][1]
        play["playEvents"].insert(1, {"index": 1, "type": "action", "isPitch": False,
            "count": {"balls": 1, "strikes": 0, "outs": 0}, "details": {"eventType": "stolen_base_2b"}})
        play["playEvents"][2]["index"] = 2
        play["runners"][0]["details"]["playIndex"] = 2
        play["runners"][1]["details"]["playIndex"] = 1
        play["runners"][2]["details"]["playIndex"] = 2
        rows[3].update(on_1b="", on_2b="1000")
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        self.assertEqual([r["features"]["bases"] for r in data["rows"][2:5]], [1, 2, 0])

    def test_ambiguous_runner_path_or_missing_post_state_is_not_guessed(self):
        for scenario in ("duplicate_path", "missing_post", "wrong_identity"):
            with self.subTest(scenario=scenario):
                feed, rows = runner_chain_fixture()
                first, second = feed["liveData"]["plays"]["allPlays"][:2]
                if scenario == "duplicate_path":
                    second["runners"].append(deepcopy(second["runners"][1]))
                elif scenario == "missing_post":
                    first["matchup"].pop("postOnFirst")
                else:
                    rows[2]["on_1b"] = "9000"
                data = build_historical_dataset([feed], rows, contract())
                self.assertEqual(data["summary"]["accepted_games"], 0)

    def test_feed_hit_by_pitch_counter_adds_one_ball_but_remains_physical(self):
        feed, rows = runner_chain_fixture()
        event = feed["liveData"]["plays"]["allPlays"][0]["playEvents"][1]
        event["details"].update(call={"code": "H"}, isBall=True, isInPlay=False)
        event["count"]["balls"] = 2
        rows[1]["description"] = "hit_by_pitch"
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        self.assertEqual(data["summary"]["regulation_pitches"], 110)

    def test_last_pitch_count_must_agree_with_call_not_only_next_row(self):
        feed, rows = starting_automatic_strike()
        feed["liveData"]["plays"]["allPlays"][0]["playEvents"][-1]["count"]["strikes"] = 2
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["summary"]["accepted_games"], 0)

    def test_excluded_non_pitch_rows_still_require_matching_game_metadata(self):
        feed, rows = starting_automatic_strike()
        rows[0]["game_date"] = "2024-06-01"
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["summary"]["accepted_games"], 0)

    def test_matching_counts_do_not_override_conflicting_call_evidence(self):
        feed, rows = starting_automatic_strike()
        rows[1]["description"] = "called_strike"
        data = build_historical_dataset([feed], rows, contract())
        self.assertFalse(data["rows"])
        self.assertIn("判決", data["excluded_games"][0]["reason"])

    def test_intentional_walk_whole_pa_and_after_two_physical_balls(self):
        for physical in (0, 2):
            with self.subTest(physical_balls=physical):
                feed, rows = intentional_walk_fixture(physical)
                data = build_historical_dataset([feed], rows, contract())
                self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
                verify_dataset(data)
                self.assertEqual(data["summary"]["regulation_pitches"], 108 + physical)
                self.assertEqual(data["games"][0]["alignment"]["non_pitch_rows"], 4 - physical)
                self.assertEqual(data["games"][0]["no_pitch_plate_appearances"], int(physical == 0))
                self.assertEqual(sum(r["sampling"]["re24_first_pitch"] for r in data["rows"]), 54 + int(physical > 0))
                second = next(r for r in data["rows"] if r["at_bat_number"] == 2)
                self.assertEqual(second["features"]["bases"], 1)

    def test_automatic_ball_between_pitches_updates_count_not_pitch_total(self):
        feed, rows = game_fixture()
        play = feed["liveData"]["plays"]["allPlays"][0]
        play["playEvents"].insert(1, {"index": 1, "type": "no_pitch", "isPitch": False,
            "pitchNumber": 1, "count": {"balls": 2, "strikes": 0, "outs": 0},
            "details": {"call": {"code": "VP"}, "isBall": True, "isStrike": False}})
        play["playEvents"][2]["index"] = 2
        play["playEvents"][2]["count"]["balls"] = 2
        play["runners"][0]["details"]["playIndex"] = 2
        automatic = dict(rows[1], description="automatic_ball")
        rows[1].update(pitch_number="3", balls="2")
        rows.insert(1, automatic)
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        self.assertEqual([(r["pitch_number"], r["features"]["balls"]) for r in data["rows"][:2]], [(1, 0), (3, 2)])

    def test_terminal_automatic_third_strike_has_no_re_sample(self):
        feed, rows = game_fixture()
        play = feed["liveData"]["plays"]["allPlays"][1]
        for number, event in enumerate(play["playEvents"], start=1):
            event["count"].update(balls=0, strikes=number)
            event["details"].update(call={"code": "C"}, isBall=False, isStrike=True, isInPlay=False)
            rows[number + 1].update(balls="0", strikes=str(number - 1), description="called_strike")
        play["playEvents"].append({"index": 2, "type": "no_pitch", "isPitch": False,
            "pitchNumber": 2, "count": {"balls": 0, "strikes": 3, "outs": 0},
            "details": {"call": {"code": "AC"}, "isBall": False, "isStrike": True}})
        play["runners"][0]["details"]["playIndex"] = 2
        play["count"].update(balls=0, strikes=3)
        rows.insert(4, dict(rows[3], pitch_number="3", strikes="2", description="automatic_strike"))
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        self.assertEqual(data["rows"][4]["features"]["outs"], 1)
        self.assertEqual(len(data["rows"]), 110)

    def test_batter_timeout_terminal_automatic_strike_is_non_pitch(self):
        feed, rows = game_fixture()
        play = feed["liveData"]["plays"]["allPlays"][1]
        for number, event in enumerate(play["playEvents"], start=1):
            event["count"].update(balls=0, strikes=number)
            event["details"].update(call={"code": "C"}, isBall=False, isStrike=True, isInPlay=False)
            rows[number + 1].update(balls="0", strikes=str(number - 1), description="called_strike")
        play["playEvents"].append({"index": 2, "type": "no_pitch", "isPitch": False,
            "pitchNumber": 2, "count": {"balls": 0, "strikes": 3, "outs": 0},
            "details": {"call": {"code": "AB", "description": "Automatic Strike - Batter Timeout Violation"},
                        "violation": {"type": "batter_timeout"},
                        "isBall": False, "isStrike": True}})
        play["runners"][0]["details"]["playIndex"] = 2
        play["count"].update(balls=0, strikes=3)
        rows.insert(4, dict(rows[3], pitch_number="3", strikes="2", description="automatic_strike"))
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        verify_dataset(data)
        self.assertEqual(data["games"][0]["alignment"]["non_pitch_events"][0]["feed_call_code"], "AB")
        self.assertEqual(len(data["rows"]), 110)

    def test_batter_timeout_code_without_structured_evidence_is_rejected(self):
        for violation in ({}, None, {"type": "pitcher_timeout"}):
            with self.subTest(violation=violation):
                feed, rows = starting_automatic_strike()
                event = feed["liveData"]["plays"]["allPlays"][0]["playEvents"][0]
                event["details"]["call"] = {"code": "AB",
                    "description": "Automatic Strike - Batter Timeout Violation"}
                event["details"]["isBall"] = False
                event["details"]["isStrike"] = True
                event["details"]["violation"] = violation
                data = build_historical_dataset([feed], rows, contract())
                self.assertEqual(data["summary"]["excluded_games"], 1)
                self.assertEqual(data["rows"], [])

    def test_ambiguous_or_unexplained_alignment_fails_closed(self):
        for scenario in ("missing_auto", "wrong_auto_count", "unknown_code", "wrong_kind", "missing_feed_count", "extra_row"):
            with self.subTest(scenario=scenario):
                feed, rows = starting_automatic_strike()
                event = feed["liveData"]["plays"]["allPlays"][0]["playEvents"][0]
                if scenario == "missing_auto":
                    rows.pop(0)
                elif scenario == "wrong_auto_count":
                    event["count"]["strikes"] = 2
                elif scenario == "unknown_code":
                    event["details"]["call"]["code"] = "UNKNOWN"
                elif scenario == "wrong_kind":
                    rows[0]["description"] = "called_strike"
                elif scenario == "missing_feed_count":
                    del event["count"]
                else:
                    rows.insert(3, dict(rows[2], pitch_number="4"))
                data = build_historical_dataset([feed], rows, contract())
                self.assertFalse(data["rows"])
                self.assertEqual(data["summary"]["excluded_games"], 1)

    def test_third_out_has_no_continuing_base_state(self):
        feed, rows = third_out_fixture()
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        self.assertEqual(data["rows"][5]["features"]["bases"], 3)
        self.assertEqual(data["rows"][6]["features"]["bases"], 0)

    def test_empty_runner_placeholder_does_not_compete_with_real_movement(self):
        feed, rows = runner_chain_fixture()
        play = feed["liveData"]["plays"]["allPlays"][0]
        placeholder = deepcopy(play["runners"][0])
        placeholder["movement"] = {"originBase": None, "start": None, "end": None,
            "outBase": None, "isOut": None, "outNumber": None}
        play["runners"].insert(0, placeholder)
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        self.assertEqual(data["rows"][2]["features"]["bases"], 1)

    def test_pinch_runner_replaces_identity_before_next_pitch(self):
        feed, rows = runner_chain_fixture()
        play = feed["liveData"]["plays"]["allPlays"][1]
        play["playEvents"].insert(0, {"index": 0, "type": "action", "isPitch": False,
            "count": {"balls": 0, "strikes": 0, "outs": 0},
            "details": {"eventType": "offensive_substitution"}, "isSubstitution": True,
            "position": {"code": "12"}, "player": {"id": 9000},
            "replacedPlayer": {"id": 1000}, "base": 1})
        for index, event in enumerate(play["playEvents"]):
            event["index"] = index
        for runner in play["runners"]:
            runner["details"]["playIndex"] = 2
            if runner["details"]["runner"]["id"] == 1000:
                runner["details"]["runner"]["id"] = 9000
        for row in rows[2:4]:
            row["on_1b"] = "9000"
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        self.assertEqual(data["rows"][2]["alignment"]["runner_ids_before"], [9000, None, None])

    def test_runner_multiple_movements_in_one_event_form_a_unique_path(self):
        feed, rows = runner_chain_fixture()
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        self.assertEqual(data["rows"][2]["features"]["bases"], 1)
        self.assertEqual(data["rows"][4]["features"]["bases"], 0)

    def test_valid_range_but_wrong_pre_pitch_outs_or_bases_excludes_game(self):
        for field, value in (("outs_when_up", "1"), ("on_1b", "12345")):
            with self.subTest(field=field):
                feed, rows = starting_automatic_strike()
                rows[1][field] = value
                data = build_historical_dataset([feed], rows, contract())
                self.assertEqual(data["rows"], [])
                self.assertIn("投球前出局／壘包", data["excluded_games"][0]["reason"])

    def test_starting_automatic_strike_keeps_physical_pitches_and_source_keys(self):
        feed, rows = starting_automatic_strike()
        original = deepcopy((feed, rows))
        data = build_historical_dataset([feed], rows, contract())
        self.assertEqual(data["status"], "complete_selected_games", data["excluded_games"])
        verify_dataset(data)
        pitches = [r for r in data["rows"] if r["at_bat_number"] == 1]
        self.assertEqual([(r["pitch_number"], r["features"]["balls"], r["features"]["strikes"])
                          for r in pitches], [(2, 0, 1), (3, 1, 1)])
        self.assertEqual([r["alignment"]["feed_pitch_number"] for r in pitches], [1, 2])
        self.assertEqual([r["alignment"]["statcast_pitch_number"] for r in pitches], [2, 3])
        self.assertEqual(data["games"][0]["alignment"]["non_pitch_rows"], 1)
        self.assertEqual(data["summary"]["regulation_pitches"], 110)
        self.assertEqual((feed, rows), original)


if __name__ == "__main__":
    unittest.main()
