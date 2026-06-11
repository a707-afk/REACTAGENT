"""Agentic 闭环：Worker 路径、RAG 路径（通过 override）、策略拦截。"""
from __future__ import annotations

import asyncio
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
def test_refund_query_routes_to_worker(mock_policy, mock_retrieve, _idx):
    """退款意图 query → refund_flow worker（不经过 retrieve/gate/grader）。"""
    mock_policy.return_value = _low_risk_policy()

    out = asyncio.run(
        run_ticket_agent(
            ticket_id="T-H01",
            user_query="我要退款",
            user_context={"tenant_id": "corp-default", "roles": ["support_agent"]},
        )
    )

    # Worker now goes through retrieve → gate → grader pipeline
    # (no longer bypasses — Phase 5 evidence chain fix)
    mock_retrieve.assert_called()
    steps = [t.get("step") for t in out.get("audit_trace") or []]
    assert "supervisor" in steps
    assert "draft" in steps
    # Worker reply is still generated (draft_reply set by worker, draft node passes through)
    assert out.get("final_action") is not None


@patch("app.agent_graph.nodes.get_vector_index")
@patch("app.agent_graph.nodes.retrieve_scored_nodes")
@patch("app.agent_graph.nodes.evaluate_policy")
@patch("app.supervisor.router.route_after_supervisor", return_value="retrieve")
def test_rag_pipeline_via_supervisor_override(mock_route, mock_policy, mock_retrieve, _idx):
    """强制走 RAG 路径（override supervisor routing）→ retrieve → gate → draft。"""
    mock_policy.return_value = _low_risk_policy()
    mock_retrieve.return_value = _retrieve_mock()

    with patch("app.llm.chat_completion", return_value="建议按标准退款流程处理。"):
        out = asyncio.run(
            run_ticket_agent(
                ticket_id="T-H02",
                user_query="测试 RAG 路径",
                user_context={"tenant_id": "corp-default", "roles": ["support_agent"]},
            )
        )

    # RAG 路径：retrieve 应该被调用
    mock_retrieve.assert_called_once()
    steps = [t.get("step") for t in out.get("audit_trace") or []]
    assert "retrieve" in steps
    assert out.get("final_action") is not None


@patch("app.agent_graph.nodes.get_vector_index")
@patch("app.agent_graph.nodes.retrieve_scored_nodes")
@patch("app.agent_graph.nodes.evaluate_policy")
def test_exchange_query_routes_to_parallel_worker(mock_policy, mock_retrieve, _idx):
    """换货意图 query → exchange_parallel worker。"""
    mock_policy.return_value = _low_risk_policy()

    out = asyncio.run(
        run_ticket_agent(
            ticket_id="T-H03",
            user_query="我要换货换个尺码",
            user_context={"tenant_id": "corp-default", "roles": ["support_agent"]},
        )
    )

    # Worker now goes through retrieve → gate → grader pipeline
    # (no longer bypasses — Phase 5 evidence chain fix)
    mock_retrieve.assert_called()
    steps = [t.get("step") for t in out.get("audit_trace") or []]
    assert "supervisor" in steps
    assert out.get("final_action") is not None
