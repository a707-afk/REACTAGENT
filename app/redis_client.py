"""Redis client: connection management, distributed cache, rate limiter, distributed lock.

Provides a thin async wrapper over redis.asyncio so the rest of the app
does not import redis directly.  All operations accept an optional
``redis`` parameter so tests can inject a fakeredis instance.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

import redis.asyncio as aioredis

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# ── Module-level connection pool ──────────────────────────────────

_pool: aioredis.Redis | None = None


async def get_redis_pool(settings: Settings | None = None) -> aioredis.Redis:
    """Return (and lazily create) the module-level Redis connection pool."""
    global _pool
    if _pool is not None:
        return _pool
    settings = settings or get_settings()
    password = settings.redis_password or None
    _pool = aioredis.from_url(
        settings.redis_url,
        password=password,
        decode_responses=True,
        max_connections=20,
    )
    # Verify connectivity
    await _pool.ping()
    logger.info("Redis pool created: %s", settings.redis_url)
    return _pool


async def close_redis_pool() -> None:
    """Gracefully close the module-level pool (call on shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
        logger.info("Redis pool closed")


# ── Distributed cache ─────────────────────────────────────────────

CACHE_PREFIX = "cache:"


async def cache_get(
    key: str,
    *,
    redis: aioredis.Redis | None = None,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    """Get a JSON-serialized value from Redis cache.  Returns None on miss."""
    r = redis or await get_redis_pool(settings)
    raw = await r.get(f"{CACHE_PREFIX}{key}")
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def cache_set(
    key: str,
    value: dict[str, Any],
    *,
    ttl_seconds: int = 300,
    redis: aioredis.Redis | None = None,
    settings: Settings | None = None,
) -> None:
    """Set a JSON-serializable value in Redis cache with TTL."""
    r = redis or await get_redis_pool(settings)
    await r.set(f"{CACHE_PREFIX}{key}", json.dumps(value, ensure_ascii=False), ex=ttl_seconds)


async def cache_delete(
    key: str,
    *,
    redis: aioredis.Redis | None = None,
    settings: Settings | None = None,
) -> bool:
    """Delete a cache key.  Returns True if the key existed."""
    r = redis or await get_redis_pool(settings)
    return bool(await r.delete(f"{CACHE_PREFIX}{key}"))


# ── Distributed lock ──────────────────────────────────────────────

LOCK_PREFIX = "lock:"


class DistributedLock:
    """Simple Redis-based distributed lock with TTL.

    Usage::

        lock = DistributedLock("my_resource", redis=r)
        acquired = await lock.acquire(timeout=10, ttl=30)
        if acquired:
            try:
                ...
            finally:
                await lock.release()
    """

    def __init__(self, name: str, *, redis: aioredis.Redis | None = None):
        self.name = name
        self._redis = redis
        self._token: str | None = None

    def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            raise RuntimeError("Redis not set; call acquire() with a running event loop")
        return self._redis

    async def acquire(self, *, timeout: float = 10.0, ttl: float = 30.0) -> bool:
        """Try to acquire the lock.  *timeout* = max wait seconds; *ttl* = lock expiry."""
        r = self._get_redis()
        key = f"{LOCK_PREFIX}{self.name}"
        deadline = time.monotonic() + timeout
        token = str(uuid.uuid4())
        while time.monotonic() < deadline:
            ok = await r.set(key, token, nx=True, ex=int(ttl))
            if ok:
                self._token = token
                return True
            await asyncio_sleep(0.1)
        return False

    async def release(self) -> bool:
        """Release the lock (only if we still hold it).

        Uses GET+DELETE instead of Lua for fakeredis compatibility.
        There is a small race window between GET and DEL, but this is
        acceptable for our use case (non-critical lock, TTL provides safety).
        """
        if self._token is None:
            return False
        r = self._get_redis()
        key = f"{LOCK_PREFIX}{self.name}"
        current = await r.get(key)
        if current == self._token:
            await r.delete(key)
            self._token = None
            return True
        self._token = None
        return False


async def asyncio_sleep(seconds: float) -> None:
    """Small helper to avoid importing asyncio at module level."""
    import asyncio
    await asyncio.sleep(seconds)


# ── Rate limiter (sliding window) ──────────────────────────────────

RATE_PREFIX = "rate:"


class RateLimiter:
    """Sliding-window rate limiter using a Redis sorted set.

    Usage::

        limiter = RateLimiter(redis=r)
        allowed = await limiter.is_allowed("user:123", max_requests=60, window_seconds=60)
    """

    def __init__(self, *, redis: aioredis.Redis | None = None):
        self._redis = redis

    def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            raise RuntimeError("Redis not set")
        return self._redis

    async def is_allowed(
        self,
        key: str,
        *,
        max_requests: int = 60,
        window_seconds: int = 60,
    ) -> bool:
        """Check if the request is within rate limit.  Returns True if allowed."""
        r = self._get_redis()
        now = time.time()
        window_start = now - window_seconds
        k = f"{RATE_PREFIX}{key}"

        # Remove old entries outside the window
        await r.zremrangebyscore(k, 0.0, window_start)
        # Count current entries BEFORE adding this request
        current_count = await r.zcard(k)
        # Check if we would exceed the limit
        if current_count >= max_requests:
            return False
        # Add current request (use unique member to avoid zadd overwriting)
        member = f"{now}:{uuid.uuid4().hex[:8]}"
        await r.zadd(k, {member: now})
        # Set expiry on the key
        try:
            await r.expire(k, window_seconds)
        except Exception:
            pass  # Non-critical
        return True
