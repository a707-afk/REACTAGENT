"""离线权限评测（检索链路 + access Pre-filter，无 Post-filter 兜底）。

路线图 A：**首个脚本** — 与企业题集拆分，每条样例可自带 ``user_context``。

用法（仓库根目录）::

    python scripts/run_eval_access_control.py

环境变量::

    ACCESS_EVAL_QUESTIONS=data/eval_access_control_questions.jsonl
    ACCESS_EVAL_OUTPUT_JSON=docs/eval_access_control.json
    ACCESS_EVAL_OUTPUT_MD=docs/ACCESS-CONTROL-EVAL.md
    EVAL_ENTERPRISE_STRICT=1          # 默认题库时建议开启，校验 enterprise 索引
    EVAL_STRICT_ENTERPRISE=1          # 未对齐 enterprise_ai_ops 时退出码 2

企业索引对齐（与 run_eval_retrieve.py 一致）::

    DOCS_DIR=data/docs/enterprise_ai_ops
    CHROMA_COLLECTION_NAME=enterprise_ai_ops
    BM25_CORPUS_PATH=data/bm25_enterprise_corpus.jsonl

默认 **``RERANK_ENABLED=true``**（与线上一致）。若在 Windows CPU 上出现进程异常退出，设 **``ACCESS_EVAL_USE_RERANK=false``** 或 **``INFERENCE_DEVICE=cuda``**。混合召回默认 **``HYBRID_SCORE_NORMALIZE=true``**（BM25/向量分归一化后再 merge）。

JSONL 每行示例::

    {"id":"AC01","question":"退款必须人工复核的案例要点是什么？","user_context":{"security_clearance":0},"forbidden_doc_substrings":["case-refund-human-review"],"expected_no_forbidden_top5":true}
    {"id":"AC02","question":"P0 首次响应 SLA？","user_context":{"security_clearance":2},"expect_top1_file_contains":"sla-and-escalation","expected_domain":"ticket_workflow"}

``user_context`` 缺省字段见 ``app.schemas.UserContext``（未写则 tenant 不过滤、clearance=1）。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
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
    """Warn or exit if access eval runs against learning-docs / default rag_kb index."""
    use_enterprise_check = (
        eval_path.name == "eval_access_control_questions.jsonl"
        or _env_truthy("EVAL_ENTERPRISE_STRICT")
    )
    if not use_enterprise_check:
        return
    docs_resolved = str(Path(settings.docs_dir).resolve()).lower()
    coll = (settings.chroma_collection_name or "").strip().lower()
    bm25_resolved = str(Path(settings.bm25_corpus_path).resolve()).lower()
    docs_ok = _ENTERPRISE_SLUG in docs_resolved
    coll_ok = coll == _ENTERPRISE_SLUG
    bm25_ok = (not settings.hybrid_bm25_enabled) or (
        _ENTERPRISE_SLUG in bm25_resolved or "bm25_enterprise" in bm25_resolved
    )
    aligned = docs_ok or coll_ok or (_ENTERPRISE_SLUG in bm25_resolved)
    if aligned:
        return
    print(
        "WARNING: Access-control eval expects the enterprise_ai_ops index only, but "
        "DOCS_DIR / CHROMA_COLLECTION_NAME / BM25_CORPUS_PATH do not clearly target it. "
        "Metrics may be contaminated by learning docs (e.g. 模块6-7, LangGraph学习路线).\n"
        f"  DOCS_DIR (resolved)={Path(settings.docs_dir).resolve()}\n"
        f"  CHROMA_COLLECTION_NAME={settings.chroma_collection_name}\n"
        f"  BM25_CORPUS_PATH (resolved)={Path(settings.bm25_corpus_path).resolve()}\n"
        "Fix: DOCS_DIR=data/docs/enterprise_ai_ops, CHROMA_COLLECTION_NAME=enterprise_ai_ops, "
        "BM25_CORPUS_PATH=data/bm25_enterprise_corpus.jsonl (or reindex with those vars).\n",
        file=sys.stderr,
    )
    if _env_truthy("EVAL_STRICT_ENTERPRISE"):
        sys.exit(2)


def _pool_paths(chunks_meta: list[dict]) -> str:
    return " ".join(
        ((c.get("file_name") or "") + " " + (c.get("file_path") or ""))
        for c in chunks_meta[:EVAL_TOP_K]
    ).lower()


def main() -> None:
    # 默认开启 Rerank；Windows CPU 崩溃时可 ACCESS_EVAL_USE_RERANK=false
    if os.getenv("ACCESS_EVAL_USE_RERANK", "true").strip().lower() in (
        "0",
        "false",
        "no",
    ):
        os.environ["RERANK_ENABLED"] = "false"

    from app.config import get_settings

    get_settings.cache_clear()

    from app.vector_index import clear_index_memory_cache, get_vector_index

    clear_index_memory_cache()
    from app.retrieval_pipeline import retrieve_scored_nodes
    from app.schemas import UserContext

    settings = get_settings()
    eval_path = Path(os.getenv("ACCESS_EVAL_QUESTIONS", "data/eval_access_control_questions.jsonl"))
    if not eval_path.is_absolute():
        eval_path = ROOT / eval_path
    _maybe_warn_enterprise_index_alignment(settings, eval_path)
    if not eval_path.is_file():
        print(f"Missing {eval_path}", file=sys.stderr)
        sys.exit(2)

    out_json = Path(os.getenv("ACCESS_EVAL_OUTPUT_JSON", "docs/eval_access_control.json"))
    if not out_json.is_absolute():
        out_json = ROOT / out_json
    out_md = Path(os.getenv("ACCESS_EVAL_OUTPUT_MD", "docs/ACCESS-CONTROL-EVAL.md"))
    if not out_md.is_absolute():
        out_md = ROOT / out_md

    index = get_vector_index()
    candidate_k = (
        max(EVAL_TOP_K, settings.rerank_candidate_top_k)
        if settings.rerank_enabled
        else EVAL_TOP_K
    )
    vec_retriever = index.as_retriever(similarity_top_k=candidate_k)

    rows_out: list[dict] = []
    n_forbidden = n_forbidden_ok = 0
    n_expect = n_expect_ok = 0
    n_domain = n_domain_ok = 0

    for line in eval_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        q = (obj.get("question") or "").strip()
        if not q:
            continue
        uc_raw = obj.get("user_context") or {}
        uc = UserContext.model_validate(uc_raw)

        scored_vec = vec_retriever.retrieve(q)
        sr = retrieve_scored_nodes(
            index,
            q,
            EVAL_TOP_K,
            settings,
            skip_domain_router=True,
            user_context=uc,
        )
        scored_final = sr.nodes

        chunks_meta = []
        for sn in scored_final:
            meta = dict(sn.node.metadata or {})
            chunks_meta.append(
                {
                    "score": float(sn.score) if sn.score is not None else None,
                    "file_name": meta.get("file_name"),
                    "file_path": meta.get("file_path"),
                    "domain": meta.get("domain"),
                    "security_level": meta.get("security_level"),
                }
            )

        pool = _pool_paths(chunks_meta)

        forbidden = obj.get("forbidden_doc_substrings") or []
        expect_no_fb = bool(obj.get("expected_no_forbidden_top5"))
        forbid_ok = True
        if expect_no_fb and forbidden:
            n_forbidden += 1
            forbid_ok = not any(fs.lower() in pool for fs in forbidden if fs)
            if forbid_ok:
                n_forbidden_ok += 1

        expect_sub = obj.get("expect_top1_file_contains")
        matched = None
        if expect_sub and chunks_meta:
            n_expect += 1
            top = (chunks_meta[0]["file_name"] or "") + " " + (chunks_meta[0]["file_path"] or "")
            matched = expect_sub.lower() in top.lower()
            if matched:
                n_expect_ok += 1

        exp_dom = obj.get("expected_domain")
        dom_ok = None
        if exp_dom is not None and chunks_meta:
            n_domain += 1
            top_d = chunks_meta[0].get("domain")
            dom_ok = str(exp_dom).lower() == str(top_d or "").lower()
            if dom_ok:
                n_domain_ok += 1

        rows_out.append(
            {
                "id": obj.get("id"),
                "question": q,
                "user_context": uc.model_dump(),
                "chunks_topk": chunks_meta,
                "forbidden_check_passed": forbid_ok if expect_no_fb and forbidden else None,
                "top1_expect_matched": matched,
                "domain_top1_match": dom_ok,
            }
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "eval_file": str(eval_path.relative_to(ROOT)),
        "vector_backend": settings.vector_backend,
        "qdrant_url": (
            settings.qdrant_url
            if settings.vector_backend == "qdrant" and not settings.qdrant_path
            else None
        ),
        "qdrant_path": settings.qdrant_path if settings.vector_backend == "qdrant" else None,
        "chroma_collection_name": settings.chroma_collection_name,
        "docs_dir": settings.docs_dir,
        "count_rows": len(rows_out),
        "forbidden_top5_checks": {
            "total": n_forbidden,
            "passed": n_forbidden_ok,
            "pass_rate": round(n_forbidden_ok / max(n_forbidden, 1), 4),
        },
        "expect_top1_contains": {
            "total": n_expect,
            "passed": n_expect_ok,
            "pass_rate": round(n_expect_ok / max(n_expect, 1), 4),
        },
        "domain_top1": {
            "total": n_domain,
            "passed": n_domain_ok,
            "pass_rate": round(n_domain_ok / max(n_domain, 1), 4),
        },
        "notes": (
            "forbidden_*：低 clearance 用户在易触发受限文档的问法下，top5 路径不应命中给定子串；"
            "受检索排序噪声影响，请以人工 spot-check bad case。"
        ),
    }

    payload = {"summary": summary, "results": rows_out}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# 权限评测（检索前 Pre-filter）",
        "",
        f"生成时间 UTC：{summary['generated_at']}",
        "",
        "## 摘要",
        "",
        f"- 向量后端：**{summary.get('vector_backend', 'chroma')}**"
        + (
            f"（`qdrant_path={summary.get('qdrant_path')}`）"
            if summary.get("qdrant_path")
            else (
                f"（`qdrant_url={summary.get('qdrant_url')}`）"
                if summary.get("qdrant_url")
                else ""
            )
        ),
        f"- 样例条数：**{summary['count_rows']}**",
        f"- Forbidden top5：**{summary['forbidden_top5_checks']['passed']}/{summary['forbidden_top5_checks']['total']}**（通过率 {summary['forbidden_top5_checks']['pass_rate']}）",
        f"- Expect top1 子串：**{summary['expect_top1_contains']['passed']}/{summary['expect_top1_contains']['total']}**",
        f"- Domain top1：**{summary['domain_top1']['passed']}/{summary['domain_top1']['total']}**",
        "",
        f"明细：`{out_json.relative_to(ROOT)}`",
        "",
        summary["notes"],
        "",
        "## 路线图",
        "",
        "权限逻辑：`app/access_prefilter.py`（向量 Chroma ids + BM25 子集预筛）；规则见 `app/access_control.py`。",
        "",
    ]
    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
