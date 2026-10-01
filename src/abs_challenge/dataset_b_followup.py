"""檢查 Dataset B 到達基線的缺漏／設限敏感度與下一機會分布。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
from statistics import median

from .dataset_b_baseline import _episode_nll
from .phase1_cli import _runtime
from .provenance import build_file_manifest
from .source_cache import atomic_json_new


ROOT = Path(__file__).resolve().parents[2]


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("空樣本無法計算分位數")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _value_category(next_candidate: dict, breaks: list[float]) -> tuple[str, float | None]:
    labels = next_candidate["analysis_labels"]
    s0, s1 = labels.get("s0"), labels.get("s1")
    if (not isinstance(s0, dict) or not isinstance(s1, dict)
            or s0.get("supported") is not True or s1.get("supported") is not True
            or type(s0.get("wp_decision")) not in (int, float)
            or type(s1.get("wp_decision")) not in (int, float)):
        return "unsupported", None
    delta = round(s1["wp_decision"] - s0["wp_decision"], 6)
    if not math.isfinite(delta):
        raise ValueError("下一機會的官方 WP 差值非有限數")
    if delta <= breaks[0]:
        return "nonpositive", delta
    if delta <= breaks[1]:
        return "up_to_0_5_pp", delta
    if delta <= breaks[2]:
        return "over_0_5_to_2_pp", delta
    return "over_2_pp", delta


def load_observed_paths(preparation: dict, baseline: dict, protocol: dict) -> dict[str, list[dict]]:
    if (baseline.get("schema_version") != "dataset-b-observational-baseline-results-v1"
            or baseline.get("observational_baseline_evaluation_completed") is not True):
        raise ValueError("前一版到達基線結果未完成")
    gate_manifests = baseline["input_manifests"]
    for item in gate_manifests:
        path = Path(item["source_path"])
        if item != build_file_manifest(path, source_type=item["source_type"]):
            raise ValueError(f"到達基線輸入來源已變更：{item['source_type']}")
    archived = {item["game_pk"]: item for item in baseline["candidate_manifests"]}
    unresolved = {row["game_pk"] for row in preparation["game_rows"]
                  if row["status"] == "recovery_unresolved"}
    if unresolved != set(protocol["excluded_unlocalized_game_pks"]):
        raise ValueError("五場缺漏排除清冊已變更")
    included = [row for row in preparation["game_rows"]
                if row["status"] in {"provisional_population_pass", "provisional_population_recovered"}]
    if len(included) != len(archived):
        raise ValueError("基線候選場次數與準備報告不符")
    paths: dict[str, list[dict]] = defaultdict(list)
    for game in included:
        pk = game["game_pk"]
        artifact_path = Path(game["candidate_artifact"])
        manifest = build_file_manifest(artifact_path, source_type="dataset_b_provisional_candidates")
        if (manifest != game["candidate_manifest"]
                or archived.get(pk) != {"game_pk": pk, **manifest}):
            raise ValueError(f"場次 {pk} 候選資料與已評估基線指紋不符")
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        if artifact["game_pk"] != pk or artifact["split"] != game["split"]:
            raise ValueError(f"場次 {pk} 候選檔身分或切分不符")
        risk_rows = [row for row in artifact["rows"]
                     if row["analysis_labels"]["population"] == protocol["risk_set_population"]]
        next_by_team: dict[int, dict] = {}
        game_paths = []
        for current in reversed(risk_rows):
            features = current["decision_features"]
            state = features["pre_pitch_state"]
            team = features["decision_team_id"]
            next_candidate = next_by_team.get(team)
            target = current["arrival_target"]
            observed = target["next_opportunity_observed"]
            if observed != (next_candidate is not None):
                raise ValueError(f"場次 {pk} 下一機會的到達／設限標記不一致")
            if next_candidate is not None:
                gap = next_candidate["physical_pitch_index"] - current["physical_pitch_index"]
                if target["pitch_gap"] != gap or gap <= 0:
                    raise ValueError(f"場次 {pk} 同隊下一機會的物理投球間隔不一致")
                next_features = next_candidate["decision_features"]
                category, delta = _value_category(next_candidate, protocol["wp_value_breaks"])
                future = {"next_decision_side": next_features["decision_side"],
                          "next_inning": next_features["pre_pitch_state"]["inning"],
                          "next_challenges_remaining": next_features["challenges_remaining"],
                          "next_bases": next_features["pre_pitch_state"]["bases"],
                          "next_outs": next_features["pre_pitch_state"]["outs"],
                          "next_wp_value_category": category,
                          "next_wp_delta_decision": delta}
            else:
                if target["censoring_boundary"] != "regulation_end":
                    raise ValueError(f"場次 {pk} 右設限邊界不一致")
                future = None
            game_paths.append({"game_pk": pk, "split": game["split"],
                               "year": int(game["date"][:4]),
                               "start_inning": state["inning"],
                               "balls": state["balls"], "strikes": state["strikes"],
                               "current_side": features["decision_side"],
                               "challenges_remaining": features["challenges_remaining"],
                               "gap": target["pitch_gap"], "event_observed": observed,
                               "future": future})
            next_by_team[team] = current
        paths[game["split"]].extend(reversed(game_paths))
    for split, evaluation in baseline["evaluations"].items():
        rows = paths[split]
        observed = sum(row["event_observed"] for row in rows)
        if (len(rows) != evaluation["selected_model"]["episodes"]
                or observed != evaluation["selected_model"]["events"]):
            raise ValueError(f"切分 {split} 的未來機會序列與前一版基線不符")
    return dict(paths)


def _phase(inning: int, protocol: dict) -> str:
    for name, (start, end) in protocol["game_phase_innings"].items():
        if start <= inning <= end:
            return name
    raise ValueError(f"候選開始局數不屬第 1–9 局：{inning}")


def _phase_sensitivity(paths: dict[str, list[dict]], baseline: dict, protocol: dict) -> dict:
    pooled = baseline["training_fit"]["pooled_model"]
    selected = baseline["selected_model_parameters"]
    result = {}
    for split, episodes in paths.items():
        groups = defaultdict(list)
        for episode in episodes:
            groups[_phase(episode["start_inning"], protocol)].append(episode)
        summary = {}
        for phase, group in groups.items():
            exposure = sum(item["gap"] for item in group)
            events = sum(item["event_observed"] for item in group)
            known = sum(item["event_observed"] or item["gap"] >= protocol["censoring_horizon_pitches"]
                        for item in group)
            summary[phase] = {"game_clusters": len({item["game_pk"] for item in group}),
                              "episodes": len(group), "events": events,
                              "right_censored": len(group) - events,
                              "pitch_exposure": exposure,
                              "empirical_event_per_exposure": events / exposure if exposure else None,
                              "horizon_observable_fraction": known / len(group),
                              "pooled_nll_per_exposure": sum(_episode_nll(pooled, item) for item in group) / exposure if exposure else None,
                              "selected_nll_per_exposure": sum(_episode_nll(selected, item) for item in group) / exposure if exposure else None}
        result[split] = summary
    train = paths[protocol["training_split"]]
    complete = [row for row in train if row["event_observed"]]
    before_ninth = [row for row in train if row["start_inning"] < 9]
    result["train_fit_scenarios"] = {
        "full_hazard": pooled["global_hazard"],
        "drop_censored_hazard_diagnostic_only": len(complete) / sum(row["gap"] for row in complete),
        "start_innings_1_to_8_hazard": sum(row["event_observed"] for row in before_ninth) / sum(row["gap"] for row in before_ninth),
        "start_innings_1_to_8_episodes": len(before_ninth)}
    return result


def _missing_game_scenarios(train: list[dict], protocol: dict,
                            unresolved_rows: list[dict]) -> dict:
    games: dict[int, list[dict]] = defaultdict(list)
    for episode in train:
        games[episode["game_pk"]].append(episode)
    per_game = [{"game_pk": pk,
                 "year": rows[0]["year"],
                 "episodes": len(rows),
                 "events": sum(row["event_observed"] for row in rows),
                 "exposure": sum(row["gap"] for row in rows)} for pk, rows in games.items()]
    hazards = [row["events"] / row["exposure"] for row in per_game]
    reference_exposure = median(row["exposure"] for row in per_game)
    observed_events = sum(row["events"] for row in per_game)
    observed_exposure = sum(row["exposure"] for row in per_game)
    missing_count = len(protocol["excluded_unlocalized_game_pks"])
    by_year = {}
    for year in sorted({row["year"] for row in per_game}):
        cohort = [row for row in per_game if row["year"] == year]
        excluded = sum(int(row["date"][:4]) == year for row in unresolved_rows)
        events_year = sum(row["events"] for row in cohort)
        exposure_year = sum(row["exposure"] for row in cohort)
        by_year[str(year)] = {"included_games": len(cohort),
                              "excluded_games": excluded,
                              "fixed_selected_games": len(cohort) + excluded,
                              "included_event_per_pitch_exposure": events_year / exposure_year}
    scenarios = []
    for probability in protocol["missing_game_scenario_hazard_quantiles"]:
        assumed_hazard = _quantile(hazards, probability)
        total_exposure = observed_exposure + missing_count * reference_exposure
        total_events = observed_events + missing_count * reference_exposure * assumed_hazard
        scenarios.append({"reference_hazard_quantile": probability,
                          "assumed_missing_game_hazard": assumed_hazard,
                          "hypothetical_pooled_hazard": total_events / total_exposure,
                          "hypothetical_arrival_probability_within_5_pitches":
                          1 - (1 - total_events / total_exposure) ** 5})
    return {"selected_train_games": len(per_game), "excluded_train_games": missing_count,
            "train_year_cohorts": by_year,
            "reference_exposure_pitches_per_missing_game": reference_exposure,
            "observed_pooled_hazard": observed_events / observed_exposure,
            "observed_arrival_probability_within_5_pitches":
            1 - (1 - observed_events / observed_exposure) ** 5,
            "observed_game_hazard_min": min(hazards),
            "observed_game_hazard_max": max(hazards),
            "scenarios": scenarios,
            "interpretation": "假設性缺漏場情境；不是來源復原、識別界限或機率區間"}


def _current_key(row: dict) -> str:
    return f"{row['current_side']}|{row['challenges_remaining']}"


def _fit_categorical(train: list[dict], label: str, classes: list[str],
                     prior_per_class: float, smoothing: int | None) -> dict:
    global_counts = Counter(row["future"][label] for row in train)
    n = len(train)
    global_prob = {category: (global_counts[category] + prior_per_class) /
                   (n + prior_per_class * len(classes)) for category in classes}
    if smoothing is None:
        return {"kind": "pooled", "classes": classes, "global_probabilities": global_prob,
                "train_events": n}
    strata: dict[str, Counter] = defaultdict(Counter)
    for row in train:
        strata[_current_key(row)][row["future"][label]] += 1
    probabilities = {}
    for key, counts in strata.items():
        count = sum(counts.values())
        probabilities[key] = {category: (counts[category] + smoothing * global_prob[category]) /
                              (count + smoothing) for category in classes}
    return {"kind": "state_stratified", "classes": classes,
            "global_probabilities": global_prob,
            "smoothing_prior_event_counts": smoothing,
            "stratum_probabilities": probabilities, "train_events": n}


def _categorical_probability(model: dict, row: dict, category: str) -> float:
    return model.get("stratum_probabilities", {}).get(
        _current_key(row), model["global_probabilities"])[category]


def _categorical_nll(model: dict, row: dict, label: str) -> float:
    return -math.log(_categorical_probability(model, row, row["future"][label]))


def _bootstrap_difference(global_model: dict, selected_model: dict, rows: list[dict],
                          label: str, replicates: int, seed: int) -> dict:
    groups: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        groups[row["game_pk"]].append(_categorical_nll(selected_model, row, label)
                                      - _categorical_nll(global_model, row, label))
    games = sorted(groups)
    rng = random.Random(seed)
    samples = []
    for _ in range(replicates):
        drawn = [rng.choice(games) for _ in games]
        samples.append(sum(sum(groups[pk]) for pk in drawn) / sum(len(groups[pk]) for pk in drawn))
    samples.sort()
    return {"game_clusters": len(games), "replicates": replicates, "seed": seed,
            "ci_95_difference_per_event": [samples[int(0.025 * (replicates - 1))],
                                            samples[int(0.975 * (replicates - 1))]]}


def _categorical_analysis(paths: dict[str, list[dict]], protocol: dict,
                          label: str, classes: list[str], seed_offset: int) -> dict:
    observed = {split: [row for row in rows if row["future"] is not None]
                for split, rows in paths.items()}
    train = observed[protocol["training_split"]]
    validation = observed[protocol["selection_split"]]
    pooled = _fit_categorical(train, label, classes, protocol["global_dirichlet_per_class"], None)
    candidates = [(f"state_alpha_{alpha}", _fit_categorical(
        train, label, classes, protocol["global_dirichlet_per_class"], alpha))
        for alpha in protocol["multinomial_smoothing_event_counts"]]
    options = [("pooled_global", pooled), *candidates]
    validation_scores = [{"model": name, "log_loss_per_observed_next_event":
                          sum(_categorical_nll(model, row, label) for row in validation) / len(validation)}
                         for name, model in options]
    selected_name = min(validation_scores, key=lambda item: (item["log_loss_per_observed_next_event"], item["model"]))["model"]
    selected = dict(options)[selected_name]
    evaluations = {}
    for index, split in enumerate(("train", "validation", *protocol["held_out_splits"])):
        rows = observed[split]
        counts = Counter(row["future"][label] for row in rows)
        evaluation = {"game_clusters": len({row["game_pk"] for row in rows}),
                      "observed_next_events": len(rows),
                      "outcome_counts": {category: counts[category] for category in classes},
                      "pooled_log_loss": sum(_categorical_nll(pooled, row, label) for row in rows) / len(rows),
                      "selected_log_loss": sum(_categorical_nll(selected, row, label) for row in rows) / len(rows),
                      "selected_mean_prediction": {category:
                          sum(_categorical_probability(selected, row, category) for row in rows) / len(rows)
                          for category in classes}}
        if split in protocol["held_out_splits"] and selected_name != "pooled_global":
            evaluation["cluster_bootstrap"] = _bootstrap_difference(
                pooled, selected, rows, label, protocol["bootstrap_replicates"],
                protocol["bootstrap_seed"] + seed_offset + index)
        evaluations[split] = evaluation
    return {"label": label, "classes": classes,
            "validation_options": validation_scores,
            "selected_model": selected_name,
            "selected_parameters": selected,
            "evaluations": evaluations}


def _numeric_wp_support(paths: dict[str, list[dict]]) -> dict:
    result = {}
    for split, rows in paths.items():
        future = [row["future"] for row in rows if row["future"] is not None]
        supported = [row["next_wp_delta_decision"] for row in future
                     if row["next_wp_delta_decision"] is not None]
        result[split] = {"observed_next_events": len(future),
                         "both_sides_wp_supported": len(supported),
                         "support_fraction": len(supported) / len(future),
                         "supported_delta_wp_mean": sum(supported) / len(supported) if supported else None,
                         "supported_delta_wp_quantiles": {
                             "p10": _quantile(supported, 0.1), "median": _quantile(supported, 0.5),
                             "p90": _quantile(supported, 0.9)} if supported else None,
                         "unsupported_count": len(future) - len(supported)}
    return result


def _next_state_support(paths: dict[str, list[dict]], protocol: dict) -> dict:
    result = {}
    for split, rows in paths.items():
        future = [row["future"] for row in rows if row["future"] is not None]
        result[split] = {
            "observed_next_events": len(future),
            "next_inning_phase_counts": dict(sorted(Counter(
                _phase(row["next_inning"], protocol) for row in future).items())),
            "next_challenges_remaining_counts": dict(sorted(Counter(
                row["next_challenges_remaining"] for row in future).items())),
            "next_outs_counts": dict(sorted(Counter(row["next_outs"] for row in future).items())),
            "next_bases_counts": dict(sorted(Counter(row["next_bases"] for row in future).items())),
        }
    return result


def analyze_followup(paths: dict[str, list[dict]], baseline: dict, protocol: dict,
                     unresolved_rows: list[dict]) -> dict:
    if protocol["schema_version"] != "dataset-b-observational-followup-protocol-v1":
        raise ValueError("下一機會評估規格版本不符")
    return {"schema_version": "dataset-b-observational-followup-results-v1",
            "scope": protocol["scope"],
            "missing_train_games": _missing_game_scenarios(
                paths[protocol["training_split"]], protocol, unresolved_rows),
            "phase_and_censoring_sensitivity": _phase_sensitivity(paths, baseline, protocol),
            "next_side_distribution": _categorical_analysis(
                paths, protocol, "next_decision_side", protocol["next_side_classes"], 100),
            "next_wp_value_distribution": _categorical_analysis(
                paths, protocol, "next_wp_value_category", protocol["next_wp_value_classes"], 200),
            "next_wp_value_support": _numeric_wp_support(paths),
            "next_state_support": _next_state_support(paths, protocol),
            "limitations": protocol["limitations"],
            "formal_legal_opportunity_ready": False,
            "counterfactual_transition_ready": False,
            "formal_dynamic_policy_ready": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=ROOT / "config/dataset_b_followup_protocol.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("拒絕覆寫既有 Dataset B 後續敏感度結果")
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    prepared_manifest = next((item for item in baseline["input_manifests"]
                              if item["source_type"] == "dataset_b_pretraining_preparation"), None)
    if (prepared_manifest is None
            or prepared_manifest != build_file_manifest(
                args.preparation, source_type="dataset_b_pretraining_preparation")):
        raise ValueError("準備報告與已評估到達基線的指紋不符")
    paths = load_observed_paths(preparation, baseline, protocol)
    unresolved_rows = [row for row in preparation["game_rows"]
                       if row["status"] == "recovery_unresolved"]
    result = analyze_followup(paths, baseline, protocol, unresolved_rows)
    result["input_manifests"] = [build_file_manifest(path, source_type=kind) for path, kind in (
        (args.baseline, "dataset_b_observational_baseline"),
        (args.preparation, "dataset_b_pretraining_preparation"),
        (args.protocol, "dataset_b_observational_followup_protocol"))]
    result["runtime"] = _runtime()
    atomic_json_new(args.output, result)
    print(json.dumps({"test_next_side_model": result["next_side_distribution"]["selected_model"],
                      "test_next_value_model": result["next_wp_value_distribution"]["selected_model"],
                      "formal_dynamic_policy_ready": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
