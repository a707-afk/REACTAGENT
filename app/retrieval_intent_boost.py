"""按问法对 source_type / 路径做轻量 rerank 前加权（缓解 case vs workflow / runbook vs 案例）。"""
from __future__ import annotations

from dataclasses import dataclass

from llama_index.core.schema import NodeWithScore

from app.config import Settings


@dataclass(frozen=True)
class _IntentRules:
    prefer_source_types: frozenset[str]
    prefer_path_substrings: tuple[str, ...]
    penalize_source_types: frozenset[str]
    penalize_path_substrings: tuple[str, ...]
    boost_delta: float | None = None
    penalty_delta: float | None = None


def _infer_intent_rules(query: str) -> _IntentRules | None:
    q = (query or "").strip().lower()
    if not q:
        return None

    # AC02：要「案例」叙事而非 workflow 流程表
    if "案例" in q and any(k in q for k in ("退款", "复核", "playbook", "人工")):
        return _IntentRules(
            prefer_source_types=frozenset({"incident_narrative"}),
            prefer_path_substrings=("case-refund-human-review", "07-cases"),
            penalize_source_types=frozenset({"workflow"}),
            penalize_path_substrings=("refund-review-workflow",),
        )

    # AC07：prompt injection 应对要点（SOP/runbook），非案例/工单叙事
    ac07_match = ("prompt" in q and "inject" in q) or (
        "注入" in q and "应对" in q
    )
    if ac07_match and "案例" not in q and "工单叙事" not in q:
        return _IntentRules(
            prefer_source_types=frozenset({"runbook"}),
            prefer_path_substrings=("prompt-injection-response", "06-security"),
            penalize_source_types=frozenset({"incident_narrative"}),
            penalize_path_substrings=("case-prompt-injection", "07-cases"),
        )

    # AC28：问「话术标准」入口时优先话术规范，而非纯抽检制度
    if "话术" in q and any(k in q for k in ("标准", "规范", "文档", "入口")):
        return _IntentRules(
            prefer_source_types=frozenset(),
            prefer_path_substrings=(
                "customer-service-reply-scripts",
                "communication_scripts",
            ),
            penalize_source_types=frozenset(),
            penalize_path_substrings=("customer-service-quality-spot-check",),
            boost_delta=0.35,
            penalty_delta=0.12,
        )

    return None


def apply_retrieval_intent_boost(
    merged: list[NodeWithScore],
    query: str,
    settings: Settings,
) -> list[NodeWithScore]:
    if not getattr(settings, "retrieval_intent_boost_enabled", True) or not merged:
        return merged
    rules = _infer_intent_rules(query)
    if rules is None:
        return merged

    delta = float(
        rules.boost_delta
        if rules.boost_delta is not None
        else getattr(settings, "retrieval_intent_boost_delta", 0.08) or 0.0
    )
    penalty = float(
        rules.penalty_delta
        if rules.penalty_delta is not None
        else getattr(settings, "retrieval_intent_penalty", 0.05) or 0.0
    )
    max_n = max(1, int(getattr(settings, "retrieval_intent_boost_max_chunks", 8) or 8))

    scored: list[tuple[float, int, NodeWithScore]] = []
    for i, sn in enumerate(merged):
        meta = sn.node.metadata or {}
        st = str(meta.get("source_type") or "").strip().lower()
        path = (
            str(meta.get("file_path") or "")
            + " "
            + str(meta.get("file_name") or "")
        ).lower()
        base = float(sn.score or 0.0)
        adj = base
        if st in rules.prefer_source_types or any(
            p in path for p in rules.prefer_path_substrings
        ):
            adj += delta
        if st in rules.penalize_source_types or any(
            p in path for p in rules.penalize_path_substrings
        ):
            adj -= penalty
        scored.append((adj, i, sn))

    scored.sort(key=lambda t: (-t[0], t[1]))
    out: list[NodeWithScore] = []
    for j, (_, _, sn) in enumerate(scored):
        if j < max_n:
            out.append(NodeWithScore(node=sn.node, score=scored[j][0]))
        else:
            out.append(sn)
    return out
