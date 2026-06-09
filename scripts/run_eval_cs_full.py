"""Comprehensive evaluation pipeline for CS Agent Backend.

Metrics:
- Retrieval: Precision@K, Recall@K, MRR, NDCG@K
- Domain Router: accuracy
- Latency: p50/p95/p99
- Throughput: QPS
- RAGAS: faithfulness, answer_relevancy, context_precision, context_recall (optional, needs LLM)

Usage:
    python scripts/run_eval_cs_full.py --size full       # All 78K docs
    python scripts/run_eval_cs_full.py --size sample_10k  # 10K doc subset
    python scripts/run_eval_cs_full.py --size sample_1k   # 1K doc subset (fast)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ── Eval Questions (curated to match the CS corpus content) ──

EVAL_QUESTIONS: list[dict[str, Any]] = [
    # Order / Returns
    {"query": "How do I cancel my order?", "domain": "order", "relevant_terms": ["cancel", "order"]},
    {"query": "I want to return a defective product and get a refund", "domain": "returns", "relevant_terms": ["refund", "return"]},
    {"query": "Where is my package? I haven't received it yet", "domain": "delivery", "relevant_terms": ["package", "delivery", "tracking"]},
    {"query": "Can I change my shipping address after placing the order?", "domain": "delivery", "relevant_terms": ["shipping", "address"]},
    # Billing
    {"query": "I was charged twice for the same subscription this month", "domain": "billing", "relevant_terms": ["charged", "duplicate", "billing"]},
    {"query": "How do I update my payment method for the monthly plan?", "domain": "billing", "relevant_terms": ["payment", "update", "card"]},
    {"query": "What is the price difference between Basic and Enterprise plans?", "domain": "sales", "relevant_terms": ["pricing", "plan", "enterprise"]},
    # Account
    {"query": "I forgot my password and can't log in to my account", "domain": "account", "relevant_terms": ["password", "login", "account"]},
    {"query": "How do I delete my account permanently?", "domain": "account", "relevant_terms": ["delete", "account"]},
    # Tech Support
    {"query": "The application keeps crashing when I try to open reports", "domain": "tech_support", "relevant_terms": ["crash", "error", "not working"]},
    {"query": "VPN connection drops every few minutes after the latest update", "domain": "tech_support", "relevant_terms": ["vpn", "connection", "update"]},
    {"query": "My printer is not recognized by the new workstation", "domain": "it_support", "relevant_terms": ["printer", "workstation", "not recognized"]},
    # Outages
    {"query": "Is the service down right now? I can't access anything", "domain": "outages", "relevant_terms": ["down", "outage", "not accessible"]},
    # Feedback
    {"query": "I want to file a complaint about the rude customer service agent", "domain": "feedback", "relevant_terms": ["complaint", "service"]},
    # HR
    {"query": "How do I request time off through the HR portal?", "domain": "hr", "relevant_terms": ["leave", "request", "hr"]},
    # Product Support
    {"query": "How do I set up two-factor authentication on my account?", "domain": "product_support", "relevant_terms": ["setup", "authentication", "2fa"]},
    {"query": "What are the system requirements for installing the desktop client?", "domain": "product_support", "relevant_terms": ["install", "requirements", "desktop"]},
    # General CS
    {"query": "I need to speak to a human agent, this is urgent", "domain": "customer_service", "relevant_terms": ["human", "agent", "urgent"]},
    {"query": "Can I get a callback from your support team?", "domain": "customer_service", "relevant_terms": ["callback", "support"]},
    {"query": "Do you offer discounts for non-profit organizations?", "domain": "sales", "relevant_terms": ["discount", "non-profit"]},
    # ── 中文评测问题 ──
    {"query": "我的包裹到哪了？怎么查物流？", "domain": "delivery", "relevant_terms": ["物流", "包裹", "delivery", "tracking"]},
    {"query": "我忘记密码了，登不上账号怎么办？", "domain": "account", "relevant_terms": ["密码", "登录", "password", "account"]},
    {"query": "软件一直闪退，根本用不了！", "domain": "tech_support", "relevant_terms": ["闪退", "crash", "报错"]},
    {"query": "怎么取消订单？我不想要了", "domain": "order", "relevant_terms": ["取消", "订单", "cancel", "order"]},
    {"query": "我要退货退款，收到的东西是坏的", "domain": "returns", "relevant_terms": ["退货", "退款", "return", "refund"]},
    {"query": "为什么自动扣了我两笔钱？", "domain": "billing", "relevant_terms": ["扣费", "billing", "charge"]},
    {"query": "你们系统是不是崩了？打不开网页", "domain": "outages", "relevant_terms": ["崩", "打不开", "down", "outage"]},
    {"query": "打印机连不上新电脑，驱动装不上", "domain": "it_support", "relevant_terms": ["打印机", "驱动", "printer", "driver"]},
    {"query": "我要投诉你们的客服态度极差", "domain": "feedback", "relevant_terms": ["投诉", "complaint", "态度"]},
    {"query": "有没有企业版优惠？多少钱一年？", "domain": "sales", "relevant_terms": ["企业版", "优惠", "多少钱", "pricing"]},

]


@dataclass
class EvalResult:
    total_queries: int = 0
    retrieval_precision_at_3: float = 0.0
    retrieval_precision_at_5: float = 0.0
    retrieval_recall_at_5: float = 0.0
    mrr: float = 0.0
    domain_accuracy: float = 0.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    throughput_qps: float = 0.0
    failed_queries: int = 0
    detail: list[dict[str, Any]] = field(default_factory=list)


def _judge_relevance(hit_text: str, relevant_terms: list[str]) -> float:
    """Simple keyword overlap relevance judge. Returns 0-1 score."""
    text_lower = hit_text.lower()
    hits = sum(1 for term in relevant_terms if term.lower() in text_lower)
    return min(1.0, hits / max(1, len(relevant_terms)))


def _compute_precision_at_k(relevances: list[float], k: int) -> float:
    """Precision@K: fraction of top-K that are relevant."""
    if not relevances:
        return 0.0
    top_k = relevances[:k]
    return sum(1.0 for r in top_k if r >= 0.5) / max(1, len(top_k))


def _compute_recall_at_k(relevances: list[float], k: int, total_relevant: int = 3) -> float:
    """Recall@K: fraction of total relevant docs found in top-K."""
    if not relevances:
        return 0.0
    top_k = relevances[:k]
    found = sum(1.0 for r in top_k if r >= 0.5)
    return found / max(1, total_relevant)


def _compute_mrr(relevances_per_query: list[list[float]]) -> float:
    """Mean Reciprocal Rank."""
    rr_sum = 0.0
    for rels in relevances_per_query:
        for rank, r in enumerate(rels, start=1):
            if r >= 0.5:
                rr_sum += 1.0 / rank
                break
    return rr_sum / max(1, len(relevances_per_query))


def _compute_ndcg_at_k(relevances: list[float], k: int) -> float:
    """NDCG@K: Normalized Discounted Cumulative Gain."""
    import math
    dcg = sum(
        (2**r - 1) / math.log2(i + 2)
        for i, r in enumerate(relevances[:k])
    )
    ideal = sorted(relevances, reverse=True)[:k]
    idcg = sum(
        (2**r - 1) / math.log2(i + 2)
        for i, r in enumerate(ideal)
    )
    return dcg / max(1e-9, idcg)


def run_eval(settings, size: str = "full") -> EvalResult:
    """Run the full evaluation suite."""
    from app.retrieval_pipeline import retrieve_scored_nodes
    from app.vector_index import get_vector_index
    from app.domain_router import route_domains

    result = EvalResult()

    logger.info("Loading vector index...")
    idx = get_vector_index()
    if idx is None:
        logger.error("Vector index failed to load")
        result.failed_queries = len(EVAL_QUESTIONS)
        return result

    logger.info("Running evaluation on %d questions...", len(EVAL_QUESTIONS))

    queries = EVAL_QUESTIONS
    if size == "sample_1k":
        queries = EVAL_QUESTIONS[:5]
    elif size == "sample_10k":
        queries = EVAL_QUESTIONS[:10]

    latencies: list[float] = []
    relevances_per_query: list[list[float]] = []
    domain_correct = 0
    domain_total = 0

    total_start = time.perf_counter()

    for i, eq in enumerate(queries):
        q = eq["query"]
        logger.info("  [%d/%d] %s", i + 1, len(queries), q[:60])

        try:
            # Retrieval
            t0 = time.perf_counter()
            sr = retrieve_scored_nodes(idx, q, 5, settings)
            latencies.append(time.perf_counter() - t0)

            # Relevance judgment
            relevances: list[float] = []
            for sn in sr.nodes[:5]:
                text = sn.node.get_content()
                rel = _judge_relevance(text, eq.get("relevant_terms", []))
                relevances.append(rel)
            relevances_per_query.append(relevances)

            # Domain router
            rr = route_domains(q, settings)
            expected_domain = eq.get("domain", "")
            if expected_domain and rr.primary_domain:
                domain_total += 1
                if rr.primary_domain == expected_domain:
                    domain_correct += 1

            result.detail.append({
                "query": q,
                "expected_domain": expected_domain,
                "routed_domain": rr.primary_domain,
                "hits": len(sr.nodes),
                "top_score": float(sr.nodes[0].score) if sr.nodes else 0,
                "precision_at_5": round(_compute_precision_at_k(relevances, 5), 3),
                "latency_s": round(latencies[-1], 3),
            })

        except Exception as e:
            logger.error("  FAILED: %s", e)
            result.failed_queries += 1

    total_time = time.perf_counter() - total_start

    # Aggregate metrics
    result.total_queries = len(queries)
    if relevances_per_query:
        all_p3 = [_compute_precision_at_k(r, 3) for r in relevances_per_query]
        all_p5 = [_compute_precision_at_k(r, 5) for r in relevances_per_query]
        all_r5 = [_compute_recall_at_k(r, 5, 3) for r in relevances_per_query]
        result.retrieval_precision_at_3 = sum(all_p3) / len(all_p3)
        result.retrieval_precision_at_5 = sum(all_p5) / len(all_p5)
        result.retrieval_recall_at_5 = sum(all_r5) / len(all_r5)
        result.mrr = _compute_mrr(relevances_per_query)

    if domain_total > 0:
        result.domain_accuracy = domain_correct / domain_total

    if latencies:
        sorted_l = sorted(latencies)
        n = len(sorted_l)
        result.latency_p50 = sorted_l[int(n * 0.50)] if n > 0 else 0
        result.latency_p95 = sorted_l[int(n * 0.95)] if n > 1 else sorted_l[-1]
        result.latency_p99 = sorted_l[int(n * 0.99)] if n > 1 else sorted_l[-1]
        result.throughput_qps = len(queries) / max(total_time, 1e-9)

    return result


def main():
    parser = argparse.ArgumentParser(description="CS Agent Evaluation")
    parser.add_argument("--size", default="full", choices=["full", "sample_10k", "sample_1k"])
    parser.add_argument("--output", default="docs/eval_cs_full.json")
    args = parser.parse_args()

    # Point to CS agent data
    os.environ.setdefault("QDRANT_COLLECTION_NAME", "cs_agent")
    os.environ.setdefault("QDRANT_PATH", "data/qdrant_cs_local")
    os.environ.setdefault("DOCS_DIR", "data/docs_cs")
    os.environ.setdefault("BM25_CORPUS_PATH", "data/bm25_cs_corpus.jsonl")

    from app.config import get_settings
    settings = get_settings()

    logger.info("Collection: %s", settings.qdrant_collection_name)
    logger.info("Documents: %s", settings.docs_dir)
    logger.info("GPU: %s", settings.inference_device)

    result = run_eval(settings, size=args.size)

    # Report
    print()
    print("=" * 60)
    print("  CS Agent Backend — Evaluation Results")
    print("=" * 60)
    print(f"  Queries:          {result.total_queries}")
    print(f"  Failed:           {result.failed_queries}")
    print(f"  Precision@3:      {result.retrieval_precision_at_3:.3f}")
    print(f"  Precision@5:      {result.retrieval_precision_at_5:.3f}")
    print(f"  Recall@5:         {result.retrieval_recall_at_5:.3f}")
    print(f"  MRR:              {result.mrr:.3f}")
    print(f"  Domain Accuracy:  {result.domain_accuracy:.3f}")
    print(f"  Latency p50:      {result.latency_p50:.3f}s")
    print(f"  Latency p95:      {result.latency_p95:.3f}s")
    print(f"  Latency p99:      {result.latency_p99:.3f}s")
    print(f"  Throughput:       {result.throughput_qps:.3f} QPS")
    print("=" * 60)

    # Save detailed results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "config": {"collection": settings.qdrant_collection_name, "size": args.size},
            "summary": {
                "total_queries": result.total_queries,
                "failed": result.failed_queries,
                "precision_at_3": round(result.retrieval_precision_at_3, 4),
                "precision_at_5": round(result.retrieval_precision_at_5, 4),
                "recall_at_5": round(result.retrieval_recall_at_5, 4),
                "mrr": round(result.mrr, 4),
                "domain_accuracy": round(result.domain_accuracy, 4),
                "latency_p50": round(result.latency_p50, 3),
                "latency_p95": round(result.latency_p95, 3),
                "latency_p99": round(result.latency_p99, 3),
                "throughput_qps": round(result.throughput_qps, 3),
            },
            "detail": result.detail,
        }, f, ensure_ascii=False, indent=2)

    logger.info("Results saved to %s", output_path)


if __name__ == "__main__":
    main()
