"""离线评测句级 grounding（sentence_level_grounding / node_hallucination）。

在项目根::

    python scripts/run_eval_hallucination.py

环境变量::
    HALLUCINATION_EVAL_GOLDEN=data/eval_hallucination.jsonl（默认）
    HALLUCINATION_EVAL_OUT_JSON=docs/eval_hallucination.json
    HALLUCINATION_EVAL_OUT_MD=docs/HALLUCINATION-EVAL.md
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


def _relative_to_repo(path: Path) -> str:
    ap = path.resolve()
    br = ROOT.resolve()
    try:
        return str(ap.relative_to(br))
    except ValueError:
        return str(ap)


def _check_case(report, expect: dict) -> list[str]:
    errors: list[str] = []
    if "passed" in expect and bool(report.passed) != bool(expect["passed"]):
        errors.append(f"passed: got {report.passed}, want {expect['passed']}")
    if "unsupported_sentence_rate_min" in expect:
        rate = float(report.unsupported_sentence_rate)
        want = float(expect["unsupported_sentence_rate_min"])
        if rate < want:
            errors.append(f"unsupported_sentence_rate: got {rate}, want >= {want}")
    if "overlap_ratio_min" in expect:
        from app.citation_verify import citation_overlap_ratio

        # HG-08 仅测 overlap 时用 draft+chunks 重算
        ov = float(report.overlap_ratio)
        want = float(expect["overlap_ratio_min"])
        if ov < want:
            errors.append(f"overlap_ratio: got {ov}, want >= {want}")
    return errors


def _run_one(case: dict) -> dict:
    from app.citation_verify import citation_overlap_ratio, sentence_level_grounding

    draft = str(case.get("draft") or "")
    chunks = list(case.get("chunks") or [])
    expect = case.get("expect") or {}

    if "overlap_ratio_min" in expect and "passed" not in expect:
        texts = [str(c.get("text") or c) if isinstance(c, dict) else str(c) for c in chunks]
        ov = citation_overlap_ratio(draft, texts)
        report = sentence_level_grounding(draft, chunks, prefer_embedding=False)
        report.overlap_ratio = ov
    else:
        report = sentence_level_grounding(draft, chunks, prefer_embedding=False)

    errors = _check_case(report, expect)
    return {
        "id": case.get("id"),
        "description": case.get("description"),
        "expect": expect,
        "actual": report.to_dict(),
        "passed": not errors,
        "errors": errors,
    }


def main() -> int:
    golden = Path(os.getenv("HALLUCINATION_EVAL_GOLDEN", "data/eval_hallucination.jsonl"))
    if not golden.is_absolute():
        golden = ROOT / golden
    out_json = ROOT / os.getenv("HALLUCINATION_EVAL_OUT_JSON", "docs/eval_hallucination.json")
    out_md = ROOT / os.getenv("HALLUCINATION_EVAL_OUT_MD", "docs/HALLUCINATION-EVAL.md")

    if not golden.is_file():
        print(f"Missing golden: {golden}", file=sys.stderr)
        return 2

    cases: list[dict] = []
    for line in golden.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))

    results = [_run_one(c) for c in cases]
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    failed = [r for r in results if not r["passed"]]

    summary = {
        "golden": _relative_to_repo(golden),
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

    md_lines = [
        "# Hallucination / grounding eval",
        "",
        f"- **Run date (UTC)**: {summary['run_utc']}",
        "- **Command**: `python scripts/run_eval_hallucination.py`",
        f"- **Golden**: `{summary['golden']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total | {total} |",
        f"| Passed | {passed} |",
        f"| Pass rate | {summary['pass_rate']:.2%} |",
        "",
    ]
    if failed:
        md_lines.append("### Failed\n")
        for r in failed:
            md_lines.append(f"- **{r['id']}**: {'; '.join(r['errors'])}")
    else:
        md_lines.append("(all passed)\n")
    md_lines.append(f"\nFull JSON: `{_relative_to_repo(out_json)}`.\n")
    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Wrote {out_json} and {out_md}")
    print(f"pass_rate={summary['pass_rate']} ({passed}/{total})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
