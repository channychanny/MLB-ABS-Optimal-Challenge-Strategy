"""第 1–9 局純好壞球判決的狀態重建；不推定額外跑壘結果。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any


def checked_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    """拒絕缺失、布林及被靜默截斷的小數。"""
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} 必須是 {minimum}–{maximum} 的整數")
    return value


@dataclass(frozen=True)
class GameState:
    """打席尚未結束的狀態；比分固定為主隊／客隊視角。"""

    inning: int
    half: str
    outs: int
    bases: int
    balls: int
    strikes: int
    home_score: int
    away_score: int

    def __post_init__(self) -> None:
        for name, minimum, maximum in (
            ("inning", 1, 9), ("outs", 0, 2), ("bases", 0, 7),
            ("balls", 0, 3), ("strikes", 0, 2),
            ("home_score", 0, 1000), ("away_score", 0, 1000),
        ):
            checked_int(getattr(self, name), name, minimum, maximum)
        if self.half not in {"top", "bottom"}:
            raise ValueError("half 必須是 top 或 bottom")
        if self.inning == 9 and self.half == "bottom" and self.home_score > self.away_score:
            raise ValueError("主隊已領先時不存在繼續進行的九局下打席")

    @classmethod
    def from_statcast(cls, row: dict[str, Any]) -> GameState:
        required = ("inning", "inning_topbot", "outs_when_up", "balls", "strikes",
                    "home_score", "away_score", "on_1b", "on_2b", "on_3b")
        if any(key not in row for key in required):
            raise ValueError("判決前狀態缺少必要欄位；壘包缺欄不能當作無人")
        half = {"Top": "top", "Bot": "bottom", "Bottom": "bottom"}.get(row["inning_topbot"])
        bases = 0
        for bit, name in enumerate(("on_1b", "on_2b", "on_3b")):
            value = row[name]
            if value is None or value == "":
                continue
            if isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
                raise ValueError(f"{name} 不是有效跑者 ID")
            bases |= 1 << bit
        return cls(row["inning"], half, row["outs_when_up"], bases, row["balls"],
                   row["strikes"], row["home_score"], row["away_score"])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CallTransition:
    """判決後的下一狀態，以及原半局 RE 所需的狀態。"""

    next_state: GameState | None
    terminal: str | None
    runs_scored: int
    half_ended: bool
    re_bases: int
    re_outs: int
    re_balls: int
    re_strikes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def apply_call(state: GameState, call: str) -> CallTransition:
    """只套用 called ball／strike；第三好球假定打者出局且無額外跑壘。"""
    if call not in {"ball", "strike"}:
        raise ValueError("只支援 ball／strike 判決")
    balls, strikes, outs, bases = state.balls, state.strikes, state.outs, state.bases
    runs = 0
    if call == "ball":
        if balls < 3:
            balls += 1
        else:
            # 只有連續被迫的跑者進壘；二／三壘單獨有人時不可全部右移。
            runs = int(bases == 7)
            bases = bases | 1 | (2 if bases & 1 else 0) | (4 if bases & 3 == 3 else 0)
            balls, strikes = 0, 0
    elif strikes < 2:
        strikes += 1
    else:
        outs += 1
        balls, strikes = 0, 0

    home_score = state.home_score + (runs if state.half == "bottom" else 0)
    away_score = state.away_score + (runs if state.half == "top" else 0)
    terminal = None
    next_state = None
    half_ended = outs == 3
    if state.inning == 9 and state.half == "bottom" and home_score > away_score:
        terminal = "home_win"
    elif half_ended and state.inning == 9 and state.half == "bottom":
        terminal = "away_win" if away_score > home_score else "regulation_tie"
    elif half_ended and state.inning == 9 and state.half == "top" and home_score > away_score:
        terminal = "home_win"
    elif half_ended:
        next_state = GameState(
            state.inning + int(state.half == "bottom"),
            "bottom" if state.half == "top" else "top", 0, 0, 0, 0,
            home_score, away_score,
        )
    else:
        next_state = replace(state, outs=outs, bases=bases, balls=balls, strikes=strikes,
                             home_score=home_score, away_score=away_score)
    return CallTransition(next_state, terminal, runs, half_ended, bases, outs, balls, strikes)


def counterfactual_states(state: GameState, original_call: str) -> tuple[CallTransition, CallTransition]:
    """回傳 S0 原判維持與 S1 翻轉原判；與實際有沒有翻判無關。"""
    stands = apply_call(state, original_call)
    overturn = apply_call(state, "strike" if original_call == "ball" else "ball")
    return stands, overturn
