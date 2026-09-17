"""固定官方 RE288／含球數 WP 快照，並以同一來源估值兩種判決。"""

from __future__ import annotations

from hashlib import sha256
from itertools import product
import json
import math
import re
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .provenance import build_download_manifest
from .state_value import CallTransition, GameState, checked_int, counterfactual_states


EXPLORER_URL = "https://baseballsavant.mlb.com/game-strategy-explorer"
SNAPSHOT_VERSION = "savant-baseline-v2"
BOUNDARY_VERSION = "savant-regulation-tie-home-v1"


def finite_number(value: Any, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} 必須是有限數值")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"{name} 超出範圍 {minimum}–{maximum}")
    return number


def _fetch_text(url: str, *, accept: str) -> str:
    # 官方頁面拒絕 urllib 預設識別；不帶認證或私有資訊。
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 ABS-research/0.1", "Accept": accept})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _query_url(kind: str, params: dict[str, Any]) -> str:
    return EXPLORER_URL + "?" + urlencode({"type": kind, "params": json.dumps(params, sort_keys=True)})


def download_baseline_bundle() -> dict[str, Any]:
    """下載一次官方原始回應組；後續轉換可完全離線重播。"""
    documents: dict[str, Any] = {}

    def fetch(name: str, url: str, accept: str) -> str:
        content = _fetch_text(url, accept=accept)
        row_count = len(json.loads(content)) if accept == "application/json" else 1
        documents[name] = {
            "content": content,
            "manifest": build_download_manifest(source_type=f"savant_explorer_{name}",
                source_url=url, content=content, row_count=row_count),
        }
        return content

    page = fetch("page", EXPLORER_URL, "text/html")
    matches = re.findall(r'<script[^>]+src="([^"]+/game-strategy-explorer\.js)"', page)
    if len(matches) != 1 or urlsplit(matches[0]).hostname != "builds.mlbstatic.com":
        raise ValueError("官方頁面程式來源已改變，需重新核對 adapter")
    fetch("script", matches[0], "text/javascript")
    fetch("re288", _query_url("runexp-count", {"balls": None, "strikes": None}), "application/json")
    for bases in range(8):
        fetch(f"wp_{bases}", _query_url("winexp", {
            "perspective": "bat", "is_by_count": True,
            "runners": {name: bool(bases & (1 << bit)) for bit, name in enumerate(("1b", "2b", "3b"))},
        }), "application/json")
    return {"schema_version": "savant-explorer-bundle-v1", "documents": documents}


def build_baseline_snapshot(bundle: dict[str, Any]) -> dict[str, Any]:
    """驗證原始 hash、來源語意與完整度後正規化；不估計或插補任何值。"""
    if bundle.get("schema_version") != "savant-explorer-bundle-v1":
        raise ValueError("不支援的官方原始快照版本")
    documents = bundle["documents"]
    required = {"page", "script", "re288", *(f"wp_{i}" for i in range(8))}
    if set(documents) != required:
        raise ValueError("官方快照缺少或多出必要來源")
    for name, document in documents.items():
        content, manifest = document["content"], document["manifest"]
        encoded = content.encode("utf-8")
        if sha256(encoded).hexdigest() != manifest["content_sha256"] or len(encoded) != manifest["byte_length"]:
            raise ValueError(f"原始快照 hash 不一致：{name}")
        if not manifest.get("retrieved_at_utc"):
            raise ValueError("原始來源缺少擷取時間")

    page = documents["page"]["content"]
    if documents["page"]["manifest"]["source_url"] != EXPLORER_URL:
        raise ValueError("方法說明不是預期的官方頁面")
    if urlsplit(documents["script"]["manifest"]["source_url"]).hostname != "builds.mlbstatic.com":
        raise ValueError("Adapter 程式不是預期的官方來源")
    periods = set(re.findall(r"10 seasons between (\d{4})-(\d{4})", page))
    if len(periods) != 1:
        raise ValueError("無法唯一確認官方頁面的資料年份宣告")
    period = [int(year) for year in periods.pop()]
    re_source = documents["re288"]
    if re_source["manifest"]["source_url"] != _query_url("runexp-count", {"balls": None, "strikes": None}):
        raise ValueError("RE288 查詢參數不符合 adapter")
    re_rows = []
    years = set()
    raw_re_rows = json.loads(re_source["content"])
    if re_source["manifest"]["row_count"] != len(raw_re_rows):
        raise ValueError("RE288 manifest 列數不一致")
    for row in raw_re_rows:
        years.add(checked_int(row["year"], "source_year", 1900, 2100))
        checked_int(row["n"], "source_n", 0, 1000000000)
        re_rows.append({"bases": row["runners_on_cd"], "outs": row["outs"],
            "balls": row["ball_count"], "strikes": row["strike_count"],
            "run_expectancy": row["run_expectancy"], "source_n": row["n"]})

    wp_rows, boundary = [], None
    for bases in range(8):
        document = documents[f"wp_{bases}"]
        expected_urls = {_query_url("winexp", {
            "perspective": perspective, "is_by_count": True,
            "runners": {name: bool(bases & (1 << bit)) for bit, name in enumerate(("1b", "2b", "3b"))},
        }) for perspective in ("home", "bat")}
        if document["manifest"]["source_url"] not in expected_urls:
            raise ValueError("WP 查詢視角或篩選不符合 adapter")
        rows = json.loads(document["content"])
        if document["manifest"]["row_count"] != len(rows):
            raise ValueError("WP manifest 列數不一致")
        for row in rows:
            if row["bases_cd"] != bases:
                raise ValueError("WP 回應壘包與查詢不符")
            inning = checked_int(row["inning"], "inning", 1, 10)
            half = {"Top": "top", "Bottom": "bottom"}.get(row["bottom_top"])
            normalized = {"inning": inning, "half": half, "outs": row["outs"], "bases": bases,
                "balls": row["ball_count"], "strikes": row["strike_count"],
                "home_win_probabilities": [row[f"bat_wins_minus_{-diff}" if diff < 0 else f"bat_wins_{diff}"]
                                           for diff in range(-5, 6)]}
            if half == "top":
                # 原始 bat_wins 同時使用打方分差與打方勝率；兩個維度都必須轉換。
                # 不能相信請求 perspective=home 就已轉換；見 ADR-0001。
                normalized["home_win_probabilities"] = [
                    1 - finite_number(value, "source_batting_wp", 0, 1)
                    for value in reversed(normalized["home_win_probabilities"])
                ]
            if inning <= 9:
                wp_rows.append(normalized)
            elif (half, row["outs"], bases, row["ball_count"], row["strike_count"]) == ("top", 0, 2, 0, 0):
                if boundary is not None:
                    raise ValueError("九局平手邊界來源重複")
                boundary = normalized["home_win_probabilities"][5]
    snapshot = {
        "schema_version": SNAPSHOT_VERSION,
        "purpose": "external_prototype_not_out_of_sample_research",
        "source_url": EXPLORER_URL,
        "source_page_seasons": period,
        "re_response_years": sorted(years),
        "source_window_caveat": "頁面年份與 RE 列 year 分別保留；不推定底層估計窗口一致。",
        "wp_perspective": "home",
        "source_wp_perspective": "batting",
        "perspective_conversion": "top_reverse_score_and_complement_probability_bottom_identity",
        "home_score_diff_range": [-5, 5],
        "innings": [1, 9],
        "regulation_boundary": {
            "version": BOUNDARY_VERSION, "home_win_probability": boundary,
            "source_document": "wp_2",
            "source_state": {"inning": 10, "half": "top", "outs": 0, "bases": 2,
                             "balls": 0, "strikes": 0, "home_score_diff": 0},
            "extra_inning_policy_modeled": False,
        },
        "source_manifests": {name: doc["manifest"] for name, doc in documents.items()},
        "re288": sorted(re_rows, key=lambda row: (row["bases"], row["outs"], row["balls"], row["strikes"])),
        "wp": sorted(wp_rows, key=lambda row: (row["inning"], row["half"], row["outs"], row["bases"], row["balls"], row["strikes"])),
    }
    SavantBaseline(snapshot)
    return snapshot


class MissingBaselineState(ValueError):
    """固定來源沒有該狀態；不能擅自截尾或以實際路徑補值。"""


class SavantBaseline:
    """公開估值介面：完整且固定的官方表格，主隊與決策方視角分離。"""

    def __init__(self, snapshot: dict[str, Any]) -> None:
        if snapshot.get("schema_version") != SNAPSHOT_VERSION or snapshot.get("wp_perspective") != "home":
            raise ValueError("不支援的 WP 快照版本或視角")
        if snapshot.get("home_score_diff_range") != [-5, 5] or snapshot.get("innings") != [1, 9]:
            raise ValueError("不支援的 WP 覆蓋範圍")
        self.snapshot = snapshot
        boundary = snapshot["regulation_boundary"]
        if boundary["version"] != BOUNDARY_VERSION or boundary["extra_inning_policy_modeled"] is not False:
            raise ValueError("九局平手邊界版本不符")
        self.boundary = finite_number(boundary["home_win_probability"], "regulation_boundary", 0, 1)
        self._re: dict[tuple[int, ...], float] = {}
        self._wp: dict[tuple[Any, ...], tuple[float, ...]] = {}
        for row in snapshot["re288"]:
            key = tuple(checked_int(row[name], name, 0, maximum)
                        for name, maximum in (("bases", 7), ("outs", 2), ("balls", 3), ("strikes", 2)))
            if key in self._re:
                raise ValueError("RE288 狀態重複")
            self._re[key] = finite_number(row["run_expectancy"], "run_expectancy", 0, 100)
        if set(self._re) != set(product(range(8), range(3), range(4), range(3))):
            raise ValueError("RE288 必須完整涵蓋 288 個狀態")
        for row in snapshot["wp"]:
            inning = checked_int(row["inning"], "inning", 1, 9)
            if row["half"] not in {"top", "bottom"}:
                raise ValueError("WP 半局無效")
            key = (inning, row["half"], *(checked_int(row[name], name, 0, maximum)
                for name, maximum in (("outs", 2), ("bases", 7), ("balls", 3), ("strikes", 2))))
            values = row["home_win_probabilities"]
            if len(values) != 11 or key in self._wp:
                raise ValueError("WP 分差欄位不足或狀態重複")
            self._wp[key] = tuple(finite_number(value, "home_wp", 0, 1) for value in values)
        expected = set(product(range(1, 10), ("top", "bottom"), range(3), range(8), range(4), range(3)))
        if set(self._wp) != expected:
            raise ValueError("含球數 WP 未完整涵蓋 5,184 個 regulation 狀態")

    def home_wp(self, state: GameState) -> float:
        diff = state.home_score - state.away_score
        if not -5 <= diff <= 5:
            raise MissingBaselineState(f"主隊分差 {diff} 超出官方表格 ±5；未截尾")
        return self._wp[(state.inning, state.half, state.outs, state.bases, state.balls, state.strikes)][diff + 5]

    def run_expectancy(self, bases: int, outs: int, balls: int, strikes: int) -> float:
        for value, name, maximum in ((bases, "bases", 7), (outs, "outs", 2), (balls, "balls", 3), (strikes, "strikes", 2)):
            checked_int(value, name, 0, maximum)
        return self._re[(bases, outs, balls, strikes)]

    def transition_home_wp(self, transition: CallTransition) -> float:
        if transition.terminal == "home_win":
            return 1.0
        if transition.terminal == "away_win":
            return 0.0
        if transition.terminal == "regulation_tie":
            return self.boundary
        if transition.next_state is None:
            raise ValueError("非終局轉移缺少下一個狀態")
        return self.home_wp(transition.next_state)

    def transition_re(self, transition: CallTransition) -> float:
        """原半局得分價值；不把換邊後對手 RE 加入，不依再見截斷表格。"""
        if transition.half_ended:
            return float(transition.runs_scored)
        return transition.runs_scored + self.run_expectancy(
            transition.re_bases, transition.re_outs, transition.re_balls, transition.re_strikes)

    def value_call(self, state: GameState, original_call: str) -> dict[str, Any]:
        stands, overturned = counterfactual_states(state, original_call)
        batting_home = state.half == "bottom"
        decision_home = batting_home if original_call == "strike" else not batting_home
        home0, home1 = self.transition_home_wp(stands), self.transition_home_wp(overturned)
        team0, team1 = (home0, home1) if decision_home else (1 - home0, 1 - home1)
        re0, re1 = self.transition_re(stands), self.transition_re(overturned)
        run_value = (re1 - re0) * (1 if original_call == "strike" else -1)
        return {
            "decision_side": "batting" if original_call == "strike" else "fielding",
            "decision_home_away": "home" if decision_home else "away",
            "s0": stands.to_dict(), "s1": overturned.to_dict(),
            "wp_home_stands": home0, "wp_home_overturned": home1,
            "wp_decision_stands": team0, "wp_decision_overturned": team1,
            "delta_wp_decision": team1 - team0,
            "delta_wp_percentage_points": 100 * (team1 - team0),
            "re_stands": re0, "re_overturned": re1, "run_value_decision": run_value,
            "savant_static_threshold": 0.2 / (0.2 + run_value) if run_value > 0 else None,
            "re_convention": "uncensored_current_half_inning_including_immediate_runs",
            "regulation_boundary_used": "regulation_tie" in {stands.terminal, overturned.terminal},
            "warnings": ["官方查表出現負向翻判價值，需檢查來源平滑與狀態；未截成零"] if team1 < team0 or run_value < 0 else [],
        }
