"""Prometheus 风格指标；未安装 prometheus_client 时使用内存 stub，/metrics 仍可输出文本。"""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_prometheus_available = False
_registry: Any = None
_REQUESTS: Any = None
_REQUEST_LATENCY: Any = None
_RETRIEVE_LATENCY: Any = None
_CACHE_HITS: Any = None

# 内存 stub
_stub_requests: dict[tuple[str, str, str], int] = {}
_stub_request_latency: list[tuple[str, float]] = []
_stub_retrieve_latency: list[float] = []
_stub_cache_hits: dict[str, int] = {}


def _init_prometheus() -> None:
    global _prometheus_available, _registry, _REQUESTS, _REQUEST_LATENCY
    global _RETRIEVE_LATENCY, _CACHE_HITS
    try:
        from prometheus_client import Counter, Histogram, REGISTRY, generate_latest

        _registry = REGISTRY
        _REQUESTS = Counter(
            "rag_http_requests_total",
            "HTTP requests",
            ["method", "endpoint", "status"],
            registry=REGISTRY,
        )
        _REQUEST_LATENCY = Histogram(
            "rag_http_request_duration_seconds",
            "HTTP request latency",
            ["endpoint"],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
            registry=REGISTRY,
        )
        _RETRIEVE_LATENCY = Histogram(
            "rag_retrieve_duration_seconds",
            "retrieve_scored_nodes latency",
            buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 15.0, 60.0),
            registry=REGISTRY,
        )
        _CACHE_HITS = Counter(
            "rag_cache_hits_total",
            "Retrieval cache hits",
            ["level"],
            registry=REGISTRY,
        )
        _prometheus_available = True
        logger.debug("prometheus_client metrics initialized")
    except ImportError:
        _prometheus_available = False
        logger.debug("prometheus_client not installed; using in-memory metrics stub")


_init_prometheus()


def record_http_request(method: str, endpoint: str, status: int, duration_s: float) -> None:
    ep = endpoint or "unknown"
    st = str(status)
    if _prometheus_available and _REQUESTS is not None:
        _REQUESTS.labels(method=method, endpoint=ep, status=st).inc()
        if _REQUEST_LATENCY is not None:
            _REQUEST_LATENCY.labels(endpoint=ep).observe(duration_s)
        return
    key = (method, ep, st)
    _stub_requests[key] = _stub_requests.get(key, 0) + 1
    _stub_request_latency.append((ep, duration_s))


def record_retrieve_duration(duration_s: float) -> None:
    if _prometheus_available and _RETRIEVE_LATENCY is not None:
        _RETRIEVE_LATENCY.observe(duration_s)
    else:
        _stub_retrieve_latency.append(duration_s)


def record_cache_hit(level: str) -> None:
    lvl = level or "unknown"
    if _prometheus_available and _CACHE_HITS is not None:
        _CACHE_HITS.labels(level=lvl).inc()
        return
    _stub_cache_hits[lvl] = _stub_cache_hits.get(lvl, 0) + 1


class _RetrieveTimer:
    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self.cache_hit = False

    def stop(self) -> float:
        return time.perf_counter() - self._t0


def observe_retrieve(timer: _RetrieveTimer, *, cache_level: str | None = None) -> None:
    record_retrieve_duration(timer.stop())
    if cache_level:
        record_cache_hit(cache_level)


def metrics_text() -> str:
    if _prometheus_available:
        from prometheus_client import generate_latest

        return generate_latest(_registry).decode("utf-8")

    lines: list[str] = []
    lines.append("# HELP rag_http_requests_total HTTP requests (stub)")
    lines.append("# TYPE rag_http_requests_total counter")
    for (method, ep, status), count in sorted(_stub_requests.items()):
        lines.append(
            f'rag_http_requests_total{{method="{method}",endpoint="{ep}",status="{status}"}} {count}'
        )

    lines.append("# HELP rag_http_request_duration_seconds HTTP latency (stub)")
    lines.append("# TYPE rag_http_request_duration_seconds summary")
    by_ep: dict[str, list[float]] = {}
    for ep, d in _stub_request_latency:
        by_ep.setdefault(ep, []).append(d)
    for ep, vals in sorted(by_ep.items()):
        lines.append(
            f'rag_http_request_duration_seconds_sum{{endpoint="{ep}"}} {sum(vals):.6f}'
        )
        lines.append(
            f'rag_http_request_duration_seconds_count{{endpoint="{ep}"}} {len(vals)}'
        )

    lines.append("# HELP rag_retrieve_duration_seconds retrieve latency (stub)")
    lines.append("# TYPE rag_retrieve_duration_seconds summary")
    if _stub_retrieve_latency:
        lines.append(
            f"rag_retrieve_duration_seconds_sum {sum(_stub_retrieve_latency):.6f}"
        )
        lines.append(f"rag_retrieve_duration_seconds_count {len(_stub_retrieve_latency)}")

    lines.append("# HELP rag_cache_hits_total Retrieval cache hits (stub)")
    lines.append("# TYPE rag_cache_hits_total counter")
    for lvl, count in sorted(_stub_cache_hits.items()):
        lines.append(f'rag_cache_hits_total{{level="{lvl}"}} {count}')

    return "\n".join(lines) + "\n"
