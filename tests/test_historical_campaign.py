"""全季取得計畫必須固定清冊、保護保留年度，並能在缺空間時停止。"""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from abs_challenge.historical import content_hash
from abs_challenge.historical_batch import ALLOWED_SEASONS, schedule_url
from abs_challenge.source_cache import SourceCache
from historical_support import contract, game_fixture
from test_historical_batch import batch_sources


def load_script(name):
    spec = importlib.util.spec_from_file_location(name,
        Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


planner = load_script("plan_historical_seasons")
with patch.dict(sys.modules, {"plan_historical_seasons": planner}):
    runner = load_script("run_historical_month")


class HistoricalCampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = {}
        for season in sorted(ALLOWED_SEASONS):
            sources = batch_sources(season, first_game=game_fixture(season=season, game_pk=season))
            url = schedule_url(season)
            schedule = json.loads(sources[url])
            schedule["dates"][0]["games"] = [g for g in schedule["dates"][0]["games"] if g["gamePk"] == season]
            schedule["totalGames"] = 1
            sources[url] = json.dumps(schedule)
            self.sources.update(sources)
        self.fetch = Mock(side_effect=lambda url: self.sources[url])
        self.cache = SourceCache(self.root / "cache", fetch=self.fetch, attempts=1)

    def plan(self):
        campaign = planner.build_campaign(self.cache)
        return {"campaign": campaign, "campaign_sha256": content_hash(campaign)}

    def test_all_candidates_in_fixed_months_and_holdouts_untouched(self):
        document = self.plan()
        campaign = document["campaign"]
        self.assertEqual(campaign["expected_games"], 5)
        self.assertEqual(campaign["seasons"], [2019, 2021, 2022, 2023, 2024])
        self.assertEqual(campaign["months"][0]["expected_game_pks"], [2019])
        self.assertTrue(all(b["plan"]["games_per_date"] is None for b in campaign["months"]))
        self.assertFalse(campaign["full_season_coverage_verified"])

    def test_month_build_and_offline_replay_have_same_lock(self):
        document = self.plan()
        runtime = {"code_manifests": [], "worktree_clean": False}
        first = runner.run_month(document, "2019-06", self.cache, self.root / "artifacts", contract(), runtime, lambda e: None)
        offline = SourceCache(self.cache.root, offline=True)
        second = runner.run_month(document, "2019-06", offline, self.root / "artifacts", contract(), runtime, lambda e: None)
        self.assertEqual(first["summary"]["accepted_games"], 1)
        self.assertEqual(first["dataset_lock_sha256"], second["dataset_lock_sha256"])
        self.assertEqual(second["execution"]["downloads"], 0)
        self.assertEqual(second["execution"]["reused_shards"], 1)

    def test_changed_selection_rejected_even_with_recomputed_hash(self):
        document = self.plan()
        document["campaign"]["months"][0]["expected_game_pks"] = []
        document["campaign_sha256"] = content_hash(document["campaign"])
        with self.assertRaisesRegex(ValueError, "已變更"):
            runner.run_month(document, "2019-06", self.cache, self.root, contract(), {}, lambda e: None)

    def test_holdout_month_rejected(self):
        with self.assertRaisesRegex(ValueError, "月份不在"):
            runner.run_month(self.plan(), "2025-06", self.cache, self.root, contract(), {}, lambda e: None)

    def test_low_space_stops_before_network(self):
        cache = runner.CapacityLimitedCache(self.root, fetch=self.fetch)
        with patch.object(runner.shutil, "disk_usage", return_value=SimpleNamespace(free=runner.RESERVE_BYTES - 1)):
            with self.assertRaisesRegex(RuntimeError, "保留額"):
                cache.get("https://example.invalid", "test", lambda value: 0)
        self.fetch.assert_not_called()

    def test_duplicate_game_across_seasons_is_rejected(self):
        for season in ALLOWED_SEASONS:
            url = schedule_url(season)
            schedule = json.loads(self.sources[url])
            schedule["dates"][0]["games"][0]["gamePk"] = 501
            self.sources[url] = json.dumps(schedule)
        with self.assertRaisesRegex(ValueError, "重複"):
            self.plan()

    def test_schedule_exclusions_are_kept_out_of_download_list(self):
        url = schedule_url(2021)
        schedule = json.loads(self.sources[url])
        extra = deepcopy(schedule["dates"][0]["games"][0])
        extra.update(gamePk=777, scheduledInnings=7)
        schedule["dates"][0]["games"].append(extra)
        schedule["totalGames"] = 2
        self.sources[url] = json.dumps(schedule)
        campaign = self.plan()["campaign"]
        self.assertEqual(campaign["expected_games"], 5)
        self.assertEqual(campaign["catalog_excluded_games"][0]["game_pk"], 777)
