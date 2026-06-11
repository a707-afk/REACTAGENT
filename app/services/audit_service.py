"""Audit service: write immutable audit logs to policy_audit_logs table."""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def write_audit_log(
    *,
    tenant_id: str,
    event_type: str,
    action: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    risk_level: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Write an audit log entry to the database.

    This function is fire-and-forget: if the DB write fails, it logs
    the error but does not raise, to avoid disrupting business logic.
    """
    try:
        from app.db.models.policy_audit_log import PolicyAuditLog
        from app.db.engine import get_sessionmaker

        sm = get_sessionmaker()
        async with sm() as session:
            entry = PolicyAuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                event_type=event_type,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
                risk_level=risk_level,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(entry)
            await session.commit()
    except Exception:
        logger.exception("Failed to write audit log: event=%s action=%s", event_type, action)


async def write_tool_call_audit(
    *,
    tenant_id: str,
    tool_name: str,
    params: dict | None = None,
    result: dict | None = None,
    success: bool = True,
    error_message: str | None = None,
    permission_result: str | None = None,
    permission_reason: str | None = None,
    idempotency_key: str | None = None,
    latency_ms: float = 0.0,
    run_id: str | None = None,
) -> None:
    """Write a tool call audit entry to the database."""
    try:
        from app.db.models.tool_call import ToolCall
        from app.db.engine import get_sessionmaker

        sm = get_sessionmaker()
        async with sm() as session:
            entry = ToolCall(
                run_id=run_id,
                tenant_id=tenant_id,
                tool_name=tool_name,
                params_json=json.dumps(params, ensure_ascii=False) if params else None,
                result_json=json.dumps(result, ensure_ascii=False) if result else None,
                success=success,
                error_message=error_message,
                permission_result=permission_result,
                permission_reason=permission_reason,
                idempotency_key=idempotency_key,
                latency_ms=latency_ms,
            )
            session.add(entry)
            await session.commit()
    except Exception:
        logger.exception("Failed to write tool call audit: tool=%s", tool_name)
