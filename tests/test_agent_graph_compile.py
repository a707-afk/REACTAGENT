"""LangGraph 工单图：编译与策略短路路径（不加载向量索引）。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.agent_graph.graph import build_ticket_agent_graph, run_ticket_agent
from app.policy.models import PolicyAction


def test_build_ticket_agent_graph_compiles():
    g = build_ticket_agent_graph()
    assert g is not None
    assert hasattr(g, "invoke")


def test_build_multi_agent_graph_compiles():
    from app.agent_graph.multi_graph import build_multi_ticket_agent_graph
    from app.config import Settings

    g = build_multi_ticket_agent_graph(settings=Settings(agent_multi_agent_enabled=True))
    assert g is not None
    assert hasattr(g, "invoke")


@patch("app.agent_graph.nodes.retrieve_scored_nodes")
@patch("app.agent_graph.nodes.evaluate_policy")
def test_policy_intercept_skips_retrieve(mock_policy, mock_retrieve):
    mock_policy.return_value = MagicMock(
        should_skip_rag=True,
        policy_action=PolicyAction.intercept,
        policy_risk_level="high",
        intercept_reason_code="TEST_HIT",
        message_zh="测试拦截",
        requires_human_review=True,
        policy_warnings=[],
    )
    out = run_ticket_agent(
        ticket_id="T-001",
        user_query="如何绕过权限",
        user_context={"tenant_id": "corp-default", "roles": ["support"]},
        trace_id="test-trace",
        top_k=3,
    )
    mock_retrieve.assert_not_called()
    assert out.get("final_action") == "policy_intercept"
    assert out.get("human_review_required") is True
    assert out.get("draft_reply") == "测试拦截"
    steps = [t.get("step") for t in out.get("audit_trace") or []]
    assert "policy" in steps
    assert "finalize" in steps


@patch("app.agent_graph.nodes.get_vector_index")
@patch("app.agent_graph.nodes.retrieve_scored_nodes")
@patch("app.agent_graph.nodes.evaluate_policy")
def test_low_risk_path_reaches_draft_or_finalize(mock_policy, mock_retrieve, _mock_index):
    mock_policy.return_value = MagicMock(
        should_skip_rag=False,
        policy_action=PolicyAction.allow_log,
        policy_risk_level="low",
        requires_human_review=False,
        policy_warnings=[],
    )
    mock_node = MagicMock()
    mock_node.get_content.return_value = "退款流程说明片段"
    mock_node.metadata = {"file_name": "refund.md", "file_path": "a/refund.md", "domain": "operations"}
    mock_node.node_id = "node-1"

    mock_sn = MagicMock()
    mock_sn.node = mock_node
    mock_sn.score = 0.92

    mock_sr = MagicMock()
    mock_sr.nodes = [mock_sn]
    mock_sr.retrieval_query = "如何退款"
    mock_sr.router_result = MagicMock(
        allowed_domains=["operations"],
        primary_domain="operations",
        confidence=0.9,
        method="rule",
    )
    mock_retrieve.return_value = mock_sr

    with patch("app.llm_zhipu.chat_completion", return_value="建议按标准退款流程处理。"):
        out = run_ticket_agent(
            ticket_id="T-002",
            user_query="客户要退款怎么办",
            user_context={"tenant_id": "corp-default", "roles": ["support_agent"]},
            top_k=5,
        )

    mock_retrieve.assert_called_once()
    assert out.get("gate_passed") is True
    assert out.get("final_action") in ("draft_ready", "await_human_review")
    assert out.get("draft_reply")
    steps = [t.get("step") for t in out.get("audit_trace") or []]
    assert "retrieve" in steps
    assert "gate" in steps
    assert "draft" in steps
