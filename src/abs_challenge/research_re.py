"""僅使用 Train 的 RE24／RE288 及九局平手邊界開發估計。"""

from __future__ import annotations

from collections import defaultdict
from itertools import product
from typing import Any

from .historical import SPLITS, verify_dataset


def estimate_re_and_boundary(datasets: list[dict[str, Any]]) -> dict[str, Any]:
    if not datasets:
        raise ValueError("至少需要一份 Dataset A")
    games, rows, hashes = {}, [], []
    for dataset in datasets:
        verify_dataset(dataset)
        hashes.append(dataset["dataset_content_sha256"])
        for game in dataset["games"]:
            if game["game_pk"] in games:
                raise ValueError("不同 dataset 重複包含同一場比賽，不得重複加權")
            games[game["game_pk"]] = game
        rows.extend(r for r in dataset["rows"] if r["split"] == "train")
    train_games = [g for g in games.values() if g["split"] == "train"]
    eligible = [r for r in rows if r["sampling"]["re_half_eligible"]]
    if not eligible:
        raise ValueError("沒有可用 Train 完整半局；Validation／Test／External 不得代替")
    tables = {}
    for table_name, dimensions in (("re24", (range(8), range(3))),
                                   ("re288", (range(8), range(3), range(4), range(3)))):
        cells = defaultdict(list)
        for row in eligible:
            if table_name == "re24" and not row["sampling"]["re24_first_pitch"]:
                continue
            state = row["features"]
            key = (state["bases"], state["outs"])
            if table_name == "re288":
                key += (state["balls"], state["strikes"])
            cells[key].append(row)
        table = []
        for key in product(*dimensions):
            selected = cells[key]
            total = sum(r["labels"]["runs_to_half_end"] for r in selected)
            table.append(dict(zip(("bases", "outs", "balls", "strikes"), key)) | {
                "n": len(selected), "games": len({r["game_pk"] for r in selected}),
                "run_sum": total, "mean": total / len(selected) if selected else None})
        tables[table_name] = table
    ties = sorted((g for g in train_games if g["regulation_tied"]), key=lambda g: g["game_pk"])
    home_wins = sum(g["home_win"] for g in ties)
    boundary = {"schema_version": "historical-regulation-boundary-v1", "fit_split": "train",
        "allowed_seasons": SPLITS["train"], "games": len(ties), "home_wins": home_wins,
        "home_wp": home_wins / len(ties) if ties else None,
        "game_pks": [g["game_pk"] for g in ties],
        "status": "development_estimate" if ties else "missing_training_ties",
        "estimator": "empirical_home_win_fraction_without_smoothing"}
    return {"schema_version": "research-re-development-v1", "fit_split": "train",
        "dataset_content_sha256": sorted(hashes), "allowed_train_seasons": SPLITS["train"],
        "observed_train_seasons": sorted({g["season"] for g in train_games}),
        "sampling": {"re24": "first_observed_pitch_per_plate_appearance",
                     "re288": "all_observed_pitches", "halves": "three_out_halves_only"},
        **tables, "regulation_boundary": boundary,
        "summary": {"train_games": len(train_games), "train_pitches": len(rows),
            "re_eligible_pitches": len(eligible), "excluded_censored_pitches": len(rows) - len(eligible),
            "ignored_nontrain_games": len(games) - len(train_games),
            "re24_observed_states": sum(c["n"] > 0 for c in tables["re24"]),
            "re288_observed_states": sum(c["n"] > 0 for c in tables["re288"])},
        "formal_model_ready": False, "formal_policy_evaluation_ready": False,
        "limitations": ["開發估計，未驗證全季覆蓋與正式版本。", "空格為 null，不以零或官方表格插補。",
                        "再見半局排除可能帶來選擇效應；後續需與只取前八局作敏感度比較。",
                        "尚未提供以比賽為單位的信賴區間，不作統計推論。"]}
