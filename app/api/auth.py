"""API authentication dependency: API key hash validation + tenant scope."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, update

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


async def _get_api_key_from_request(request: Request) -> str | None:
    """Extract API key from Authorization header or query param."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    # Fallback: query param
    return request.query_params.get("api_key")


async def require_auth(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict:
    """FastAPI dependency: validate API key and return user context.

    If api_auth_enabled=False, returns a default context (demo mode).
    If api_auth_enabled=True, validates the key hash against the DB.

    Returns:
        dict with: tenant_id, user_id, roles, scopes, is_authenticated
    """
    if not settings.api_auth_enabled:
        # Demo mode: trust tenant from header
        tenant_id = getattr(request.state, "tenant_id", "default")
        return {
            "tenant_id": tenant_id,
            "user_id": "anonymous",
            "roles": ["user"],
            "scopes": ["read", "write"],
            "is_authenticated": False,
        }

    raw_key = await _get_api_key_from_request(request)
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Set Authorization: Bearer <key>",
        )

    from app.db.models.user import ApiKey
    from app.db.engine import get_sessionmaker

    key_hash = ApiKey.hash_key(raw_key)
    sm = get_sessionmaker()

    async with sm() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
        )
        api_key = result.scalar_one_or_none()

        if api_key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

        if api_key.is_expired():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired")

        # Load user for roles
        from app.db.models.user import User
        user_result = await session.execute(select(User).where(User.id == api_key.user_id))
        user = user_result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive or deleted")

        # Update last_used_at
        await session.execute(
            update(ApiKey).where(ApiKey.id == api_key.id).values(
                last_used_at=datetime.now(timezone.utc)
            )
        )
        await session.commit()

    # Merge scopes from api_key and user
    key_scopes = json.loads(api_key.scopes_json or "[]")
    user_scopes = json.loads(user.scopes_json or "[]")
    user_roles = json.loads(user.roles_json or "[]")

    return {
        "tenant_id": api_key.tenant_id,
        "user_id": user.id,
        "roles": user_roles,
        "scopes": list(set(key_scopes + user_scopes)),
        "is_authenticated": True,
    }


async def require_admin(auth: dict = Depends(require_auth)) -> dict:
    """Require admin role."""
    if not auth.get("is_authenticated"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
    roles = auth.get("roles", [])
    if "admin" not in roles and "superadmin" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return auth
