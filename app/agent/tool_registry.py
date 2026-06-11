"""Tool Registry: centralized registration, validation, and execution dispatch.

Every tool must be registered with:
- name, description, JSON schema
- side_effect level (read_only | write_internal | external_side_effect)
- required scopes
- timeout, retry policy
- idempotency key builder
- concurrency rule

Execution MUST go through:
    ToolCall → Schema validate → Permission gate → Execute → Result validate → Audit log

Never call execute_tool directly from nodes — always use execute_registered_tool().
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ── Types ──────────────────────────────────────────────────────────

class SideEffect(Enum):
    READ_ONLY = "read_only"
    WRITE_INTERNAL = "write_internal"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"


class RiskLevel(Enum):
    LOW = "low"        # read_only: auto-execute
    MEDIUM = "medium"  # write_internal: auto-execute + audit
    HIGH = "high"      # create_ticket, issue_refund: need scope/HITL
    CRITICAL = "critical"  # delete, export: deny or HITL


@dataclass
class ToolDef:
    """Complete tool definition."""
    name: str
    description: str
    schema: dict[str, Any]
    side_effect: SideEffect = SideEffect.READ_ONLY
    risk_level: RiskLevel = RiskLevel.LOW
    required_scopes: list[str] = field(default_factory=list)
    timeout_seconds: float = 30.0
    max_retries: int = 1
    idempotency_window_seconds: int = 300

    # Implementation
    handler: Callable | None = None
    mock_handler: Callable | None = None

    # Eval fixtures
    eval_fixtures: list[dict] = field(default_factory=list)

    def build_idempotency_key(self, params: dict[str, Any]) -> str:
        """Build an idempotency key from tool name + sorted params."""
        canonical = json.dumps(params, sort_keys=True, ensure_ascii=False)
        raw = f"{self.name}:{canonical}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class ToolCallResult:
    """Result of a tool execution."""
    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    latency_ms: float = 0.0
    idempotency_key: str | None = None
    permission_denied: bool = False
    permission_reason: str | None = None


# ── Registry ───────────────────────────────────────────────────────

class ToolRegistry:
    """Central registry for all agent tools."""

    def __init__(self):
        self._tools: dict[str, ToolDef] = {}
        # In-memory fallback when Redis is unavailable
        self._idempotency_cache: dict[str, ToolCallResult] = {}
        self._redis_enabled: bool = True

    def register(self, tool: ToolDef) -> None:
        """Register a tool definition."""
        if tool.name in self._tools:
            logger.warning("Overwriting registered tool: %s", tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDef | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self, risk_filter: RiskLevel | None = None) -> list[ToolDef]:
        """List all tools, optionally filtered by risk level."""
        tools = list(self._tools.values())
        if risk_filter:
            tools = [t for t in tools if t.risk_level == risk_filter]
        return tools

    def validate_params(self, tool_name: str, params: dict[str, Any]) -> list[str]:
        """Validate parameters against the tool's JSON schema. Returns list of errors."""
        tool = self._tools.get(tool_name)
        if tool is None:
            return [f"Unknown tool: {tool_name}"]

        schema = tool.schema
        required = schema.get("function", {}).get("parameters", {}).get("required", [])
        properties = schema.get("function", {}).get("parameters", {}).get("properties", {})

        errors = []
        # Check required fields
        for field in required:
            if field not in params:
                errors.append(f"Missing required parameter: {field}")

        # Basic type checks
        for key, value in params.items():
            if key in properties:
                prop = properties[key]
                expected_type = prop.get("type", "string")
                if expected_type == "integer" and not isinstance(value, (int, float)):
                    errors.append(f"Parameter {key} should be integer, got {type(value).__name__}")
                elif expected_type == "string" and not isinstance(value, str):
                    errors.append(f"Parameter {key} should be string, got {type(value).__name__}")

        return errors

    async def execute(
        self,
        tool_name: str,
        params: dict[str, Any],
        *,
        user_context: dict[str, Any] | None = None,
        tenant_id: str = "default",
        skip_permission: bool = False,
    ) -> ToolCallResult:
        """Execute a tool through the full gate pipeline.

        Args:
            tool_name: Name of the tool to execute
            params: Tool parameters
            user_context: User context for permission checking
            tenant_id: Tenant scope
            skip_permission: If True, bypass permission gate (for testing only)

        Returns:
            ToolCallResult with execution outcome
        """
        t0 = time.perf_counter()
        tool = self._tools.get(tool_name)
        if tool is None:
            return ToolCallResult(tool_name, False, error=f"Unknown tool: {tool_name}",
                                  latency_ms=(time.perf_counter() - t0) * 1000)

        # Step 1: Schema validate
        errors = self.validate_params(tool_name, params)
        if errors:
            return ToolCallResult(tool_name, False, error="; ".join(errors),
                                  latency_ms=(time.perf_counter() - t0) * 1000)

        # Step 2: Permission gate
        if not skip_permission:
            from app.agent.permission_gate import check_permission, PermissionResult
            perm: PermissionResult = check_permission(tool, user_context or {}, params, tenant_id)
            if not perm.allowed:
                return ToolCallResult(
                    tool_name, False,
                    error=f"Permission denied: {perm.reason}",
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    permission_denied=True,
                    permission_reason=perm.reason,
                )
            if perm.requires_approval:
                return ToolCallResult(
                    tool_name, False,
                    error="Requires human approval",
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    permission_denied=True,
                    permission_reason="requires_approval",
                )

        # Step 3: Idempotency check (Redis-first, in-memory fallback)
        idem_key = tool.build_idempotency_key(params)
        redis_cache_key = f"idem:{tool_name}:{idem_key}"

        # Try Redis first
        if self._redis_enabled:
            try:
                from app.redis_client import cache_get
                cached_redis = await cache_get(redis_cache_key)
                if cached_redis is not None:
                    logger.info("Redis idempotency cache hit for %s/%s", tool_name, idem_key)
                    return ToolCallResult(
                        tool_name=tool_name,
                        success=cached_redis.get("success", False),
                        data=cached_redis.get("data", {}),
                        error=cached_redis.get("error"),
                        latency_ms=0.0,
                        idempotency_key=idem_key,
                        permission_denied=cached_redis.get("permission_denied", False),
                        permission_reason=cached_redis.get("permission_reason"),
                    )
            except Exception:
                logger.debug("Redis idempotency check failed, falling back to in-memory")

        # In-memory fallback
        if idem_key in self._idempotency_cache:
            cached = self._idempotency_cache[idem_key]
            logger.info("In-memory idempotency cache hit for %s/%s", tool_name, idem_key)
            return cached

        # Step 4: Execute
        handler = tool.handler
        if handler is None:
            return ToolCallResult(tool_name, False, error=f"No handler for tool: {tool_name}",
                                  latency_ms=(time.perf_counter() - t0) * 1000)

        try:
            result = handler(params)
            # If handler is async, await it
            import asyncio
            import inspect
            if inspect.iscoroutine(result):
                result = await asyncio.wait_for(result, timeout=tool.timeout_seconds)
            # If result is a ToolResult (old format), convert
            if hasattr(result, 'success'):
                tr = ToolCallResult(
                    tool_name=tool_name,
                    success=result.success,
                    data=result.data if hasattr(result, 'data') else {},
                    error=result.error if hasattr(result, 'error') else None,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    idempotency_key=idem_key,
                )
            else:
                tr = ToolCallResult(
                    tool_name=tool_name, success=True, data=result if isinstance(result, dict) else {"result": str(result)},
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    idempotency_key=idem_key,
                )
        except asyncio.TimeoutError:
            tr = ToolCallResult(tool_name, False, error=f"Timeout after {tool.timeout_seconds}s",
                                latency_ms=tool.timeout_seconds * 1000)
        except Exception as e:
            logger.exception("Tool %s execution failed", tool_name)
            tr = ToolCallResult(tool_name, False, error=str(e),
                                latency_ms=(time.perf_counter() - t0) * 1000)

        # Step 5: Cache idempotency result (Redis + in-memory fallback)
        self._idempotency_cache[idem_key] = tr
        # Clean old in-memory entries (simple LRU by count)
        if len(self._idempotency_cache) > 1000:
            oldest = list(self._idempotency_cache.keys())[:100]
            for k in oldest:
                del self._idempotency_cache[k]

        # Write to Redis with TTL
        if self._redis_enabled:
            try:
                from app.redis_client import cache_set
                await cache_set(
                    redis_cache_key,
                    {
                        "success": tr.success,
                        "data": tr.data,
                        "error": tr.error,
                        "permission_denied": tr.permission_denied,
                        "permission_reason": tr.permission_reason,
                    },
                    ttl_seconds=tool.idempotency_window_seconds,
                )
            except Exception:
                logger.debug("Redis idempotency write failed (non-critical)")

        return tr

    def clear_idempotency_cache(self) -> None:
        self._idempotency_cache.clear()


# ── Global singleton ───────────────────────────────────────────────

_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_default_tools(_registry)
    return _registry


def _register_default_tools(reg: ToolRegistry) -> None:
    """Register all default e-commerce after-sales tools."""
    from app.agent.tools import (
        TOOL_ORDER_LOOKUP, TOOL_POLICY_CHECK, TOOL_INVENTORY_QUERY,
        TOOL_CREATE_PICKUP, TOOL_TRACK_SHIPMENT, TOOL_CREATE_AFTER_SALE_TICKET,
        _execute_order_lookup, _execute_policy_check, _execute_inventory_query,
        _execute_create_pickup, _execute_track_shipment, _execute_create_after_sale_ticket,
    )

    def _wrap_sync(fn):
        """Wrap a sync function that takes (state, args) into a (params) function."""
        def wrapped(params):
            # The handler now only takes params (state is handled by harness)
            return fn(None, params)
        return wrapped

    reg.register(ToolDef(
        name="order_lookup", description="Look up user orders",
        schema=TOOL_ORDER_LOOKUP,
        side_effect=SideEffect.READ_ONLY, risk_level=RiskLevel.LOW,
        handler=_wrap_sync(_execute_order_lookup), timeout_seconds=10,
    ))
    reg.register(ToolDef(
        name="policy_check", description="Check return/exchange eligibility",
        schema=TOOL_POLICY_CHECK,
        side_effect=SideEffect.READ_ONLY, risk_level=RiskLevel.LOW,
        handler=_wrap_sync(_execute_policy_check), timeout_seconds=10,
    ))
    reg.register(ToolDef(
        name="inventory_query", description="Check inventory availability",
        schema=TOOL_INVENTORY_QUERY,
        side_effect=SideEffect.READ_ONLY, risk_level=RiskLevel.LOW,
        handler=_wrap_sync(_execute_inventory_query), timeout_seconds=10,
    ))
    reg.register(ToolDef(
        name="create_pickup", description="Create pickup for returns",
        schema=TOOL_CREATE_PICKUP,
        side_effect=SideEffect.WRITE_INTERNAL, risk_level=RiskLevel.MEDIUM,
        handler=_wrap_sync(_execute_create_pickup), timeout_seconds=15,
    ))
    reg.register(ToolDef(
        name="track_shipment", description="Track shipment status",
        schema=TOOL_TRACK_SHIPMENT,
        side_effect=SideEffect.READ_ONLY, risk_level=RiskLevel.LOW,
        handler=_wrap_sync(_execute_track_shipment), timeout_seconds=10,
    ))
    reg.register(ToolDef(
        name="create_after_sale_ticket", description="Create after-sales ticket",
        schema=TOOL_CREATE_AFTER_SALE_TICKET,
        side_effect=SideEffect.WRITE_INTERNAL, risk_level=RiskLevel.HIGH,
        required_scopes=["ticket:write"],
        handler=_wrap_sync(_execute_create_after_sale_ticket), timeout_seconds=15,
    ))
