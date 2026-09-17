"""Command-line entry points for the ABS challenge research pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .audit import audit_feed
from . import phase1_cli, phase2_cli
from .mlb_api import BASE_URL as MLB_API_BASE_URL, get_live_feed
from .opportunities import (
    EXPECTED_CHALLENGE_RATE_THRESHOLD,
    PRIMARY_MAX_INNING,
    RUN_VALUE_THRESHOLD,
    ZONE_EDGE_THRESHOLD_FEET,
    build_challenge_opportunities,
)
from .provenance import build_download_manifest, build_file_manifest
from .rules import DEFAULT_RULE_CONFIG, RuleResolutionError, resolve_game_rules
from .savant import (
    build_abs_csv_url,
    build_called_pitches_csv_url,
    fetch_abs_rows,
    fetch_called_pitch_rows,
    parse_csv_text,
)
from .validation import (
    DEFAULT_PHASE0_REQUIREMENTS,
    build_official_game_record_comparison,
    evaluate_phase0_gate,
)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_csv(path: Path) -> list[dict[str, str]]:
    return parse_csv_text(path.read_text(encoding="utf-8-sig"))


def _savant_csv_source_type(path: Path) -> str:
    manifest_path = Path(f"{path}.manifest.json")
    if manifest_path.exists():
        source_type = _load_json(manifest_path).get("source_type")
        if source_type in {
            "baseball_savant_abs_csv",
            "baseball_savant_pitch_csv",
        }:
            return str(source_type)
    return "baseball_savant_abs_csv"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abs-challenge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit-game", help="audit one official game feed")
    source = audit.add_mutually_exclusive_group(required=True)
    source.add_argument("--game-pk", type=int, help="official MLB game identifier")
    source.add_argument("--feed-json", type=Path, help="previously saved live-feed JSON")
    audit.add_argument("--initial-challenges", type=int)
    audit.add_argument(
        "--extra-inning-refill",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    audit.add_argument("--abs-format", choices=("challenge", "full_abs"))
    audit.add_argument("--rule-config", type=Path, default=DEFAULT_RULE_CONFIG)
    audit.add_argument("--raw-output", type=Path)
    audit.add_argument("--output", type=Path)

    audit.add_argument(
        "--savant-csv",
        type=Path,
        help="optional Savant ABS-only or full pitch CSV used to attach pre-pitch state",
    )

    download = subparsers.add_parser(
        "download-statcast-abs",
        help="download one day of official Savant ABS challenge pitches",
    )
    download.add_argument("--date", required=True, help="YYYY-MM-DD")
    download.add_argument("--level", choices=("mlb", "aaa"), required=True)
    download.add_argument("--output", type=Path, required=True)

    pitch_download = subparsers.add_parser(
        "download-statcast-pitches",
        help="下載一日完整逐球資料，供 Challenge Opportunity 建構",
    )
    pitch_download.add_argument("--date", required=True, help="YYYY-MM-DD")
    pitch_download.add_argument("--level", choices=("mlb", "aaa"), required=True)
    pitch_download.add_argument("--output", type=Path, required=True)

    opportunities = subparsers.add_parser(
        "build-opportunities",
        help="從完整逐球 CSV 建立 Legal／Reasonable Challenge Opportunity",
    )
    opportunities.add_argument("--feed-json", type=Path, required=True)
    opportunities.add_argument("--statcast-csv", type=Path, required=True)
    opportunities.add_argument("--output", type=Path, required=True)
    opportunities.add_argument("--abs-format", choices=("challenge", "full_abs"))
    opportunities.add_argument("--initial-challenges", type=int)
    opportunities.add_argument(
        "--extra-inning-refill",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    opportunities.add_argument("--rule-config", type=Path, default=DEFAULT_RULE_CONFIG)

    validation = subparsers.add_parser(
        "validate-phase0",
        help="依版本化門檻彙總多場稽核並判定 Phase 0",
    )
    validation.add_argument("--audit", type=Path, action="append", required=True)
    validation.add_argument(
        "--requirements", type=Path, default=DEFAULT_PHASE0_REQUIREMENTS
    )
    validation.add_argument("--official-comparison", type=Path, action="append")
    validation.add_argument("--output", type=Path, required=True)

    comparison = subparsers.add_parser(
        "build-official-comparison",
        help="compare extracted challenges with official per-game ABS counters",
    )
    comparison.add_argument("--scope-id", required=True)
    comparison.add_argument("--audit", type=Path, action="append", required=True)
    comparison.add_argument("--feed-json", type=Path, action="append", required=True)
    comparison.add_argument("--output", type=Path, required=True)
    phase1_cli.register_commands(subparsers)
    phase2_cli.register_commands(subparsers)
    return parser


def _run_audit(args: argparse.Namespace) -> int:
    if args.feed_json:
        feed = _load_json(args.feed_json)
    else:
        feed = get_live_feed(args.game_pk)
    if args.raw_output:
        _write_json(args.raw_output, feed)

    rules = resolve_game_rules(
        feed,
        config_path=args.rule_config,
        abs_format=args.abs_format,
        initial_challenges_override=args.initial_challenges,
        extra_inning_refill_override=args.extra_inning_refill,
    )
    report = audit_feed(
        feed,
        rules,
        statcast_rows=_load_csv(args.savant_csv) if args.savant_csv else None,
    )
    if args.feed_json:
        feed_manifest = build_file_manifest(
            args.feed_json, source_type="mlb_stats_api_feed_json"
        )
    else:
        feed_manifest = build_download_manifest(
            source_type="mlb_stats_api_feed_json",
            source_url=f"{MLB_API_BASE_URL}/api/v1.1/game/{args.game_pk}/feed/live",
            content=json.dumps(feed, ensure_ascii=False, sort_keys=True),
            row_count=1,
        )
    report["input_manifests"] = [
        feed_manifest,
        *(
            [
                build_file_manifest(
                    args.savant_csv,
                    source_type=_savant_csv_source_type(args.savant_csv),
                )
            ]
            if args.savant_csv
            else []
        ),
        build_file_manifest(args.rule_config, source_type="rule_regime_config"),
    ]
    if args.output:
        _write_json(args.output, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["phase0_game_pass"] else 1


def _run_download(args: argparse.Namespace) -> int:
    if args.command == "download-statcast-abs":
        text, rows = fetch_abs_rows(args.date, args.level)
        source_url = build_abs_csv_url(args.date, args.level)
        source_type = "baseball_savant_abs_csv"
    else:
        text, rows = fetch_called_pitch_rows(args.date, args.level)
        source_url = build_called_pitches_csv_url(args.date, args.level)
        source_type = "baseball_savant_pitch_csv"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    manifest_path = Path(f"{args.output}.manifest.json")
    _write_json(
        manifest_path,
        build_download_manifest(
            source_type=source_type,
            source_url=source_url,
            content=text,
            row_count=len(rows),
        ),
    )
    print(
        json.dumps(
            {
                "date": args.date,
                "level": args.level,
                "rows": len(rows),
                "output": str(args.output),
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _run_build_opportunities(args: argparse.Namespace) -> int:
    feed = _load_json(args.feed_json)
    statcast_rows = _load_csv(args.statcast_csv)
    rules = resolve_game_rules(
        feed,
        config_path=args.rule_config,
        abs_format=args.abs_format,
        initial_challenges_override=args.initial_challenges,
        extra_inning_refill_override=args.extra_inning_refill,
    )
    opportunities = build_challenge_opportunities(feed, statcast_rows, rules)
    payload = {
        "schema_version": "opportunity-dataset-v1",
        "game_pk": int(feed["gamePk"]),
        "rules": {
            "regime_id": rules.regime_id,
            "rule_status": rules.rule_status,
            "extra_inning_rule_status": rules.extra_inning_rule_status,
            "abs_format": rules.abs_format,
            "initial_challenges": rules.initial_challenges,
            "successful_challenge_retained": rules.successful_challenge_retained,
            "refill_if_empty_each_extra_inning": (
                rules.refill_if_empty_each_extra_inning
            ),
            "source": rules.source,
        },
        "research_scope": {
            "schema_version": "regulation-innings-primary-v1",
            "innings": [1, PRIMARY_MAX_INNING],
            "extra_inning_policy_in_scope": False,
        },
        "legal_opportunity_criteria": {
            "schema_version": "legal-opportunity-v1",
            "status": "provisional_source_limitations",
            "called_pitch_required": True,
            "adverse_call_required": True,
            "challenge_remaining_required": True,
            "position_player_pitching_exclusion": True,
            "technical_outage_exclusion": False,
            "post_replay_review_exclusion": False,
        },
        "reasonable_candidate_criteria": {
            "schema_version": "reasonable-candidate-v1",
            "zone_edge_threshold_inches": ZONE_EDGE_THRESHOLD_FEET * 12,
            "run_value_threshold": RUN_VALUE_THRESHOLD,
            "expected_challenge_rate_threshold": (
                EXPECTED_CHALLENGE_RATE_THRESHOLD
            ),
            "unknown_when_inputs_are_insufficient": True,
        },
        "model_input_contract": {
            "schema_version": "decision-time-features-v1",
            "decision_time": "after_umpire_call_before_challenge_decision",
            "allowed_feature_groups": [
                "pre_pitch_state",
                "challenges_remaining",
                "original_call",
                "decision_team_id",
            ],
            "label_only_groups": [
                "actual_challenge",
                "overturned",
                "reasonable_candidate",
                "reasonable_reasons",
                "pitch_observation",
            ],
        },
        "summary": {
            "legal_opportunities": len(opportunities),
            "actual_challenges": sum(row.actual_challenge for row in opportunities),
            "reasonable_candidates": sum(
                row.reasonable_candidate is True for row in opportunities
            ),
            "reasonable_unknown": sum(
                row.reasonable_candidate is None for row in opportunities
            ),
        },
        "input_manifests": [
            build_file_manifest(args.feed_json, source_type="mlb_stats_api_feed_json"),
            build_file_manifest(
                args.statcast_csv, source_type="baseball_savant_pitch_csv"
            ),
        ],
        "opportunities": [row.to_dict() for row in opportunities],
    }
    _write_json(args.output, payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


def _run_validate_phase0(args: argparse.Namespace) -> int:
    audits = [_load_json(path) for path in args.audit]
    requirements = _load_json(args.requirements)
    comparison_paths = args.official_comparison or []
    comparisons = [_load_json(path) for path in comparison_paths]
    result = evaluate_phase0_gate(audits, requirements, comparisons)
    result["requirements_schema_version"] = requirements.get("schema_version")
    result["input_manifests"] = [
        *(
            build_file_manifest(path, source_type="phase0_game_audit")
            for path in args.audit
        ),
        build_file_manifest(
            args.requirements, source_type="phase0_gate_requirements"
        ),
        *(
            build_file_manifest(path, source_type="official_aggregate_comparison")
            for path in comparison_paths
        ),
    ]
    _write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["phase0_gate_pass"] else 1


def _run_build_official_comparison(args: argparse.Namespace) -> int:
    result = build_official_game_record_comparison(
        scope_id=args.scope_id,
        audits=[_load_json(path) for path in args.audit],
        feeds=[_load_json(path) for path in args.feed_json],
    )
    result["input_manifests"] = [
        *(
            build_file_manifest(path, source_type="phase0_game_audit")
            for path in args.audit
        ),
        *(
            build_file_manifest(path, source_type="mlb_stats_api_feed_json")
            for path in args.feed_json
        ),
    ]
    _write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in phase1_cli.COMMANDS:
            try:
                return phase1_cli.run_command(args)
            except (OSError, ValueError, KeyError, TypeError) as error:
                print(json.dumps({"error": str(error)}, ensure_ascii=False))
                return 2
        if args.command in phase2_cli.COMMANDS:
            try:
                return phase2_cli.run_command(args)
            except (OSError, ValueError, KeyError, TypeError) as error:
                print(json.dumps({"error": str(error)}, ensure_ascii=False))
                return 2
        if args.command == "audit-game":
            return _run_audit(args)
        if args.command in {"download-statcast-abs", "download-statcast-pitches"}:
            return _run_download(args)
        if args.command == "build-opportunities":
            return _run_build_opportunities(args)
        if args.command == "validate-phase0":
            return _run_validate_phase0(args)
        if args.command == "build-official-comparison":
            return _run_build_official_comparison(args)
    except RuleResolutionError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 2
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
