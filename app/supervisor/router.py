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
    angry_keywords = ["垃圾", "骗子", "投诉你", "差评", "举报", "气死", "!!!"]
    # Note: "退款" removed — normal refund queries are not angry
    query_lower = query.lower()
    for kw in angry_keywords:
        if kw in query_lower:
            return "angry"
    if query.count("!") + query.count("！") >= 2:
        return "angry"
    return "neutral"


def route_intent(state: TicketAgentState) -> dict[str, Any]:
    """
    Supervisor 节点：纯关键词匹配 + LLM fallback 意图识别。
    废弃 domain_router（旧 CS 14 域），直接分类为 4 个电商意图。
    """
    query = (state.get("user_query") or "").strip()

    # ── 关键词快速路径（覆盖 95% 的常见表达）──────────────────
    EXCHANGE_KW  = ["换货", "换个", "换成", "换一件", "换尺码", "换码",
                    "太小", "太大", "尺寸不对", "尺码不合适", "想换"]
    REFUND_KW    = ["退款", "退货", "退钱", "不想要", "取消订单", "申请退"]
    TRACKING_KW  = ["物流", "快递", "到哪了", "几天到", "发货了吗",
                    "运输", "签收", "查一下", "查快递", "查物流"]
    COMPLAINT_KW = ["投诉", "差评", "举报", "骗子", "假货", "质量问题",
                    "态度差", "要投诉", "太差了", "气死", "骗人"]

    def match(kw_list):
        return any(kw in query for kw in kw_list)

    if match(EXCHANGE_KW):
        intent, confidence = "exchange", 0.95
    elif match(REFUND_KW):
        intent, confidence = "refund", 0.95
    elif match(TRACKING_KW):
        intent, confidence = "tracking", 0.95
    elif match(COMPLAINT_KW):
        intent, confidence = "complaint", 0.95
    else:
        # ── LLM fallback（关键词未命中时）────────────────────
        intent, confidence = _llm_classify_intent(query)

    # ── 情绪检测（仅投诉意图）────────────────────────────────
    emotion = detect_emotion(query) if intent == "complaint" else None

    # ── 商品关键词提取（供 order_lookup 使用）────────────────
    PRODUCT_KW = ["T恤", "衬衫", "裤子", "裙子", "卫衣", "外套",
                  "鞋", "运动鞋", "包", "手机", "耳机", "手表"]
    order_hint = next((kw for kw in PRODUCT_KW if kw in query), "")

    return {
        "intent": intent,
        "emotion": emotion,
        "order_hint": order_hint,
        "intent_confidence": confidence,
        "audit_trace": state.get("audit_trace", []) + [{
            "step": "supervisor",
            "intent": intent,
            "emotion": emotion,
            "confidence": confidence,
            "method": "keyword" if confidence == 0.95 else "llm_fallback",
        }],
    }


def _llm_classify_intent(query: str) -> tuple[str, float]:
    """LLM fallback：关键词未命中时调用 LLM 分类。"""
    VALID = {"exchange", "refund", "complaint", "tracking"}
    prompt = (
        f'用户说："{query}"\n\n'
        "判断意图，只返回以下之一：exchange（换货）/ refund（退款）/ "
        "complaint（投诉）/ tracking（物流查询）\n"
        "只返回一个英文单词，不要解释。"
    )
    try:
        from app.llm import chat_completion
        result = chat_completion("你是意图分类器", prompt).strip().lower()
        if result in VALID:
            return result, 0.80
    except Exception:
        pass
    return "refund", 0.30  # 兜底：不确定时默认走退款流程（最常见）


def route_after_supervisor(state: TicketAgentState) -> str:
    """
    LangGraph 条件路由：根据 intent 分派到对应的专属节点。
    exchange    → exchange_parallel（asyncio.gather 三Worker并行）
    refund      → refund_flow（串行：policy检查→计算退款→工单）
    complaint   → complaint_flow（情绪分级：angry=P0工单，neutral=补偿推荐）
    tracking    → tracking_flow（直通：order_lookup→track_shipment→回复）
    unknown     → retrieve（通用 RAG 兜底）
    """
    intent = state.get("intent")
    routes = {
        "exchange":  "exchange_parallel",
        "refund":    "refund_flow",
        "complaint": "complaint_flow",
        "tracking":  "tracking_flow",
    }
    return routes.get(intent, "retrieve")
