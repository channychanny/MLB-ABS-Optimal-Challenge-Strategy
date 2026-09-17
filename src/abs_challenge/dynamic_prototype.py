"""只驗證流程的有限情境樹；不是由歷史資料訓練的 ABS policy。"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .baseline import SavantBaseline, finite_number
from .state_value import GameState, checked_int


@dataclass(frozen=True)
class ValueLeaf:
    decision_win_probability: float

    def __post_init__(self) -> None:
        finite_number(self.decision_win_probability, "decision_win_probability", 0, 1)


@dataclass(frozen=True)
class ChallengeNode:
    """成功／原判分支必須分開提供；同一決策球隊及固定不挑戰的對手。"""

    overturn_probability: float
    stands: ValueLeaf | ChallengeNode
    overturned: ValueLeaf | ChallengeNode

    def __post_init__(self) -> None:
        finite_number(self.overturn_probability, "overturn_probability", 0, 1)
        if not isinstance(self.stands, (ValueLeaf, ChallengeNode)) or not isinstance(self.overturned, (ValueLeaf, ChallengeNode)):
            raise ValueError("情境分支必須是葉節點或挑戰節點")


def solve_scenario(root: ValueLeaf | ChallengeNode, challenges_remaining: int) -> dict[str, Any]:
    """精確向後求值；成功保留、失敗扣一，零額度只能維持原判。"""
    checked_int(challenges_remaining, "challenges_remaining", 0, 2)
    if not isinstance(root, (ValueLeaf, ChallengeNode)):
        raise ValueError("情境根節點類型不支援")

    @lru_cache(maxsize=None)
    def value(node: ValueLeaf | ChallengeNode, budget: int) -> float:
        if isinstance(node, ValueLeaf):
            return node.decision_win_probability
        save = value(node.stands, budget)
        if budget == 0:
            return save
        challenge = node.overturn_probability * value(node.overturned, budget) + (1 - node.overturn_probability) * value(node.stands, budget - 1)
        return max(save, challenge)

    if isinstance(root, ValueLeaf):
        save, challenge, action = value(root, challenges_remaining), None, "terminal"
    else:
        save = value(root.stands, challenges_remaining)
        challenge = None if challenges_remaining == 0 else (
            root.overturn_probability * value(root.overturned, challenges_remaining)
            + (1 - root.overturn_probability) * value(root.stands, challenges_remaining - 1))
        action = "challenge" if challenge is not None and challenge > save else "save"
    return {"challenges_remaining": challenges_remaining, "q_save": save, "q_challenge": challenge,
            "value": value(root, challenges_remaining), "action": action}


def build_dynamic_demo(baseline: SavantBaseline) -> dict[str, Any]:
    """九下合成兩機會情境；未來分支及可靠度是假設，絕非實際比賽未來資訊。"""
    # 同一主隊、同一打席：目前 2–2 的好球可結束打席，翻判則變為 3–2。
    # 原判保留且未出局後，假設下一打席首球也是可挑戰機會。
    current_state = GameState(9, "bottom", 0, 0, 2, 2, 0, 0)
    current = baseline.value_call(current_state, "strike")
    after_stands = GameState(9, "bottom", 1, 0, 0, 0, 0, 0)
    after_overturned = GameState(9, "bottom", 0, 0, 3, 2, 0, 0)
    future_stands = baseline.value_call(after_stands, "strike")
    future_overturned = baseline.value_call(after_overturned, "strike")
    stands_node = ChallengeNode(0.6, ValueLeaf(future_stands["wp_decision_stands"]), ValueLeaf(future_stands["wp_decision_overturned"]))
    overturned_node = ChallengeNode(0.6, ValueLeaf(future_overturned["wp_decision_stands"]), ValueLeaf(future_overturned["wp_decision_overturned"]))
    root = ChallengeNode(0.6, stands_node, overturned_node)
    return {
        "schema_version": "phase1-dynamic-demo-v1",
        "purpose": "synthetic_scenario_not_policy_evaluation",
        "formal_policy_evaluation_ready": False,
        "assumptions": {
            "decision_team": "home", "opponent_policy": "never_challenge",
            "initial_challenges": 2, "successful_challenge_retained": True,
            "overturn_probability": 0.6, "probability_source": "assumed_not_fitted",
            "future_opportunities": "每個分支假設下一球為 called strike 機會，之後不再挑戰",
            "leaf_source": "同一 Savant snapshot；省略的比賽過程以外部 WP 承接",
            "extra_inning_policy_modeled": False,
        },
        "current_state": current_state.to_dict(), "current_valuation": current,
        "future_stands_valuation": future_stands, "future_overturned_valuation": future_overturned,
        "results": [solve_scenario(root, budget) for budget in range(3)],
        "limitations": ["僅驗證 Bellman 分支與額度轉移，不估計真實 Future Opportunity。",
                        "未校準球員信心，不產生正式 RRA，不是實際比賽回測。"],
    }
