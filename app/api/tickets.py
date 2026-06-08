"""Ticket API — CRUD endpoints with state machine enforcement."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_db_session, verify_api_key
from app.config import get_settings
from app.db.models.ticket import TicketPriority, TicketStatus, can_transition
from app.services.ticket_sm import TicketStateMachine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tickets", tags=["tickets"])


# In-memory store for demo (replace with DB queries in production)
_tickets: dict[str, dict[str, Any]] = {}


@router.post("")
async def create_ticket(
    request: Request,
    _auth: bool = Depends(verify_api_key),
    db=Depends(get_db_session),
):
    """Create a new support ticket."""
    body = await request.json()
    title = str(body.get("title", ""))[:200]
    description = str(body.get("description", ""))[:2000]
    priority = body.get("priority", "p2_medium")

    ticket_id = f"TKT-{len(_tickets) + 1:06d}"
    sm = TicketStateMachine(ticket_id, TicketStatus.NEW, TicketPriority(priority))
    deadline = sm.compute_sla_deadline()

    ticket = {
        "id": ticket_id,
        "title": title,
        "description": description,
        "status": TicketStatus.NEW.value,
        "priority": priority,
        "sla_deadline": deadline.isoformat() if deadline else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "audit": sm.audit,
    }
    _tickets[ticket_id] = ticket
    return ticket


@router.get("")
async def list_tickets(
    status_filter: str | None = None,
    _auth: bool = Depends(verify_api_key),
):
    """List tickets, optionally filtered by status."""
    result = list(_tickets.values())
    if status_filter:
        result = [t for t in result if t["status"] == status_filter]
    return {"tickets": result, "total": len(result)}


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    _auth: bool = Depends(verify_api_key),
):
    """Get a single ticket by ID."""
    ticket = _tickets.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.patch("/{ticket_id}/transition")
async def transition_ticket(
    ticket_id: str,
    request: Request,
    _auth: bool = Depends(verify_api_key),
):
    """Transition a ticket to a new status (state machine enforced)."""
    ticket = _tickets.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    body = await request.json()
    target_status = str(body.get("status", ""))
    reason = str(body.get("reason", ""))

    try:
        target = TicketStatus(target_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {target_status}")

    current = TicketStatus(ticket["status"])
    sm = TicketStateMachine(ticket_id, current, TicketPriority(ticket["priority"]))

    if not sm.transition(target, reason=reason):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {current.value} to {target.value}",
        )

    ticket["status"] = target.value
    ticket["audit"] = sm.audit
    if target == TicketStatus.RESOLVED:
        ticket["resolved_at"] = datetime.now(timezone.utc).isoformat()

    return ticket
