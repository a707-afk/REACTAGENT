"""SSE 流式路由：Content-Type 与 event 格式。"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.policy.models import PolicyAction


def test_chat_stream_headers_and_done_event():
    app = create_app()
    client = TestClient(app)

    mock_pe = MagicMock(
        should_skip_rag=False,
        policy_action=PolicyAction.allow_log,
        policy_risk_level="low",
        requires_human_review=False,
        policy_warnings=[],
        policy_hits=[],
    )

    with patch("app.routes_rag.evaluate_policy", return_value=mock_pe):
        with patch("app.routes_rag.get_vector_index") as mock_idx:
            mock_idx.side_effect = RuntimeError("index not ready")
            r = client.post("/chat/stream", json={"query": "测试问题", "top_k": 3})

    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    body = r.text
    assert "event: error" in body or "event: done" in body


def test_agent_ticket_stream_headers():
    app = create_app()
    client = TestClient(app)

    low_risk = MagicMock(
        should_skip_rag=True,
        policy_action=PolicyAction.intercept,
        policy_risk_level="high",
        requires_human_review=True,
        intercept_reason_code="POLICY_TEST",
        message_zh="策略拦截",
        policy_warnings=[],
    )

    with patch("app.agent_graph.nodes.evaluate_policy", return_value=low_risk):
        r = client.post(
            "/agent/ticket/stream",
            json={
                "ticket_id": "T-SSE-01",
                "user_query": "测试",
                "top_k": 3,
            },
        )

    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    assert "event: step" in r.text
    assert "event: done" in r.text
    done_lines = [ln for ln in r.text.split("\n") if ln.startswith("data:")]
    assert any("final_action" in ln for ln in done_lines)
