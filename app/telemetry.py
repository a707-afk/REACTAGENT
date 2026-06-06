"""OpenTelemetry / Langfuse 可选集成（未配置时 no-op）。"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from app.config import Settings

logger = logging.getLogger(__name__)

_telemetry_initialized = False
_missing_deps_logged = False
_tracer: Any = None
_langfuse: Any = None


def setup_telemetry(settings: Settings | None = None) -> None:
    """应用启动时调用；依赖缺失或开关关闭时静默 no-op。"""
    global _telemetry_initialized, _missing_deps_logged, _tracer, _langfuse

    if _telemetry_initialized:
        return
    _telemetry_initialized = True

    if settings.otel_enabled:
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({"service.name": settings.otel_service_name})
            provider = TracerProvider(resource=resource)
            if settings.otel_exporter_endpoint:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                provider.add_span_processor(
                    BatchSpanProcessor(
                        OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
                    )
                )
            trace.set_tracer_provider(provider)
            _tracer = trace.get_tracer(settings.otel_service_name)
            logger.info(
                "OpenTelemetry enabled (service=%s, endpoint=%s)",
                settings.otel_service_name,
                settings.otel_exporter_endpoint or "none",
            )
        except ImportError:
            if not _missing_deps_logged:
                logger.info(
                    "OTEL_ENABLED=true but opentelemetry SDK not installed; telemetry no-op"
                )
                _missing_deps_logged = True

    if settings.langfuse_enabled and settings.langfuse_public_key and settings.langfuse_secret_key:
        try:
            from langfuse import Langfuse

            _langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            logger.info("Langfuse client initialized (host=%s)", settings.langfuse_host)
        except ImportError:
            if not _missing_deps_logged:
                logger.info(
                    "LANGFUSE_ENABLED=true but langfuse not installed; telemetry no-op"
                )
                _missing_deps_logged = True
        except Exception as exc:
            logger.warning("Langfuse init failed: %s", exc)


@contextmanager
def trace_span(
    name: str,
    trace_id: str | None = None,
    **attrs: Any,
) -> Iterator[None]:
    """最小 span 包装；无 tracer 时 no-op。"""
    if _tracer is not None:
        with _tracer.start_as_current_span(name) as span:
            if trace_id:
                span.set_attribute("trace_id", trace_id)
            for k, v in attrs.items():
                if v is not None:
                    span.set_attribute(str(k), str(v))
            yield
        return
    yield
