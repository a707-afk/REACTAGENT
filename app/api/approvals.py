"""Human-in-the-Loop (HITL) approval API.

Endpoints:
- GET /api/approvals — List pending approvals (tenant-scoped)
- POST /api/approvals/{id}/approve — Approve a request
- POST /api/approvals/{id}/reject — Reject a request
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import AuthContext, get_db_session, require_auth
from app.db.models.approval import Approval

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/approvals", tags=["approvals"])


# ── Models ─────────────────────────────────────────────────────────

class ApprovalResponse(BaseModel):
    id: str
    tenant_id: str
    run_id: str | None = None
    tool_name: str
    reason: str | None = None
    risk_level: str
    status: str
    requested_by: str | None = None
    approved_by: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class ApprovalListResponse(BaseModel):
    items: list[ApprovalResponse]
    total: int
    offset: int
    limit: int


class ApproveRequest(BaseModel):
    approved_by: str = "admin"
    comment: str | None = None


class RejectRequest(BaseModel):
    approved_by: str = "admin"
    reason: str = "Rejected by reviewer"


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/", response_model=ApprovalListResponse)
async def list_approvals(
    status: str | None = Query(default="pending"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require_auth),
    db=Depends(get_db_session),
):
    """List approvals for a tenant (tenant-scoped via auth)."""
    from sqlalchemy import select, func

    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    tenant_id = auth.tenant_id
    base = (Approval.tenant_id == tenant_id)
    if status:
        base = base & (Approval.status == status)

    count_q = select(func.count()).select_from(Approval).where(base)
    total = (await db.execute(count_q)).scalar() or 0

    q = select(Approval).where(base).order_by(Approval.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    approvals = list(result.scalars().all())

    items = [
        ApprovalResponse(
            id=a.id, tenant_id=a.tenant_id, run_id=a.run_id, tool_name=a.tool_name,
            reason=a.reason, risk_level=a.risk_level, status=a.status,
            requested_by=a.requested_by, approved_by=a.approved_by,
            created_at=a.created_at.isoformat() if a.created_at else "",
            updated_at=a.updated_at.isoformat() if a.updated_at else "",
        )
        for a in approvals
    ]
    return ApprovalListResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    approval_id: str,
    body: ApproveRequest,
    auth: AuthContext = Depends(require_auth),
    db=Depends(get_db_session),
):
    """Approve a pending approval request."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    tenant_id = auth.tenant_id
    approval = await db.get(Approval, approval_id)
    if approval is None or approval.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval already {approval.status}")

    approval.status = "approved"
    approval.approved_by = body.approved_by
    approval.approved_at = datetime.now(timezone.utc)
    approval.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return ApprovalResponse(
        id=approval.id, tenant_id=approval.tenant_id, run_id=approval.run_id,
        tool_name=approval.tool_name, reason=approval.reason, risk_level=approval.risk_level,
        status=approval.status, requested_by=approval.requested_by,
        approved_by=approval.approved_by,
        created_at=approval.created_at.isoformat() if approval.created_at else "",
        updated_at=approval.updated_at.isoformat() if approval.updated_at else "",
    )


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_request(
    approval_id: str,
    body: RejectRequest,
    auth: AuthContext = Depends(require_auth),
    db=Depends(get_db_session),
):
    """Reject a pending approval request."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    tenant_id = auth.tenant_id
    approval = await db.get(Approval, approval_id)
    if approval is None or approval.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval already {approval.status}")

    approval.status = "rejected"
    approval.approved_by = body.approved_by
    approval.rejection_reason = body.reason
    approval.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return ApprovalResponse(
        id=approval.id, tenant_id=approval.tenant_id, run_id=approval.run_id,
        tool_name=approval.tool_name, reason=approval.reason, risk_level=approval.risk_level,
        status=approval.status, requested_by=approval.requested_by,
        approved_by=approval.approved_by,
        created_at=approval.created_at.isoformat() if approval.created_at else "",
        updated_at=approval.updated_at.isoformat() if approval.updated_at else "",
    )
