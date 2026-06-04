"""Prometheus /metrics 端点与 HTTP 延迟指标。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_metrics_endpoint_returns_prometheus_text():
    client = TestClient(create_app())
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")
    body = r.text
    assert "rag_http_requests_total" in body or "# HELP rag_http_requests_total" in body


def test_health_records_http_request_metric():
    client = TestClient(create_app())
    client.get("/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert 'endpoint="/health"' in r.text or 'endpoint=\\"/health\\"' in r.text
