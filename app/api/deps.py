"""API dependencies: auth, DB session, rate limiting."""
from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings


async def get_db_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Yield an async DB session. Returns None if DB is not configured."""
    try:
        from app.db.engine import get_session
        async for session in get_session():
            yield session
    except Exception:
        yield None


async def verify_api_key(request: Request) -> bool:
    """Optional API key auth. Returns True if auth is disabled or key matches."""
    settings = get_settings()
    if not settings.api_auth_enabled:
        return True
    keys_str = (settings.api_keys or "").strip()
    if not keys_str:
        return True
    valid_keys = {k.strip() for k in keys_str.split(",") if k.strip()}
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if token in valid_keys:
        return True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
