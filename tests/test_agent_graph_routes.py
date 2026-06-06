"""Agentic 闭环：grader 回环、句级 grounding、路由保护。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.agent_graph.graph import run_ticket_agent
from app.agent_graph import nodes
from app.policy.models import PolicyAction


def _low_risk_policy():
    return MagicMock(
        should_skip_rag=False,
        policy_action=PolicyAction.allow_log,
        policy_risk_level="low",
        requires_human_review=False,
        policy_warnings=[],
    )


def _retrieve_mock(*, score: float = 0.92, text: str = "标准退款流程说明"):
    mock_node = MagicMock()
    mock_node.get_content.return_value = text
    mock_node.metadata = {
        "file_name": "refund.md",
        "file_path": "cs/refund.md",
        "domain": "customer_service",
    }
    mock_node.node_id = "n-1"
    mock_sn = MagicMock()
    mock_sn.node = mock_node
    mock_sn.score = score
    mock_sr = MagicMock()
    mock_sr.nodes = [mock_sn]
    mock_sr.retrieval_query = "如何退款"
    mock_sr.router_result = MagicMock(
        allowed_domains=["customer_service"],
        primary_domain="customer_service",
        confidence=0.9,
        method="rule",
    )
    return mock_sr


@patch("app.agent_graph.nodes.get_vector_index")
@patch("app.agent_graph.nodes.retrieve_scored_nodes")
@patch("app.agent_graph.nodes.evaluate_policy")
def test_grader_pass_reaches_hallucination(mock_policy, mock_retrieve, _idx):
    mock_policy.return_value = _low_risk_policy()
    mock_retrieve.return_value = _retrieve_mock()

    with patch("app.llm_zhipu.chat_completion", return_value="建议按标准退款流程处理。"):
        out = run_ticket_agent(
            ticket_id="T-H01",
            user_query="客户要退款怎么办",
            user_context={"tenant_id": "corp-default", "roles": ["support_agent"]},
        )

    steps = [t.get("step") for t in out.get("audit_trace") or []]
    assert out.get("grader_passed") is True
    assert out.get("hallucination_passed") is True
    assert "grader" in steps
    assert "hallucination" in steps
    assert "draft" in steps
    assert out.get("final_action") in ("draft_ready", "await_human_review")


@patch("app.agent_graph.nodes.get_vector_index")
@patch("app.agent_graph.nodes.retrieve_scored_nodes")
@patch("app.agent_graph.nodes.evaluate_policy")
def test_grader_retry_then_finalize_without_draft(mock_policy, mock_retrieve, _idx):
    mock_policy.return_value = _low_risk_policy()
    mock_retrieve.return_value = _retrieve_mock(score=0.25, text="弱相关")

    out = run_ticket_agent(
        ticket_id="T-H02",
        user_query="退款大概要多久",
        user_context={"tenant_id": "corp-default", "roles": ["support_agent"]},
    )

    assert mock_retrieve.call_count == 1
    assert out.get("grader_passed") is not True
    assert out.get("final_action") == "gate_fail"
    assert "draft" not in [t.get("step") for t in out.get("audit_trace") or []]


@patch("app.agent_graph.nodes.get_vector_index")
@patch("app.agent_graph.nodes.retrieve_scored_nodes")
@patch("app.agent_graph.nodes.evaluate_policy")
def test_rewrite_loop_detection(mock_policy, mock_retrieve, _idx):
    mock_policy.return_value = _low_risk_policy()
    mock_retrieve.return_value = _retrieve_mock(score=0.25, text="弱相关")

    with patch.object(nodes, "MAX_AGENT_ITERATIONS", 10):
        with patch(
            "app.agent_graph.nodes.node_rewrite_query",
            side_effect=lambda s, **kw: {
                "iterations": int(s.get("iterations") or 0) + 1,
                "retrieval_query": "固定 query",
                "rewrite_history": ["rewrite:固定 query", "rewrite:固定 query"],
                "loop_detected": True,
                "grader_passed": False,
                "grader_feedback": "loop",
                "human_review_required": True,
                "audit_trace": nodes._append_audit(s, "rewrite_query", {"loop_detected": True}),
            },
        ):
            out = run_ticket_agent(
                ticket_id="T-H03",
                user_query="测试循环",
                user_context={"tenant_id": "corp-default", "roles": ["support"]},
            )

    assert out.get("final_action") == "gate_fail"
    assert "draft" not in [t.get("step") for t in out.get("audit_trace") or []]
