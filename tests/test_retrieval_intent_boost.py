"""检索意图加权单元测试（不加载向量索引）。"""
from __future__ import annotations

from unittest.mock import MagicMock

from llama_index.core.schema import NodeWithScore, TextNode

from app.config import Settings
from app.retrieval_intent_boost import _infer_intent_rules, apply_retrieval_intent_boost


def _node(path: str, source_type: str, score: float = 0.5) -> NodeWithScore:
    n = TextNode(text="x", metadata={"file_path": path, "source_type": source_type})
    return NodeWithScore(node=n, score=score)


def test_ac07_rule_matches_eval_question():
    q = "prompt injection 常见攻击话术与标准应对要点？"
    rules = _infer_intent_rules(q)
    assert rules is not None
    assert "runbook" in rules.prefer_source_types
    assert "case-prompt-injection" in rules.penalize_path_substrings[0]


def test_ac07_excludes_case_narrative_query():
    q = "prompt injection 案例工单叙事"
    assert _infer_intent_rules(q) is None


def test_ac07_inject_yingdui_pattern():
    q = "注入攻击的应对流程"
    rules = _infer_intent_rules(q)
    assert rules is not None


def test_ac02_prefers_case_over_workflow():
    q = "退款案例中客户拒绝上传日志但仍要求立即退款时，应按照哪个人工复核 playbook？"
    rules = _infer_intent_rules(q)
    assert rules is not None
    assert "incident_narrative" in rules.prefer_source_types
    assert "refund-review-workflow" in rules.penalize_path_substrings[0]


def test_ac28_prefers_scripts_over_spot_check():
    q = "客服质检抽检的话术标准文档入口？"
    rules = _infer_intent_rules(q)
    assert rules is not None
    assert "customer-service-reply-scripts" in rules.prefer_path_substrings
    assert "customer-service-quality-spot-check" in rules.penalize_path_substrings[0]
    assert not rules.prefer_source_types


def test_apply_boost_reorders_top():
    settings = Settings(retrieval_intent_boost_enabled=True)
    merged = [
        _node("07-cases/case-prompt-injection.md", "incident_narrative", 0.62),
        _node("06-security/prompt-injection-response.md", "runbook", 0.60),
    ]
    q = "prompt injection 常见攻击话术与标准应对要点？"
    out = apply_retrieval_intent_boost(merged, q, settings)
    top_path = out[0].node.metadata.get("file_path", "")
    assert "prompt-injection-response" in top_path
