"""Agent tools: function definitions the Agent can call during a conversation.

Each tool has a JSON Schema for its parameters (OpenAI function-calling format)
and a sync implementation that the LangGraph node invokes.
Uses async DB via asyncio bridge for real persistence.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.agent_graph.state import TicketAgentState

logger = logging.getLogger(__name__)


# ── Tool Schema Definitions (OpenAI function-calling compatible) ──

TOOL_RETRIEVE_KB = {
    "type": "function",
    "function": {
        "name": "retrieve_kb",
        "description": "Search the customer service knowledge base for relevant articles, policies, and solutions. Returns top matching document chunks.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query about the customer's issue.",
                },
                "domain": {
                    "type": "string",
                    "enum": [
                        "tech_support", "billing", "account", "order", "returns",
                        "delivery", "outages", "sales", "feedback", "hr",
                        "it_support", "product_support", "customer_service", "general"
                    ],
                    "description": "Optional domain filter to narrow search scope.",
                },
                "top_k": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                    "description": "Number of document chunks to retrieve.",
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_CREATE_TICKET = {
    "type": "function",
    "function": {
        "name": "create_ticket",
        "description": "Create a new customer service ticket. Use this when the customer's issue cannot be resolved immediately and needs tracking.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short summary of the issue (max 200 chars).",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the issue, including what was tried and relevant context.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["p0_critical", "p1_high", "p2_medium", "p3_low"],
                    "description": "Ticket priority. p0=service down/business critical, p1=major impact, p2=normal, p3=minor.",
                },
                "domain": {
                    "type": "string",
                    "enum": [
                        "tech_support", "billing", "account", "order", "returns",
                        "delivery", "outages", "sales", "feedback", "hr",
                        "it_support", "product_support", "customer_service", "general"
                    ],
                    "description": "Issue category for routing.",
                },
            },
            "required": ["title", "description", "priority"],
        },
    },
}

TOOL_ESCALATE = {
    "type": "function",
    "function": {
        "name": "escalate",
        "description": "Escalate the current ticket or issue to a human agent (L2 support). Use when the AI cannot resolve the issue, the customer demands human assistance, or the issue requires supervisor authority.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Clear reason for escalation: what was tried, why AI cannot resolve, and what expertise is needed.",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["immediate", "soon", "when_available"],
                    "description": "How quickly human intervention is needed.",
                },
            },
            "required": ["reason", "urgency"],
        },
    },
}

TOOL_CUSTOMER_LOOKUP = {
    "type": "function",
    "function": {
        "name": "customer_lookup",
        "description": "Look up customer information by ID or email. Returns account tier, open ticket count, and recent activity.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID (UUID). Use this if known.",
                },
                "email": {
                    "type": "string",
                    "description": "Customer email address for lookup.",
                },
            },
        },
    },
}

ALL_TOOLS = [TOOL_RETRIEVE_KB, TOOL_CREATE_TICKET, TOOL_ESCALATE, TOOL_CUSTOMER_LOOKUP]


# ── Tool Result ──

@dataclass
class ToolResult:
    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


# ── Async DB helpers ──

def _run_async(coro):
    """Bridge: run async DB op from sync LangGraph node context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # If already in event loop, try to create a new one (limited but works for simple ops)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(asyncio.run, coro)
        return fut.result(timeout=15)


async def _get_async_session():
    """Get an async DB session."""
    from app.db.engine import get_sessionmaker
    sm = get_sessionmaker()
    return sm()


async def _lookup_customer_db(customer_id: str | None, email: str | None) -> dict[str, Any]:
    """Query customer from DB."""
    from sqlalchemy import select
    from app.db.models.customer import Customer

    async with await _get_async_session() as session:
        stmt = select(Customer)
        if customer_id:
            stmt = stmt.where(Customer.id == customer_id)
        elif email:
            stmt = stmt.where(Customer.email == email)
        else:
            return {"found": False, "reason": "no identifier"}

        result = await session.execute(stmt)
        customer = result.scalar_one_or_none()
        if customer is None:
            return {"found": False}
        return {
            "found": True,
            "customer_id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "tier": customer.tier.value if customer.tier else "free",
            "tenant_id": customer.tenant_id,
        }


async def _create_ticket_db(
    title: str,
    description: str,
    priority: str,
    domain: str | None,
    customer_id: str | None,
    tenant_id: str,
) -> dict[str, Any]:
    """Create a ticket in DB with proper state machine and SLA."""
    from app.db.models.ticket import Ticket, TicketPriority, TicketStatus
    from app.db.models.customer import Customer, CustomerTier, TIER_SLA_MINUTES
    from sqlalchemy import select

    async with await _get_async_session() as session:
        # Resolve priority enum
        pri_map = {
            "p0_critical": TicketPriority.P0_CRITICAL,
            "p1_high": TicketPriority.P1_HIGH,
            "p2_medium": TicketPriority.P2_MEDIUM,
            "p3_low": TicketPriority.P3_LOW,
        }
        pri = pri_map.get(priority, TicketPriority.P2_MEDIUM)

        # Calculate SLA deadline from customer tier
        sla_minutes = 480  # default 8h
        if customer_id:
            result = await session.execute(
                select(Customer).where(Customer.id == customer_id)
            )
            cust = result.scalar_one_or_none()
            if cust and cust.tier:
                sla_minutes = TIER_SLA_MINUTES.get(cust.tier, 480)

        sla_deadline = datetime.now(timezone.utc) + timedelta(minutes=sla_minutes)

        ticket = Ticket(
            title=title[:500],
            description=description[:5000],
            status=TicketStatus.NEW,
            priority=pri,
            domain=domain,
            customer_id=customer_id,
            tenant_id=tenant_id,
            sla_deadline=sla_deadline,
        )
        session.add(ticket)
        await session.flush()
        await session.refresh(ticket)

        return {
            "ticket_id": ticket.id,
            "title": ticket.title,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "domain": ticket.domain,
            "sla_deadline": sla_deadline.isoformat(),
            "sla_minutes": sla_minutes,
            "tenant_id": ticket.tenant_id,
            "message": f"工单 {ticket.id[:8]} 已创建，优先级 {priority}，SLA {sla_minutes} 分钟。",
        }


# ── Tool Implementations ──

def _execute_retrieve_kb(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    """Execute knowledge base retrieval from agent context."""
    query = str(args.get("query", ""))
    if not query.strip():
        return ToolResult("retrieve_kb", False, error="Empty query")

    try:
        from app.config import get_settings
        from app.retrieval_pipeline import retrieve_scored_nodes
        from app.vector_index import get_vector_index

        settings = get_settings()
        index = get_vector_index()
        top_k = min(int(args.get("top_k", 5)), 10)

        sr = retrieve_scored_nodes(
            index, query, top_k, settings, trace_id=state.get("trace_id")
        )

        chunks: list[dict[str, Any]] = []
        for sn in sr.nodes:
            meta = dict(sn.node.metadata or {})
            chunks.append({
                "text": sn.node.get_content()[:800],
                "file_name": meta.get("file_name"),
                "domain": meta.get("domain"),
                "score": float(sn.score) if sn.score is not None else None,
            })

        return ToolResult("retrieve_kb", True, data={
            "query": query,
            "hits": len(chunks),
            "chunks": chunks,
        })
    except Exception as e:
        logger.exception("retrieve_kb tool failed")
        return ToolResult("retrieve_kb", False, error=str(e))


def _execute_create_ticket(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    """Create a ticket with real DB persistence."""
    title = str(args.get("title", ""))[:200]
    description = str(args.get("description", ""))[:2000]
    priority = str(args.get("priority", "p2_medium"))
    domain = args.get("domain")

    if not title.strip():
        return ToolResult("create_ticket", False, error="Title is required")

    customer_id = state.get("customer_id")
    tenant_id = state.get("user_context", {}).get("tenant_id", "default") if state.get("user_context") else "default"

    try:
        data = _run_async(_create_ticket_db(
            title=title,
            description=description,
            priority=priority,
            domain=domain,
            customer_id=customer_id,
            tenant_id=tenant_id,
        ))
        return ToolResult("create_ticket", True, data=data)
    except Exception as e:
        logger.exception("create_ticket DB failed")
        return ToolResult("create_ticket", False, error=str(e))


def _execute_escalate(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    """Escalate to human agent, update ticket status if ticket_id exists."""
    reason = str(args.get("reason", ""))[:500]
    urgency = str(args.get("urgency", "soon"))

    ticket_id = state.get("ticket_id")

    async def _escalate_db():
        if not ticket_id or ticket_id == "unknown":
            return {
                "reason": reason,
                "urgency": urgency,
                "ticket_id": None,
                "message": f"已转人工（{urgency}）。原因: {reason[:120]}",
            }
        from app.db.models.ticket import Ticket, TicketStatus
        from sqlalchemy import select

        async with await _get_async_session() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.id == ticket_id)
            )
            ticket = result.scalar_one_or_none()
            if ticket is None:
                return {
                    "reason": reason,
                    "urgency": urgency,
                    "ticket_id": ticket_id,
                    "message": f"已转人工（{urgency}），但工单 {ticket_id[:8]} 未在数据库中找到。",
                }
            ticket.status = TicketStatus.ESCALATED
            ticket.assignee = "L2_SUPPORT"
            await session.flush()
            return {
                "reason": reason,
                "urgency": urgency,
                "ticket_id": ticket.id,
                "new_status": "escalated",
                "message": f"工单 {ticket.id[:8]} 已升级至二线支持（{urgency}）。",
            }

    try:
        data = _run_async(_escalate_db())
        return ToolResult("escalate", True, data=data)
    except Exception as e:
        logger.exception("escalate DB failed")
        # Fallback: non-persistent escalation still works
        return ToolResult("escalate", True, data={
            "reason": reason,
            "urgency": urgency,
            "message": f"已转人工（{urgency}，数据库暂不可用）。",
        })


def _execute_customer_lookup(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    """Look up customer info from DB."""
    customer_id = args.get("customer_id")
    email = args.get("email")

    if not customer_id and not email:
        return ToolResult("customer_lookup", False, error="Need customer_id or email")

    try:
        data = _run_async(_lookup_customer_db(customer_id, email))
        if not data.get("found"):
            return ToolResult("customer_lookup", True, data={
                "found": False,
                "note": "客户未在系统中注册。建议创建新客户档案。",
            })
        return ToolResult("customer_lookup", True, data=data)
    except Exception as e:
        logger.exception("customer_lookup DB failed")
        return ToolResult("customer_lookup", False, error=str(e))


TOOL_DISPATCH = {
    "retrieve_kb": _execute_retrieve_kb,
    "create_ticket": _execute_create_ticket,
    "escalate": _execute_escalate,
    "customer_lookup": _execute_customer_lookup,
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
