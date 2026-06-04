"""OPA HTTP 客户端：POST /v1/data/{policy_path}。"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


def query_opa_allow(
    settings: Settings,
    *,
    input_payload: dict[str, Any],
) -> tuple[bool | None, dict[str, Any] | None, str | None]:
    """查询 OPA allow 决策。

    Returns:
        (allow, result_dict, error_message)
        allow=None 表示 OPA 不可用或解析失败（由 fail_open 决定是否拦截）。
    """
    if not settings.opa_enabled:
        return None, None, None

    base = (settings.opa_url or "").rstrip("/")
    path = (settings.opa_policy_path or "rag/allow").strip("/")
    url = f"{base}/v1/data/{path}"

    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.post(url, json={"input": input_payload})
            resp.raise_for_status()
            body = resp.json()
    except Exception as exc:
        logger.warning("OPA query failed: %s", exc)
        return None, None, str(exc)

    result = body.get("result") if isinstance(body, dict) else None
    if not isinstance(result, dict):
        return None, body if isinstance(body, dict) else None, "invalid OPA response"

    allow = result.get("allow")
    if allow is None and "allow" in result:
        allow = result["allow"]
    if isinstance(allow, bool):
        return allow, result, None
    return None, result, "missing allow field"
