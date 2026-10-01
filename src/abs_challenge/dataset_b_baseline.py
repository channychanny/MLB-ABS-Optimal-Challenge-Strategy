"""可重現的 Dataset B 觀察性離散到達率基線。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random

from .phase1_cli import _runtime
from .provenance import build_file_manifest
from .source_cache import atomic_json_new
from .dataset_b_readiness import validate_inputs as validate_readiness_inputs


ROOT = Path(__file__).resolve().parents[2]
FEATURE_FIELDS = {"pre_pitch_state", "challenges_remaining", "original_call",
                  "decision_team_id", "decision_side"}
STATE_FIELDS = {"inning", "half", "outs", "bases", "balls", "strikes", "home_score", "away_score"}
EPSILON = 1e-12


def _read_episodes(gate: dict, preparation: dict, policy: dict) -> dict[str, list[dict]]:
    if (gate.get("schema_version") != "dataset-b-limited-model-input-gate-v1"
            or gate.get("limited_observational_baseline_input_ready") is not True
            or gate.get("formal_legal_opportunity_ready") is not False
            or gate.get("formal_dynamic_policy_ready") is not False):
        raise ValueError("限定觀察性模型輸入閘門未通過")
    if preparation.get("selection_sha256") != policy.get("selection_sha256"):
        raise ValueError("固定選場指紋與模型輸入政策不符")
    manifests = {item["source_type"]: item for item in gate["input_manifests"]}
    for kind, path in (("dataset_b_pretraining_preparation", preparation["_path"]),
                       ("dataset_b_model_input_policy", policy["_path"])):
        item = manifests.get(kind)
        if item is None or item != build_file_manifest(path, source_type=kind):
            raise ValueError(f"輸入檔與已通過的資料閘門不符：{kind}")
    selection_manifest = manifests.get("dataset_b_schedule_selection")
    if selection_manifest is None:
        raise ValueError("限定輸入閘門未包含固定選場清冊")
    selection_path = Path(selection_manifest["source_path"])
    if build_file_manifest(selection_path, source_type="dataset_b_schedule_selection") != selection_manifest:
        raise ValueError("固定選場清冊與輸入閘門不符")
    validated_gate = validate_readiness_inputs(
        json.loads(selection_path.read_text(encoding="utf-8")), preparation, policy)
    for key in ("selected_games", "included_games", "excluded_unlocalized_game_pks",
                "split_games", "candidate_counts", "candidate_counts_by_split"):
        if gate.get(key) != validated_gate.get(key):
            raise ValueError(f"限定輸入閘門的衍生檢查不一致：{key}")

    included_status = {"provisional_population_pass", "provisional_population_recovered"}
    expected_games = gate["split_games"]
    game_rows = [row for row in preparation["game_rows"] if row["status"] in included_status]
    actual_games = Counter(row["split"] for row in game_rows)
    if dict(sorted(actual_games.items())) != expected_games:
        raise ValueError("準備資料的場次 split 數與輸入閘門不符")
    episodes_by_split: dict[str, list[dict]] = defaultdict(list)
    seen_games: set[int] = set()
    for game in game_rows:
        pk = game["game_pk"]
        if pk in seen_games or game.get("official_counter_pass") is not True:
            raise ValueError(f"場次重複或官方計數未通過：{pk}")
        seen_games.add(pk)
        path = Path(game["candidate_artifact"])
        manifest = build_file_manifest(path, source_type="dataset_b_provisional_candidates")
        if manifest != game["candidate_manifest"]:
            raise ValueError(f"候選檔 SHA-256 與準備報告不符：{pk}")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if (artifact.get("schema_version") != "dataset-b-provisional-candidates-v2"
                or artifact.get("game_pk") != pk or artifact.get("split") != game["split"]
                or artifact.get("source_eligibility_status") != "provisional_source_limitations"):
            raise ValueError(f"候選檔契約不符：{pk}")
        for candidate in artifact["rows"]:
            labels = candidate["analysis_labels"]
            if labels["population"] != "provisional_opportunity":
                continue
            features = candidate["decision_features"]
            target = candidate["arrival_target"]
            state = features["pre_pitch_state"]
            if (set(features) != FEATURE_FIELDS or set(state) != STATE_FIELDS
                    or features["challenges_remaining"] not in (1, 2)
                    or type(state["balls"]) is not int or not 0 <= state["balls"] <= 3
                    or type(state["strikes"]) is not int or not 0 <= state["strikes"] <= 2
                    or type(target["pitch_gap"]) is not int or target["pitch_gap"] < 0
                    or type(target["next_opportunity_observed"]) is not bool):
                raise ValueError(f"風險集候選的決策特徵或到達標籤無效：{pk}")
            observed = target["next_opportunity_observed"]
            gap = target["pitch_gap"]
            if (observed and (gap < 1 or target["censoring_boundary"] is not None)
                    or not observed and target["censoring_boundary"] != "regulation_end"):
                raise ValueError(f"風險集到達或右設限標記矛盾：{pk}")
            episodes_by_split[game["split"]].append({
                "game_pk": pk,
                "split": game["split"],
                "balls": state["balls"],
                "strikes": state["strikes"],
                "challenges_remaining": features["challenges_remaining"],
                "gap": gap,
                "event_observed": observed,
            })
    if sum(map(len, episodes_by_split.values())) != gate["candidate_counts"]["provisional_opportunity"]:
        raise ValueError("模型風險集總數與輸入閘門不符")
    return dict(episodes_by_split)


def _state_key(episode: dict) -> tuple[int, int, int]:
    return episode["balls"], episode["strikes"], episode["challenges_remaining"]


def _fit_hazards(episodes: list[dict], smoothing: int | None) -> dict:
    exposure = sum(item["gap"] for item in episodes)
    events = sum(item["event_observed"] for item in episodes)
    if exposure <= 0 or events <= 0 or events >= exposure:
        raise ValueError("Train 資料不足以估計非退化離散 hazard")
    global_hazard = events / exposure
    grouped: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    for item in episodes:
        counts = grouped[_state_key(item)]
        counts[0] += int(item["event_observed"])
        counts[1] += item["gap"]
    if smoothing is None:
        return {"kind": "pooled", "global_hazard": global_hazard,
                "exposure_pitches": exposure, "events": events}
    strata = {}
    for key, (stratum_events, stratum_exposure) in grouped.items():
        strata["|".join(map(str, key))] = {
            "hazard": (stratum_events + smoothing * global_hazard) / (stratum_exposure + smoothing),
            "exposure_pitches": stratum_exposure,
            "events": stratum_events,
        }
    return {"kind": "state_stratified", "global_hazard": global_hazard,
            "smoothing_prior_pitch_exposures": smoothing, "strata": strata,
            "exposure_pitches": exposure, "events": events}


def _hazard(model: dict, episode: dict) -> float:
    if model["kind"] == "pooled":
        return model["global_hazard"]
    key = "|".join(map(str, _state_key(episode)))
    return model["strata"].get(key, {}).get("hazard", model["global_hazard"])


def predict_arrival_probability(model: dict, *, balls: int, strikes: int,
                                challenges_remaining: int, horizon_pitches: int) -> float:
    """回傳觀察性模型下，指定投球視野內的同隊暫定機會到達機率。"""
    if (type(balls) is not int or not 0 <= balls <= 3
            or type(strikes) is not int or not 0 <= strikes <= 2
            or challenges_remaining not in (1, 2)
            or type(horizon_pitches) is not int or horizon_pitches < 1):
        raise ValueError("預測狀態或投球視野無效")
    episode = {"balls": balls, "strikes": strikes,
               "challenges_remaining": challenges_remaining}
    return 1 - (1 - _hazard(model, episode)) ** horizon_pitches


def _episode_nll(model: dict, episode: dict) -> float:
    h = min(1 - EPSILON, max(EPSILON, _hazard(model, episode)))
    if episode["event_observed"]:
        return -(math.log(h) + (episode["gap"] - 1) * math.log1p(-h))
    return -episode["gap"] * math.log1p(-h)


def _summarize(model: dict, episodes: list[dict], horizons: tuple[int, ...]) -> dict:
    nll = [_episode_nll(model, episode) for episode in episodes]
    exposure = sum(item["gap"] for item in episodes)
    result = {"episodes": len(episodes),
              "events": sum(item["event_observed"] for item in episodes),
              "right_censored": sum(not item["event_observed"] for item in episodes),
              "pitch_exposure": exposure,
              "negative_log_likelihood_per_episode": sum(nll) / len(nll),
              "negative_log_likelihood_per_pitch_exposure": sum(nll) / exposure}
    for horizon in horizons:
        known, brier = 0, 0.0
        for episode in episodes:
            gap = episode["gap"]
            observed = episode["event_observed"]
            if observed or gap >= horizon:
                outcome = int(observed and gap <= horizon)
                predicted = 1 - (1 - _hazard(model, episode)) ** horizon
                brier += (predicted - outcome) ** 2
                known += 1
        result[f"horizon_{horizon}_pitches"] = {
            "brier_score": brier / known if known else None,
            "known_episodes": known,
            "coverage": known / len(episodes),
        }
    return result


def _bootstrap_nll_difference(global_model: dict, candidate_model: dict,
                              episodes: list[dict], replicates: int, seed: int) -> dict:
    by_game: dict[int, list[dict]] = defaultdict(list)
    for episode in episodes:
        by_game[episode["game_pk"]].append(episode)
    games = sorted(by_game)
    if len(games) < 2:
        return {"game_clusters": len(games), "replicates": 0, "ci_95": None}
    rng = random.Random(seed)
    differences = []
    for _ in range(replicates):
        sampled = [rng.choice(games) for _ in games]
        values, n = 0.0, 0
        for pk in sampled:
            group = by_game[pk]
            values += sum(_episode_nll(candidate_model, item) - _episode_nll(global_model, item)
                          for item in group)
            n += len(group)
        differences.append(values / n)
    differences.sort()
    return {"game_clusters": len(games), "replicates": replicates,
            "seed": seed,
            "mean_difference_per_episode": sum(differences) / len(differences),
            "ci_95": [differences[int(0.025 * (len(differences) - 1))],
                      differences[int(0.975 * (len(differences) - 1))]]}


def fit_and_evaluate(episodes_by_split: dict[str, list[dict]], protocol: dict) -> dict:
    train = episodes_by_split[protocol["training_split"]]
    validation = episodes_by_split[protocol["selection_split"]]
    horizons = tuple(protocol["forecast_horizons_pitches"])
    global_model = _fit_hazards(train, None)
    candidates = [{"model": _fit_hazards(train, strength), "selection_score": None}
                  for strength in protocol["smoothing_prior_pitch_exposures"]]
    for candidate in candidates:
        candidate["selection_score"] = _summarize(candidate["model"], validation, horizons)[
            protocol["selection_metric"]]
    pooled_score = _summarize(global_model, validation, horizons)[protocol["selection_metric"]]
    options = [{"name": "pooled_global", "score": pooled_score, "model": global_model}]
    options.extend({"name": f"state_stratified_alpha_{item['model']['smoothing_prior_pitch_exposures']}",
                    "score": item["selection_score"], "model": item["model"]} for item in candidates)
    selected = min(options, key=lambda item: (item["score"], item["name"]))
    evaluations = {}
    for split in ("train", "validation", *protocol["held_out_splits"]):
        episodes = episodes_by_split[split]
        evaluation = {"game_clusters": len({item["game_pk"] for item in episodes}),
                      "pooled_global": _summarize(global_model, episodes, horizons),
                      "selected_model": _summarize(selected["model"], episodes, horizons)}
        if split in protocol["held_out_splits"] and selected["name"] != "pooled_global":
            evaluation["selected_minus_pooled_cluster_bootstrap"] = _bootstrap_nll_difference(
                global_model, selected["model"], episodes,
                protocol["bootstrap_replicates"], protocol["bootstrap_seed"] + len(evaluations))
        evaluations[split] = evaluation
    return {"schema_version": "dataset-b-observational-baseline-results-v1",
            "estimand": protocol["estimand"],
            "training_fit": {"episodes": len(train), "pooled_model": global_model,
                             "state_model_candidate_scores": [
                                 {"smoothing_prior_pitch_exposures": item["model"]["smoothing_prior_pitch_exposures"],
                                  "validation_negative_log_likelihood_per_pitch_exposure": item["selection_score"]}
                                 for item in candidates]},
            "validation_model_selection": {
                "metric": protocol["selection_metric"],
                "options": [{"model": item["name"], "score": item["score"]} for item in options],
                "selected_model": selected["name"]},
            "selected_model_parameters": selected["model"],
            "evaluations": evaluations,
            "forecast_horizons_pitches": protocol["forecast_horizons_pitches"],
            "primary_metric": protocol["primary_metric"],
            "secondary_metric": protocol["secondary_metric"],
            "limitations": protocol["limitations"],
            "observational_baseline_evaluation_completed": True,
            "formal_legal_opportunity_ready": False,
            "formal_dynamic_policy_ready": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=ROOT / "config/dataset_b_model_input_policy.json")
    parser.add_argument("--protocol", type=Path, default=ROOT / "config/dataset_b_baseline_protocol.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("拒絕覆寫既有 Dataset B 基線結果")
    gate = json.loads(args.gate.read_text(encoding="utf-8"))
    preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("schema_version") != "dataset-b-observational-baseline-protocol-v1":
        raise ValueError("基線評估規格版本不符")
    preparation["_path"] = args.preparation
    policy["_path"] = args.policy
    episodes = _read_episodes(gate, preparation, policy)
    result = fit_and_evaluate(episodes, protocol)
    result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
        (args.gate, "dataset_b_limited_input_gate"),
        (args.preparation, "dataset_b_pretraining_preparation"),
        (args.policy, "dataset_b_model_input_policy"),
        (args.protocol, "dataset_b_observational_baseline_protocol"))]
    result["candidate_manifests"] = [{"game_pk": row["game_pk"], **row["candidate_manifest"]}
                                     for row in preparation["game_rows"]
                                     if row["status"] in {"provisional_population_pass", "provisional_population_recovered"}]
    result["runtime"] = _runtime()
    result["executed_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    atomic_json_new(args.output, result)
    print(json.dumps({"selected_model": result["validation_model_selection"]["selected_model"],
                      "test_nll_per_pitch_exposure": result["evaluations"]["test"]["selected_model"]["negative_log_likelihood_per_pitch_exposure"],
                      "external_nll_per_pitch_exposure": result["evaluations"]["external"]["selected_model"]["negative_log_likelihood_per_pitch_exposure"],
                      "observational_baseline_evaluation_completed": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
