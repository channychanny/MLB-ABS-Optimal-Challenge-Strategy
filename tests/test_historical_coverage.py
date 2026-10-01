"""覆蓋報告必須保留失敗分母、保護保留年度，並驗證來源鏈。"""

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.error import URLError

from abs_challenge.historical import content_hash
from abs_challenge.historical_batch import run_historical_batch
from abs_challenge.source_cache import SourceCache
from historical_support import contract, game_fixture
from test_historical_batch import batch_sources, sample_plan


spec = importlib.util.spec_from_file_location("coverage_report",
    Path(__file__).resolve().parents[1] / "scripts" / "summarize_historical_coverage.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class HistoricalCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def batch(self, seasons=(2019,), failed=False):
        sources = {}
        for season in seasons:
            # 各年度需不同 game_pk，沿用 fixture 時顯式重新編號來源。
            first = game_fixture(season=season, game_pk=season - 1900)
            source = batch_sources(season, first_game=first)
            sources.update(source)
        plan = sample_plan(seasons[0])
        plan.update(seasons=list(seasons), dates=[f"{s}-06-01" for s in seasons], games_per_date=1)

        def fetch(url):
            if failed and "/game/" in url:
                raise URLError("測試來源缺失")
            return sources[url]

        cache = SourceCache(self.root / "cache", fetch=fetch, attempts=1)
        return run_historical_batch(plan, contract(), cache, self.root / "artifacts", code_signature="test")

    def test_train_validation_separation(self):
        report = self.batch((2019, 2024))
        result = module.summarize(report, self.root / "artifacts")
        self.assertEqual(result["accepted_games"], 2)
        self.assertEqual(result["re_development"]["summary"]["train_games"], 1)
        self.assertEqual(result["re_development"]["summary"]["ignored_nontrain_games"], 1)
        self.assertEqual(result["split_coverage"]["validation"]["score_bands"]["0-5"]["game_pks"], [124])
        self.assertFalse(result["formal_training_ready"])

    def test_missing_sources_remain_in_denominator(self):
        result = module.summarize(self.batch(failed=True), self.root / "artifacts")
        self.assertEqual(result["selected_games"], 1)
        self.assertEqual(result["accepted_games"], 0)
        self.assertEqual(result["coverage"]["season"]["2019"]["not_accepted_fraction"], 1)
        self.assertIsNone(result["re_development"])

    def test_lock_tampering_rejected(self):
        report = self.batch()
        report["dataset_lock"]["games"] = []
        with self.assertRaisesRegex(ValueError, "lock 指紋"):
            module.summarize(report, self.root / "artifacts")

    def test_missing_selected_record_rejected(self):
        report = self.batch()
        report["dataset_lock"]["games"] = []
        report["dataset_lock_sha256"] = content_hash(report["dataset_lock"])
        with self.assertRaisesRegex(ValueError, "選定場次"):
            module.summarize(report, self.root / "artifacts")

    def test_path_escape_rejected(self):
        report = self.batch()
        report["dataset_lock"]["games"][0]["relative_path"] = "../outside.json"
        report["dataset_lock_sha256"] = content_hash(report["dataset_lock"])
        with self.assertRaisesRegex(ValueError, "超出資料目錄"):
            module.summarize(report, self.root / "artifacts")

    def test_holdout_plan_rejected(self):
        report = self.batch()
        report["plan"].update(seasons=[2025], dates=["2025-06-01"])
        report["dataset_lock"]["plan_sha256"] = content_hash(report["plan"])
        report["dataset_lock_sha256"] = content_hash(report["dataset_lock"])
        with self.assertRaisesRegex(ValueError, "受保留"):
            module.summarize(report, self.root / "artifacts")
