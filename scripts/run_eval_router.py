"""离线评测领域路由模块（独立于检索管线）。

在项目根::

    python scripts/run_eval_router.py

环境变量::
    ROUTER_EVAL_GOLDEN=data/router_eval_golden.jsonl（默认）
    ROUTER_EVAL_OUT_PREFIX=docs/router_eval_metrics（不含扩展名前缀）
    DOMAIN_ROUTER_ENHANCED / DOMAIN_ROUTER_USE_EMBEDDING 等同生产 Settings

输出（UTF-8-sig）：``{PREFIX}_predictions.csv`` / ``*_aggregate.csv`` / ``*_confusion.csv`` / ``*_f1.csv`` / ``*_summary.json``。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def macro_f1(precisions: dict[str, float], recalls: dict[str, float]) -> float:
    f1_by: dict[str, float] = {}
    labs = set(precisions) | set(recalls)
    for d in labs:
        p = precisions.get(d, 0.0)
        r = recalls.get(d, 0.0)
        f1_by[d] = 0.0 if (p + r) == 0 else 2 * p * r / (p + r)
    if not f1_by:
        return 0.0
    return sum(f1_by.values()) / len(f1_by)


def main() -> int:
    from app.config import get_settings
    from app.domain_router import route_domains

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--golden",
        default=os.getenv("ROUTER_EVAL_GOLDEN", "data/router_eval_golden.jsonl"),
    )
    parser.add_argument(
        "--out-prefix",
        default=os.getenv("ROUTER_EVAL_OUT_PREFIX", "docs/router_eval_metrics"),
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=int(os.getenv("ROUTER_EVAL_TOP_K", "3")),
        help="Top-k overlap：预测的 allowed_domains 截断后 ∪ expect_domains 非空相交",
    )
    args = parser.parse_args()

    gp = ROOT / Path(args.golden)
    if not gp.is_file():
        print(f"Missing golden: {gp}", file=sys.stderr)
        return 2

    settings = get_settings()
    rows: list[dict] = []
    with gp.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            q = (obj.get("question") or "").strip()
            if not q:
                continue
            exp_p = obj.get("expect_primary")
            exp_ds = obj.get("expect_domains") or []
            if isinstance(exp_ds, str):
                exp_ds = [exp_ds]
            rr = route_domains(q, settings)
            preds = list(rr.allowed_domains)
            pk = preds[: args.top_k] if preds else []
            overlap = bool(set(pk) & set(exp_ds)) if pk and exp_ds else False
            primary_ok = (rr.primary_domain == exp_p) if exp_p else None
            rb = ""
            rt = rr.routing_trace or {}
            if isinstance(rt, dict):
                rb = str(rt.get("confidence_branch") or "")
            dw_parts = [f"{d}:{float(w):.4f}" for d, w in (rr.domain_weights or ())]
            rows.append(
                {
                    "line": line_no,
                    "id": obj.get("id"),
                    "question": q,
                    "expect_primary": exp_p,
                    "expect_domains": "|".join(exp_ds),
                    "pred_primary": rr.primary_domain or "",
                    "pred_domains": "|".join(preds),
                    "domain_weights": "|".join(dw_parts),
                    "method": rr.method,
                    "confidence_branch": rb,
                    "raw_confidence": ""
                    if rr.raw_confidence is None
                    else f"{float(rr.raw_confidence):.6f}",
                    "confidence": f"{float(rr.confidence):.6f}",
                    "hit_topk_overlap": overlap,
                    "primary_match": primary_ok,
                }
            )

    pref = ROOT / Path(args.out_prefix)
    out_dir = pref.parent if str(pref.parent) != "." else ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = pref.name if pref.suffix != ".csv" else pref.stem

    csv_pred = out_dir / f"{stem}_predictions.csv"
    csv_agg = out_dir / f"{stem}_aggregate.csv"
    csv_cm = out_dir / f"{stem}_confusion.csv"
    csv_f1 = out_dir / f"{stem}_f1.csv"
    json_sum = out_dir / f"{stem}_summary.json"

    tp_topk = sum(1 for r in rows if r["hit_topk_overlap"])
    n = len(rows)
    pk_hit = sum(1 for r in rows if r["primary_match"] is True)
    denom_pk = sum(1 for r in rows if r["primary_match"] is not None)

    with csv_pred.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(
            fp,
            fieldnames=[
                "line",
                "id",
                "question",
                "expect_primary",
                "expect_domains",
                "pred_primary",
                "pred_domains",
                "domain_weights",
                "method",
                "confidence_branch",
                "raw_confidence",
                "confidence",
                "hit_topk_overlap",
                "primary_match",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)

    cm: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for r in rows:
        ep = r.get("expect_primary")
        pp = r.get("pred_primary") or "<none>"
        if ep:
            cm[str(ep)][str(pp)] += 1

    with csv_agg.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["metric", "value"])
        w.writerow(["count", str(n)])
        w.writerow(["topk_overlap_hit_rate", f"{tp_topk/n:.6f}" if n else "0"])
        w.writerow(["primary_accuracy", f"{pk_hit/max(denom_pk,1):.6f}"])

    all_labels = sorted(set(cm.keys()) | {p for ctr in cm.values() for p in ctr.keys()})
    with csv_cm.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["gold_primary\\pred_primary"] + all_labels)
        for g in sorted(cm.keys()):
            w.writerow([g] + [str(cm[g][pred]) for pred in all_labels])

    per_gold_counts: Counter[str] = Counter(
        str(r["expect_primary"]) for r in rows if r["expect_primary"]
    )
    per_pred_positive: defaultdict[str, int] = defaultdict(int)
    per_tp_prim: defaultdict[str, int] = defaultdict(int)
    for r in rows:
        eg = r.get("expect_primary")
        pg = (r.get("pred_primary") or "").strip()
        if not eg:
            continue
        per_pred_positive[pg if pg else "<none>"] += 1
        if pg == eg:
            per_tp_prim[str(eg)] += 1

    recalls = {d: per_tp_prim[d] / max(per_gold_counts[d], 1) for d in per_gold_counts}
    precisions: dict[str, float] = {}
    for d in set(per_tp_prim) | set(per_pred_positive.keys()):
        den = max(per_pred_positive.get(d, 0), 0)
        precisions[d] = (per_tp_prim[d] / den) if den else 0.0

    f1m = macro_f1(precisions, recalls)

    with csv_f1.open("w", newline="", encoding="utf-8-sig") as fp:
        ww = csv.writer(fp)
        ww.writerow(["domain", "precision", "recall"])
        labs = sorted(set(precisions) | set(recalls))
        for d in labs:
            ww.writerow(
                [
                    d,
                    f"{precisions.get(d, 0.0):.6f}",
                    f"{recalls.get(d, 0.0):.6f}",
                ]
            )
        ww.writerow(["macro_f1_approx", "", f"{f1m:.6f}"])

    json_sum.write_text(
        json.dumps(
            {
                "count": n,
                "topk_overlap_hit_rate": tp_topk / max(n, 1),
                "primary_accuracy": pk_hit / max(denom_pk, 1),
                "macro_f1_approx": f1m,
                "golden": str(gp),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"wrote predictions {csv_pred}")
    print(f"wrote aggregate   {csv_agg}")
    print(f"wrote confusion   {csv_cm}")
    print(f"wrote f1          {csv_f1}")
    print(f"wrote summary     {json_sum}")
    pa = pk_hit / max(denom_pk, 1)
    tk = tp_topk / max(n, 1)
    print(f"topk_overlap@{args.top_k} {tk:.4f} primary_accuracy {pa:.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
