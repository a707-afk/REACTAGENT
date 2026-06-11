"""Tests for Redis client: distributed cache, rate limiter, distributed lock.

Uses fakeredis so no real Redis instance is needed.
"""
from __future__ import annotations

import pytest
import fakeredis.aioredis

from app.redis_client import (
    cache_get,
    cache_set,
    cache_delete,
    DistributedLock,
    RateLimiter,
)


@pytest.fixture
async def fake_redis():
    """Create a fakeredis instance for testing."""
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


# ── Cache tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_set_and_get(fake_redis):
    """Set a value and retrieve it."""
    await cache_set("test_key", {"foo": "bar"}, redis=fake_redis, ttl_seconds=60)
    result = await cache_get("test_key", redis=fake_redis)
    assert result == {"foo": "bar"}


@pytest.mark.asyncio
async def test_cache_get_miss(fake_redis):
    """Getting a non-existent key returns None."""
    result = await cache_get("nonexistent", redis=fake_redis)
    assert result is None


@pytest.mark.asyncio
async def test_cache_delete(fake_redis):
    """Delete a key that exists returns True."""
    await cache_set("to_delete", {"x": 1}, redis=fake_redis, ttl_seconds=60)
    deleted = await cache_delete("to_delete", redis=fake_redis)
    assert deleted is True
    # After deletion, get returns None
    result = await cache_get("to_delete", redis=fake_redis)
    assert result is None


@pytest.mark.asyncio
async def test_cache_delete_nonexistent(fake_redis):
    """Deleting a key that doesn't exist returns False."""
    deleted = await cache_delete("never_existed", redis=fake_redis)
    assert deleted is False


@pytest.mark.asyncio
async def test_cache_overwrite(fake_redis):
    """Setting the same key overwrites the value."""
    await cache_set("key", {"v": 1}, redis=fake_redis, ttl_seconds=60)
    await cache_set("key", {"v": 2}, redis=fake_redis, ttl_seconds=60)
    result = await cache_get("key", redis=fake_redis)
    assert result == {"v": 2}


# ── Distributed lock tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_lock_acquire_and_release(fake_redis):
    """Acquire and release a lock successfully."""
    lock = DistributedLock("resource_1", redis=fake_redis)
    acquired = await lock.acquire(timeout=1.0, ttl=10.0)
    assert acquired is True
    released = await lock.release()
    assert released is True


@pytest.mark.asyncio
async def test_lock_acquire_conflict(fake_redis):
    """Second locker cannot acquire while first holds the lock."""
    lock1 = DistributedLock("resource_2", redis=fake_redis)
    lock2 = DistributedLock("resource_2", redis=fake_redis)

    acquired1 = await lock1.acquire(timeout=0.5, ttl=10.0)
    assert acquired1 is True

    # Second lock should fail (very short timeout)
    acquired2 = await lock2.acquire(timeout=0.1, ttl=10.0)
    assert acquired2 is False

    # Release first lock
    await lock1.release()

    # Now second should succeed
    acquired2 = await lock2.acquire(timeout=1.0, ttl=10.0)
    assert acquired2 is True
    await lock2.release()


@pytest.mark.asyncio
async def test_lock_release_without_acquire(fake_redis):
    """Releasing without acquiring returns False."""
    lock = DistributedLock("resource_3", redis=fake_redis)
    released = await lock.release()
    assert released is False


# ── Rate limiter tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit(fake_redis):
    """Requests within limit are allowed."""
    limiter = RateLimiter(redis=fake_redis)
    for i in range(5):
        allowed = await limiter.is_allowed("user:abc", max_requests=5, window_seconds=60)
        assert allowed is True


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit(fake_redis):
    """Requests over limit are blocked."""
    limiter = RateLimiter(redis=fake_redis)
    for i in range(5):
        allowed = await limiter.is_allowed("user:xyz", max_requests=5, window_seconds=60)
    # 6th request should be blocked
    allowed = await limiter.is_allowed("user:xyz", max_requests=5, window_seconds=60)
    assert allowed is False


@pytest.mark.asyncio
async def test_rate_limiter_per_key_isolation(fake_redis):
    """Different keys have independent rate limits."""
    limiter = RateLimiter(redis=fake_redis)
    # Exhaust user:A limit
    for i in range(5):
        await limiter.is_allowed("user:A", max_requests=5, window_seconds=60)
    # user:A should be blocked
    assert await limiter.is_allowed("user:A", max_requests=5, window_seconds=60) is False
    # user:B should still be allowed
    assert await limiter.is_allowed("user:B", max_requests=5, window_seconds=60) is True
