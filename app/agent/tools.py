"""Agent tools: function definitions the Agent can call during a conversation.

Each tool has a JSON Schema for its parameters (OpenAI function-calling format)
and a sync implementation that the LangGraph node invokes.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
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


# ── Tool Implementations ──

@dataclass
class ToolResult:
    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


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
    """Create a ticket (stores in state; persists via service layer)."""
    title = str(args.get("title", ""))[:200]
    description = str(args.get("description", ""))[:2000]
    priority = str(args.get("priority", "p2_medium"))
    domain = args.get("domain")

    if not title.strip():
        return ToolResult("create_ticket", False, error="Title is required")

    ticket_data = {
        "title": title,
        "description": description,
        "priority": priority,
        "domain": domain,
        "status": "new",
    }

    return ToolResult("create_ticket", True, data={
        "ticket": ticket_data,
        "message": f"Ticket '{title}' created with priority {priority}.",
    })


def _execute_escalate(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    """Escalate to human agent."""
    reason = str(args.get("reason", ""))[:500]
    urgency = str(args.get("urgency", "soon"))

    return ToolResult("escalate", True, data={
        "reason": reason,
        "urgency": urgency,
        "message": f"Escalated to L2 support ({urgency}). Reason: {reason[:120]}...",
    })


def _execute_customer_lookup(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    """Look up customer info."""
    customer_id = args.get("customer_id")
    email = args.get("email")

    if not customer_id and not email:
        return ToolResult("customer_lookup", False, error="Need customer_id or email")

    # In production, this queries a CRM/DB. For now, return stub.
    return ToolResult("customer_lookup", True, data={
        "customer_id": customer_id or "unknown",
        "email": email or "unknown",
        "tier": "basic",
        "open_tickets": 0,
        "note": "Stub implementation — connect to CRM for live data.",
    })


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
