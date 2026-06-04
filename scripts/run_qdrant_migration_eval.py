"""Qdrant 迁移 + 企业权限/检索评测（本地嵌入式 Qdrant，无需 Docker）。

用法（仓库根目录）::

    python scripts/run_qdrant_migration_eval.py
    python scripts/run_qdrant_migration_eval.py --skip-reindex   # 已有 Qdrant 索引时

环境变量（脚本内默认设置，可覆盖）::

    VECTOR_BACKEND=qdrant
    QDRANT_PATH=data/qdrant_local
    DOCS_DIR=data/docs/enterprise_ai_ops
    CHROMA_COLLECTION_NAME=enterprise_ai_ops
    BM25_CORPUS_PATH=data/bm25_enterprise_corpus.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CHROMA_BASELINE = ROOT / "docs" / "eval_access_control_chroma_baseline.json"
QDRANT_EVAL_JSON = ROOT / "docs" / "eval_access_control_qdrant.json"
QDRANT_EVAL_MD = ROOT / "docs" / "ACCESS-CONTROL-EVAL-QDRANT.md"
RETRIEVE_EVAL_JSON = ROOT / "docs" / "eval_retrieve_qdrant.json"


def _set_enterprise_qdrant_env() -> None:
    os.environ["VECTOR_BACKEND"] = "qdrant"
    os.environ["QDRANT_PATH"] = os.getenv("QDRANT_PATH", "data/qdrant_local")
    os.environ.pop("QDRANT_URL", None)
    os.environ["DOCS_DIR"] = os.getenv("DOCS_DIR", "data/docs/enterprise_ai_ops")
    os.environ["CHROMA_COLLECTION_NAME"] = os.getenv(
        "CHROMA_COLLECTION_NAME", "enterprise_ai_ops"
    )
    os.environ["BM25_CORPUS_PATH"] = os.getenv(
        "BM25_CORPUS_PATH", "data/bm25_enterprise_corpus.jsonl"
    )
    os.environ["EVAL_ENTERPRISE_STRICT"] = "1"


def _run(cmd: list[str], *, label: str) -> None:
    print(f"\n=== {label} ===\n", flush=True)
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc != 0:
        raise SystemExit(rc)


def _load_summary(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("summary")


def _compare_access(baseline: dict, qdrant: dict) -> dict:
    keys = ("forbidden_top5_checks", "expect_top1_contains", "domain_top1")
    rows = []
    for k in keys:
        b = baseline.get(k) or {}
        q = qdrant.get(k) or {}
        rows.append(
            {
                "metric": k,
                "chroma_passed": b.get("passed"),
                "chroma_total": b.get("total"),
                "qdrant_passed": q.get("passed"),
                "qdrant_total": q.get("total"),
                "delta_passed": (q.get("passed") or 0) - (b.get("passed") or 0),
            }
        )
    return {"metrics": rows, "chroma_backend": baseline.get("vector_backend", "chroma"), "qdrant_backend": qdrant.get("vector_backend")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-reindex", action="store_true")
    parser.add_argument("--skip-retrieve-eval", action="store_true")
    args = parser.parse_args()

    _set_enterprise_qdrant_env()

    if not args.skip_reindex:
        _run([sys.executable, "scripts/reindex.py"], label="Qdrant reindex")

    env = os.environ.copy()
    env["ACCESS_EVAL_OUTPUT_JSON"] = str(QDRANT_EVAL_JSON.relative_to(ROOT))
    env["ACCESS_EVAL_OUTPUT_MD"] = str(QDRANT_EVAL_MD.relative_to(ROOT))
    _run(
        [sys.executable, "scripts/run_eval_access_control.py"],
        label="Access-control eval (Qdrant)",
    )

    baseline = _load_summary(CHROMA_BASELINE) or _load_summary(ROOT / "docs/eval_access_control.json")
    qdrant_sum = _load_summary(QDRANT_EVAL_JSON)
    comparison = None
    if baseline and qdrant_sum:
        comparison = _compare_access(baseline, qdrant_sum)
        out_cmp = ROOT / "docs" / "eval_qdrant_vs_chroma_access.json"
        out_cmp.write_text(
            json.dumps(
                {"comparison": comparison, "chroma_summary": baseline, "qdrant_summary": qdrant_sum},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nwrote {out_cmp}", flush=True)
        print(json.dumps(comparison, ensure_ascii=False, indent=2), flush=True)

    if not args.skip_retrieve_eval:
        env2 = env.copy()
        env2["EVAL_OUTPUT_PATH"] = str(RETRIEVE_EVAL_JSON.relative_to(ROOT))
        subprocess.call(
            [sys.executable, "scripts/run_eval_retrieve.py"],
            cwd=ROOT,
            env=env2,
        )


if __name__ == "__main__":
    main()
