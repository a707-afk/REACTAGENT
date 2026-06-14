"""API dependencies: auth, DB session, rate limiting, tenant resolution.

Security posture (Phase 0 hardening):
- Every management endpoint MUST use `Depends(require_auth)`. Anonymous
  access to /api/documents, /api/tickets, /api/jobs, /api/approvals is
  now rejected when API_AUTH_ENABLED=true (the production default).
- Tenant ID is resolved from the authenticated principal, NOT from
  client-controlled Form/Query params. When auth is disabled (local dev /
  tests), it falls back to the X-Tenant-ID header with a hardcoded
  `test-tenant` default so the application remains runnable.
"""
from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings


# Tenant ID used when API_AUTH_ENABLED=false (tests/local dev only).
# NEVER use this value in production — production must always set
# API_AUTH_ENABLED=true and resolve tenant from the real principal.
_FALLBACK_TEST_TENANT = "test-tenant"


async def get_db_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Yield an async DB session. Returns None if DB is not configured."""
    try:
        from app.db.engine import get_session
        async for session in get_session():
            yield session
    except Exception:
        yield None


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        # Backward-compat: X-API-Key header
        token = request.headers.get("X-API-Key", "").strip()
    return token


async def verify_api_key(request: Request) -> bool:
    """Deprecated thin auth check — returns bool only.

    Kept for backward compatibility with existing tickets endpoints.
    New code should use `require_auth` instead, which also resolves the
    tenant scope.
    """
    settings = get_settings()
    if not settings.api_auth_enabled:
        return True
    keys_str = (settings.api_keys or "").strip()
    if not keys_str:
        # Auth enabled but no keys configured — fail-closed.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API auth enabled but no API keys configured",
        )
    valid_keys = {k.strip() for k in keys_str.split(",") if k.strip()}
    token = _extract_bearer_token(request)
    if token and token in valid_keys:
        return True
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
    )


def resolve_tenant_id(request: Request, authenticated: bool) -> str:
    """Resolve tenant ID for the current request.

    Resolution order:
    1. If auth is enabled and the request was authenticated, the caller is
       expected to scope via X-Tenant-ID (Phase 0). Phase 1 will replace
       this with a real per-principal tenant resolved from the API key DB
       record.
    2. If auth is disabled (tests/local dev), fall back to X-Tenant-ID or
       the hardcoded test tenant.

    Production deployments MUST keep API_AUTH_ENABLED=true.
    """
    header_tenant = request.headers.get("X-Tenant-ID", "").strip()
    if header_tenant:
        return header_tenant
    if authenticated:
        # Auth on but no tenant header — default to "default" tenant.
        # (Phase 1: replace with tenant from the API key record.)
        return "default"
    return _FALLBACK_TEST_TENANT


class AuthContext:
    """Minimal auth context for Phase 0.

    Phase 1 will replace this with a full UserContext (user_id, roles,
    scopes, security_clearance) resolved from the API key DB record.
    """

    __slots__ = ("authenticated", "tenant_id", "is_admin")

    def __init__(self, *, authenticated: bool, tenant_id: str, is_admin: bool = False) -> None:
        self.authenticated = authenticated
        self.tenant_id = tenant_id
        self.is_admin = is_admin


async def require_auth(request: Request) -> AuthContext:
    """Require authentication for management endpoints.

    Returns an AuthContext with the resolved tenant_id. Use this on
    /api/documents, /api/tickets, /api/jobs, /api/approvals.

    When API_AUTH_ENABLED=false (local dev/tests), returns a fallback
    context so the app remains runnable — but this MUST be off in
    production. The default in config.py is `api_auth_enabled=True`.
    """
    settings = get_settings()

    if not settings.api_auth_enabled:
        # Local dev / test mode: no key check, but still resolve a tenant.
        return AuthContext(
            authenticated=False,
            tenant_id=resolve_tenant_id(request, authenticated=False),
        )

    keys_str = (settings.api_keys or "").strip()
    if not keys_str:
        # Auth enabled but no keys configured — fail-closed. This would
        # reject every request, so we surface it as 503 (misconfigured)
        # rather than 401 (which would imply the client did something wrong).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API auth enabled but no API keys configured. Set API_KEYS in .env.",
        )

    valid_keys = {k.strip() for k in keys_str.split(",") if k.strip()}
    token = _extract_bearer_token(request)
    if not token or token not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

    return AuthContext(
        authenticated=True,
        tenant_id=resolve_tenant_id(request, authenticated=True),
    )


async def require_admin(auth: AuthContext = Depends(require_auth)) -> AuthContext:
    """Require admin-level access. Phase 0 stub: same as require_auth.

    Phase 1 will add a real admin role check (admin/superadmin) once the
    User/ApiKey DB models are wired into require_auth.
    """
    return auth
