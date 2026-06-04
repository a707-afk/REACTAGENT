"""离线评测 LangGraph 工单 Agent 状态机路径（mock policy / retrieve / LLM，不加载向量索引）。

在项目根::

    python scripts/run_eval_agent_ticket.py

环境变量::
    AGENT_EVAL_GOLDEN=data/eval_agent_ticket.jsonl（默认）
    AGENT_EVAL_OUT_JSON=docs/eval_agent_ticket.json
    AGENT_EVAL_OUT_MD=docs/AGENT-TICKET-EVAL.md

验证 ``final_action``、``human_review_required``、``audit_trace`` 步骤与金标一致。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _relative_to_repo(path: Path) -> str:
    ap = path.resolve()
    br = ROOT.resolve()
    try:
        return str(ap.relative_to(br))
    except ValueError:
        return str(ap)


def _policy_mock_from_spec(spec: dict) -> MagicMock:
    from app.policy.models import PolicyAction

    action = spec.get("policy_action", "allow_log")
    if isinstance(action, str):
        try:
            pa = PolicyAction(action)
        except ValueError:
            pa = PolicyAction.allow_log
    else:
        pa = action
    m = MagicMock(
        should_skip_rag=bool(spec.get("should_skip_rag", False)),
        policy_action=pa,
        policy_risk_level=spec.get("policy_risk_level", "low"),
        intercept_reason_code=spec.get("intercept_reason_code"),
        message_zh=spec.get("message_zh"),
        requires_human_review=bool(spec.get("requires_human_review", False)),
        policy_warnings=list(spec.get("policy_warnings") or []),
    )
    return m


def _retrieve_mock_from_spec(spec: dict | None) -> MagicMock:
    spec = spec or {"nodes": []}
    nodes_spec = spec.get("nodes") or []
    scored_nodes: list[MagicMock] = []
    for n in nodes_spec:
        node = MagicMock()
        node.get_content.return_value = str(n.get("text") or "")
        node.metadata = {
            "file_path": n.get("file_path"),
            "file_name": n.get("file_name"),
            "domain": n.get("domain"),
        }
        node.node_id = str(n.get("node_id") or "")
        sn = MagicMock()
        sn.node = node
        sn.score = n.get("score")
        scored_nodes.append(sn)

    rr_spec = spec.get("router_result") or {}
    router_result = MagicMock(
        allowed_domains=list(rr_spec.get("allowed_domains") or []),
        primary_domain=rr_spec.get("primary_domain"),
        confidence=rr_spec.get("confidence", 0.0),
        method=rr_spec.get("method", "mock"),
    )

    sr = MagicMock()
    sr.nodes = scored_nodes
    sr.retrieval_query = spec.get("retrieval_query") or "mock-query"
    sr.router_result = router_result if rr_spec or scored_nodes else None
    return sr


def _audit_steps(result: dict) -> list[str]:
    return [str(t.get("step") or "") for t in (result.get("audit_trace") or [])]


def _check_case(result: dict, expect: dict) -> list[str]:
    errors: list[str] = []
    fa = result.get("final_action")
    if expect.get("final_action") and fa != expect["final_action"]:
        errors.append(f"final_action: got {fa!r}, want {expect['final_action']!r}")

    if "human_review_required" in expect:
        hr = bool(result.get("human_review_required"))
        if hr != bool(expect["human_review_required"]):
            errors.append(
                f"human_review_required: got {hr}, want {expect['human_review_required']}"
            )

    steps = _audit_steps(result)
    for req in expect.get("audit_steps") or []:
        if req not in steps:
            errors.append(f"missing audit step: {req!r} (have {steps})")

    for forbidden in expect.get("forbidden_steps") or []:
        if forbidden in steps:
            errors.append(f"forbidden audit step present: {forbidden!r}")

    return errors


def _run_one_case(case: dict) -> dict:
    from app.agent_graph.graph import run_ticket_agent

    policy_spec = case.get("mock_policy") or {}
    retrieve_spec = case.get("mock_retrieve")
    llm_reply = case.get("mock_llm_reply") or "【mock 草稿】依据知识片段回复。"

    policy_mock = _policy_mock_from_spec(policy_spec)
    retrieve_mock = _retrieve_mock_from_spec(retrieve_spec)

    patches = [
        patch("app.agent_graph.nodes.evaluate_policy", return_value=policy_mock),
        patch("app.agent_graph.nodes.retrieve_scored_nodes", return_value=retrieve_mock),
        patch("app.agent_graph.nodes.get_vector_index", return_value=MagicMock()),
        patch("app.llm_zhipu.chat_completion", return_value=llm_reply),
    ]

    for p in patches:
        p.start()
    try:
        out = run_ticket_agent(
            ticket_id=str(case.get("ticket_id") or case.get("id") or "T-mock"),
            user_query=str(case.get("user_query") or ""),
            user_context=dict(case.get("user_context") or {}),
            trace_id=f"eval-{case.get('id')}",
            top_k=int(case.get("top_k") or 5),
        )
    finally:
        for p in patches:
            p.stop()

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
        },
        "passed": not errors,
        "errors": errors,
    }


def main() -> int:
    golden = Path(os.getenv("AGENT_EVAL_GOLDEN", "data/eval_agent_ticket.jsonl"))
    if not golden.is_absolute():
        golden = ROOT / golden
    out_json = ROOT / os.getenv("AGENT_EVAL_OUT_JSON", "docs/eval_agent_ticket.json")
    out_md = ROOT / os.getenv("AGENT_EVAL_OUT_MD", "docs/AGENT-TICKET-EVAL.md")

    if not golden.is_file():
        print(f"Missing golden: {golden}", file=sys.stderr)
        return 2

    cases: list[dict] = []
    for line in golden.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        cases.append(json.loads(line))

    results = [_run_one_case(c) for c in cases]
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    by_action: dict[str, int] = {}
    for r in results:
        fa = (r.get("actual") or {}).get("final_action") or "unknown"
        by_action[fa] = by_action.get(fa, 0) + 1

    failed = [r for r in results if not r["passed"]]

    summary = {
        "golden": _relative_to_repo(golden),
        "total": total,
        "passed": passed,
        "failed": len(failed),
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "by_final_action": by_action,
        "failed_ids": [r["id"] for r in failed],
        "python": sys.executable,
        "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    payload = {"summary": summary, "results": results}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    iso_now = summary["run_utc"]
    md_lines = [
        "# Agent ticket path eval",
        "",
        f"- **Run date (UTC)**: {iso_now}",
        "- **Command**: `python scripts/run_eval_agent_ticket.py`（repo root）",
        f"- **Golden**: `{summary['golden']}`",
        "- **Mode**: mock `evaluate_policy` / `retrieve_scored_nodes` / LLM（不加载 Chroma/Qdrant）",
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
        "### By `final_action`",
        "",
        "| final_action | count |",
        "|--------------|-------|",
    ]
    for action, cnt in sorted(by_action.items()):
        md_lines.append(f"| {action} | {cnt} |")

    md_lines.extend(
        [
            "",
            "### Coverage",
            "",
            "- `policy_intercept`：策略短路，audit 不含 retrieve",
            "- `no_evidence` / `gate_fail`：检索或门控失败，跳过 draft",
            "- `draft_ready` / `await_human_review`：完整路径至 finalize",
            "",
            "### Failed cases",
            "",
        ]
    )
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
        ]
    )
    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Wrote {out_json} and {out_md}")
    print(f"pass_rate={summary['pass_rate']} ({passed}/{total})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
