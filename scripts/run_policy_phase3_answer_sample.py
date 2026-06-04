"""Phase 3 验收：POLICY_EMBEDDING_GUARD=true 时抽样 answer_with_citation 不应短路 RAG。

用法（在项目根）::

    set POLICY_EMBEDDING_GUARD=true
    python scripts/run_policy_phase3_answer_sample.py

可选环境变量：
    EVAL_QUESTIONS_PATH — 默认 data/eval_enterprise_questions.jsonl
    POLICY_EMBEDDING_THRESHOLD — 与 Settings 一致
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


def main() -> None:
    os.environ.setdefault("POLICY_EMBEDDING_GUARD", "true")
    eval_path = Path(os.getenv("EVAL_QUESTIONS_PATH", "data/eval_enterprise_questions.jsonl"))
    if not eval_path.is_absolute():
        eval_path = ROOT / eval_path

    from app.config import get_settings
    from app.policy.engine import evaluate_policy

    settings = get_settings()
    if not settings.policy_embedding_guard_enabled:
        print(
            "ERROR: POLICY_EMBEDDING_GUARD must be true (set env before import).",
            file=sys.stderr,
        )
        sys.exit(2)

    samples: list[tuple[str, str]] = []
    for line in eval_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("expected_behavior") != "answer_with_citation":
            continue
        q = (obj.get("question") or "").strip()
        if q:
            samples.append((str(obj.get("id")), q))
        if len(samples) >= 10:
            break

    print(f"Embedding guard={settings.policy_embedding_guard_enabled}, threshold={settings.policy_embedding_threshold}")
    print(f"Sampling first {len(samples)} answer_with_citation rows.")

    violations: list[str] = []
    for eid, q in samples:
        pe = evaluate_policy(
            q,
            settings,
            trace_id=f"phase3-sample-{eid}",
            endpoint="phase3_answer_sample",
            skip_audit_log=True,
        )
        if pe.should_skip_rag:
            violations.append(f"{eid}: intercepted ({pe.intercept_reason_code}) :: {q[:80]}...")

    if violations:
        print("FAIL: unexpected intercept on answer_with_citation samples:", file=sys.stderr)
        for v in violations:
            print(v, file=sys.stderr)
        sys.exit(1)

    print("PASS: no intercept on sampled answer_with_citation rows.")
    sys.exit(0)


if __name__ == "__main__":
    main()
