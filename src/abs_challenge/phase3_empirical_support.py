"""稽核固定 Dataset B 的歷史後續路徑與識別缺口；不估計反事實政策。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from .dataset_b_action_support import INCLUDED
from .phase1_cli import _runtime
from .provenance import build_file_manifest
from .source_cache import atomic_json_new


ROOT = Path(__file__).resolve().parents[2]
SPLITS = ("train", "validation", "test", "external")


def _outside(row: dict) -> bool:
    state = row["decision_features"]["pre_pitch_state"]
    return abs(state["home_score"] - state["away_score"]) > 5


def audit_game(rows: list[dict], episodes: list[dict]) -> list[dict]:
    """以同隊歷史路徑核對到達與表外／返回，不推演未採取的行動。"""
    risks = [row for row in rows if row["analysis_labels"]["population"] == "provisional_opportunity"]
    by_index = {row["physical_pitch_index"]: row for row in risks}
    episode_index = {row["physical_pitch_index"]: row for row in episodes}
    if len(by_index) != len(risks) or set(by_index) != set(episode_index):
        raise ValueError("風險集與額度感知 episode 未一對一對齊")
    next_by_team: dict[int, dict] = {}
    suffix: dict[int, tuple[bool, bool, bool]] = {}
    output = []
    for row in reversed(risks):
        features = row["decision_features"]
        team = features["decision_team_id"]
        index = row["physical_pitch_index"]
        episode = episode_index[index]
        next_row = next_by_team.get(team)
        observed = episode["outcome"] == "next_opportunity"
        if (episode["game_pk"] != row["game_pk"]
                or episode["pre_action_budget"] != features["challenges_remaining"]
                or episode["actual_challenge"] is not row["analysis_labels"]["actual_challenge"]
                or episode["event_observed"] is not observed
                or observed != (next_row is not None)
                or observed != row["arrival_target"]["next_opportunity_observed"]):
            raise ValueError("候選與歷史行動／到達契約不一致")
        if observed and episode["gap"] != next_row["physical_pitch_index"] - index:
            raise ValueError("下一同隊機會投球間隔不一致")
        if not observed and episode["outcome"] not in ("budget_exhausted", "regulation_end"):
            raise ValueError("未知設限或資源終止類型")
        eligibility = row["source_eligibility"]
        if (eligibility["abs_technical_availability"],
                eligibility["post_replay_challenge_eligibility"]) != ("unknown", "unknown"):
            raise ValueError("來源資格契約已變更，須重新設計稽核")
        current_outside = _outside(row)
        next_outside = _outside(next_row) if next_row else None
        later_outside, later_inside, later_return = suffix.get(team, (False, False, False))
        return_after_outside = (not current_outside and later_return)
        output.append({
            "game_pk": row["game_pk"], "physical_pitch_index": index,
            "actual_challenge": episode["actual_challenge"],
            "outcome": episode["outcome"], "current_outside": current_outside,
            "next_outside": next_outside,
            "observed_later_outside": later_outside,
            "observed_later_reentry": return_after_outside if not current_outside else later_inside,
            "current_wp_pair_supported": all(
                isinstance(row["analysis_labels"].get(side), dict)
                and row["analysis_labels"][side].get("supported") is True
                for side in ("s0", "s1")),
            "next_wp_pair_supported": (all(
                isinstance(next_row["analysis_labels"].get(side), dict)
                and next_row["analysis_labels"][side].get("supported") is True
                for side in ("s0", "s1")) if next_row else None),
        })
        suffix[team] = (current_outside or later_outside,
                        not current_outside or later_inside,
                        later_return or (current_outside and later_inside))
        next_by_team[team] = row
    return list(reversed(output))


def summarize(rows: list[dict]) -> dict:
    observed = [row for row in rows if row["outcome"] == "next_opportunity"]
    by_action = {}
    for action, name in ((False, "save"), (True, "challenge")):
        arm = [row for row in rows if row["actual_challenge"] is action]
        arm_observed = [row for row in arm if row["outcome"] == "next_opportunity"]
        by_action[name] = {
            "episodes": len(arm), "games": len({row["game_pk"] for row in arm}),
            "next_observed": len(arm_observed),
            "next_outside": sum(row["next_outside"] for row in arm_observed),
            "next_wp_pair_unsupported": sum(
                not row["next_wp_pair_supported"] for row in arm_observed),
        }
    return {
        "episodes": len(rows), "games": len({row["game_pk"] for row in rows}),
        "historical_actions": dict(sorted(Counter(
            "challenge" if row["actual_challenge"] else "save" for row in rows).items())),
        "resource_outcomes": dict(sorted(Counter(row["outcome"] for row in rows).items())),
        "current_outside": sum(row["current_outside"] for row in rows),
        "current_wp_pair_unsupported": sum(not row["current_wp_pair_supported"] for row in rows),
        "observed_next": len(observed),
        "observed_next_outside": sum(row["next_outside"] for row in observed),
        "observed_next_wp_pair_unsupported": sum(not row["next_wp_pair_supported"] for row in observed),
        "observed_inside_to_outside_next": sum(
            not row["current_outside"] and row["next_outside"] for row in observed),
        "observed_outside_to_inside_next": sum(
            row["current_outside"] and not row["next_outside"] for row in observed),
        "observed_later_outside_from_inside": sum(
            not row["current_outside"] and row["observed_later_outside"] for row in rows),
        "observed_later_reentry_from_inside": sum(
            not row["current_outside"] and row["observed_later_reentry"] for row in rows),
        "observed_later_reentry_from_outside": sum(
            row["current_outside"] and row["observed_later_reentry"] for row in rows),
        "by_historical_action_descriptive_only": by_action,
    }


def analyze(preparation: dict, episodes: dict, closeout: dict) -> dict:
    if (episodes.get("schema_version") != "dataset-b-resource-aware-episodes-v1"
            or closeout.get("schema_version") != "official-wp-phase2-closeout-result-v1"
            or closeout.get("gates", {}).get("formal_policy_evaluation_ready") is not False):
        raise ValueError("前序額度或 Phase 2 閘門版本不符")
    games = [game for game in preparation["game_rows"] if game["status"] in INCLUDED]
    if len(games) != closeout["included_games"] or len(games) != 91:
        raise ValueError("固定場次清冊不符")
    source_by_game = {item["game_pk"]: item for item in episodes["source_manifests"]}
    if len(source_by_game) != len(games) or {game["game_pk"] for game in games} != set(source_by_game):
        raise ValueError("額度 episode 來源場次清冊不符")
    episode_by_game = defaultdict(list)
    for split in SPLITS:
        for episode in episodes["rows_by_split"][split]:
            if episode["split"] != split:
                raise ValueError("額度 episode 切分不一致")
            episode_by_game[episode["game_pk"]].append(episode)
    if set(episode_by_game) != set(source_by_game):
        raise ValueError("額度 episode 有多餘或缺少場次")
    grouped = defaultdict(list)
    for game in games:
        path = Path(game["candidate_artifact"])
        if (build_file_manifest(path, source_type="dataset_b_provisional_candidates") != game["candidate_manifest"]
                or source_by_game[game["game_pk"]]["candidate_manifest"] != game["candidate_manifest"]
                or source_by_game[game["game_pk"]]["feed_manifest"] != game["feed_manifest"]):
            raise ValueError(f"候選檔指紋不符：{game['game_pk']}")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact["game_pk"] != game["game_pk"] or artifact["split"] != game["split"]:
            raise ValueError("候選場次或切分不符")
        grouped[game["split"]].extend(audit_game(
            artifact["rows"], episode_by_game[game["game_pk"]]))
    summaries = {split: summarize(grouped[split]) for split in SPLITS}
    if (sum(item["episodes"] for item in summaries.values()) != 13132
            or any(summaries[split]["episodes"] != closeout["regulation_candidate_counts_by_split"][split]
                   for split in SPLITS)
            or sum(item["resource_outcomes"].get("budget_exhausted", 0)
                   for item in summaries.values()) != 50):
        raise ValueError("固定候選／資源終止總數不符")
    return {
        "schema_version": "phase3-empirical-path-support-v1",
        "estimand": "固定樣本歷史實際行動下的同隊後續候選與官方 WP 表內外支持",
        "split_summaries": summaries,
        "source_eligibility_unknown_rows": 13132,
        "excluded_unlocalized_games": closeout["excluded_games"],
        "gates": {
            "observed_path_support_audited": True,
            "formal_legal_opportunity_ready": False,
            "counterfactual_transition_ready": False,
            "empirical_outside_continuation_ready": False,
            "formal_policy_evaluation_ready": False,
        },
        "limitations": [
            "後續路徑只在歷史實際行動及結果下觀察；挑戰與保留兩臂的差異不可作因果效果。",
            "表內外以真實投球前分差判定，後續候選不等於每一次未來投球或完整 Game State 分布。",
            "只有觀察到後續機會時才有下一狀態；額度耗盡與九局右設限不能填補未知路徑。",
            "ABS 停用與 replay 後資格逐球未知；五場缺漏仍整場排除。",
            "官方 WP 表外後續缺值未估計，不能由觀察到的返回比例填入反事實機率。",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--phase2-closeout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("拒絕覆寫既有稽核結果")
    preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
    episodes = json.loads(args.episodes.read_text(encoding="utf-8"))
    closeout = json.loads(args.phase2_closeout.read_text(encoding="utf-8"))
    expected = {item["source_type"]: item for item in episodes["input_manifests"]}
    if any(item != build_file_manifest(Path(item["source_path"]), source_type=item["source_type"])
           for item in episodes["input_manifests"]):
        raise ValueError("額度 episode 的上游來源指紋已變更")
    if expected.get("dataset_b_pretraining_preparation") != build_file_manifest(
            args.preparation, source_type="dataset_b_pretraining_preparation"):
        raise ValueError("額度 episode 與資料準備指紋不符")
    closeout_inputs = {item["source_type"]: item for item in closeout["input_manifests"]}
    if closeout_inputs.get("dataset_b_pretraining_preparation") != build_file_manifest(
            args.preparation, source_type="dataset_b_pretraining_preparation"):
        raise ValueError("Phase 2 收尾與資料準備指紋不符")
    result = analyze(preparation, episodes, closeout)
    result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
        (args.preparation, "dataset_b_pretraining_preparation"),
        (args.episodes, "dataset_b_resource_aware_episodes"),
        (args.phase2_closeout, "phase2_closeout"))]
    result["runtime"] = _runtime()
    atomic_json_new(args.output, result)
    print(json.dumps(result["split_summaries"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
