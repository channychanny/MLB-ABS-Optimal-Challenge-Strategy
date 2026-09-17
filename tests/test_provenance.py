from __future__ import annotations

import unittest

from abs_challenge.provenance import build_download_manifest


class ProvenanceTests(unittest.TestCase):
    def test_download_manifest_records_reproducibility_fields(self) -> None:
        manifest = build_download_manifest(
            source_type="baseball_savant_csv",
            source_url="https://example.test/data.csv?level=aaa&date=2025-05-11",
            content="a,b\n1,2\n",
            row_count=1,
            retrieved_at_utc="2026-09-11T10:00:00Z",
        )

        self.assertEqual(manifest["schema_version"], "source-manifest-v1")
        self.assertEqual(manifest["request_parameters"]["level"], "aaa")
        self.assertEqual(manifest["row_count"], 1)
        self.assertEqual(
            manifest["content_sha256"],
            "492d5ea496056f1a6a6592241032fab764c321596317930b4fa0e1e8bc3b7470",
        )
        self.assertEqual(manifest["retrieved_at_utc"], "2026-09-11T10:00:00Z")


if __name__ == "__main__":
    unittest.main()
