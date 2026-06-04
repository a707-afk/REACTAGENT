"""Phase 6：依次运行 router×rerank 四组合检索评测（企业索引环境变量对齐）。

在项目根执行::

    python scripts/run_eval_four_baselines.py

**语义（与生产默认一致后的回归约定）**

- **r0 组合**：`EVAL_SKIP_DOMAIN_ROUTER=true` → 不调用路由推断（等价历史「Router 关」，无 trace）。
- **r1 组合**：`EVAL_SKIP_DOMAIN_ROUTER=false` 且 **`DOMAIN_ROUTER_HARD_FILTER=true`**
  → 复现 2026-05-15 矩阵「Router 开 + 硬性按域过滤」；生产默认 `DOMAIN_ROUTER_HARD_FILTER=false` 不适用此列。

依赖：本地已存在 ``enterprise_ai_ops`` Chroma 集合与 BM25 语料（见 README）。
"""


from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMMON_ENV = {
    "DOCS_DIR": "data/docs/enterprise_ai_ops",
    "CHROMA_COLLECTION_NAME": "enterprise_ai_ops",
    "BM25_CORPUS_PATH": "data/bm25_enterprise_corpus.jsonl",
    "EVAL_QUESTIONS_PATH": "data/eval_enterprise_questions.jsonl",
}

def _summaries_from_quartet(paths: dict[str, str]) -> dict[str, dict]:
    """仅从磁盘合并四份 eval JSON（不因最后一步 subprocess 报错而丢汇总）。"""
    out: dict[str, dict] = {}
    for label, rel in paths.items():
        p = ROOT / rel
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            out[label] = data.get("summary") or {}
        except json.JSONDecodeError:
            continue
    return out


COMBOS: list[tuple[str, str, str, str, str]] = [
    ("r0_k0", "true", "false", "false", "docs/eval_enterprise_r0_k0.json"),
    ("r0_k1", "true", "true", "false", "docs/eval_enterprise_r0_k1.json"),
    ("r1_k0", "false", "false", "true", "docs/eval_enterprise_r1_k0.json"),
    ("r1_k1", "false", "true", "true", "docs/eval_enterprise_r1_k1.json"),
]

_EXPECTED_KEYS: dict[str, str] = {t[0]: t[4] for t in COMBOS}


def main() -> None:
    env_base = os.environ.copy()
    env_base.update(COMMON_ENV)

    summaries: dict[str, dict] = {}
    subprocess_failures: list[str] = []

    for label, skip_dr, rerank, hard_filter, out_rel in COMBOS:
        env = env_base.copy()
        env["EVAL_SKIP_DOMAIN_ROUTER"] = skip_dr
        env["RERANK_ENABLED"] = rerank
        env["DOMAIN_ROUTER_HARD_FILTER"] = hard_filter
        env["EVAL_OUTPUT_PATH"] = out_rel
        print(
            f"\n=== Running {label} skip_inference={skip_dr} rerank={rerank} "
            f"hard_filter={hard_filter} -> {out_rel} ==="
        )
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_eval_retrieve.py")],
            cwd=str(ROOT),
            env=env,
        )
        outp = ROOT / out_rel
        if outp.is_file():
            try:
                data = json.loads(outp.read_text(encoding="utf-8"))
                summaries[label] = data.get("summary") or {}
            except json.JSONDecodeError:
                subprocess_failures.append(f"{label} (invalid json)")
        if r.returncode != 0:
            print(f"WARNING: subprocess non-zero ({r.returncode}) at {label}", file=sys.stderr)
            subprocess_failures.append(f"{label} (exit {r.returncode})")

    # 与磁盘完全一致：避免末尾崩溃导致 summary 早于最新 json
    disk = _summaries_from_quartet(_EXPECTED_KEYS)

    merged: dict[str, dict] = {}
    for lk in sorted(set(summaries) | set(disk)):
        merged[lk] = disk.get(lk) or summaries.get(lk) or {}

    snap_path = ROOT / "docs" / "eval_four_baselines_summary.json"
    merged_out = dict(merged)
    if subprocess_failures:
        merged_out["_meta"] = {
            "source": "run_eval_four_baselines.py merge (disk summaries preferred)",
            "subprocess_issues": subprocess_failures,
        }
    snap_path.write_text(json.dumps(merged_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {snap_path}")
    sys.exit(0 if not subprocess_failures else 4)


if __name__ == "__main__":
    main()
