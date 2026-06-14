"""Supervisor emotion detection.

Historically this module also contained LangGraph intent-routing helpers
(``route_intent``, ``route_after_supervisor``, ``_llm_classify_intent``).
Those were removed together with the LangGraph path; intent classification
now lives in ``app.agent.harness._classify_intent``. Only ``detect_emotion``
remains, which is still used by the Harness and composite tools.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def detect_emotion(query: str) -> str:
    """Inline emotion detection: angry keywords or exclamation intensity."""
    angry_keywords = ["垃圾", "骗子", "投诉你", "差评", "举报", "气死", "!!!"]
    # Note: "退款" removed — normal refund queries are not angry
    query_lower = query.lower()
    for kw in angry_keywords:
        if kw in query_lower:
            return "angry"
    if query.count("!") + query.count("！") >= 2:
        return "angry"
    return "neutral"
