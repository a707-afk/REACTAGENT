"""API 鉴权与防护中间件（X-API-Key/Bearer、RPM 限流、请求体大小检查）。"""
from __future__ import annotations

import hmac
import logging
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_413_CONTENT_TOO_LARGE, HTTP_429_TOO_MANY_REQUESTS

from app.config import get_settings
from app.metrics import record_rate_limit_hit

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {"/health", "/health/ready", "/metrics", "/docs", "/openapi.json", "/redoc"}

_RPM_TRACKER: dict[str, list[float]] = defaultdict(list)
_AUTH_FAILURE_TRACKER: dict[str, list[float]] = defaultdict(list)
_redis_limiter = None
_redis_limiter_failed = False

AUTH_FAILURE_MAX = 5  # max auth failures per minute per IP
AUTH_FAILURE_WINDOW = 60.0  # seconds


def _check_rate_limit(client_key: str, rpm: int) -> bool:
    now = time.time()
    window = 60.0
    entries = [t for t in _RPM_TRACKER[client_key] if now - t < window]
    if len(entries) >= rpm:
        return False
    entries.append(now)
    _RPM_TRACKER[client_key] = entries
    return True


class ApiGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        path = request.url.path.rstrip("/")
        settings = get_settings()

        # 公开路径 放行
        if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        # 请求体大小检查
        max_body = getattr(settings, "api_max_body_bytes", 65536)
        if max_body > 0:
            cl = request.headers.get("content-length") or "0"
            try:
                if int(cl) > max_body:
                    return JSONResponse(
                        status_code=HTTP_413_CONTENT_TOO_LARGE,
                        content={"detail": f"Request body exceeds {max_body} bytes"},
                    )
            except ValueError:
                pass

        # Auth failure rate limiting (before auth check)
        client_ip = request.client.host if request.client else "unknown"
        auth_enabled = getattr(settings, "api_auth_enabled", False)
        if auth_enabled:
            now = time.time()
            failures = _AUTH_FAILURE_TRACKER[client_ip]
            failures[:] = [t for t in failures if now - t < AUTH_FAILURE_WINDOW]
            if len(failures) >= AUTH_FAILURE_MAX:
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many authentication failures"},
                )

        # API Key 鉴权
        if auth_enabled:
            valid_keys_str = getattr(settings, "api_keys", "")
            valid_keys = [k.strip() for k in valid_keys_str.split(",") if k.strip()]
            auth_header = request.headers.get("authorization", "")
            client_key = ""
            if auth_header.startswith("Bearer "):
                client_key = auth_header[7:].strip()
            elif auth_header.startswith("X-API-Key "):
                client_key = auth_header[9:].strip()
            else:
                api_key_header = request.headers.get("x-api-key", "")
                if api_key_header:
                    client_key = api_key_header

            if not client_key or not any(
                hmac.compare_digest(client_key, vk) for vk in valid_keys
            ):
                # Record auth failure for rate limiting
                _AUTH_FAILURE_TRACKER[client_ip].append(time.time())
                return JSONResponse(
                    status_code=HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid or missing API key"},
                )

        # RPM 限流 (Redis-first, in-memory fallback)
        rpm = getattr(settings, "api_rate_limit_rpm", 120)
        if rpm > 0:
            client_ip = request.client.host if request.client else "unknown"

            # Try Redis rate limiter
            global _redis_limiter, _redis_limiter_failed
            if not _redis_limiter_failed:
                try:
                    if _redis_limiter is None:
                        from app.redis_client import RateLimiter
                        _redis_limiter = RateLimiter()
                    allowed = await _redis_limiter.is_allowed(
                        f"api:{client_ip}", max_requests=rpm, window_seconds=60
                    )
                    if not allowed:
                        record_rate_limit_hit()
                        return JSONResponse(
                            status_code=HTTP_429_TOO_MANY_REQUESTS,
                            content={"detail": "Rate limit exceeded"},
                        )
                except Exception:
                    _redis_limiter_failed = True
                    logger.debug("Redis rate limiter unavailable, falling back to in-memory")

            # In-memory fallback when Redis is unavailable
            if _redis_limiter_failed and not _check_rate_limit(client_ip, rpm):
                record_rate_limit_hit()
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded"},
                )

        return await call_next(request)
