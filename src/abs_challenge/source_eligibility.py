"""盤點 feed 的資格線索；不從事件缺席推定 ABS 全場可用。"""

from __future__ import annotations

SOURCE_ELIGIBILITY_VERSION = "abs-source-eligibility-evidence-v1"


def candidate_source_status() -> dict[str, str]:
    """在沒有完整停用區間／replay 時序來源前，逐球資格維持未知。"""
    return {"source_eligibility_version": SOURCE_ELIGIBILITY_VERSION,
            "abs_technical_availability": "unknown",
            "post_replay_challenge_eligibility": "unknown"}


def inspect_source_signals(feed: dict) -> dict:
    """只記錄非 ABS review 與文字線索；線索本身不能作排除區間。"""
    hints = []
    abs_reviews = 0
    for play in feed["liveData"]["plays"]["allPlays"]:
        pa = play["atBatIndex"] + 1
        for event in play["playEvents"]:
            review = event.get("reviewDetails") or {}
            review_type = review.get("reviewType")
            if review_type == "MJ":
                abs_reviews += 1
            elif review_type:
                hints.append({"at_bat_number": pa, "feed_event_index": event["index"],
                              "signal_type": "non_abs_review_type", "value": str(review_type)})
            if event.get("type") != "action":
                continue
            details = event.get("details") or {}
            description = str(details.get("description") or "")
            event_type = str(details.get("eventType") or "")
            searchable = f"{description} {event_type}".lower()
            for signal, words in (("replay_text_hint", ("replay",)),
                                  ("technical_text_hint", ("technical", "outage", "unavailable"))):
                if any(word in searchable for word in words):
                    hints.append({"at_bat_number": pa, "feed_event_index": event["index"],
                                  "signal_type": signal, "value": description or event_type})
    return {"schema_version": SOURCE_ELIGIBILITY_VERSION,
            "abs_review_events": abs_reviews, "hints": hints,
            "technical_interval_coverage": "unknown",
            "post_replay_ordering_coverage": "unknown",
            "absence_of_hints_proves_eligibility": False}


def summarize_source_audits(games: list[dict]) -> dict:
    """來源失敗亦留在選定場次分母；沒有線索不代表資格完整。"""
    audits = [game["eligibility_source_audit"] for game in games if "eligibility_source_audit" in game]
    return {"selected_games": len(games), "games_with_feed_audit": len(audits),
            "games_without_feed_audit": len(games) - len(audits),
            "abs_review_events": sum(audit["abs_review_events"] for audit in audits),
            "hint_events": sum(len(audit["hints"]) for audit in audits),
            "technical_interval_coverage": "unknown",
            "post_replay_ordering_coverage": "unknown",
            "complete_eligibility_evidence": False}
