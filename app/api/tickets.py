"""Ticket API — CRUD endpoints with state machine enforcement, DB-backed."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, verify_api_key
from app.config import get_settings
from app.db.models.ticket import Ticket, TicketPriority, TicketStatus, can_transition
from app.db.models.ticket_event import TicketEvent
from app.services.ticket_sm import TicketStateMachine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.post("")
async def create_ticket(
    request: Request,
    _auth: bool = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new support ticket (persisted to DB)."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    body = await request.json()
    title = str(body.get("title", ""))[:500]
    description = str(body.get("description", ""))[:2000]
    priority = str(body.get("priority", "p2_medium"))
    domain = body.get("domain")
    customer_id = body.get("customer_id")
    tenant_id = getattr(request.state, "tenant_id", "default")

    # Validate priority
    try:
        prio = TicketPriority(priority)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    # Compute SLA deadline via state machine
    sm = TicketStateMachine("pending", TicketStatus.NEW, prio)
    deadline = sm.compute_sla_deadline()

    ticket = Ticket(
        title=title,
        description=description,
        status=TicketStatus.NEW,
        priority=prio,
        domain=domain,
        customer_id=customer_id,
        tenant_id=tenant_id,
        sla_deadline=deadline,
    )
    db.add(ticket)
    # Flush to get the auto-generated UUID before creating the event
    await db.flush()

    # Write initial event
    event = TicketEvent(
        ticket_id=ticket.id,
        from_status="",
        to_status=TicketStatus.NEW.value,
        reason="ticket created",
        actor="system",
        allowed=True,
        tenant_id=tenant_id,
    )
    db.add(event)

    await db.flush()
    await db.refresh(ticket)

    return _ticket_to_dict(ticket)


@router.get("")
async def list_tickets(
    request: Request,
    status_filter: str | None = None,
    tenant_id_filter: str | None = None,
    offset: int = 0,
    limit: int = 50,
    _auth: bool = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    """List tickets with pagination, tenant and status filtering."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    tenant_id = tenant_id_filter or getattr(request.state, "tenant_id", "default")

    # Base query: always filter by tenant
    base_q = select(Ticket).where(Ticket.tenant_id == tenant_id)
    count_q = select(func.count()).select_from(Ticket).where(Ticket.tenant_id == tenant_id)

    if status_filter:
        try:
            s = TicketStatus(status_filter)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")
        base_q = base_q.where(Ticket.status == s)
        count_q = count_q.where(Ticket.status == s)

    # Count
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    base_q = base_q.order_by(Ticket.created_at.desc()).offset(offset).limit(limit)
    result = (await db.execute(base_q)).scalars().all()

    return {
        "tickets": [_ticket_to_dict(t) for t in result],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    request: Request,
    _auth: bool = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    """Get a single ticket by ID (tenant-scoped)."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    tenant_id = getattr(request.state, "tenant_id", "default")
    q = select(Ticket).where(Ticket.id == ticket_id, Ticket.tenant_id == tenant_id)
    ticket = (await db.execute(q)).scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _ticket_to_dict(ticket)


@router.patch("/{ticket_id}/transition")
async def transition_ticket(
    ticket_id: str,
    request: Request,
    _auth: bool = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    """Transition a ticket to a new status (state machine enforced)."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    tenant_id = getattr(request.state, "tenant_id", "default")
    q = select(Ticket).where(Ticket.id == ticket_id, Ticket.tenant_id == tenant_id)
    ticket = (await db.execute(q)).scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    body = await request.json()
    target_status = str(body.get("status", ""))
    reason = str(body.get("reason", ""))
    actor = str(body.get("actor", "system"))

    try:
        target = TicketStatus(target_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {target_status}")

    current = ticket.status
    sm = TicketStateMachine(ticket_id, current, ticket.priority)
    allowed = sm.transition(target, reason=reason)

    # Write audit event (whether allowed or not)
    event = TicketEvent(
        ticket_id=ticket_id,
        from_status=current.value,
        to_status=target.value,
        reason=reason,
        actor=actor,
        allowed=allowed,
        tenant_id=tenant_id,
    )
    db.add(event)

    if not allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {current.value} to {target.value}",
        )

    # Update ticket
    ticket.status = target
    if target == TicketStatus.RESOLVED:
        ticket.resolved_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(ticket)

    return _ticket_to_dict(ticket)


def _ticket_to_dict(ticket: Ticket) -> dict[str, Any]:
    """Convert a Ticket ORM object to a response dict."""
    return {
        "id": ticket.id,
        "title": ticket.title,
        "description": ticket.description,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "domain": ticket.domain,
        "customer_id": ticket.customer_id,
        "assignee": ticket.assignee,
        "sla_deadline": ticket.sla_deadline.isoformat() if ticket.sla_deadline else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "tags_json": ticket.tags_json,
        "tenant_id": ticket.tenant_id,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
    }
