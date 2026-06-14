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
