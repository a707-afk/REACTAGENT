"""Run end-to-end evaluation suite on the Customer Service Agent corpus.

Runs retrieval evaluation (hybrid search + rerank + domain routing) on the 77K
CS agent corpus using GPU, then generates an eval report.

Usage:
    python scripts/run_cs_eval.py

Before running:
    1. Ensure .env.cs-agent has ZHIPUAI_API_KEY set
    2. Ensure data is indexed: python scripts/reindex_cs.py

Output:
    docs/eval_cs_retrieve.json      (detailed per-question results)
    docs/eval_cs_summary.json       (aggregated metrics)
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Force CS Agent config ──────────────────────────────────────────
os.environ["QDRANT_COLLECTION_NAME"] = "cs_agent"
os.environ["BM25_CORPUS_PATH"] = "data/bm25_cs_corpus.jsonl"
os.environ["QDRANT_PATH"] = "data/qdrant_cs_local"
os.environ["VECTOR_BACKEND"] = "qdrant"
os.environ["INFERENCE_DEVICE"] = "cuda"
os.environ["EVAL_SKIP_DOMAIN_ROUTER"] = "false"
os.environ["DOMAIN_ROUTER_PROFILES_PATH"] = "data/domain_router_profiles_cs.json"
os.environ["DOMAIN_ROUTER_ENHANCED"] = "true"
os.environ["DOMAIN_ROUTER_EMBEDDING_ENABLED"] = "true"

EVAL_TOP_K = 5


def main() -> None:
    from app.config import get_settings
    from app.inference_device import resolve_inference_device
    from app.vector_index import get_vector_index
    from app.retrieval_gates import evaluate_similarity_gate
    from app.retrieval_pipeline import retrieve_scored_nodes

    settings = get_settings()
    print(f"=== CS Agent Evaluation ===")
    print(f"Collection: {settings.qdrant_collection_name}")
    print(f"BM25 path:  {settings.bm25_corpus_path}")
    print(f"Device:     {resolve_inference_device(settings)}")
    print(f"Hybrid:     {settings.hybrid_bm25_enabled} ({settings.hybrid_fusion} k={settings.hybrid_rrf_k})")
    print(f"Rerank:     {settings.rerank_enabled} ({settings.rerank_backend})")
    print(f"Router:     {settings.domain_router_enabled} (enhanced={settings.domain_router_enhanced})")

    eval_path = ROOT / "data" / "eval_cs_questions.jsonl"
    if not eval_path.exists():
        print(f"ERROR: Eval questions not found: {eval_path}")
        sys.exit(1)

    # Load index
    t0 = time.perf_counter()
    index = get_vector_index()
    candidate_k = max(EVAL_TOP_K, settings.rerank_candidate_top_k) if settings.rerank_enabled else EVAL_TOP_K
    vec_retriever = index.as_retriever(similarity_top_k=candidate_k)
    print(f"Index loaded: {time.perf_counter() - t0:.1f}s\n")

    rows_out: list[dict] = []
    expect_total = 0
    expect_hits = 0
    expect_top5_total = 0
    expect_top5_hits = 0
    domain_total = 0
    domain_hits = 0
    gate_passed = 0
    gate_failed = 0
    latencies: list[float] = []

    for line in eval_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        q = obj.get("question", "")
        if not q:
            continue

        t_query = time.perf_counter()
        sr = retrieve_scored_nodes(index, q, EVAL_TOP_K, settings, skip_domain_router=False)
        lat = time.perf_counter() - t_query
        latencies.append(lat)

        scored_final = sr.nodes
        gate = evaluate_similarity_gate(scored_final, settings)
        if gate.passed:
            gate_passed += 1
        else:
            gate_failed += 1

        chunks_meta = []
        for sn in scored_final:
            meta = dict(sn.node.metadata or {})
            chunks_meta.append({
                "score": round(float(sn.score), 4) if sn.score is not None else None,
                "domain": meta.get("domain"),
                "source": meta.get("source"),
                "queue": meta.get("queue"),
                "text_preview": (sn.node.get_content() or "")[:120],
            })

        # Check expectations
        exp_doc = obj.get("expected_doc_contains")
        top1_text = chunks_meta[0]["text_preview"] if chunks_meta else ""
        matched = None
        if exp_doc:
            expect_total += 1
            matched = exp_doc.lower() in top1_text.lower()
            if matched:
                expect_hits += 1

        top5_matched = None
        if exp_doc and chunks_meta:
            expect_top5_total += 1
            pool = " ".join(c["text_preview"] for c in chunks_meta[:5]).lower()
            top5_matched = exp_doc.lower() in pool
            if top5_matched:
                expect_top5_hits += 1

        exp_dom = obj.get("expected_domain")
        top1_dom = chunks_meta[0].get("domain") if chunks_meta else None
        dom_match = None
        if exp_dom:
            domain_total += 1
            dom_match = str(exp_dom).lower() == str(top1_dom or "").lower()
            if dom_match:
                domain_hits += 1

        rows_out.append({
            "id": obj.get("id"),
            "question": q,
            "retrieval_query": sr.retrieval_query,
            "router_trace": {
                "allowed_domains": list(sr.router_result.allowed_domains) if sr.router_result else [],
                "primary_domain": sr.router_result.primary_domain if sr.router_result else None,
                "method": sr.router_result.method if sr.router_result else None,
                "confidence": sr.router_result.confidence if sr.router_result else None,
            } if sr.router_result else None,
            "expected_domain": exp_dom,
            "expected_behavior": obj.get("expected_behavior"),
            "top1_expect_matched": matched,
            "top5_expect_matched": top5_matched,
            "top1_domain": top1_dom,
            "domain_top1_match": dom_match,
            "gate_passed": gate.passed,
            "gate_error_code": gate.error_code,
            "latency_seconds": round(lat, 4),
            "top_hits": chunks_meta,
        })

        status = "✓" if matched else ("~" if top5_matched else "✗")
        print(f"  {status} {obj.get('id')}: {q[:70]}... ({lat:.2f}s)")

    # Summary
    latencies_sorted = sorted(latencies)
    summary = {
        "config": {
            "query_rewrite_mode": settings.query_rewrite_mode,
            "device": resolve_inference_device(settings),
            "hybrid": f"{settings.hybrid_fusion}/k{settings.hybrid_rrf_k}",
            "rerank": settings.rerank_enabled,
            "domain_router": settings.domain_router_enabled,
            "collection": settings.qdrant_collection_name,
        },
        "metrics": {
            "total_questions": len(rows_out),
            "gate_pass_rate": round(gate_passed / (gate_passed + gate_failed), 4) if (gate_passed + gate_failed) else 0,
            "expect_top1_hits": expect_hits,
            "expect_top1_total": expect_total,
            "expect_top1_accuracy": round(expect_hits / expect_total, 4) if expect_total else None,
            "expect_top5_hits": expect_top5_hits,
            "expect_top5_total": expect_top5_total,
            "expect_top5_accuracy": round(expect_top5_hits / expect_top5_total, 4) if expect_top5_total else None,
            "domain_top1_hits": domain_hits,
            "domain_top1_total": domain_total,
            "domain_accuracy": round(domain_hits / domain_total, 4) if domain_total else None,
            "latency_p50": round(latencies_sorted[len(latencies_sorted) // 2], 3) if latencies_sorted else 0,
            "latency_p95": round(latencies_sorted[int(len(latencies_sorted) * 0.95)], 3) if latencies_sorted else 0,
            "latency_p99": round(latencies_sorted[int(len(latencies_sorted) * 0.99)], 3) if latencies_sorted else 0,
            "latency_mean": round(sum(latencies) / len(latencies), 3) if latencies else 0,
        },
    }

    # Write results
    out_path = ROOT / "docs" / "eval_cs_retrieve.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary, "results": rows_out}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_path = ROOT / "docs" / "eval_cs_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Results written to: {out_path}")
    print(f"Summary written to: {summary_path}")
    print(f"\n=== Summary ===")
    print(f"Questions:          {len(rows_out)}")
    print(f"Retrieval Gate:     {gate_passed}/{gate_passed+gate_failed} ({summary['metrics']['gate_pass_rate']:.1%})")
    if expect_total:
        print(f"Top-1 Recall:       {expect_hits}/{expect_total} ({summary['metrics']['expect_top1_accuracy']:.1%})")
    if expect_top5_total:
        print(f"Top-5 Recall:       {expect_top5_hits}/{expect_top5_total} ({summary['metrics']['expect_top5_accuracy']:.1%})")
    if domain_total:
        print(f"Domain Accuracy:    {domain_hits}/{domain_total} ({summary['metrics']['domain_accuracy']:.1%})")
    print(f"Latency p50:        {summary['metrics']['latency_p50']}s")
    print(f"Latency p95:        {summary['metrics']['latency_p95']}s")
    print(f"Latency mean:       {summary['metrics']['latency_mean']}s")


if __name__ == "__main__":
    main()
