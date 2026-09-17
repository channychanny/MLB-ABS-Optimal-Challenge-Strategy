"""Dataset A 切分、完整性、大比分與防洩漏契約。"""

from copy import deepcopy
import unittest

from abs_challenge.historical import build_historical_dataset, content_hash, split_for_game, verify_dataset
from abs_challenge.historical_sources import read_historical_bundle
from historical_support import bundle_fixture, contract, game_fixture


class HistoricalTests(unittest.TestCase):
    def setUp(self):
        self.feed, self.rows = game_fixture()

    def build(self, feed=None, rows=None):
        return build_historical_dataset([self.feed if feed is None else feed],
                                       self.rows if rows is None else rows, contract())

    def test_complete_game_labels_and_first_pitch(self):
        data = self.build()
        verify_dataset(data)
        self.assertEqual(data["status"], "complete_selected_games")
        self.assertEqual(data["rows"][0]["labels"], {"home_win": 0, "runs_to_half_end": 1})
        self.assertEqual(data["rows"][2]["labels"]["runs_to_half_end"], 0)
        self.assertTrue(data["rows"][0]["sampling"]["re24_first_pitch"])
        self.assertFalse(data["rows"][1]["sampling"]["re24_first_pitch"])
        self.assertFalse(data["formal_training_ready"])

    def test_all_years_fixed_and_2020_rejected(self):
        for year, expected in ((2019, "train"), (2021, "train"), (2022, "train"),
                               (2023, "train"), (2024, "validation"), (2025, "test"), (2026, "external")):
            self.assertEqual(split_for_game(year, 501), expected)
        with self.assertRaises(ValueError):
            split_for_game(2020, 501)
        self.assertEqual(split_for_game(2026, 825027), "development_external")
        with self.assertRaises(ValueError):
            split_for_game(2019, 825027)

    def test_large_scores_retained_and_banded(self):
        feed, rows = game_fixture(away_runs=12)
        data = self.build(feed, rows)
        self.assertEqual(min(r["features"]["score_diff"] for r in data["rows"]), -12)
        for value in data["summary"]["coverage"]["train"]["score_bands"].values():
            self.assertGreater(value["pitches"], 0)
            self.assertEqual(value["games"], 1)

    def test_observations_never_enter_features(self):
        before = self.build()
        for row in self.rows:
            row.update(plate_x="999", plate_z="999", delta_home_win_exp="1", delta_run_exp="99",
                       home_win_exp="1", bat_win_exp="0", overturned=True)
        after = self.build()
        self.assertEqual(before["rows"], after["rows"])
        self.assertEqual(before["dataset_content_sha256"], after["dataset_content_sha256"])

    def test_order_independent_replay(self):
        self.assertEqual(self.build(), self.build(rows=list(reversed(self.rows))))

    def test_missing_pitch_excludes_entire_game(self):
        data = self.build(rows=self.rows[:-1])
        self.assertEqual(data["rows"], [])
        self.assertIn("缺少 1", data["excluded_games"][0]["reason"])

    def test_duplicate_keys_are_fatal(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.build(rows=self.rows + [self.rows[0]])
        with self.assertRaises(ValueError):
            build_historical_dataset([self.feed, self.feed], self.rows, contract())

    def test_ineligible_game_metadata(self):
        for path, value in ((["gameData", "game", "type"], "S"),
                            (["gameData", "status", "abstractGameState"], "Live"),
                            (["gameData", "teams", "away", "sport", "id"], 11),
                            (["liveData", "linescore", "scheduledInnings"], 7),
                            (["liveData", "linescore", "currentInning"], 7)):
            feed = deepcopy(self.feed)
            target = feed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            self.assertEqual(self.build(feed)["summary"]["accepted_games"], 0)

    def test_missing_runner_column_not_empty_base(self):
        del self.rows[0]["on_1b"]
        self.assertIn("壘包", self.build()["excluded_games"][0]["reason"])

    def test_invalid_state_and_date_excluded(self):
        for field, value in (("balls", "4"), ("home_score", "-1"), ("outs_when_up", "1.5"),
                             ("inning_topbot", "Bot"), ("game_date", "2025-06-01")):
            rows = deepcopy(self.rows)
            rows[0][field] = value
            self.assertEqual(self.build(rows=rows)["rows"], [])

    def test_official_final_and_half_scores_must_match(self):
        self.feed["liveData"]["linescore"]["teams"]["away"]["runs"] = 2
        self.assertIn("終場比分", self.build()["excluded_games"][0]["reason"])
        self.feed, _ = game_fixture()
        self.feed["liveData"]["plays"]["allPlays"][3]["result"]["awayScore"] = 9
        self.assertIn("逐局比分", self.build()["excluded_games"][0]["reason"])

    def test_missing_half_or_play_rejected(self):
        self.feed["liveData"]["plays"]["allPlays"].pop(3)
        self.assertIn("打席序號", self.build()["excluded_games"][0]["reason"])

    def test_walkoff_kept_for_wp_but_not_re(self):
        feed, rows = game_fixture(walkoff=True)
        data = self.build(feed, rows)
        self.assertEqual(data["status"], "complete_selected_games")
        ninth = [r for r in data["rows"] if r["features"]["inning"] == 9 and r["features"]["half"] == "bottom"]
        self.assertTrue(ninth)
        for row in ninth:
            self.assertEqual(row["labels"], {"home_win": 1, "runs_to_half_end": None})
            self.assertFalse(row["sampling"]["re_half_eligible"])

    def test_extra_inning_outcome_only(self):
        feed, rows = game_fixture(extra=True)
        data = self.build(feed, rows)
        self.assertTrue(data["games"][0]["regulation_tied"])
        self.assertTrue(all(r["features"]["inning"] <= 9 for r in data["rows"]))
        self.assertEqual({r["labels"]["home_win"] for r in data["rows"]}, {0})
        self.assertGreater(data["summary"]["excluded_extra_inning_rows"], 0)

    def test_skip_bottom_ninth_home_ahead(self):
        feed, rows = game_fixture()
        # 將所有比分及逐局得分鏡像到主隊；首分改為一局下首打席。
        for play in feed["liveData"]["plays"]["allPlays"]:
            play["result"] = {"homeScore": int(play["about"]["halfInning"] == "bottom" or play["about"]["inning"] > 1), "awayScore": 0}
        line = feed["liveData"]["linescore"]
        line["innings"][0]["home"]["runs"], line["innings"][0]["away"]["runs"] = 1, 0
        line["teams"]["home"]["runs"], line["teams"]["away"]["runs"] = 1, 0
        feed["liveData"]["plays"]["allPlays"] = [p for p in feed["liveData"]["plays"]["allPlays"] if not (p["about"]["inning"] == 9 and p["about"]["halfInning"] == "bottom")]
        feed["liveData"]["boxscore"]["teams"]["away"]["teamStats"]["pitching"]["numberOfPitches"] -= 6
        filtered = []
        for row in rows:
            if row["inning"] == "9" and row["inning_topbot"] == "Bot":
                continue
            row["home_score"] = str(int(int(row["inning"]) > 1 or (row["inning_topbot"] == "Bot" and int(row["at_bat_number"]) > 5)))
            row["away_score"] = "0"
            filtered.append(row)
        self.assertEqual(self.build(feed, filtered)["status"], "complete_selected_games")

    def test_contract_cannot_reassign_test_or_clip(self):
        settings = contract()
        settings["splits"]["train"].append(2025)
        with self.assertRaises(ValueError):
            build_historical_dataset([self.feed], self.rows, settings)

    def test_dataset_hash_and_feature_allowlist_verified(self):
        data = self.build()
        data["rows"][0]["features"]["plate_x"] = 0
        with self.assertRaisesRegex(ValueError, "指紋"):
            verify_dataset(data)
        data["dataset_content_sha256"] = content_hash({k: v for k, v in data.items() if k != "dataset_content_sha256"})
        with self.assertRaisesRegex(ValueError, "白名單"):
            verify_dataset(data)

    def test_bundle_round_trip_and_tampering(self):
        bundle = bundle_fixture(self.feed, self.rows)
        feed, rows, digest = read_historical_bundle(bundle)
        self.assertEqual(feed, self.feed)
        self.assertEqual(rows, self.rows)
        self.assertEqual(len(digest), 64)
        bundle["statcast"]["text"] += "\n"
        with self.assertRaisesRegex(ValueError, "指紋"):
            read_historical_bundle(bundle)

    def test_bundle_wrong_query_or_count_rejected(self):
        for key, value in (("row_count", 1), ("source_url", "https://example.com"),
                           ("source_type", "baseball_savant_abs_csv"), ("request_parameters", {})):
            bundle = bundle_fixture(self.feed, self.rows)
            bundle["statcast"]["manifest"][key] = value
            with self.assertRaises(ValueError):
                read_historical_bundle(bundle)

    def test_feed_and_csv_missing_same_pitch_still_rejected(self):
        self.feed["liveData"]["plays"]["allPlays"][0]["playEvents"].pop(0)
        self.rows.pop(0)
        self.assertIn("投球總數", self.build()["excluded_games"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
