"""合成有限視野的跨界契約測試；不估計真實未來機會或正式策略。"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .baseline import BOUNDARY_VERSION, SavantBaseline, finite_number
from .state_value import checked_int


@dataclass(frozen=True)
class BoundedLeaf:
    lower: float
    upper: float
    assumption: str = "synthetic_fixed"

    def __post_init__(self) -> None:
        lower = finite_number(self.lower, "lower", 0, 1)
        upper = finite_number(self.upper, "upper", 0, 1)
        if lower > upper or (lower != upper and self.assumption == "synthetic_fixed"):
            raise ValueError("未知延續必須有有效區間與明示假設")
        if not isinstance(self.assumption, str) or not self.assumption.strip():
            raise ValueError("延續假設不得為空")


@dataclass(frozen=True)
class StateStep:
    """明示路徑上的真實主隊分差；表外中繼狀態不可直接查表。"""

    home_score_diff: int
    next_node: BoundedLeaf | StateStep | ChanceNode | ChallengeDecision

    def __post_init__(self) -> None:
        if type(self.home_score_diff) is not int:
            raise ValueError("主隊分差必須為整數")
        _check_node(self.next_node)


@dataclass(frozen=True)
class ChanceNode:
    branches: tuple[tuple[float, BoundedLeaf | StateStep | ChanceNode | ChallengeDecision], ...]

    def __post_init__(self) -> None:
        if not self.branches:
            raise ValueError("機率分支不得為空")
        total = 0.0
        for probability, node in self.branches:
            total += finite_number(probability, "branch_probability", 0, 1)
            _check_node(node)
        if abs(total - 1) > 1e-12:
            raise ValueError("機率分支總和必須為一")


@dataclass(frozen=True)
class ChallengeDecision:
    overturn_probability: float
    stands: BoundedLeaf | StateStep | ChanceNode | ChallengeDecision
    overturned: BoundedLeaf | StateStep | ChanceNode | ChallengeDecision

    def __post_init__(self) -> None:
        finite_number(self.overturn_probability, "overturn_probability", 0, 1)
        _check_node(self.stands)
        _check_node(self.overturned)


def _check_node(node: Any) -> None:
    if not isinstance(node, (BoundedLeaf, StateStep, ChanceNode, ChallengeDecision)):
        raise ValueError("分支節點類型不支援")


def terminal_leaf(outcome: str, baseline: SavantBaseline, *, decision_home: bool) -> BoundedLeaf:
    """合成樹須明示勝負終局；平手只取版本化 regulation boundary。"""
    if type(decision_home) is not bool:
        raise ValueError("決策方主客視角必須明確")
    home_probability = {"home_win": 1.0, "away_win": 0.0,
                        "regulation_tie": baseline.boundary}.get(outcome)
    if home_probability is None:
        raise ValueError("終局結果不支援")
    probability = home_probability if decision_home else 1 - home_probability
    version = f":{BOUNDARY_VERSION}" if outcome == "regulation_tie" else ""
    return BoundedLeaf(probability, probability,
                       f"known_terminal:{outcome}{version}:decision_home={decision_home}")


def regulation_tie_leaf(baseline: SavantBaseline, *, decision_home: bool) -> BoundedLeaf:
    return terminal_leaf("regulation_tie", baseline, decision_home=decision_home)


@dataclass(frozen=True)
class _Envelope:
    value: tuple[float, float]
    outside: tuple[float, float]
    reentry: tuple[float, float]
    unresolved: tuple[float, float]


def _mix(branches: tuple[tuple[float, _Envelope], ...]) -> _Envelope:
    return _Envelope(*(tuple(sum(probability * getattr(result, field)[side]
                                  for probability, result in branches) for side in (0, 1))
                       for field in ("value", "outside", "reentry", "unresolved")))


def _choice(save: _Envelope, challenge: _Envelope) -> _Envelope:
    return _Envelope((max(save.value[0], challenge.value[0]), max(save.value[1], challenge.value[1])),
                     *(tuple((min(getattr(save, field)[0], getattr(challenge, field)[0]),
                               max(getattr(save, field)[1], getattr(challenge, field)[1])))
                       for field in ("outside", "reentry", "unresolved")))


def _action(save: _Envelope, challenge: _Envelope | None) -> str:
    if challenge is None or save.value[0] >= challenge.value[1]:
        return "save"
    if challenge.value[0] > save.value[1]:
        return "challenge"
    return "undetermined"


def _as_dict(result: _Envelope) -> dict[str, list[float]]:
    return {"value_interval": list(result.value), "outside_mass_interval": list(result.outside),
            "reentry_mass_interval": list(result.reentry),
            "unresolved_mass_interval": list(result.unresolved)}


def solve_finite_horizon(root: BoundedLeaf | StateStep | ChanceNode | ChallengeDecision,
                         challenges_remaining: int) -> dict[str, Any]:
    """人工有限樹的保守區間；不將表外狀態截尾或當成 0／1。"""
    checked_int(challenges_remaining, "challenges_remaining", 0, 2)
    _check_node(root)

    @lru_cache(maxsize=None)
    def evaluate(node: BoundedLeaf | StateStep | ChanceNode | ChallengeDecision,
                 budget: int, seen_outside: bool, reentered: bool,
                 current_outside: bool) -> _Envelope:
        if isinstance(node, BoundedLeaf):
            if (current_outside and node.lower == node.upper
                    and not node.assumption.startswith("known_terminal:")):
                raise ValueError("表外終點不可直接指定固定勝率")
            return _Envelope((node.lower, node.upper),
                             (float(seen_outside),) * 2, (float(reentered),) * 2,
                             (float(node.lower != node.upper),) * 2)
        if isinstance(node, StateStep):
            outside = not -5 <= node.home_score_diff <= 5
            return evaluate(node.next_node, budget, seen_outside or outside,
                            reentered or (seen_outside and not outside), outside)
        if isinstance(node, ChanceNode):
            return _mix(tuple((probability, evaluate(child, budget, seen_outside, reentered, current_outside))
                              for probability, child in node.branches))
        save = evaluate(node.stands, budget, seen_outside, reentered, current_outside)
        if budget == 0:
            return save
        challenge = _mix(((node.overturn_probability,
                           evaluate(node.overturned, budget, seen_outside, reentered, current_outside)),
                          (1 - node.overturn_probability,
                           evaluate(node.stands, budget - 1, seen_outside, reentered, current_outside))))
        action = _action(save, challenge)
        return save if action == "save" else challenge if action == "challenge" else _choice(save, challenge)

    if isinstance(root, ChallengeDecision):
        save = evaluate(root.stands, challenges_remaining, False, False, False)
        challenge = None if challenges_remaining == 0 else _mix((
            (root.overturn_probability, evaluate(root.overturned, challenges_remaining, False, False, False)),
            (1 - root.overturn_probability, evaluate(root.stands, challenges_remaining - 1, False, False, False))))
        action = _action(save, challenge)
        result = save if action == "save" else challenge if action == "challenge" else _choice(save, challenge)
    else:
        save = challenge = None
        action = "no_decision"
        result = evaluate(root, challenges_remaining, False, False, False)
    return {"schema_version": "finite-horizon-continuation-contract-v1",
            "purpose": "synthetic_contract_not_policy_evaluation",
            "formal_policy_evaluation_ready": False, "extra_inning_policy_modeled": False,
            "challenges_remaining": challenges_remaining, "action": action,
            "q_save": _as_dict(save) if save else None,
            "q_challenge": _as_dict(challenge) if challenge else None,
            **_as_dict(result)}
