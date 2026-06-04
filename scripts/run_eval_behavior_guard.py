"""Batch-evaluate `evaluate_policy` (intercept tier) on enterprise eval boundary rows.

Loads JSONL from ``EVAL_QUESTIONS_PATH`` (default ``data/eval_enterprise_questions.jsonl``),
keeps rows whose ``expected_behavior`` is exactly one of:
``human_review``, ``refuse_or_human_review``, ``refuse_or_clarify_boundary``, …

Writes ``docs/eval_behavior_guard.json`` and a short ``docs/BEHAVIOR-GUARD-EVAL.md``.

Metrics: intercept **hit** means ``PolicyEvalResult.should_skip_rag`` (rule / embedding /
LLM 任一触发短路). Optional stages controlled by ``POLICY_EMBEDDING_GUARD`` /
``POLICY_LLM_GUARD`` appear in summary.
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

BOUNDARY_EXPECTED = frozenset(
    {
        "human_review",
        "refuse_or_human_review",
        "refuse_or_clarify_boundary",
    }
)


def _relative_to_repo(path: Path) -> str:
    ap = path.resolve()
    br = ROOT.resolve()
    try:
        return str(ap.relative_to(br))
    except ValueError:
        return str(ap)


def _result_to_hit_dict(pe) -> dict | None:
    if not getattr(pe, "should_skip_rag", False):
        return None
    return {
        "reason_code": pe.intercept_reason_code or "POLICY_HIT",
        "behavior": pe.behavior or "human_review",
        "message_zh": pe.message_zh,
        "policy_action": getattr(pe.policy_action, "value", str(pe.policy_action)),
        "matched_rule_ids": list(pe.matched_rule_ids),
        "embedding_hit": pe.embedding_hit,
        "embedding_max_sim": pe.embedding_max_sim,
        "llm_hit": pe.llm_hit,
    }


def main() -> None:
    from app.config import get_settings
    from app.policy.engine import evaluate_policy

    settings = get_settings()
    eval_path = Path(os.getenv("EVAL_QUESTIONS_PATH", "data/eval_enterprise_questions.jsonl"))
    if not eval_path.is_absolute():
        eval_path = ROOT / eval_path
    out_json = ROOT / "docs/eval_behavior_guard.json"
    out_md = ROOT / "docs/BEHAVIOR-GUARD-EVAL.md"

    rows: list[dict] = []
    for line in eval_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        eb = obj.get("expected_behavior")
        if eb not in BOUNDARY_EXPECTED:
            continue
        q = (obj.get("question") or "").strip()
        if not q:
            continue
        pe = evaluate_policy(
            q,
            settings,
            trace_id=None,
            user_context_summary=None,
            endpoint="eval_behavior_guard",
            skip_audit_log=True,
        )
        rows.append(
            {
                "id": obj.get("id"),
                "question": q,
                "expected_behavior": eb,
                "risk_level": obj.get("risk_level"),
                "guard_hit": bool(pe.should_skip_rag),
                "hit": _result_to_hit_dict(pe),
                "policy_trace": {
                    "policy_action": getattr(pe.policy_action, "value", str(pe.policy_action)),
                    "policy_warnings": list(pe.policy_warnings),
                    "requires_human_review": pe.requires_human_review,
                },
            }
        )

    boundary_total = len(rows)
    boundary_hits = sum(1 for r in rows if r["guard_hit"])

    high_rows = [r for r in rows if (r.get("risk_level") or "").strip().lower() == "high"]
    high_total = len(high_rows)
    high_hits = sum(1 for r in high_rows if r["guard_hit"])

    fn_ids = [r["id"] for r in rows if not r["guard_hit"]]

    summary = {
        "eval_questions_path": _relative_to_repo(eval_path),
        "behavior_guard_enabled": settings.behavior_guard_enabled,
        "behavior_guard_rules_path": settings.behavior_guard_rules_path,
        "policy_embedding_guard_enabled": getattr(
            settings, "policy_embedding_guard_enabled", False
        ),
        "policy_embedding_threshold": getattr(settings, "policy_embedding_threshold", None),
        "policy_llm_guard_enabled": getattr(settings, "policy_llm_guard_enabled", False),
        "policy_llm_confidence_threshold": getattr(
            settings, "policy_llm_confidence_threshold", None
        ),
        "subset_boundary_labeled_total": boundary_total,
        "subset_boundary_labeled_hits": boundary_hits,
        "recall_boundary_labeled": round(boundary_hits / boundary_total, 4)
        if boundary_total
        else None,
        "subset_risk_level_high_total": high_total,
        "subset_risk_level_high_hits": high_hits,
        "recall_risk_level_high": round(high_hits / high_total, 4) if high_total else None,
        "false_negative_ids": fn_ids,
        "false_negative_count": len(fn_ids),
        "python": sys.executable,
    }

    payload = {"summary": summary, "results": rows}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    ran_cmd = "python scripts/run_eval_behavior_guard.py"
    iso_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    md_lines = [
        "# Behavior guard eval",
        "",
        f"- **Run date (UTC)**: {iso_now}",
        f"- **Command**: `{ran_cmd}` (from repo root)",
        f"- **Questions file**: `{summary['eval_questions_path']}`",
        f"- **behavior_guard_enabled**: {settings.behavior_guard_enabled}",
        f"- **POLICY_EMBEDDING_GUARD**: {summary['policy_embedding_guard_enabled']} "
        f"(threshold={summary['policy_embedding_threshold']})",
        f"- **POLICY_LLM_GUARD**: {summary['policy_llm_guard_enabled']} "
        f"(confidence≥{summary['policy_llm_confidence_threshold']} → intercept)",
        "",
        "## MVP behavior (consistent with handoff 「中危记录」)",
        "",
        "- **`intercept`**：短路，不调用 RAG/完整生成；沿用 `behavior: human_review` 与 "
        "`refusal_reason_code`。",
        "- **`warn`**：写审计、`policy_warnings` 入 JSON，**仍继续检索**（吞吐优先）。",
        "- **向量 / LLM 阶段**：仅在 **规则层未短路**时运行； cosine ≥ `POLICY_EMBEDDING_THRESHOLD` "
        "或 LLM `medium|high` 且 confidence ≥ `POLICY_LLM_CONFIDENCE` 时 **短路**（intercept）。",
        "",
        "## Metrics",
        "",
        "Assumption: rows with `expected_behavior` in "
        "`human_review` / `refuse_or_human_review` / `refuse_or_clarify_boundary` "
        "denote boundary/policy scenarios; `evaluate_policy(...).should_skip_rag` is an "
        "**intercept (hit)**. **Recall (high risk)** = hits / count where "
        "`risk_level == \"high\"` within that subset. **Recall (all boundary-labeled)** uses "
        "the full three-behavior subset.",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Subset size (boundary labels) | {boundary_total} |",
        f"| Hits | {boundary_hits} |",
        f"| Recall (all boundary-labeled) | {summary['recall_boundary_labeled']} |",
        f"| Subset `risk_level=high` | {high_total} |",
        f"| Hits (high) | {high_hits} |",
        f"| Recall (risk_level=high) | {summary['recall_risk_level_high']} |",
        f"| False negatives (no hit), count | {len(fn_ids)} |",
        "",
        "### False negative ids (expected boundary label, intercept missed)",
        "",
        ", ".join(str(i) for i in fn_ids) if fn_ids else "(none)",
        "",
        f"Full JSON: `{_relative_to_repo(out_json)}`.",
        "",
    ]
    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Wrote {out_json} and {out_md}")
    print(
        f"recall_boundary_labeled={summary['recall_boundary_labeled']} "
        f"recall_risk_level_high={summary['recall_risk_level_high']}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        err_md = ROOT / "docs/BEHAVIOR-GUARD-EVAL.md"
        err_md.parent.mkdir(parents=True, exist_ok=True)
        err_md.write_text(
            "# Behavior guard eval\n\n"
            f"**Status**: run failed ({type(exc).__name__}: {exc}).\n\n"
            "Fix dependencies / environment and re-run `python scripts/run_eval_behavior_guard.py`.\n",
            encoding="utf-8",
        )
        raise
