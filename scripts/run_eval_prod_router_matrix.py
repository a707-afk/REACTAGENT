"""路线图 A：生产等价 Router 评估（Hard filter OFF，非历史 r1）。

依次跑三种组合，写入固定路径并生成汇总 JSON：

1. router off（跳过推断）→ docs/eval_enterprise_prod_router_off_rerank_on.json
2. router trace-only，soft boost 关 → docs/eval_enterprise_prod_router_trace_rerank_on.json
3. router trace-only，soft boost 开 → docs/eval_enterprise_prod_router_softboost_rerank_on.json

在项目根::

    python scripts/run_eval_prod_router_matrix.py

**CPU / Windows 稳定跑完**（Reranker 易触发原生崩溃时）::

    set PROD_ROUTER_EVAL_STABLE_CPU=1   # PowerShell: $env:PROD_ROUTER_EVAL_STABLE_CPU="true"
    python scripts/run_eval_prod_router_matrix.py

稳定模式会设 ``RERANK_ENABLED=false``，并默认 **``DOMAIN_ROUTER_USE_EMBEDDING=false``**
以缩短 trace 组合耗时；各 JSON 顶层 ``summary`` 会标明 ``rerank_enabled``、
``domain_router_embedding_enabled``。全量 Embedding + Rerank 请关稳定模式并保证算力。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMBOS: list[tuple[str, dict[str, str]]] = [
    (
        "prod_router_off_rerank_on",
        {
            "EVAL_SKIP_DOMAIN_ROUTER": "true",
            "DOMAIN_ROUTER_SOFT_BOOST_ENABLED": "false",
            "EVAL_OUTPUT_PATH": "docs/eval_enterprise_prod_router_off_rerank_on.json",
        },
    ),
    (
        "prod_router_trace_softboost_off",
        {
            "EVAL_SKIP_DOMAIN_ROUTER": "false",
            "DOMAIN_ROUTER_SOFT_BOOST_ENABLED": "false",
            "EVAL_OUTPUT_PATH": "docs/eval_enterprise_prod_router_trace_rerank_on.json",
        },
    ),
    (
        "prod_router_trace_softboost_on",
        {
            "EVAL_SKIP_DOMAIN_ROUTER": "false",
            "DOMAIN_ROUTER_SOFT_BOOST_ENABLED": "true",
            "EVAL_OUTPUT_PATH": "docs/eval_enterprise_prod_router_softboost_rerank_on.json",
        },
    ),
]

_LABEL_TO_REL = {label: extra["EVAL_OUTPUT_PATH"] for label, extra in COMBOS}


def _load_disk_summaries() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for label, rel in _LABEL_TO_REL.items():
        p = ROOT / rel
        if not p.is_file():
            continue
        try:
            out[label] = json.loads(p.read_text(encoding="utf-8")).get("summary") or {}
        except json.JSONDecodeError:
            continue
    return out


def main() -> None:
    env_base = os.environ.copy()
    env_base.update(
        {
            "DOCS_DIR": "data/docs/enterprise_ai_ops",
            "CHROMA_COLLECTION_NAME": "enterprise_ai_ops",
            "BM25_CORPUS_PATH": "data/bm25_enterprise_corpus.jsonl",
            "EVAL_QUESTIONS_PATH": "data/eval_enterprise_questions.jsonl",
            "DOMAIN_ROUTER_HARD_FILTER": "false",
        }
    )

    stable_cpu = os.getenv("PROD_ROUTER_EVAL_STABLE_CPU", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    eff_rerank = "false" if stable_cpu else "true"
    env_base["RERANK_ENABLED"] = eff_rerank
    if stable_cpu:
        env_base["DOMAIN_ROUTER_USE_EMBEDDING"] = os.getenv(
            "PROD_ROUTER_EVAL_STABLE_USE_EMBEDDING", "false"
        )

    failures: list[str] = []
    mem: dict[str, dict] = {}

    for label, extra in COMBOS:
        env = env_base.copy()
        env.update(extra)
        outp_rel = extra["EVAL_OUTPUT_PATH"]
        print(
            f"\n=== {label} → {outp_rel} "
            f"(rerank={eff_rerank} stable_cpu={stable_cpu}) ==="
        )
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_eval_retrieve.py")],
            cwd=str(ROOT),
            env=env,
        )
        outp = ROOT / outp_rel
        if outp.is_file():
            try:
                mem[label] = json.loads(outp.read_text(encoding="utf-8")).get(
                    "summary"
                ) or {}
            except json.JSONDecodeError:
                failures.append(f"{label} invalid json")
        if r.returncode != 0:
            print(
                f"WARNING subprocess exit {r.returncode} at {label}",
                file=sys.stderr,
            )
            failures.append(f"{label} exit {r.returncode}")

    disk = _load_disk_summaries()
    merged: dict[str, dict] = {}
    for lk in sorted(set(mem) | set(disk)):
        merged[lk] = disk.get(lk) or mem.get(lk) or {}

    snap = ROOT / "docs" / "eval_prod_router_matrix_summary.json"
    snap_payload: dict = {
        **_merge_meta(stable_cpu, eff_rerank, failures),
    }
    for k, v in merged.items():
        snap_payload[k] = v
    snap.write_text(
        json.dumps(snap_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {snap}")
    sys.exit(0 if not failures else 3)


def _merge_meta(stable_cpu: bool, eff_rerank: str, failures: list[str]) -> dict:
    return {
        "_meta": {
            "source": "run_eval_prod_router_matrix.py",
            "prod_router_eval_stable_cpu": stable_cpu,
            "rerank_enabled_env": eff_rerank,
            "subprocess_issues": failures,
            "note_zh": (
                "稳定模式默认关 Rerank + 关 Embedding Router，用于弱机/Windows 快速落盘；"
                "生产一致请 unset PROD_ROUTER_EVAL_STABLE_CPU，并可选 PROD_ROUTER_EVAL_STABLE_USE_EMBEDDING=true 仅开嵌入。"
            ),
        }
    }


if __name__ == "__main__":
    main()
