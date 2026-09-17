from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from abs_challenge.cli import main
from test_extract import feed_with_event


class CliTests(unittest.TestCase):
    def test_audit_command_fails_when_phase0_game_is_incomplete(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        with tempfile.TemporaryDirectory() as directory:
            feed_path = Path(directory) / "feed.json"
            feed_path.write_text(json.dumps(feed), encoding="utf-8")

            exit_code = main(
                [
                    "audit-game",
                    "--feed-json",
                    str(feed_path),
                    "--initial-challenges",
                    "2",
                ]
            )

        self.assertEqual(exit_code, 1)

    def test_audit_command_resolves_rules_without_manual_budget(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        feed["gameData"]["game"] = {"season": "2026"}
        for team in feed["gameData"]["teams"].values():
            team["sport"] = {"id": 1, "name": "Major League Baseball"}
            team["league"] = {"id": 103, "name": "American League"}

        with tempfile.TemporaryDirectory() as directory:
            feed_path = Path(directory) / "feed.json"
            feed_path.write_text(json.dumps(feed), encoding="utf-8")

            exit_code = main(["audit-game", "--feed-json", str(feed_path)])

        self.assertEqual(exit_code, 1)

    def test_download_command_writes_a_source_manifest(self) -> None:
        csv_text = "game_pk,at_bat_number,pitch_number\n1,4,1\n"
        rows = [{"game_pk": "1", "at_bat_number": "4", "pitch_number": "1"}]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "abs.csv"
            with patch(
                "abs_challenge.cli.fetch_abs_rows", return_value=(csv_text, rows)
            ):
                exit_code = main(
                    [
                        "download-statcast-abs",
                        "--date",
                        "2025-05-11",
                        "--level",
                        "aaa",
                        "--output",
                        str(output),
                    ]
                )

            manifest_path = Path(f"{output}.manifest.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(manifest["schema_version"], "source-manifest-v1")
        self.assertEqual(manifest["row_count"], 1)
        self.assertIn("hfABSFlag", manifest["request_parameters"])

    def test_called_pitch_download_supports_opportunity_population(self) -> None:
        csv_text = "game_pk,at_bat_number,pitch_number\n1,4,1\n"
        rows = [{"game_pk": "1", "at_bat_number": "4", "pitch_number": "1"}]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pitches.csv"
            with patch(
                "abs_challenge.cli.fetch_called_pitch_rows",
                return_value=(csv_text, rows),
            ):
                exit_code = main(
                    [
                        "download-statcast-pitches",
                        "--date",
                        "2025-05-11",
                        "--level",
                        "aaa",
                        "--output",
                        str(output),
                    ]
                )

            manifest = json.loads(
                Path(f"{output}.manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(exit_code, 0)
        self.assertNotIn("hfABSFlag", manifest["request_parameters"])

    def test_build_opportunities_command_writes_dataset_and_input_hashes(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        csv_text = (
            "game_pk,at_bat_number,pitch_number,inning,inning_topbot,balls,"
            "strikes,outs_when_up,home_score,away_score,on_1b,on_2b,on_3b,description\n"
            "1,4,1,4,Top,0,0,0,0,0,,,,called_strike\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            feed_path = Path(directory) / "feed.json"
            csv_path = Path(directory) / "pitches.csv"
            output = Path(directory) / "opportunities.json"
            feed_path.write_text(json.dumps(feed), encoding="utf-8")
            csv_path.write_text(csv_text, encoding="utf-8")
            exit_code = main(
                [
                    "build-opportunities",
                    "--feed-json",
                    str(feed_path),
                    "--statcast-csv",
                    str(csv_path),
                    "--output",
                    str(output),
                ]
            )
            dataset = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(dataset["schema_version"], "opportunity-dataset-v1")
        self.assertEqual(dataset["summary"]["legal_opportunities"], 1)
        self.assertEqual(len(dataset["input_manifests"]), 2)
        self.assertTrue(dataset["input_manifests"][0]["content_sha256"])
        self.assertEqual(
            dataset["model_input_contract"]["allowed_feature_groups"],
            [
                "pre_pitch_state",
                "challenges_remaining",
                "original_call",
                "decision_team_id",
            ],
        )
        self.assertIn(
            "pitch_observation",
            dataset["model_input_contract"]["label_only_groups"],
        )
        self.assertEqual(
            dataset["legal_opportunity_criteria"]["status"],
            "provisional_source_limitations",
        )
        self.assertFalse(
            dataset["legal_opportunity_criteria"]["technical_outage_exclusion"]
        )
        self.assertEqual(dataset["research_scope"]["innings"], [1, 9])
        self.assertFalse(dataset["research_scope"]["extra_inning_policy_in_scope"])

    def test_audit_output_records_input_manifests(self) -> None:
        feed = feed_with_event(
            final_code="C",
            final_description="Called Strike",
            overturned=False,
            challenge_team_id=10,
            player={"id": 100, "fullName": "Batter"},
        )
        csv_text = (
            "game_pk,at_bat_number,pitch_number,inning,inning_topbot,balls,"
            "strikes,outs_when_up,home_score,away_score,on_1b,on_2b,on_3b,description\n"
            "1,4,1,4,Top,0,0,0,0,0,,,,called_strike\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            feed_path = Path(directory) / "feed.json"
            csv_path = Path(directory) / "abs.csv"
            output = Path(directory) / "audit.json"
            feed_path.write_text(json.dumps(feed), encoding="utf-8")
            csv_path.write_text(csv_text, encoding="utf-8")
            Path(f"{csv_path}.manifest.json").write_text(
                json.dumps({"source_type": "baseball_savant_pitch_csv"}),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "audit-game",
                    "--feed-json",
                    str(feed_path),
                    "--savant-csv",
                    str(csv_path),
                    "--output",
                    str(output),
                ]
            )
            audit = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(audit["input_manifests"]), 3)
        self.assertEqual(
            audit["input_manifests"][1]["source_type"],
            "baseball_savant_pitch_csv",
        )
        self.assertTrue(audit["input_manifests"][1]["content_sha256"])

    def test_validate_phase0_command_uses_versioned_requirements(self) -> None:
        audit = {
            "game": {
                "game_pk": 1,
                "competition": "MLB",
                "season": 2026,
                "extra_inning_game": False,
            },
            "summary": {"phase0_game_pass": True},
        }
        requirements = {
            "schema_version": "phase0-gate-requirements-v1",
            "required_cohorts": [
                {"competition": "MLB", "season": 2026, "minimum_games": 1}
            ],
            "minimum_extra_inning_games": 0,
            "official_aggregate_comparison_required": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "audit.json"
            requirements_path = Path(directory) / "requirements.json"
            output = Path(directory) / "gate.json"
            audit_path.write_text(json.dumps(audit), encoding="utf-8")
            requirements_path.write_text(json.dumps(requirements), encoding="utf-8")

            exit_code = main(
                [
                    "validate-phase0",
                    "--audit",
                    str(audit_path),
                    "--requirements",
                    str(requirements_path),
                    "--output",
                    str(output),
                ]
            )
            result = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["phase0_gate_pass"])
        self.assertEqual(result["requirements_schema_version"], requirements["schema_version"])

    def test_build_official_comparison_command_writes_provenance(self) -> None:
        audit = {
            "game": {"game_pk": 123},
            "summary": {"challenge_events": 2, "overturned": 1},
        }
        feed = {
            "gamePk": 123,
            "gameData": {
                "absChallenges": {
                    "hasChallenges": True,
                    "away": {"usedSuccessful": 1, "usedFailed": 1},
                    "home": {"usedSuccessful": 0, "usedFailed": 0},
                }
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "audit.json"
            feed_path = Path(directory) / "feed.json"
            output = Path(directory) / "comparison.json"
            audit_path.write_text(json.dumps(audit), encoding="utf-8")
            feed_path.write_text(json.dumps(feed), encoding="utf-8")

            exit_code = main(
                [
                    "build-official-comparison",
                    "--scope-id",
                    "regulation-sample",
                    "--audit",
                    str(audit_path),
                    "--feed-json",
                    str(feed_path),
                    "--output",
                    str(output),
                ]
            )
            comparison = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(comparison["official_attempts"], 2)
        self.assertEqual(len(comparison["input_manifests"]), 2)


if __name__ == "__main__":
    unittest.main()
