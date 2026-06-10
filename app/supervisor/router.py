"""Supervisor intent router: classifies user intent and dispatches to Worker flows.

Routes user queries into one of 4 intent flows:
- exchange: 3 parallel Workers (policy + inventory + logistics)
- refund: serial flow (policy check -> calculate -> ticket)
- complaint: emotion-graded (angry -> urgent ticket, neutral -> compensation)
- tracking: direct shipment lookup
"""
from __future__ import annotations
import json
import logging
from typing import Any

from app.agent_graph.state import TicketAgentState

logger = logging.getLogger(__name__)


def detect_emotion(query: str) -> str:
    """Inline emotion detection: angry keywords or exclamation intensity."""
    angry_keywords = ["垃圾", "骗子", "投诉你", "差评", "举报", "气死", "退款", "!!!"]
    query_lower = query.lower()
    for kw in angry_keywords:
        if kw in query_lower:
            return "angry"
    if query.count("!") + query.count("！") >= 2:
        return "angry"
    return "neutral"


def route_intent(state: TicketAgentState) -> dict[str, Any]:
    """Supervisor node: classify intent using domain_router + detect emotion."""
    query = (state.get("user_query") or "").strip()

    # Use domain_router for domain classification
    from app.config import get_settings
    from app.domain_router import route_domains

    settings = get_settings()
    router_result = route_domains(query, settings)
    domain = router_result.primary_domain or "refund"

    # Map domain_router domain to intent
    domain_to_intent = {
        "exchange": "exchange",
        "refund": "refund",
        "return_policy": "refund",
        "complaint": "complaint",
        "shipping": "tracking",
    }
    intent = domain_to_intent.get(domain, "refund")

    # Detect emotion for complaints
    emotion = None
    if intent == "complaint":
        emotion = detect_emotion(query)

    # Extract order hint from query
    order_hint = ""
    product_keywords = ["T恤", "卫衣", "衬衫", "裤子", "裙子", "外套", "鞋", "包", "手机", "电脑", "运动鞋"]
    for kw in product_keywords:
        if kw in query:
            order_hint = kw
            break

    return {
        "intent": intent,
        "emotion": emotion,
        "order_hint": order_hint,
        "intent_confidence": router_result.confidence,
        "audit_trace": state.get("audit_trace", []) + [{
            "step": "supervisor",
            "intent": intent,
            "emotion": emotion,
            "domain": domain,
            "confidence": router_result.confidence,
        }],
    }


def route_after_supervisor(state: TicketAgentState) -> str:
    """LangGraph routing: direct to correct flow based on intent."""
    intent = state.get("intent", "refund")
    if intent == "exchange":
        return "exchange_parallel"
    elif intent == "complaint":
        return "retrieve"
    elif intent == "tracking":
        return "retrieve"
    else:
        return "retrieve"
