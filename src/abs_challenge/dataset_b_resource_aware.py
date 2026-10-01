"""以來源驗證後的挑戰結果，建立額度感知的觀察性到達契約與評估。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from .dataset_b_action_support import INCLUDED, _verify_inputs
from .dataset_b_baseline import fit_and_evaluate
from .extract import extract_challenge_events
from .phase1_cli import _runtime
from .provenance import build_file_manifest
from .source_cache import SourceCache, atomic_json_new


ROOT = Path(__file__).resolve().parents[2]


def _feed_count(text: str) -> int:
    feed = json.loads(text)
    if type(feed.get("gamePk")) is not int or not feed.get("liveData", {}).get("plays", {}).get("allPlays"):
        raise ValueError("官方逐球來源缺少場次或比賽事件")
    return 1


def _challenge_outcomes(game: dict, cache: SourceCache) -> dict[tuple[int, int], tuple[bool, int]]:
    pk = game["game_pk"]
    url = f"https://statsapi.mlb.com/api/v1.1/game/{pk}/feed/live"
    source = cache.get(url, "mlb_stats_api_feed_json", _feed_count)
    if source["manifest"] != game["feed_manifest"]:
        raise ValueError(f"官方逐球來源指紋不符：{pk}")
    feed = json.loads(source["text"])
    if feed["gamePk"] != pk:
        raise ValueError(f"官方逐球場次不符：{pk}")
    outcomes = {}
    for event in extract_challenge_events(feed):
        if event.inning > 9:
            continue
        key = (event.at_bat_index + 1, event.play_event_index)
        if key in outcomes or type(event.overturned) is not bool:
            raise ValueError(f"官方挑戰事件重複或結果不明：{pk} {key}")
        outcomes[key] = (event.overturned, event.challenge_team_id)
    for evidence in game.get("recovery_evidence", []):
        key = (evidence["at_bat_number"], evidence["feed_event_index"])
        if (key in outcomes or type(evidence["overturned"]) is not bool
                or evidence["alignment"]["state_checks_pass"] is not True):
            raise ValueError(f"復原挑戰事件重複或證據不足：{pk} {key}")
        outcomes[key] = (evidence["overturned"], evidence["challenge_team_id"])
    return outcomes


def build_game_episodes(game: dict, rows: list[dict],
                        outcomes: dict[tuple[int, int], tuple[bool, int]]) -> list[dict]:
    """僅以已核對的歷史行動建立事後資源狀態；不改寫舊候選檔。"""
    pk = game["game_pk"]
    candidate_keys = {(row["at_bat_number"], row["alignment_evidence"]["feed_event_index"])
                      for row in rows if row["analysis_labels"]["actual_challenge"]}
    if (len(candidate_keys) != sum(row["analysis_labels"]["actual_challenge"] for row in rows)
            or candidate_keys != set(outcomes)):
        raise ValueError(f"挑戰事件與候選未完整一對一對齊：{pk}")
    if any(a["physical_pitch_index"] >= b["physical_pitch_index"] for a, b in zip(rows, rows[1:])):
        raise ValueError(f"候選投球序列不遞增：{pk}")
    current_budget: dict[int, int] = {}
    post_budgets: dict[int, int] = {}
    challenge_results: dict[int, bool | None] = {}
    for row in rows:
        features = row["decision_features"]
        labels = row["analysis_labels"]
        team = features["decision_team_id"]
        before = features["challenges_remaining"]
        if (type(before) is not int or not 0 <= before <= 2
                or team in current_budget and current_budget[team] != before):
            raise ValueError(f"相鄰同隊候選的額度轉移不一致：{pk}")
        if (labels["population"] == "provisional_opportunity" and before == 0
                or labels["population"] == "zero_budget" and before != 0):
            raise ValueError(f"候選母體與挑戰額度不一致：{pk}")
        action = labels["actual_challenge"]
        if (type(action) is not bool or action and before == 0
                or action and labels["population"] != "provisional_opportunity"):
            raise ValueError(f"歷史挑戰行動或額度無效：{pk}")
        key = (row["at_bat_number"], row["alignment_evidence"]["feed_event_index"])
        overturned = outcomes[key][0] if action else None
        if action and outcomes[key][1] != team:
            raise ValueError(f"挑戰方與決策隊伍不一致：{pk} {key}")
        after = before - int(action and not overturned)
        current_budget[team] = after
        post_budgets[row["physical_pitch_index"]] = after
        challenge_results[row["physical_pitch_index"]] = overturned
    next_risk: dict[int, dict] = {}
    episodes = []
    for row in reversed(rows):
        labels = row["analysis_labels"]
        if labels["population"] != "provisional_opportunity":
            continue
        features = row["decision_features"]
        state = features["pre_pitch_state"]
        team = features["decision_team_id"]
        index = row["physical_pitch_index"]
        after = post_budgets[index]
        next_row = next_risk.get(team)
        observed = next_row is not None
        old_target = row["arrival_target"]
        if (old_target["next_opportunity_observed"] is not observed
                or old_target["censoring_boundary"] != (None if observed else "regulation_end")
                or (observed and old_target["pitch_gap"] !=
                    next_row["physical_pitch_index"] - index)):
            raise ValueError(f"舊到達標籤與來源序列不一致：{pk} {index}")
        if after == 0 and observed:
            raise ValueError(f"額度耗盡後仍有下一個有額度候選：{pk} {index}")
        if after == 0:
            outcome, gap, event = "budget_exhausted", 0, False
        elif observed:
            outcome, gap, event = "next_opportunity", old_target["pitch_gap"], True
        else:
            outcome, gap, event = "regulation_end", old_target["pitch_gap"], False
        if type(gap) is not int or gap < 0 or event and gap < 1:
            raise ValueError(f"到達間隔不合法：{pk} {index}")
        episodes.append({"game_pk": pk, "split": game["split"],
                         "at_bat_number": row["at_bat_number"],
                         "pitch_number": row["pitch_number"],
                         "physical_pitch_index": index,
                         "decision_team_id": team,
                         "decision_side": features["decision_side"],
                         "inning": state["inning"],
                         "balls": state["balls"], "strikes": state["strikes"],
                         "pre_action_budget": features["challenges_remaining"],
                         "actual_challenge": labels["actual_challenge"],
                         "challenge_overturned": challenge_results[index],
                         "post_action_budget": after,
                         "outcome": outcome,
                         "regulation_end_coincident": outcome == "budget_exhausted" and old_target["pitch_gap"] == 0,
                         "gap": gap,
                         "event_observed": event,
                         "next_decision_side": next_row["decision_features"]["decision_side"] if event else None})
        next_risk[team] = row
    return list(reversed(episodes))


def load_episode_contract(preparation: dict, baseline: dict,
                          cache_dir: Path) -> tuple[dict[str, list[dict]], list[dict]]:
    archived = {item["game_pk"]: item for item in baseline["candidate_manifests"]}
    games = [game for game in preparation["game_rows"] if game["status"] in INCLUDED]
    if len(games) != len(archived):
        raise ValueError("候選場次與基線清冊不符")
    cache = SourceCache(cache_dir, offline=True)
    splits: dict[str, list[dict]] = defaultdict(list)
    sources = []
    for game in games:
        pk = game["game_pk"]
        if game.get("official_counter_pass") is not True:
            raise ValueError(f"官方分隊計數未通過：{pk}")
        path = Path(game["candidate_artifact"])
        manifest = build_file_manifest(path, source_type="dataset_b_provisional_candidates")
        if (manifest != game["candidate_manifest"]
                or archived.get(pk) != {"game_pk": pk, **manifest}):
            raise ValueError(f"候選來源指紋不符：{pk}")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if (artifact.get("schema_version") != "dataset-b-provisional-candidates-v2"
                or artifact.get("game_pk") != pk or artifact.get("split") != game["split"]
                or artifact.get("source_eligibility_status") != "provisional_source_limitations"):
            raise ValueError(f"候選資料契約不符：{pk}")
        outcomes = _challenge_outcomes(game, cache)
        splits[game["split"]].extend(build_game_episodes(game, artifact["rows"], outcomes))
        sources.append({"game_pk": pk, "candidate_manifest": manifest,
                        "feed_manifest": game["feed_manifest"],
                        "recovered_challenge_count": len(game.get("recovery_evidence", []))})
    for split, rows in splits.items():
        expected = baseline["evaluations"][split]["selected_model"]["episodes"]
        if len(rows) != expected:
            raise ValueError(f"新版候選數與既有固定切分不符：{split}")
    return dict(splits), sources


def evaluate_contract(rows_by_split: dict[str, list[dict]], protocol: dict) -> dict:
    if protocol.get("schema_version") != "dataset-b-resource-aware-arrival-protocol-v1":
        raise ValueError("額度感知模型規格版本不符")
    expected = {protocol["training_split"], protocol["selection_split"], *protocol["held_out_splits"]}
    if set(rows_by_split) != expected:
        raise ValueError("訓練／驗證／測試切分不完整")
    counts = {}
    coincident = {}
    active = {}
    for split, rows in rows_by_split.items():
        distribution = Counter(row["outcome"] for row in rows)
        allowed = {"next_opportunity", "regulation_end", "budget_exhausted"}
        if (not rows or not set(distribution) <= allowed
                or sum(distribution.values()) != len(rows)):
            raise ValueError(f"終止類型不完整：{split}")
        counts[split] = dict(sorted(distribution.items()))
        coincident[split] = sum(row.get("regulation_end_coincident", False) for row in rows)
        active[split] = [{"game_pk": row["game_pk"], "balls": row["balls"],
                          "strikes": row["strikes"],
                          "challenges_remaining": row["post_action_budget"],
                          "gap": row["gap"], "event_observed": row["event_observed"]}
                         for row in rows if row["post_action_budget"] > 0]
    result = fit_and_evaluate(active, protocol)
    result.update(schema_version="dataset-b-resource-aware-arrival-results-v1",
                  estimand=protocol["estimand"],
                  outcome_counts_by_split=counts,
                  coincident_budget_and_regulation_end_by_split=coincident,
                  post_action_budget_contract_valid=True,
                  conditional_post_action_arrival_evaluation_completed=True,
                  decision_time_counterfactual_ready=False,
                  formal_legal_opportunity_ready=False,
                  formal_dynamic_policy_ready=False)
    result.pop("observational_baseline_evaluation_completed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data/raw/dataset_b/source_cache")
    parser.add_argument("--protocol", type=Path, default=ROOT / "config/dataset_b_resource_aware_protocol.json")
    parser.add_argument("--episodes-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output == args.episodes_output or args.output.exists() or args.episodes_output.exists():
        raise FileExistsError("拒絕覆寫既有額度感知結果或契約")
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    _verify_inputs(preparation, baseline, args.preparation)
    rows_by_split, sources = load_episode_contract(preparation, baseline, args.cache_dir)
    episodes = {"schema_version": "dataset-b-resource-aware-episodes-v1",
                "estimand": protocol["estimand"],
                "source_eligibility_status": "provisional_source_limitations",
                "decision_time_feature_warning": "post_action_budget 與 challenge_overturned 是事後欄位，不可作挑戰前預測特徵",
                "rows_by_split": rows_by_split,
                "source_manifests": sources,
                "input_manifests": [build_file_manifest(path, source_type=kind) for path, kind in (
                    (args.baseline, "dataset_b_observational_baseline"),
                    (args.preparation, "dataset_b_pretraining_preparation"),
                    (args.protocol, "dataset_b_resource_aware_protocol"))]}
    result = evaluate_contract(rows_by_split, protocol)
    result["input_manifests"] = episodes["input_manifests"]
    result["runtime"] = _runtime()
    atomic_json_new(args.episodes_output, episodes)
    result["episode_contract_manifest"] = build_file_manifest(
        args.episodes_output, source_type="dataset_b_resource_aware_episodes")
    atomic_json_new(args.output, result)
    print(json.dumps({"outcome_counts_by_split": result["outcome_counts_by_split"],
                      "selected_model": result["validation_model_selection"]["selected_model"],
                      "formal_dynamic_policy_ready": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
