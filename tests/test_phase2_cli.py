"""Phase 2 命令重播、來源驗證與不可覆寫保護。"""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from abs_challenge.cli import main
from historical_support import bundle_fixture, game_fixture


class Phase2CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "source.json"
        self.output = self.root / "dataset.json"
        self.bundle.write_text(json.dumps(bundle_fixture(*game_fixture())), encoding="utf-8")

    def run_cli(self, *args):
        with redirect_stdout(io.StringIO()), patch("abs_challenge.phase2_cli._runtime", return_value={"formal_experiment_version_ready": False}):
            return main(list(map(str, args)))

    def build(self, output=None):
        return self.run_cli("build-historical-dataset", "--bundle", self.bundle,
                            "--output", self.output if output is None else output)

    def test_build_and_re_development(self):
        self.assertEqual(self.build(), 0)
        output = self.root / "re.json"
        self.assertEqual(self.run_cli("estimate-re-development", "--dataset", self.output,
                                     "--output", output), 0)
        re = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(re["summary"]["train_games"], 1)
        self.assertFalse(re["formal_model_ready"])
        self.assertEqual(len(re["input_manifests"]), 1)

    def test_existing_output_preserved(self):
        self.output.write_text("既有成果", encoding="utf-8")
        self.assertEqual(self.build(), 2)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "既有成果")

    def test_offline_replay_identical(self):
        self.assertEqual(self.build(), 0)
        replay = self.root / "replay.json"
        self.assertEqual(self.build(replay), 0)
        self.assertEqual(self.output.read_bytes(), replay.read_bytes())

    def test_source_tampering_writes_nothing(self):
        bundle = json.loads(self.bundle.read_text(encoding="utf-8"))
        bundle["feed"]["text"] += " "
        self.bundle.write_text(json.dumps(bundle), encoding="utf-8")
        self.assertEqual(self.build(), 2)
        self.assertFalse(self.output.exists())

    def test_incomplete_game_writes_exclusion_report(self):
        feed, rows = game_fixture()
        self.bundle.write_text(json.dumps(bundle_fixture(feed, rows[:-1])), encoding="utf-8")
        self.assertEqual(self.build(), 1)
        data = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(data["summary"]["excluded_games"], 1)

    def test_validation_only_cannot_fit_re(self):
        self.bundle.write_text(json.dumps(bundle_fixture(*game_fixture(season=2024))), encoding="utf-8")
        self.assertEqual(self.build(), 0)
        output = self.root / "re.json"
        self.assertEqual(self.run_cli("estimate-re-development", "--dataset", self.output,
                                     "--output", output), 2)
        self.assertFalse(output.exists())

    def test_same_day_csv_deduplicated_by_source_hash(self):
        feed1, rows1 = game_fixture(game_pk=501)
        feed2, rows2 = game_fixture(game_pk=502)
        self.bundle.write_text(json.dumps(bundle_fixture(feed1, rows1 + rows2)), encoding="utf-8")
        other = self.root / "other.json"
        other.write_text(json.dumps(bundle_fixture(feed2, rows1 + rows2)), encoding="utf-8")
        self.assertEqual(self.run_cli("build-historical-dataset", "--bundle", self.bundle,
                                     "--bundle", other, "--output", self.output), 0)
        data = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(data["summary"]["accepted_games"], 2)


if __name__ == "__main__":
    unittest.main()
