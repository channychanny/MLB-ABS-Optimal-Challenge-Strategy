"""小樣本估值的母體限制、額外事件與 CLI 保護。"""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from abs_challenge.baseline import SavantBaseline
from abs_challenge.cli import main
from abs_challenge.phase1 import value_audited_challenges
from abs_challenge.provenance import build_download_manifest, build_file_manifest
from baseline_support import set_wp, synthetic_bundle, synthetic_snapshot


def sample() -> tuple[dict, dict]:
    state = {"inning": 4, "inning_topbot": "Bottom", "outs_when_up": 0, "balls": 0, "strikes": 0,
             "home_score": 0, "away_score": 0, "on_1b": None, "on_2b": None, "on_3b": None}
    row = {"inning": 4, "half_inning": "bottom", "at_bat_index": 0, "pitch_number": 1, "play_event_index": 0,
           "original_call": "strike", "abs_call": "strike", "challenge_team_id": 20, "challenges_before": 2,
           "batter_id": 100, "balls_before": 0, "strikes_before": 0, "statcast_pre_pitch_state": state}
    audit = {"game": {"game_pk": 1, "competition": "MLB", "season": 2026, "extra_inning_game": False,
                      "home_team": {"id": 20}, "away_team": {"id": 10}},
             "rules": {"initial_challenges": 2, "successful_challenge_retained": True, "abs_format": "challenge", "rule_status": "confirmed"},
             "summary": {"phase0_game_pass": True}, "ledger": [row]}
    feed = {"gamePk": 1, "liveData": {"plays": {"allPlays": [
        {"atBatIndex": 0, "result": {"eventType": "field_out"}, "playEvents": [
            {"index": 0, "pitchNumber": 1, "isPitch": True, "details": {"description": "Called Strike"}, "count": {"outs": 0}}], "runners": []}]}}}
    return audit, feed


class Phase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = SavantBaseline(synthetic_snapshot())

    def test_small_sample_is_never_formal_policy_evaluation(self) -> None:
        audit, feed = sample()
        result = value_audited_challenges(self.baseline, [audit], [feed])
        self.assertEqual(result["status"], "complete_smoke_test")
        self.assertFalse(result["formal_policy_evaluation_ready"])
        self.assertEqual(result["population"], "phase0_verified_actual_attempts_only")

    def test_observed_deltas_location_and_win_exp_cannot_change_counterfactual(self) -> None:
        audit, feed = sample()
        original = value_audited_challenges(self.baseline, [audit], [feed])
        audit["ledger"][0]["statcast_pitch_observation"] = {"delta_home_win_exp": 999, "delta_run_exp": -999, "plate_x": 100}
        audit["ledger"][0]["statcast_pre_pitch_state"]["home_win_exp"] = 1.0
        self.assertEqual(value_audited_challenges(self.baseline, [audit], [feed]), original)

    def test_rejects_failed_audit_and_three_challenge_regime(self) -> None:
        for key, value in (("initial_challenges", 3), ("abs_format", "full_abs"), ("rule_status", "provisional"), ("successful_challenge_retained", False)):
            audit, feed = sample()
            audit["rules"][key] = value
            with self.assertRaises(ValueError):
                value_audited_challenges(self.baseline, [audit], [feed])
        audit, feed = sample()
        audit["summary"]["phase0_game_pass"] = False
        with self.assertRaises(ValueError):
            value_audited_challenges(self.baseline, [audit], [feed])

    def test_duplicate_games_or_mismatched_feed_are_rejected(self) -> None:
        audit, feed = sample()
        for audits, feeds in (([audit, audit], [feed]), ([audit], [feed, feed]), ([audit], []), ([], [])):
            with self.assertRaises(ValueError):
                value_audited_challenges(self.baseline, audits, feeds)

    def test_extra_innings_are_excluded_without_querying_the_baseline(self) -> None:
        audit, feed = sample()
        audit["ledger"][0]["inning"] = 10
        result = value_audited_challenges(self.baseline, [audit], [feed])
        self.assertEqual(result["rows"][0]["status"], "excluded_extra_inning")
        self.assertNotEqual(result["status"], "complete_smoke_test")

    def test_out_of_range_score_is_an_explicit_partial_result(self) -> None:
        audit, feed = sample()
        audit["ledger"][0]["statcast_pre_pitch_state"]["away_score"] = 6
        result = value_audited_challenges(self.baseline, [audit], [feed])
        self.assertEqual(result["status"], "partial_smoke_test")
        self.assertEqual(result["rows"][0]["status"], "missing_baseline_state")

    def test_counterfactual_sign_warning_blocks_smoke_test_pass(self) -> None:
        snapshot = synthetic_snapshot()
        set_wp(snapshot, (4, "bottom", 0, 0, 1, 0), 0, 0.4)
        audit, feed = sample()
        result = value_audited_challenges(SavantBaseline(snapshot), [audit], [feed])
        self.assertEqual(result["summary"]["valuation_warnings"], 1)
        self.assertEqual(result["status"], "partial_smoke_test")

    def test_stolen_base_and_changed_out_count_are_not_invented(self) -> None:
        audit, feed = sample()
        play = feed["liveData"]["plays"]["allPlays"][0]
        play["runners"] = [{"details": {"playIndex": 0, "eventType": "stolen_base_2b"}, "movement": {"start": "1B", "end": "2B"}}]
        result = value_audited_challenges(self.baseline, [audit], [feed])
        self.assertEqual(result["rows"][0]["status"], "unsupported_compound_event")
        play["runners"] = []
        play["playEvents"][0]["count"]["outs"] = 1
        result = value_audited_challenges(self.baseline, [audit], [feed])
        self.assertEqual(result["rows"][0]["status"], "unsupported_compound_event")

    def test_invalid_decision_team_or_state_are_reported(self) -> None:
        for key, value in (("challenge_team_id", 10), ("challenges_before", 0), ("balls_before", 3)):
            audit, feed = sample()
            audit["ledger"][0][key] = value
            result = value_audited_challenges(self.baseline, [audit], [feed])
            self.assertEqual(result["rows"][0]["status"], "invalid_state")


class Phase1CliTests(unittest.TestCase):
    def run_cli(self, args: list[str]) -> int:
        with contextlib.redirect_stdout(io.StringIO()):
            return main(args)

    def write(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_download_and_offline_build_are_identical_and_refuse_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, snapshot, replay = root / "raw.json", root / "snapshot.json", root / "replay.json"
            with patch("abs_challenge.phase1_cli.download_baseline_bundle", return_value=synthetic_bundle()):
                self.assertEqual(self.run_cli(["download-baseline", "--raw-output", str(raw), "--output", str(snapshot)]), 0)
            self.assertEqual(self.run_cli(["build-baseline", "--bundle", str(raw), "--output", str(replay)]), 0)
            self.assertEqual(snapshot.read_bytes(), replay.read_bytes())
            before = replay.read_bytes()
            self.assertEqual(self.run_cli(["build-baseline", "--bundle", str(raw), "--output", str(replay)]), 2)
            self.assertEqual(replay.read_bytes(), before)

    def test_bad_bundle_does_not_create_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, out = root / "raw.json", root / "out.json"
            bundle = synthetic_bundle()
            bundle["documents"]["page"]["content"] = "變更"
            self.write(raw, bundle)
            self.assertEqual(self.run_cli(["build-baseline", "--bundle", str(raw), "--output", str(out)]), 2)
            self.assertFalse(out.exists())

    def test_value_command_verifies_gate_and_both_feed_manifest_formats(self) -> None:
        for format_name in ("file", "canonical"):
            with self.subTest(format=format_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                audit, feed = sample()
                baseline_path, feed_path, audit_path, gate_path, req_path, output = [root / f"{name}.json" for name in ("baseline", "feed", "audit", "gate", "requirements", "values")]
                self.write(baseline_path, synthetic_snapshot())
                self.write(feed_path, feed)
                feed_manifest = build_file_manifest(feed_path, source_type="mlb_stats_api_feed_json")
                if format_name == "canonical":
                    feed_manifest = build_download_manifest(source_type="mlb_stats_api_feed_json", source_url="https://statsapi.mlb.com/api/v1.1/game/1/feed/live",
                        content=json.dumps(feed, ensure_ascii=False, sort_keys=True), row_count=1)
                audit["input_manifests"] = [feed_manifest]
                self.write(audit_path, audit)
                self.write(req_path, {"required_cohorts": [{"competition": "MLB", "season": 2026, "minimum_games": 1}],
                    "minimum_extra_inning_games": 0, "official_aggregate_comparison_required": False})
                gate = {"schema_version": "phase0-gate-result-v1", "phase0_gate_pass": True, "input_manifests": [
                    build_file_manifest(audit_path, source_type="phase0_game_audit"), build_file_manifest(req_path, source_type="phase0_gate_requirements")]}
                self.write(gate_path, gate)
                args = ["value-challenges", "--baseline", str(baseline_path), "--phase0-gate", str(gate_path), "--audit", str(audit_path), "--feed-json", str(feed_path), "--output", str(output)]
                self.assertEqual(self.run_cli(args), 0)
                result = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(result["summary"]["status_counts"], {"valued": 1})
                self.assertEqual(result["runtime"]["dependencies"], "standard_library_only")
                self.assertTrue(result["runtime"]["code_manifests"])
                audit["ledger"][0]["challenges_before"] = 1
                self.write(audit_path, audit)
                args[-1] = str(root / "changed.json")
                self.assertEqual(self.run_cli(args), 2)
                self.assertFalse((root / "changed.json").exists())

    def test_false_gate_does_not_allow_valuation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root / "baseline.json", synthetic_snapshot())
            self.write(root / "gate.json", {"phase0_gate_pass": False})
            result = self.run_cli(["value-challenges", "--baseline", str(root / "baseline.json"), "--phase0-gate", str(root / "gate.json"),
                "--audit", str(root / "missing.json"), "--feed-json", str(root / "missing.json"), "--output", str(root / "values.json")])
            self.assertEqual(result, 2)
            self.assertFalse((root / "values.json").exists())

    def test_dynamic_cli_labels_output_as_synthetic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root / "baseline.json", synthetic_snapshot())
            self.assertEqual(self.run_cli(["run-dynamic-prototype", "--baseline", str(root / "baseline.json"), "--output", str(root / "demo.json")]), 0)
            result = json.loads((root / "demo.json").read_text(encoding="utf-8"))
            self.assertEqual(result["purpose"], "synthetic_scenario_not_policy_evaluation")
