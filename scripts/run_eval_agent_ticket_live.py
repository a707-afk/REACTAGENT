"""工单 Agent 真实联调评测（Chroma 企业索引 + 真实 policy/retrieve/gate，LLM 可占位）。

用法（仓库根目录，与 access eval 相同企业索引变量）::

    set DOCS_DIR=data/docs/enterprise_ai_ops
    set QDRANT_COLLECTION_NAME=enterprise_ai_ops
    set BM25_CORPUS_PATH=data/bm25_enterprise_corpus.jsonl
    python scripts/run_eval_agent_ticket_live.py

环境变量::

    AGENT_EVAL_GOLDEN=data/eval_agent_ticket.jsonl
    AGENT_LIVE_CASE_IDS=AT-001,AT-005,AT-011,AT-014,AT-015
    AGENT_LIVE_OUT_JSON=docs/eval_agent_ticket_live.json
    AGENT_LIVE_OUT_MD=docs/AGENT-TICKET-LIVE-EVAL.md
    EVAL_ENTERPRISE_STRICT=1

缺索引或向量加载失败时 exit 2 并打印前置条件。
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

# 策略拦截金标依赖 mock_policy；live 默认用企业 KB 可复现的检索路径用例
_DEFAULT_LIVE_IDS = ("AT-005", "AT-011", "AT-014", "AT-015")
_ENTERPRISE_SLUG = "enterprise_ai_ops"


def _relative_to_repo(path: Path) -> str:
    ap = path.resolve()
    br = ROOT.resolve()
    try:
        return str(ap.relative_to(br))
    except ValueError:
        return str(ap)


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


def _audit_steps(result: dict) -> list[str]:
    return [str(t.get("step") or "") for t in (result.get("audit_trace") or [])]


def _check_case(result: dict, expect: dict) -> list[str]:
    errors: list[str] = []
    fa = result.get("final_action")
    if expect.get("final_action") and fa != expect["final_action"]:
        errors.append(f"final_action: got {fa!r}, want {expect['final_action']!r}")

    steps = _audit_steps(result)
    for req in expect.get("audit_steps") or []:
        if req not in steps:
            errors.append(f"missing audit step: {req!r} (have {steps})")

    return errors


def _preflight_index() -> str | None:
    """Return error message if index unavailable."""
    from app.config import get_settings

    settings = get_settings()
    if _env_truthy("EVAL_ENTERPRISE_STRICT") or _env_truthy("EVAL_STRICT_ENTERPRISE"):
        docs = str(Path(settings.docs_dir).resolve()).lower()
        coll = (settings.qdrant_collection_name or "").strip().lower()
        if _ENTERPRISE_SLUG not in docs and coll != _ENTERPRISE_SLUG:
            return (
                "企业索引未对齐：请设置 DOCS_DIR=data/docs/enterprise_ai_ops 且 "
                "QDRANT_COLLECTION_NAME=enterprise_ai_ops，并运行 python scripts/reindex.py"
            )
    try:
        from app.vector_index import get_vector_index

        get_vector_index()
    except RuntimeError as e:
        return f"向量索引不可用: {e}"
    except Exception as e:
        return f"加载向量索引失败: {e}"
    return None


def _run_one_case(case: dict) -> dict:
    from app.agent.harness import run_agent_harness as run_ticket_agent

    try:
        out = run_ticket_agent(
            ticket_id=str(case.get("ticket_id") or case.get("id") or "T-live"),
            user_query=str(case.get("user_query") or ""),
            user_context=dict(case.get("user_context") or {}),
            trace_id=f"live-{case.get('id')}",
            top_k=int(case.get("top_k") or 5),
        )
    except Exception as e:
        return {
            "id": case.get("id"),
            "description": case.get("description"),
            "passed": False,
            "errors": [f"runtime: {type(e).__name__}: {e}"],
            "actual": None,
            "expect": case.get("expect"),
        }
    expect = case.get("expect") or {}
    errors = _check_case(out, expect)
    return {
        "id": case.get("id"),
        "description": case.get("description"),
        "ticket_id": case.get("ticket_id"),
        "user_query": case.get("user_query"),
        "expect": expect,
        "actual": {
            "final_action": out.get("final_action"),
            "human_review_required": out.get("human_review_required"),
            "gate_passed": out.get("gate_passed"),
            "gate_error_code": out.get("gate_error_code"),
            "audit_steps": _audit_steps(out),
            "retrieval_query": out.get("retrieval_query"),
            "hits": len(out.get("retrieved_chunks") or []),
        },
        "passed": not errors,
        "errors": errors,
    }


def main() -> int:
    golden = Path(os.getenv("AGENT_EVAL_GOLDEN", "data/eval_agent_ticket.jsonl"))
    if not golden.is_absolute():
        golden = ROOT / golden
    out_json = ROOT / os.getenv(
        "AGENT_LIVE_OUT_JSON", "docs/eval_agent_ticket_live.json"
    )
    out_md = ROOT / os.getenv("AGENT_LIVE_OUT_MD", "docs/AGENT-TICKET-LIVE-EVAL.md")

    ids_raw = os.getenv("AGENT_LIVE_CASE_IDS", ",".join(_DEFAULT_LIVE_IDS))
    live_ids = {x.strip() for x in ids_raw.split(",") if x.strip()}

    if not golden.is_file():
        print(f"Missing golden: {golden}", file=sys.stderr)
        return 2

    preflight_err = _preflight_index()
    if preflight_err:
        print("BLOCKER (exit 2):", preflight_err, file=sys.stderr)
        print(
            "\n前置条件:\n"
            "  1. conda activate rags（或指定 python.exe）\n"
            "  2. DOCS_DIR=data/docs/enterprise_ai_ops\n"
            "  3. QDRANT_COLLECTION_NAME=enterprise_ai_ops\n"
            "  4. BM25_CORPUS_PATH=data/bm25_enterprise_corpus.jsonl\n"
            "  5. python scripts/reindex.py\n"
            "  6. 可选 ZHIPUAI_API_KEY（draft 占位可缺 Key）",
            file=sys.stderr,
        )
        return 2

    all_cases: list[dict] = []
    for line in golden.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            all_cases.append(json.loads(line))

    cases = [c for c in all_cases if c.get("id") in live_ids]
    missing_ids = live_ids - {c.get("id") for c in cases}
    if missing_ids:
        print(f"Warning: unknown case ids: {sorted(missing_ids)}", file=sys.stderr)

    if not cases:
        print("No live cases selected.", file=sys.stderr)
        return 2

    from app.config import get_settings

    settings = get_settings()
    results = [_run_one_case(c) for c in cases]
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    failed = [r for r in results if not r["passed"]]

    summary = {
        "mode": "live",
        "golden": _relative_to_repo(golden),
        "case_ids": sorted(live_ids),
        "vector_backend": settings.vector_backend,
        "qdrant_collection": settings.qdrant_collection_name,
        "docs_dir": str(Path(settings.docs_dir).resolve()),
        "total": total,
        "passed": passed,
        "failed": len(failed),
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "failed_ids": [r["id"] for r in failed],
        "python": sys.executable,
        "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    payload = {"summary": summary, "results": results}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    iso_now = summary["run_utc"]
    md_lines = [
        "# Agent ticket live eval",
        "",
        f"- **Run date (UTC)**: {iso_now}",
        "- **Command**: `python scripts/run_eval_agent_ticket_live.py`",
        f"- **Golden subset**: `{summary['case_ids']}`",
        "- **Mode**: 真实 `run_ticket_agent`（policy + Chroma retrieve + gate；LLM 失败时用占位草稿）",
        "",
        "## 前置条件",
        "",
        "| 项 | 说明 |",
        "|----|------|",
        "| 索引 | `DOCS_DIR` + `QDRANT_COLLECTION_NAME=enterprise_ai_ops` + `reindex.py` |",
        "| 校验 | 建议 `EVAL_ENTERPRISE_STRICT=1` |",
        "| 智谱 | 可选；无 Key 时 `draft_ready` 路径仍可有占位 `draft_reply` |",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total cases | {total} |",
        f"| Passed | {passed} |",
        f"| Failed | {len(failed)} |",
        f"| Pass rate | {summary['pass_rate']:.2%} |",
        "",
        "### Failed cases",
        "",
    ]
    if failed:
        for r in failed:
            md_lines.append(f"- **{r['id']}**: {'; '.join(r['errors'])}")
    else:
        md_lines.append("(none)")

    md_lines.extend(
        [
            "",
            f"Full JSON: `{_relative_to_repo(out_json)}`.",
            "",
            "> 检索分与金标 mock 分不一致时，`gate_fail` / `no_evidence` 可能偏离金标；可对照 `actual.hits` 与日志 `event=retrieve|gate`。",
            "",
        ]
    )
    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Wrote {out_json} and {out_md}")
    print(f"pass_rate={summary['pass_rate']} ({passed}/{total})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
