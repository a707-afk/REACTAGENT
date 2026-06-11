"""EcomAgent tools: 6 e-commerce after-sales tools (OpenAI function-calling format)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.agent.state import TicketAgentState

logger = logging.getLogger(__name__)


# ── Tool Schema Definitions (OpenAI function-calling compatible) ──

TOOL_ORDER_LOOKUP = {
    "type": "function",
    "function": {
        "name": "order_lookup",
        "description": "Look up user's recent orders by keyword. Returns matching orders with product details, purchase date, and condition status.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User ID for order lookup."},
                "keyword": {"type": "string", "description": "Product keyword to filter orders (e.g. 'T恤')."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
            },
            "required": ["user_id"],
        },
    },
}

TOOL_POLICY_CHECK = {
    "type": "function",
    "function": {
        "name": "policy_check",
        "description": "Check if an order is eligible for return/exchange based on purchase days and product condition. Returns eligibility, refund type, and reason.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID to check."},
                "return_reason": {"type": "string", "description": "Reason for return/exchange (e.g. '尺码不合适')."},
            },
            "required": ["order_id", "return_reason"],
        },
    },
}

TOOL_INVENTORY_QUERY = {
    "type": "function",
    "function": {
        "name": "inventory_query",
        "description": "Check inventory availability for a specific product SKU, target size, and color. Used for exchange scenarios.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "description": "Product SKU code."},
                "size": {"type": "string", "description": "Target size (e.g. 'L', 'XL')."},
                "color": {"type": "string", "description": "Target color.", "default": ""},
            },
            "required": ["sku", "size"],
        },
    },
}

TOOL_CREATE_PICKUP = {
    "type": "function",
    "function": {
        "name": "create_pickup",
        "description": "Create a pickup request for return/exchange items. Generates a pickup order with scheduled pickup time window.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID to create pickup for."},
                "address": {"type": "string", "description": "Pickup address."},
            },
            "required": ["order_id", "address"],
        },
    },
}

TOOL_TRACK_SHIPMENT = {
    "type": "function",
    "function": {
        "name": "track_shipment",
        "description": "Track the shipping/delivery status of an order. Returns current status, last update, and estimated delivery.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID to track."},
            },
            "required": ["order_id"],
        },
    },
}

TOOL_CREATE_AFTER_SALE_TICKET = {
    "type": "function",
    "function": {
        "name": "create_after_sale_ticket",
        "description": "Create an after-sales service ticket (exchange/refund/complaint) with priority and SLA deadline tracking.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["exchange", "refund", "complaint"], "description": "After-sales ticket type."},
                "priority": {"type": "string", "enum": ["p0_critical", "p1_high", "p2_medium", "p3_low"], "description": "Ticket priority level."},
                "order_id": {"type": "string", "description": "Related order ID."},
                "detail": {"type": "string", "description": "Ticket detail/description.", "maxLength": 500},
            },
            "required": ["type", "priority", "order_id", "detail"],
        },
    },
}

ALL_TOOLS = [
    TOOL_ORDER_LOOKUP, TOOL_POLICY_CHECK, TOOL_INVENTORY_QUERY,
    TOOL_CREATE_PICKUP, TOOL_TRACK_SHIPMENT, TOOL_CREATE_AFTER_SALE_TICKET,
]


# ── Tool Result ──

@dataclass
class ToolResult:
    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


# ── Tool Implementations ──

def _execute_order_lookup(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    user_id = str(args.get("user_id", state.get("user_id", "u001")))
    keyword = str(args.get("keyword", ""))
    limit = min(int(args.get("limit", 3)), 5)
    from app.mock.orders import lookup_orders
    orders = lookup_orders(user_id, keyword, limit)
    return ToolResult("order_lookup", True, data={"orders": orders, "count": len(orders)})


def _execute_policy_check(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    order_id = str(args.get("order_id", ""))
    reason = str(args.get("return_reason", "未说明"))
    from app.mock.orders import get_order, days_since_purchase
    order = get_order(order_id)
    if not order:
        return ToolResult("policy_check", False, error=f"Order {order_id} not found")

    days = days_since_purchase(order_id)
    status = order.get("status", "")

    if days <= 7 and status == "unopened":
        return ToolResult("policy_check", True, data={
            "eligible": True, "policy": "7天无理由退换", "refund_type": "full",
            "days_since_purchase": days,
            "return_reason": reason,
            "reason": f"购买{days}天，未拆封，退货原因：{reason}，符合全额退换条件",
            "deduction_rate": 0,
        })
    elif days <= 30 and status == "opened_damaged":
        return ToolResult("policy_check", True, data={
            "eligible": True, "policy": "质量问题退换", "refund_type": "partial",
            "days_since_purchase": days,
            "return_reason": reason,
            "reason": f"购买{days}天，已拆封影响二次销售，退货原因：{reason}，部分退款(扣10%)",
            "deduction_rate": 0.10,
        })
    else:
        return ToolResult("policy_check", True, data={
            "eligible": False, "policy": "超出退换期限", "refund_type": "denied",
            "days_since_purchase": days,
            "return_reason": reason,
            "reason": f"购买{days}天，超出退换期限，退货原因：{reason}，不支持退换",
            "deduction_rate": 0,
        })


def _execute_inventory_query(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    sku = str(args.get("sku", "")).upper()
    size = str(args.get("size", ""))
    color = str(args.get("color", ""))
    from app.mock.inventory import query_inventory
    result = query_inventory(sku, size, color)
    return ToolResult("inventory_query", True, data=result)


def _execute_create_pickup(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    order_id = str(args.get("order_id", ""))
    address = str(args.get("address", state.get("pickup_address", "默认地址")))
    from app.mock.logistics import create_pickup
    result = create_pickup(order_id, address)
    return ToolResult("create_pickup", True, data=result)


def _execute_track_shipment(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    order_id = str(args.get("order_id", ""))
    from app.mock.logistics import track_shipment
    result = track_shipment(order_id)
    return ToolResult("track_shipment", True, data=result)


def _execute_create_after_sale_ticket(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    ticket_type = str(args.get("type", "refund"))
    priority = str(args.get("priority", "p2_medium"))
    order_id = str(args.get("order_id", "unknown"))
    detail = str(args.get("detail", ""))[:500]

    sla_hours = {"p0_critical": 2, "p1_high": 4, "p2_medium": 24, "p3_low": 72}
    hours = sla_hours.get(priority, 24)
    sla_deadline = datetime.now(timezone.utc) + timedelta(hours=hours)

    import uuid
    ticket_id = f"AS-{uuid.uuid4().hex[:8]}"
    return ToolResult("create_after_sale_ticket", True, data={
        "ticket_id": ticket_id,
        "type": ticket_type,
        "priority": priority,
        "status": "NEW",
        "sla_deadline": sla_deadline.isoformat(),
        "sla_hours": hours,
        "order_id": order_id,
        "detail": detail,
    })


TOOL_DISPATCH = {
    "order_lookup": _execute_order_lookup,
    "policy_check": _execute_policy_check,
    "inventory_query": _execute_inventory_query,
    "create_pickup": _execute_create_pickup,
    "track_shipment": _execute_track_shipment,
    "create_after_sale_ticket": _execute_create_after_sale_ticket,
}


def execute_tool(tool_name: str, state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    """Dispatch a tool call by name."""
    handler = TOOL_DISPATCH.get(tool_name)
    if handler is None:
        return ToolResult(tool_name, False, error=f"Unknown tool: {tool_name}")
    try:
        return handler(state, args)
    except Exception as e:
        logger.exception("Tool %s execution failed", tool_name)
        return ToolResult(tool_name, False, error=str(e))
