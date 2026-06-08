"""Multi-tenant isolation middleware + query helpers."""
from __future__ import annotations

import logging
from typing import Any

from starlette.requests import Request

logger = logging.getLogger(__name__)

DEFAULT_TENANT = "default"


async def tenant_middleware(request: Request, call_next):
    """Extract tenant_id from header or API key, inject into request.state.

    Priority:
    1. X-Tenant-ID header (explicit)
    2. Extracted from API key prefix (if key format is tenant:secret)
    3. Default tenant
    """
    tenant_id = request.headers.get("X-Tenant-ID") or request.headers.get("x-tenant-id")

    if not tenant_id:
        # Try to extract from Authorization header
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and ":" in auth:
            # Format: Bearer tenant_id:api_key
            parts = auth.removeprefix("Bearer ").strip().split(":", 1)
            if len(parts) == 2:
                tenant_id = parts[0]

    request.state.tenant_id = tenant_id or DEFAULT_TENANT
    response = await call_next(request)
    response.headers["X-Tenant-ID"] = request.state.tenant_id
    return response


def get_tenant_id(request: Request) -> str:
    """FastAPI dependency: extract tenant_id from request state."""
    return getattr(request.state, "tenant_id", DEFAULT_TENANT)


def tenant_filter_kwargs(tenant_id: str) -> dict[str, Any]:
    """Return kwargs for SQLAlchemy .filter_by(tenant_id=...)."""
    return {"tenant_id": tenant_id}


def tenant_qdrant_filter(tenant_id: str) -> dict[str, Any]:
    """Return Qdrant must-filter for tenant isolation."""
    if tenant_id == DEFAULT_TENANT:
        return {}  # No filter for default tenant (backward-compatible)
    return {
        "must": [
            {"key": "tenant_id", "match": {"value": tenant_id}}
        ]
    }


def tenant_bm25_filter(tenant_id: str, meta_lookup: dict) -> set[str]:
    """Return set of node_ids that belong to the given tenant."""
    if tenant_id == DEFAULT_TENANT:
        return set()  # Empty = no filter
    allowed_ids: set[str] = set()
    for nid, meta in meta_lookup.items():
        if meta.get("tenant_id", DEFAULT_TENANT) == tenant_id:
            allowed_ids.add(nid)
    return allowed_ids
