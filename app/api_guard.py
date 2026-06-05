"""API 鉴权与防护中间件（X-API-Key/Bearer、RPM 限流、请求体大小检查）。"""
from __future__ import annotations

import logging
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_413_REQUEST_ENTITY_TOO_LARGE, HTTP_429_TOO_MANY_REQUESTS

from app.config import get_settings
from app.metrics import record_rate_limit_hit

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {"/health", "/health/ready", "/metrics", "/docs", "/openapi.json", "/redoc"}

_RPM_TRACKER: dict[str, list[float]] = defaultdict(list)


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
                        status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={"detail": f"Request body exceeds {max_body} bytes"},
                    )
            except ValueError:
                pass

        # API Key 鉴权
        auth_enabled = getattr(settings, "api_auth_enabled", False)
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

            if not client_key or client_key not in valid_keys:
                return JSONResponse(
                    status_code=HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid or missing API key"},
                )

        # RPM 限流
        rpm = getattr(settings, "api_rate_limit_rpm", 120)
        if rpm > 0:
            client_ip = request.client.host if request.client else "unknown"
            if not _check_rate_limit(client_ip, rpm):
                record_rate_limit_hit()
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded"},
                )

        return await call_next(request)
