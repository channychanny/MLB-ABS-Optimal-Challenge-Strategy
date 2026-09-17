"""可攜式合成表格；不依賴本機下載資料，不將填充值當成官方結果。"""

from itertools import product
import json

from abs_challenge.baseline import BOUNDARY_VERSION, EXPLORER_URL, SNAPSHOT_VERSION
from abs_challenge.provenance import build_download_manifest
from urllib.parse import urlencode


def synthetic_snapshot() -> dict:
    return {
        "schema_version": SNAPSHOT_VERSION, "wp_perspective": "home", "home_score_diff_range": [-5, 5],
        "innings": [1, 9], "source_url": EXPLORER_URL, "source_page_seasons": [2016, 2025], "re_response_years": [2025],
        "regulation_boundary": {"version": BOUNDARY_VERSION, "home_win_probability": 0.47, "extra_inning_policy_modeled": False},
        "re288": [{"bases": b, "outs": o, "balls": a, "strikes": s, "run_expectancy": 0.5, "source_n": 10}
                  for b, o, a, s in product(range(8), range(3), range(4), range(3))],
        "wp": [{"inning": i, "half": h, "outs": o, "bases": b, "balls": a, "strikes": s, "home_win_probabilities": [0.5] * 11}
               for i, h, o, b, a, s in product(range(1, 10), ("top", "bottom"), range(3), range(8), range(4), range(3))],
    }


def set_wp(snapshot: dict, state: tuple, diff: int, value: float) -> None:
    for row in snapshot["wp"]:
        if tuple(row[k] for k in ("inning", "half", "outs", "bases", "balls", "strikes")) == state:
            row["home_win_probabilities"][diff + 5] = value
            return
    raise AssertionError("測試情境不存在")


def synthetic_bundle() -> dict:
    snapshot = synthetic_snapshot()
    documents = {}
    def add(name, url, content, count):
        documents[name] = {"content": content, "manifest": build_download_manifest(
            source_type="synthetic_fixture", source_url=url, content=content, row_count=count,
            retrieved_at_utc="2026-09-14T00:00:00Z")}
    add("page", EXPLORER_URL, "This data is based on the 10 seasons between 2016-2025.", 1)
    add("script", "https://builds.mlbstatic.com/fixture/game-strategy-explorer.js", "合成測試", 1)
    re_rows = [{"year": 2025, "runners_on_cd": r["bases"], "outs": r["outs"], "ball_count": r["balls"],
                "strike_count": r["strikes"], "run_expectancy": r["run_expectancy"], "n": r["source_n"]} for r in snapshot["re288"]]
    url = EXPLORER_URL + "?" + urlencode({"type": "runexp-count", "params": json.dumps({"balls": None, "strikes": None}, sort_keys=True)})
    add("re288", url, json.dumps(re_rows), len(re_rows))
    for bases in range(8):
        rows = []
        for r in snapshot["wp"]:
            if r["bases"] != bases:
                continue
            rows.append({"inning": r["inning"], "bottom_top": "Top" if r["half"] == "top" else "Bottom", "outs": r["outs"],
                "bases_cd": bases, "ball_count": r["balls"], "strike_count": r["strikes"],
                **{f"bat_wins_minus_{-d}" if d < 0 else f"bat_wins_{d}": 0.5 for d in range(-5, 6)}})
        if bases == 2:
            rows.append({**rows[0], "inning": 10, "bottom_top": "Top", "outs": 0, "ball_count": 0, "strike_count": 0})
        params = {"perspective": "home", "is_by_count": True,
                  "runners": {name: bool(bases & (1 << bit)) for bit, name in enumerate(("1b", "2b", "3b"))}}
        url = EXPLORER_URL + "?" + urlencode({"type": "winexp", "params": json.dumps(params, sort_keys=True)})
        add(f"wp_{bases}", url, json.dumps(rows), len(rows))
    return {"schema_version": "savant-explorer-bundle-v1", "documents": documents}
