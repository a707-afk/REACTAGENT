"""Degradation Manager: structured fault handling for every failure mode.

Each failure mode has:
- check() → bool: whether the component is healthy
- degrade(): set degradation level and emit structured log + metrics
- recover(): reset degradation and log recovery

Degradation levels:
- ok: all components healthy
- degraded_retrieval: BM25-only (Qdrant/Embedding down)
- degraded_generation: no LLM (fallback draft only)
- degraded_ingestion: ingestion paused (Embedding unavailable)
- failed_write: write APIs return 503 (Postgres down)
- failed_queue: queue unavailable (Redis down)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class DegradationLevel(str, Enum):
    OK = "ok"
    DEGRADED_RETRIEVAL = "degraded_retrieval"    # BM25-only
    DEGRADED_GENERATION = "degraded_generation"   # No LLM, fallback draft
    DEGRADED_INGESTION = "degraded_ingestion"      # Ingestion paused
    DEGRADED_RERANK = "degraded_rerank"            # Reranker off
    FAILED_WRITE = "failed_write"                  # Postgres down → 503 writes
    FAILED_QUEUE = "failed_queue"                   # Redis down
    FAILED_RETRIEVAL = "failed_retrieval"           # Qdrant down entirely


@dataclass
class ComponentStatus:
    name: str
    healthy: bool = True
    degraded_since: str | None = None
    last_check: str | None = None
    error_message: str | None = None
    metrics_counter: int = 0  # How many times this component has failed


@dataclass
class DegradationReport:
    """Structured degradation report for API responses."""
    level: DegradationLevel
    degraded_components: list[str]
    user_message: str
    timestamp: str
    recommendations: list[str] = field(default_factory=list)


class DegradationManager:
    """Singleton manager for all component degradation states."""

    _instance: DegradationManager | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._components: dict[str, ComponentStatus] = {
            "llm": ComponentStatus(name="llm"),
            "embedding": ComponentStatus(name="embedding"),
            "reranker": ComponentStatus(name="reranker"),
            "qdrant": ComponentStatus(name="qdrant"),
            "redis": ComponentStatus(name="redis"),
            "postgres": ComponentStatus(name="postgres"),
            "tool_executor": ComponentStatus(name="tool_executor"),
            "ocr": ComponentStatus(name="ocr"),
        }
        self._overall_level: DegradationLevel = DegradationLevel.OK

    # ── Public API ──────────────────────────────────────────────────

    @property
    def overall_level(self) -> DegradationLevel:
        return self._overall_level

    def get_status(self, component: str) -> ComponentStatus | None:
        return self._components.get(component)

    def is_healthy(self, component: str) -> bool:
        c = self._components.get(component)
        return c is not None and c.healthy

    def is_any_degraded(self) -> bool:
        return self._overall_level != DegradationLevel.OK

    def check(self, component: str, health_fn: Callable[[], bool]) -> bool:
        """Check component health. Returns True if healthy."""
        c = self._components.get(component)
        if c is None:
            return True

        now = datetime.now(timezone.utc).isoformat()
        c.last_check = now

        try:
            healthy = health_fn()
        except Exception as e:
            healthy = False
            c.error_message = str(e)

        if healthy:
            if not c.healthy:
                self._recover_component(component, c, now)
            c.healthy = True
            return True
        else:
            if c.healthy:
                self._degrade_component(component, c, now)
            c.healthy = False
            c.metrics_counter += 1
            return False

    def degrade(self, component: str, reason: str = "") -> None:
        """Force-degrade a component."""
        c = self._components.get(component)
        if c is None or not c.healthy:
            return
        c.healthy = False
        now = datetime.now(timezone.utc).isoformat()
        c.degraded_since = now
        c.error_message = reason
        c.metrics_counter += 1
        self._recalc_level()
        _log_degradation(component, reason)

    def recover(self, component: str) -> None:
        """Force-recover a component."""
        c = self._components.get(component)
        if c is None or c.healthy:
            return
        c.healthy = True
        c.degraded_since = None
        c.error_message = None
        self._recalc_level()
        _log_recovery(component)

    def get_report(self) -> DegradationReport:
        """Generate a structured degradation report for API responses."""
        degraded = [c.name for c in self._components.values() if not c.healthy]
        msgs = {
            "qdrant": "向量检索暂不可用，正在使用文本检索",
            "llm": "AI 回复暂不可用，将由人工客服处理",
            "redis": "任务队列暂不可用，请稍后重试",
            "postgres": "数据服务暂不可用，请稍后重试",
            "embedding": "文档摄入暂停，检索功能正常",
            "reranker": "智能排序暂不可用，结果可能不够精确",
            "ocr": "图片文字识别暂不可用",
            "tool_executor": "部分业务功能暂不可用",
        }
        user_msg = "; ".join(msgs.get(c, f"{c} 暂不可用") for c in degraded) or "所有服务正常"

        recs = ["请稍后重试"]
        if "qdrant" in degraded:
            recs.append("可用关键词精确搜索")
        if "llm" in degraded:
            recs.append("联系人工客服处理紧急问题")

        return DegradationReport(
            level=self._overall_level,
            degraded_components=degraded,
            user_message=user_msg,
            timestamp=datetime.now(timezone.utc).isoformat(),
            recommendations=recs,
        )

    # ── Internal ─────────────────────────────────────────────────────

    def _degrade_component(self, name: str, c: ComponentStatus, now: str) -> None:
        c.degraded_since = now
        self._recalc_level()
        _log_degradation(name, c.error_message or "unknown")

    def _recover_component(self, name: str, c: ComponentStatus, now: str) -> None:
        c.degraded_since = None
        c.error_message = None
        self._recalc_level()
        _log_recovery(name)

    def _recalc_level(self) -> None:
        """Recalculate overall degradation level from component states."""
        c = self._components
        if not c["postgres"].healthy:
            self._overall_level = DegradationLevel.FAILED_WRITE
        elif not c["redis"].healthy:
            self._overall_level = DegradationLevel.FAILED_QUEUE
        elif not c["qdrant"].healthy:
            self._overall_level = DegradationLevel.FAILED_RETRIEVAL
        elif not c["embedding"].healthy:
            self._overall_level = DegradationLevel.DEGRADED_INGESTION
        elif not c["llm"].healthy:
            self._overall_level = DegradationLevel.DEGRADED_GENERATION
        elif not c["reranker"].healthy:
            self._overall_level = DegradationLevel.DEGRADED_RERANK
        else:
            self._overall_level = DegradationLevel.OK


# ── Helper functions ───────────────────────────────────────────────

def _log_degradation(component: str, reason: str) -> None:
    logger.warning(
        "DEGRADATION_START component=%s reason=%s",
        component, reason,
    )


def _log_recovery(component: str) -> None:
    logger.info("DEGRADATION_END component=%s status=recovered", component)


def get_degradation_manager() -> DegradationManager:
    return DegradationManager()
