"""本機瀏覽器介面：官方 WP／RE 與明示假設的額度成本敏感度。"""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import webbrowser

from .baseline import SavantBaseline
from .state_value import GameState
from .win_decision import ROOT, _number, required_success_probability, validate_protocol
from .wp_coverage import inspect_call


ASSETS = Path(__file__).resolve().parent


def evaluate_request(snapshot: dict, protocol: dict, payload: dict) -> dict:
    """只讀判決前輸入；未驗證的未來額度模型不進即時介面。"""
    validate_protocol(protocol)
    if (not isinstance(payload, dict)
            or set(payload) != {"pre_pitch_state", "original_call", "challenges_remaining",
                                "custom_failure_cost_pp", "assume_pure_called_pitch"}
            or payload["assume_pure_called_pitch"] is not True):
        raise ValueError("請確認此球是純好壞球判決，並填齊表單")
    if not isinstance(payload["pre_pitch_state"], dict):
        raise ValueError("比賽狀態格式無效")
    state = GameState(**payload["pre_pitch_state"])
    if not 1 <= state.inning <= 9:
        raise ValueError("本研究介面只接受第 1–9 局")
    call = payload["original_call"]
    if call not in ("ball", "strike"):
        raise ValueError("原判只接受好球或壞球")
    budget = payload["challenges_remaining"]
    if type(budget) is not int or budget not in (1, 2):
        raise ValueError("剩餘挑戰次數只能是 1 或 2")
    custom_pp = payload["custom_failure_cost_pp"]
    if custom_pp is not None:
        custom_pp = _number(custom_pp, "自訂失敗額度成本（百分點）", 0, 100)
    valuation = inspect_call(SavantBaseline(snapshot), state, call)
    s0, s1 = valuation["s0"], valuation["s1"]
    re0, re1 = s0["re"], s1["re"]
    delta_re_decision = (re1 - re0 if valuation["decision_side"] == "batting"
                         else re0 - re1)
    supported = (isinstance(s0, dict) and isinstance(s1, dict)
                 and s0.get("supported") is True and s1.get("supported") is True)
    base = {"schema_version": "phase3-browser-sensitivity-v3",
            "status": "supported" if supported else "unsupported",
            "decision_side": valuation["decision_side"],
            "s0": {name: s0.get(name) if s0 else None for name in (
                "wp_decision", "re", "terminal", "missing_reason_code")},
            "s1": {name: s1.get(name) if s1 else None for name in (
                "wp_decision", "re", "terminal", "missing_reason_code")},
            "re_s0": re0, "re_s1": re1,
            "delta_re_decision": delta_re_decision,
            "re_unit": "expected_runs_current_half_inning",
            "formal_policy_evaluation_ready": False}
    if not supported:
        return base | {"reason": "官方 WP 至少一側無法估值；不輸出勝率門檻"}
    wp0, wp1 = s0["wp_decision"], s1["wp_decision"]
    delta = wp1 - wp0
    terminal = s0["terminal"] is not None
    scenarios = []
    for scenario in protocol["cost_scenarios"]:
        cost = 0.0 if terminal else scenario["failure_cost_by_budget"][str(budget)]
        scenarios.append({"id": scenario["id"], "assumed_failure_cost_wp": cost,
                          "threshold": required_success_probability(delta, cost)})
    low, high = scenarios[1:]
    threshold_range = ({
        "lower": low["threshold"]["conditional_break_even_probability"],
        "upper": high["threshold"]["conditional_break_even_probability"],
        "assumed_cost_lower_wp": low["assumed_failure_cost_wp"],
        "assumed_cost_upper_wp": high["assumed_failure_cost_wp"],
        "not_confidence_interval": True,
    } if delta > 1e-12 else None)
    response = base | {
        "wp_s0": wp0, "wp_s1": wp1,
        "delta_wp_if_overturned": delta,
        "illustrative_cost_source": "declared_not_estimated",
        "illustrative_cost_scenarios": scenarios,
        "illustrative_threshold_range": threshold_range,
        "custom_cost_threshold": (required_success_probability(
            delta, 0 if terminal else custom_pp / 100)
            if custom_pp is not None else None),
        "custom_cost_pp": custom_pp,
        "warning": "成本情境只是事先宣告的假設，不是估計值或統計信賴區間；不輸出單一最優挑戰建議。",
    }
    return response


def make_handler(snapshot: dict, protocol: dict):
    assets = {"/": ("web_ui.html", "text/html; charset=utf-8"),
              "/web_ui.css": ("web_ui.css", "text/css; charset=utf-8"),
              "/web_ui.js": ("web_ui.js", "text/javascript; charset=utf-8")}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            asset = assets.get(self.path)
            if asset is None:
                self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
                return
            self._send(HTTPStatus.OK, (ASSETS / asset[0]).read_bytes(), asset[1])

        def do_POST(self) -> None:
            if self.path != "/api/evaluate":
                self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if (self.headers.get("Content-Type", "").split(";")[0] != "application/json"
                        or not 0 < length <= 16384):
                    raise ValueError("請傳送有效的 JSON 表單，且資料不得超過 16 KB")
                payload = json.loads(self.rfile.read(length))
                result = evaluate_request(snapshot, protocol, payload)
                status = HTTPStatus.OK
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                result = {"status": "error", "message": str(exc)}
                status = HTTPStatus.BAD_REQUEST
            body = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--official-baseline", type=Path,
                        default=ROOT / "data/processed/savant_baseline_v2_2026-09-15.json")
    parser.add_argument("--win-protocol", type=Path,
                        default=ROOT / "config/phase3_win_decision_protocol.json")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise ValueError("連接埠需介於 1–65535")
    snapshot = json.loads(args.official_baseline.read_text(encoding="utf-8"))
    protocol = json.loads(args.win_protocol.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    SavantBaseline(snapshot)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(snapshot, protocol))
    url = f"http://127.0.0.1:{args.port}/"
    print(f"ABS 勝率決策介面：{url}（按 Ctrl+C 停止）", flush=True)
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
