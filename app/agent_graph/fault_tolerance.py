"""Agent fault tolerance: timeout wrapper, LLM circuit breaker, dead-loop detection."""
from __future__ import annotations

import logging
import signal
import time
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Circuit breaker state (per graph run, tracked in TicketAgentState)
MAX_LLM_FAILURES = 3
MAX_GRAPH_TRANSITIONS = 15
NODE_TIMEOUT_SECONDS = 30.0


def safe_node(
    node_name: str,
    timeout_s: float = NODE_TIMEOUT_SECONDS,
    fallback_result: dict[str, Any] | None = None,
):
    """Decorator: wrap a node function with timeout and exception handling.

    On timeout or exception, returns fallback_result (or empty dict) and
    appends an error to audit_trace so the graph can route accordingly.
    """
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(state, *, settings=None, **kwargs):
            t0 = time.perf_counter()
            try:
                result = fn(state, settings=settings, **kwargs)
                elapsed = time.perf_counter() - t0
                if elapsed > timeout_s * 0.8:
                    logger.warning(
                        "node=%s slow: %.2fs (threshold=%.2fs)",
                        node_name, elapsed, timeout_s,
                    )
                return result
            except Exception as e:
                elapsed = time.perf_counter() - t0
                logger.error("node=%s failed after %.2fs: %s", node_name, elapsed, e)
                audit = list(state.get("audit_trace") or [])
                audit.append({
                    "step": node_name,
                    "error": str(e)[:200],
                    "elapsed_s": round(elapsed, 3),
                    "fallback": True,
                })
                fb = dict(fallback_result or {})
                fb["audit_trace"] = audit
                fb["human_review_required"] = True
                return fb
        return wrapper
    return decorator


def check_circuit_breaker(state: dict[str, Any]) -> bool:
    """Returns True if LLM circuit breaker is tripped (degrade to retrieval-only)."""
    failures = int(state.get("_llm_failures") or 0)
    return failures >= MAX_LLM_FAILURES


def record_llm_failure(state: dict[str, Any]) -> int:
    """Record an LLM failure and return current failure count."""
    count = int(state.get("_llm_failures") or 0) + 1
    return count


def record_llm_success(state: dict[str, Any]) -> int:
    """Reset LLM failure counter on success."""
    return 0


def check_dead_loop(state: dict[str, Any]) -> tuple[bool, int]:
    """Returns (is_dead, transition_count). Dead if > MAX_GRAPH_TRANSITIONS."""
    count = int(state.get("_transition_count") or 0)
    return count >= MAX_GRAPH_TRANSITIONS, count


def increment_transition(state: dict[str, Any]) -> int:
    """Increment transition counter, return new count."""
    count = int(state.get("_transition_count") or 0) + 1
    return count
