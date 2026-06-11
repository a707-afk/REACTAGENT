"""Composite Tools: high-level business flows exposed as Harness-callable tools.

Each composite tool encapsulates a complete after-sales workflow:
- process_exchange: parallel policy + inventory + pickup
- process_refund: serial order → policy → calculate → ticket
- process_complaint: emotion-graded ticket + compensation
- process_tracking: order → shipment status

These replace the legacy LangGraph worker nodes
to enable the unified Harness architecture.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ── Shared helpers ────────────────────────────────────────────────

def _call_tool(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Call an atomic tool via the existing tool dispatch layer."""
    from app.agent.tools import execute_tool, ToolResult
    # execute_tool expects (tool_name, state, args) — we pass empty state
    result: ToolResult = execute_tool(tool_name, {}, params)
    if result.success:
        return result.data
    return {"_error": result.error, "_success": False}


def _detect_emotion(query: str) -> str:
    """Detect emotion from query text (reuse supervisor logic)."""
    from app.supervisor.router import detect_emotion
    return detect_emotion(query)


# ── process_exchange ──────────────────────────────────────────────

async def process_exchange(params: dict[str, Any], user_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Exchange flow: order_lookup → (parallel) policy_check + inventory_query + create_pickup.

    Params:
        user_id: str - User ID
        keyword: str - Product keyword or order hint
        target_size: str - Target size (default "L")
        color: str - Target color (optional)
        address: str - Pickup address (optional)

    Returns:
        worker_draft: str - User-facing reply
        ticket_id: str|None - Created ticket ID if any
        intermediate_data: dict - All tool results
    """
    user_context = user_context or {}
    user_id = params.get("user_id") or user_context.get("user_id", "u001")
    keyword = params.get("keyword", "")
    query = params.get("query_text", keyword)

    # Extract target size from query
    size_match = re.search(r'\b([SMLXsmlx]{1,3}|[3-4][0-9])\b', query)
    target_size = size_match.group(1).upper() if size_match else params.get("target_size", "L")
    color = params.get("color", "")
    address = params.get("address", "上海市")

    # Step 1: Order lookup
    order_data = _call_tool("order_lookup", {
        "user_id": user_id,
        "keyword": keyword or query[:15],
        "limit": 1,
    })
    orders = order_data.get("orders", [])

    if not orders:
        return {
            "worker_draft": "请问您是想换哪个订单的商品？能告诉我商品名称或订单号吗？",
            "ticket_id": None,
            "intermediate_data": {"order_lookup": "not_found"},
        }

    order = orders[0]
    order_id = order["order_id"]
    sku = order.get("sku", "TEE-WHITE")

    # Step 2: Parallel checks (policy + inventory + pickup)
    async def policy_worker():
        return await asyncio.to_thread(_call_tool, "policy_check", {
            "order_id": order_id, "return_reason": "尺码不合适"
        })

    async def inventory_worker():
        return await asyncio.to_thread(_call_tool, "inventory_query", {
            "sku": sku, "size": target_size, "color": color
        })

    async def logistics_worker():
        return await asyncio.to_thread(_call_tool, "create_pickup", {
            "order_id": order_id, "address": address
        })

    policy_r, inventory_r, logistics_r = await asyncio.gather(
        policy_worker(), inventory_worker(), logistics_worker(),
        return_exceptions=True,
    )

    def _safe(r):
        return r if isinstance(r, dict) else {"_error": str(r), "_success": False}

    policy_data = _safe(policy_r)
    inventory_data = _safe(inventory_r)
    logistics_data = _safe(logistics_r)

    # Build reply
    lines = []
    if policy_data.get("eligible"):
        lines.append(f"政策：{policy_data.get('policy', '可退换')} — {policy_data.get('reason', '')}")
    else:
        lines.append(f"政策：不符合退换条件 — {policy_data.get('reason', '不符合条件')}")

    if inventory_data.get("available"):
        lines.append(f"库存：{target_size}码有货（{inventory_data.get('warehouse', '仓库')}，库存{inventory_data.get('stock', 0)}件）")
    else:
        lines.append(f"库存：{target_size}码已售罄 — {inventory_data.get('message', '无货')}")

    lines.append(f"取件：已预约 — {logistics_data.get('scheduled', '明天')}（{logistics_data.get('carrier', '顺丰')}）")

    draft = f"换货处理结果：\n" + "\n".join(f"  {l}" for l in lines)

    return {
        "worker_draft": draft,
        "ticket_id": None,
        "intermediate_data": {
            "order": order,
            "policy": policy_data,
            "inventory": inventory_data,
            "logistics": logistics_data,
        },
    }


# ── process_refund ────────────────────────────────────────────────

async def process_refund(params: dict[str, Any], user_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Refund flow: order_lookup → policy_check → calculate → create_ticket.

    Params:
        user_id: str - User ID
        keyword: str - Product keyword or order hint
        return_reason: str - Reason for refund (default "申请退款")

    Returns:
        worker_draft: str - User-facing reply
        ticket_id: str|None - Created ticket ID
        refund_amount: float - Calculated refund amount
        intermediate_data: dict
    """
    user_context = user_context or {}
    user_id = params.get("user_id") or user_context.get("user_id", "u001")
    keyword = params.get("keyword", "")
    return_reason = params.get("return_reason", "申请退款")

    # Step 1: Order lookup
    order_data = _call_tool("order_lookup", {
        "user_id": user_id,
        "keyword": keyword,
        "limit": 1,
    })
    orders = order_data.get("orders", [])

    if not orders:
        return {
            "worker_draft": "暂时找不到您的订单，请提供订单号或商品名称，我来帮您处理退款申请。",
            "ticket_id": None,
            "refund_amount": 0,
            "intermediate_data": {"order_lookup": "not_found"},
        }

    order = orders[0]
    order_id = order["order_id"]
    amount = order.get("amount", 0)

    # Step 2: Policy check
    policy_data = _call_tool("policy_check", {
        "order_id": order_id,
        "return_reason": return_reason,
    })

    if not policy_data.get("eligible"):
        # Create denial ticket
        _call_tool("create_after_sale_ticket", {
            "type": "refund",
            "priority": "p3_low",
            "order_id": order_id,
            "detail": f"退款被拒：{policy_data.get('reason', '')}",
        })
        reply = (
            f"很抱歉，订单 {order_id}（{order.get('product', '')}）"
            f"{policy_data.get('reason', '不符合退款条件')}。\n如有疑问请联系人工客服。"
        )
        return {
            "worker_draft": reply,
            "ticket_id": None,
            "refund_amount": 0,
            "intermediate_data": {"order": order, "policy": policy_data, "denied": True},
        }

    # Step 3: Calculate refund
    deduction_rate = policy_data.get("deduction_rate", 0)
    refund_amount = round(amount * (1 - deduction_rate), 2)
    deduction_note = f"（扣除{int(deduction_rate * 100)}%手续费）" if deduction_rate > 0 else ""

    # Step 4: Create ticket
    ticket_data = _call_tool("create_after_sale_ticket", {
        "type": "refund",
        "priority": "p2_medium",
        "order_id": order_id,
        "detail": f"退款金额 ¥{refund_amount:.2f}{deduction_note}",
    })
    ticket_id = ticket_data.get("ticket_id", "AS-未知")

    reply = (
        f"退款申请已提交！\n"
        f"订单：{order_id}（{order.get('product', '')}）\n"
        f"退款金额：¥{refund_amount:.2f}{deduction_note}\n"
        f"工单号：{ticket_id}\n"
        f"预计 3-5 个工作日原路退回。"
    )

    return {
        "worker_draft": reply,
        "ticket_id": ticket_id,
        "refund_amount": refund_amount,
        "intermediate_data": {"order": order, "policy": policy_data, "ticket": ticket_data},
    }


# ── process_complaint ─────────────────────────────────────────────

async def process_complaint(params: dict[str, Any], user_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Complaint flow: emotion-graded ticket + compensation tier.

    Params:
        user_id: str - User ID
        keyword: str - Product keyword or order hint
        emotion: str - Detected emotion ("angry" | "neutral")
        query_text: str - Original query for ticket detail

    Returns:
        worker_draft: str - User-facing reply
        ticket_id: str - Created ticket ID
        intermediate_data: dict - priority, sla, compensation
    """
    user_context = user_context or {}
    user_id = params.get("user_id") or user_context.get("user_id", "u001")
    keyword = params.get("keyword", "")
    emotion = params.get("emotion", "neutral")
    query_text = params.get("query_text", "")

    # Auto-detect emotion if not provided
    if not emotion or emotion == "neutral":
        emotion = _detect_emotion(query_text or keyword)

    # Step 1: Order lookup
    order_data = _call_tool("order_lookup", {
        "user_id": user_id,
        "keyword": keyword,
        "limit": 1,
    })
    orders = order_data.get("orders", [])
    order = orders[0] if orders else {}
    order_id = order.get("order_id", "unknown")
    amount = order.get("amount", 100)

    # Compensation tier (deterministic business rule)
    if amount >= 300:
        compensation = 30
    elif amount >= 100:
        compensation = 15
    else:
        compensation = 5

    # Priority based on emotion
    priority = "p0_critical" if emotion == "angry" else "p2_medium"
    sla_desc = "2 小时" if emotion == "angry" else "24 小时"

    # Step 2: Create ticket
    ticket_data = _call_tool("create_after_sale_ticket", {
        "type": "complaint",
        "priority": priority,
        "order_id": order_id,
        "detail": f"情绪:{emotion},补偿:¥{compensation},投诉:{query_text[:100]}",
    })
    ticket_id = ticket_data.get("ticket_id", "AS-未知")

    if emotion == "angry":
        reply = (
            f"非常抱歉！已创建紧急投诉工单（{ticket_id}），优先级 P0，"
            f"承诺{sla_desc}内联系您。补偿 ¥{compensation} 优惠券，24小时内发放。"
        )
    else:
        reply = (
            f"感谢反馈，已记录投诉（{ticket_id}），{sla_desc}内联系您。"
            f"补偿 ¥{compensation} 优惠券。"
        )

    return {
        "worker_draft": reply,
        "ticket_id": ticket_id,
        "intermediate_data": {
            "order": order,
            "emotion": emotion,
            "priority": priority,
            "sla_hours": 2 if emotion == "angry" else 24,
            "compensation": compensation,
            "ticket": ticket_data,
        },
    }


# ── process_tracking ──────────────────────────────────────────────

async def process_tracking(params: dict[str, Any], user_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Tracking flow: order_lookup → track_shipment → reply.

    Params:
        user_id: str - User ID
        keyword: str - Product keyword or order hint

    Returns:
        worker_draft: str - User-facing reply
        ticket_id: None
        intermediate_data: dict
    """
    user_context = user_context or {}
    user_id = params.get("user_id") or user_context.get("user_id", "u001")
    keyword = params.get("keyword", "")

    # Step 1: Order lookup
    order_data = _call_tool("order_lookup", {
        "user_id": user_id,
        "keyword": keyword,
        "limit": 1,
    })
    orders = order_data.get("orders", [])

    if not orders:
        return {
            "worker_draft": "暂时找不到您的订单，请提供订单号或商品名称，我来帮您查询物流状态。",
            "ticket_id": None,
            "intermediate_data": {"order_lookup": "not_found"},
        }

    order = orders[0]
    order_id = order["order_id"]

    # Step 2: Track shipment
    logistics_data = _call_tool("track_shipment", {"order_id": order_id})
    status = logistics_data.get("status", "暂无物流信息")

    if status == "已签收":
        reply = f"订单 {order_id}（{order.get('product', '')}）已签收。签收时间：{logistics_data.get('last_update', '未知')}"
    elif status == "未找到物流信息":
        reply = f"订单 {order_id} 暂无物流信息，可能刚下单，请稍后再查。"
    else:
        reply = (
            f"包裹（{order_id}，{order.get('product', '')}）\n"
            f"状态：{status}\n"
            f"承运商：{logistics_data.get('carrier', '未知')}\n"
            f"最新：{logistics_data.get('last_update', '未知')}\n"
            f"预计：{logistics_data.get('estimated_delivery', '未知')}"
        )

    return {
        "worker_draft": reply,
        "ticket_id": None,
        "intermediate_data": {"order": order, "logistics": logistics_data},
    }
