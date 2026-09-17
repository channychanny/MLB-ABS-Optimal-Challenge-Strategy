"""快取原子發布、重試與離線完整性防線。"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from abs_challenge.source_cache import SourceCache, atomic_json_new


class SourceCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.url = "https://statsapi.mlb.com/example?a=1"

    def test_download_once_then_verified_offline_reuse(self):
        fetch = Mock(return_value='{"value": 1}')
        cache = SourceCache(self.root, fetch=fetch)
        first = cache.get(self.url, "test", lambda text: len(json.loads(text)))
        second = cache.get(self.url, "test", lambda text: len(json.loads(text)))
        self.assertEqual(first, second)
        fetch.assert_called_once()
        offline = SourceCache(self.root, offline=True, fetch=Mock(side_effect=AssertionError("不得連網")))
        self.assertEqual(first, offline.get(self.url, "test", lambda text: len(json.loads(text))))
        self.assertEqual(offline.hits, 1)

    def test_transient_failure_retried_before_cache_commit(self):
        fetch = Mock(side_effect=[HTTPError(self.url, 429, "限流", {}, None), URLError("暫斷"), "ok"])
        sleep = Mock()
        cache = SourceCache(self.root, fetch=fetch, sleep=sleep)
        cache.get(self.url, "test", lambda text: 1)
        self.assertEqual(cache.retries, 2)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(fetch.call_count, 3)

    def test_permanent_http_error_not_retried(self):
        fetch = Mock(side_effect=HTTPError(self.url, 404, "找不到", {}, None))
        cache = SourceCache(self.root, fetch=fetch, sleep=Mock())
        with self.assertRaises(HTTPError):
            cache.get(self.url, "test", lambda text: 1)
        fetch.assert_called_once()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_malformed_response_never_published(self):
        cache = SourceCache(self.root, fetch=lambda url: "<html>失敗</html>")
        with self.assertRaises(ValueError):
            cache.get(self.url, "test", lambda text: len(json.loads(text)))
        self.assertFalse(cache.path_for(self.url).exists())

    def test_corrupt_cache_preserved_not_redownloaded(self):
        cache = SourceCache(self.root, fetch=lambda url: "good")
        cache.get(self.url, "test", lambda text: 1)
        path = cache.path_for(self.url)
        source = json.loads(path.read_text(encoding="utf-8"))
        source["text"] = "changed"
        path.write_text(json.dumps(source), encoding="utf-8")
        before = path.read_bytes()
        cache.fetch = Mock(side_effect=AssertionError("不可掩蓋來源損毀"))
        with self.assertRaises(ValueError):
            cache.get(self.url, "test", lambda text: 1)
        self.assertEqual(before, path.read_bytes())

    def test_offline_missing_does_not_download(self):
        fetch = Mock()
        with self.assertRaises(FileNotFoundError):
            SourceCache(self.root, offline=True, fetch=fetch).get(self.url, "test", lambda text: 1)
        fetch.assert_not_called()

    def test_atomic_publication_preserves_existing_and_cleans_own_temp(self):
        path = self.root / "result.json"
        atomic_json_new(path, {"value": "原始"})
        original = path.read_bytes()
        with self.assertRaises(FileExistsError):
            atomic_json_new(path, {"value": "不得覆寫"})
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(self.root.glob(".pending-*")), [])

    def test_interrupted_publication_can_resume(self):
        cache = SourceCache(self.root, fetch=lambda url: "ok")
        with patch("abs_challenge.source_cache.os.link", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                cache.get(self.url, "test", lambda text: 1)
        self.assertFalse(cache.path_for(self.url).exists())
        cache.get(self.url, "test", lambda text: 1)
        self.assertTrue(cache.path_for(self.url).exists())


if __name__ == "__main__":
    unittest.main()
