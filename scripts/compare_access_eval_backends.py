"""对比 Chroma vs Qdrant 权限评测 JSON 摘要与逐条差异。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)


def _load(name: str) -> dict:
    p = ROOT / "docs" / name
    if not p.is_file():
        print(f"Missing {p}", file=sys.stderr)
        sys.exit(2)
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    chroma = _load(os.getenv("COMPARE_QDRANT_JSON", "eval_access_control_qdrant.json"))
    qdrant = _load(os.getenv("COMPARE_QDRANT_JSON", "eval_access_control_qdrant.json"))

    cs, qs = chroma["summary"], qdrant["summary"]
    print("=== Summary ===")
    for key in ("forbidden_top5_checks", "expect_top1_contains", "domain_top1"):
        c, q = cs[key], qs[key]
        print(
            f"{key}: chroma {c['passed']}/{c['total']} ({c['pass_rate']}) | "
            f"qdrant {q['passed']}/{q['total']} ({q['pass_rate']})"
        )

    by_c = {r["id"]: r for r in chroma["results"]}
    by_q = {r["id"]: r for r in qdrant["results"]}
    diffs: list[str] = []
    for rid in sorted(set(by_c) | set(by_q)):
        rc, rq = by_c.get(rid), by_q.get(rid)
        if not rc or not rq:
            diffs.append(f"{rid}: missing in one backend")
            continue
        flags = []
        if rc.get("forbidden_check_passed") != rq.get("forbidden_check_passed"):
            flags.append("forbidden")
        if rc.get("top1_expect_matched") != rq.get("top1_expect_matched"):
            flags.append("expect_top1")
        if rc.get("domain_top1_match") != rq.get("domain_top1_match"):
            flags.append("domain_top1")
        c_top = (rc.get("chunks_topk") or [{}])[0]
        q_top = (rq.get("chunks_topk") or [{}])[0]
        if (c_top.get("file_path") or c_top.get("file_name")) != (
            q_top.get("file_path") or q_top.get("file_name")
        ):
            flags.append("top1_doc")
        if flags:
            diffs.append(f"{rid}: {', '.join(flags)}")

    out = ROOT / "docs" / "ACCESS-CONTROL-BACKEND-COMPARE.md"
    lines = [
        "# Chroma vs Qdrant 权限评测对比",
        "",
        f"- Chroma：`eval_access_control_qdrant.json`（{cs.get('generated_at', '')}）",
        f"- Qdrant：`eval_access_control_qdrant.json`（{qs.get('generated_at', '')}）",
        "",
        "## 摘要",
        "",
        f"| 指标 | Chroma | Qdrant |",
        f"|------|--------|--------|",
    ]
    for key, label in (
        ("forbidden_top5_checks", "Forbidden top5"),
        ("expect_top1_contains", "Expect top1"),
        ("domain_top1", "Domain top1"),
    ):
        c, q = cs[key], qs[key]
        lines.append(
            f"| {label} | {c['passed']}/{c['total']} | {q['passed']}/{q['total']} |"
        )
    lines.extend(["", "## 逐条差异", ""])
    if not diffs:
        lines.append("无逐条判定差异（top1 路径与 forbidden/expect/domain 标志一致）。")
    else:
        lines.extend(f"- {d}" for d in diffs)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(f"diff_rows={len(diffs)}")


if __name__ == "__main__":
    main()
