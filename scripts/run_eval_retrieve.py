"""将评估 JSONL 批量跑「改写(可选) + 向量 + BM25 → Rerank」并导出分数。

门控阈值应作用在 **重排后的分数** 上；`vector_raw_*` 为用户原问题直检索向量分参照。

用法（在 rag-kb-project 根目录）::

    python scripts/run_eval_retrieve.py

也可用环境变量指定企业评估集::

    $env:EVAL_QUESTIONS_PATH="data/eval_enterprise_questions.jsonl"
    $env:EVAL_OUTPUT_PATH="docs/eval_enterprise_retrieve.json"
    python scripts/run_eval_retrieve.py

当问题集文件名为 ``eval_enterprise_questions.jsonl`` 或设置 ``EVAL_ENTERPRISE_STRICT=1`` 时，
脚本会校验 ``DOCS_DIR``（解析路径含 ``enterprise_ai_ops``）或 ``CHROMA_COLLECTION_NAME`` 为
``enterprise_ai_ops``，若均未对齐则向 stderr 打印 **WARNING**（避免误用默认 ``rag_kb`` / 学习库索引）。
若再设置 ``EVAL_STRICT_ENTERPRISE=1``（或 ``true``），校验失败时 **退出码 2**。

输出：docs/eval_retrieve_autorun.json

改写策略见环境变量 QUERY_REWRITE_MODE；设备见 INFERENCE_DEVICE。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EVAL_TOP_K = 5

_ENTERPRISE_SLUG = "enterprise_ai_ops"


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


def _maybe_warn_enterprise_index_alignment(settings, eval_path: Path) -> None:
    """Warn or exit if enterprise eval may run against the wrong Chroma collection."""
    use_enterprise_check = (
        eval_path.name == "eval_enterprise_questions.jsonl"
        or _env_truthy("EVAL_ENTERPRISE_STRICT")
    )
    if not use_enterprise_check:
        return
    docs_resolved = str(Path(settings.docs_dir).resolve()).lower()
    coll = (settings.chroma_collection_name or "").strip().lower()
    aligned = _ENTERPRISE_SLUG in docs_resolved or coll == _ENTERPRISE_SLUG
    if aligned:
        return
    print(
        "WARNING: Enterprise eval is active but DOCS_DIR / CHROMA_COLLECTION_NAME do not "
        "clearly target the enterprise_ai_ops index. Running against the default rag_kb or "
        "learning-docs corpus will **contaminate** metrics.\n"
        f"  DOCS_DIR (resolved)={Path(settings.docs_dir).resolve()}\n"
        f"  CHROMA_COLLECTION_NAME={settings.chroma_collection_name}\n"
        "Fix: set DOCS_DIR to a path containing 'enterprise_ai_ops' and/or "
        "CHROMA_COLLECTION_NAME=enterprise_ai_ops (and align BM25_CORPUS_PATH when using BM25).\n",
        file=sys.stderr,
    )
    if _env_truthy("EVAL_STRICT_ENTERPRISE"):
        sys.exit(2)


def main() -> None:
    from app.config import get_settings
    from app.inference_device import resolve_inference_device
    from app.index_store import get_vector_index
    from app.retrieval_gates import evaluate_similarity_gate
    from app.retrieval_pipeline import retrieve_scored_nodes

    settings = get_settings()
    eval_path = Path(os.getenv("EVAL_QUESTIONS_PATH", "data/eval_questions.jsonl"))
    if not eval_path.is_absolute():
        eval_path = ROOT / eval_path
    _maybe_warn_enterprise_index_alignment(settings, eval_path)
    out_path = Path(os.getenv("EVAL_OUTPUT_PATH", "docs/eval_retrieve_autorun.json"))
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    rows_out: list[dict] = []
    vector_scores_stats: list[float] = []
    gate_scores_stats: list[float] = []
    expect_total = 0
    expect_hits = 0

    skip_dr = os.getenv("EVAL_SKIP_DOMAIN_ROUTER", "true").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    expect_top5_total = 0
    expect_top5_hits = 0
    domain_total = 0
    domain_hits = 0

    index = get_vector_index()
    candidate_k = (
        max(EVAL_TOP_K, settings.rerank_candidate_top_k)
        if settings.rerank_enabled
        else EVAL_TOP_K
    )
    vec_retriever = index.as_retriever(similarity_top_k=candidate_k)

    for line in eval_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        q = obj.get("question", "")
        if not q:
            continue
        scored_vec = vec_retriever.retrieve(q)
        for sn in scored_vec:
            if sn.score is not None:
                vector_scores_stats.append(float(sn.score))

        sr = retrieve_scored_nodes(
            index,
            q,
            EVAL_TOP_K,
            settings,
            skip_domain_router=skip_dr,
        )
        scored_final = sr.nodes

        chunks_meta = []
        for sn in scored_final:
            if sn.score is not None:
                gate_scores_stats.append(float(sn.score))
            meta = dict(sn.node.metadata or {})
            chunks_meta.append(
                {
                    "score": float(sn.score) if sn.score is not None else None,
                    "file_name": meta.get("file_name"),
                    "file_path": meta.get("file_path"),
                    "domain": meta.get("domain"),
                }
            )
        gate = evaluate_similarity_gate(scored_final, settings)

        expect_sub = obj.get("expect_top1_file_contains") or obj.get(
            "expected_doc_contains"
        )
        top1_name = (chunks_meta[0]["file_name"] or "") if chunks_meta else ""
        top1_path = (chunks_meta[0]["file_path"] or "") if chunks_meta else ""
        matched: bool | None = None
        if expect_sub:
            expect_total += 1
            matched = expect_sub in top1_name or expect_sub in top1_path
            if matched:
                expect_hits += 1

        top5_matched: bool | None = None
        if expect_sub and chunks_meta:
            expect_top5_total += 1
            pool = " ".join(
                (c.get("file_name") or "") + " " + (c.get("file_path") or "")
                for c in chunks_meta[:5]
            )
            top5_matched = expect_sub in pool
            if top5_matched:
                expect_top5_hits += 1

        exp_dom = obj.get("expected_domain")
        top1_dom = chunks_meta[0].get("domain") if chunks_meta else None
        dom_match: bool | None = None
        if exp_dom:
            domain_total += 1
            if top1_dom:
                dom_match = (
                    str(exp_dom).strip().lower() == str(top1_dom).strip().lower()
                )
            else:
                dom_match = False
            if dom_match:
                domain_hits += 1

        rows_out.append(
            {
                "id": obj.get("id"),
                "question": q,
                "retrieval_query": sr.retrieval_query,
                "router_trace": (
                    {
                        "allowed_domains": list(sr.router_result.allowed_domains),
                        "primary_domain": sr.router_result.primary_domain,
                        "method": sr.router_result.method,
                        "confidence": sr.router_result.confidence,
                    }
                    if sr.router_result
                    else None
                ),
                "eval_skip_domain_router": skip_dr,
                "expected_domain": exp_dom,
                "expected_behavior": obj.get("expected_behavior"),
                "expected_doc_contains": expect_sub,
                "top1_expect_matched": matched,
                "top5_expect_matched": top5_matched,
                "top1_domain": top1_dom,
                "domain_top1_match": dom_match,
                "gate_passed": gate.passed,
                "gate_error_code": gate.error_code,
                "ranked_scores_after_gate_metric": gate.ranked_scores,
                "top_hits": chunks_meta,
            }
        )

    summary = {
        "query_rewrite_mode": settings.query_rewrite_mode,
        "inference_device": settings.inference_device,
        "inference_device_resolved": resolve_inference_device(settings),
        "hybrid_bm25_enabled": settings.hybrid_bm25_enabled,
        "bm25_candidate_top_k": settings.bm25_candidate_top_k,
        "rerank_enabled": settings.rerank_enabled,
        "rerank_backend": settings.rerank_backend,
        "rerank_model": settings.rerank_model,
        "rerank_candidate_top_k": settings.rerank_candidate_top_k,
        "eval_output_top_k": EVAL_TOP_K,
        "retrieval_similarity_threshold": settings.retrieval_similarity_threshold,
        "retrieval_score_higher_is_better": settings.retrieval_score_higher_is_better,
        "retrieval_gate_enabled": settings.retrieval_gate_enabled,
        "vector_raw_score_count": len(vector_scores_stats),
        "vector_raw_score_min": min(vector_scores_stats) if vector_scores_stats else None,
        "vector_raw_score_max": max(vector_scores_stats) if vector_scores_stats else None,
        "gate_score_count": len(gate_scores_stats),
        "gate_score_min": min(gate_scores_stats) if gate_scores_stats else None,
        "gate_score_max": max(gate_scores_stats) if gate_scores_stats else None,
        "expect_top1_hits": expect_hits,
        "expect_top1_total": expect_total,
        "expect_top1_hit_rate": round(expect_hits / expect_total, 4)
        if expect_total
        else None,
        "expect_top5_hits": expect_top5_hits,
        "expect_top5_total": expect_top5_total,
        "expect_top5_hit_rate": round(expect_top5_hits / expect_top5_total, 4)
        if expect_top5_total
        else None,
        "domain_top1_hits": domain_hits,
        "domain_top1_total": domain_total,
        "domain_top1_hit_rate": round(domain_hits / domain_total, 4)
        if domain_total
        else None,
        "eval_skip_domain_router": skip_dr,
    }
    payload = {"summary": summary, "results": rows_out}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {out_path}")
    if expect_total:
        print(f"expect_top1 命中: {expect_hits}/{expect_total}")
    if expect_top5_total:
        print(f"expect_top5 命中: {expect_top5_hits}/{expect_top5_total}")
    if domain_total:
        print(f"domain top1 命中: {domain_hits}/{domain_total}")


if __name__ == "__main__":
    main()
