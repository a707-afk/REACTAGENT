"""根据 golden 离线拟合路由器 calibration JSON（temperature 网格 + Platt 二元拟合）。

与 ``app/router_calibration.calibrate_probability`` 链一致::
    tempered = clamp(raw ^ (1/T))
    out = sigmoid(A * logit_clip(tempered) + B)

用法（项目根）::

    python scripts/fit_router_calibration.py --golden data/router_eval_golden.jsonl \\
        --out data/router_calibration.fitted.json

可选 ``--predictions-csv``：已由 ``run_eval_router`` 导出且含
``confidence_branch`` / ``raw_confidence`` / ``primary_match`` 时跳过在线路由。"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EPS = 1e-9


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, float(x)))


def _logit(p: float) -> float:
    pc = max(EPS, min(1.0 - EPS, _clamp01(p)))
    return math.log(pc / (1.0 - pc))


def _sigmoid(z: float) -> float:
    if z >= 35:
        return 1.0
    if z <= -35:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def _nll_binary(ps: list[float], ys: list[int]) -> float:
    loss = 0.0
    for p, y in zip(ps, ys):
        p = max(EPS, min(1.0 - EPS, p))
        loss -= y * math.log(p) + (1 - y) * math.log(1 - p)
    return loss


def grid_temperature(raws: list[float], ys: list[int]) -> float:
    if not raws:
        return 1.0
    best_t, best = 1.0, float("inf")
    for i in range(80):
        t = 0.2 + i * (4.8 / 79)
        tempered = [_clamp01(max(0.0, min(1.0, r)) ** (1.0 / max(t, EPS))) for r in raws]
        nll = _nll_binary(tempered, ys)
        if nll < best:
            best = nll
            best_t = t
    return max(best_t, 0.05)


def fit_logistic_platt(features: list[float], ys: list[int], *, iterations: int = 25) -> tuple[float, float]:
    """一维 logistic：p = sigmoid(A * f + B)。"""
    if not features:
        return (1.0, 0.0)
    a, b = 1.0, 0.0
    fs = features
    n = len(fs)
    for _ in range(iterations):
        g1 = g2 = h11 = h12 = h22 = 0.0
        for fi, yi in zip(fs, ys):
            z = a * fi + b
            p = _sigmoid(z)
            gi = yi - p
            g1 += gi * fi
            g2 += gi
            w = max(p * (1 - p), EPS)
            h11 += w * fi * fi
            h12 += w * fi
            h22 += w * 1.0
        h11 /= n
        h12 /= n
        h22 /= n
        g1 /= n
        g2 /= n
        det = h11 * h22 - h12 * h12
        if abs(det) < 1e-12:
            break
        da = ( h22 * g1 - h12 * g2) / det
        db = (-h12 * g1 + h11 * g2) / det
        a += da
        b += db
        if abs(da) + abs(db) < 1e-8:
            break
    return (float(a), float(b))


def load_base_bundle(path: Path) -> dict:
    if path.is_file():
        return dict(json.loads(path.read_text(encoding="utf-8")))
    return {"schema": "domain_router_calibration_v1", "temperature": {}, "platt": {}}


def main() -> int:
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)

    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="data/router_eval_golden.jsonl")
    parser.add_argument(
        "--predictions-csv",
        default=None,
        help="含 confidence_branch/raw_confidence/primary_match 时可替代 golden 推断",
    )
    parser.add_argument("--out", default="data/router_calibration.fitted.json")
    parser.add_argument(
        "--base",
        default="data/router_calibration.default.json",
        help="合并默认值与未样本充足分支的回退模板",
    )
    parser.add_argument("--min-branch-samples", type=int, default=3)
    args = parser.parse_args()

    # late import requires cwd
    from app.config import get_settings
    from app.domain_router import route_domains

    samples: defaultdict[str, list[tuple[float, int]]] = defaultdict(list)

    if args.predictions_csv:
        pcsv = ROOT / Path(args.predictions_csv)
        if not pcsv.is_file():
            print(f"missing predictions csv {pcsv}", file=sys.stderr)
            return 2
        with pcsv.open(encoding="utf-8-sig", newline="") as fp:
            rdr = csv.DictReader(fp)
            for row in rdr:
                br = (row.get("confidence_branch") or "").strip().lower()
                raw_s = (row.get("raw_confidence") or "").strip()
                pm = row.get("primary_match")
                if not br or not raw_s or pm not in {"True", "False"}:
                    continue
                raw = float(raw_s)
                y = 1 if pm == "True" else 0
                # none / empty branch -> merged
                bkey = br if br in {"rules", "embedding", "llm", "merged"} else "merged"
                samples[bkey].append((raw, y))
    else:
        gp = ROOT / Path(args.golden)
        if not gp.is_file():
            print(f"missing golden {gp}", file=sys.stderr)
            return 2
        settings = get_settings()
        with gp.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                q = (obj.get("question") or "").strip()
                if not q:
                    continue
                exp_p = obj.get("expect_primary")
                rr = route_domains(q, settings)
                rb = ""
                rt = rr.routing_trace or {}
                if isinstance(rt, dict):
                    rb = str(rt.get("confidence_branch") or "")
                rb = rb.lower()
                rc = rr.raw_confidence
                if rc is None:
                    continue
                y = 1 if exp_p and rr.primary_domain == exp_p else 0
                bkey = rb if rb in {"rules", "embedding", "llm", "merged"} else "merged"
                samples[bkey].append((float(rc), y))

    base = load_base_bundle(ROOT / Path(args.base))
    out_bundle = dict(base)
    temps = dict(out_bundle.get("temperature") or {})
    platts = dict(out_bundle.get("platt") or {})
    platts.setdefault("rules", {"A": 1.0, "B": 0.0})
    platts.setdefault("embedding", {"A": 1.0, "B": 0.0})
    platts.setdefault("llm", {"A": 1.0, "B": 0.0})
    platts.setdefault("merged", {"A": 1.0, "B": 0.0})
    temps.setdefault("rules", 1.0)
    temps.setdefault("embedding", 1.0)
    temps.setdefault("llm", 1.0)
    temps.setdefault("merged", 1.0)

    for branch, pairs in sorted(samples.items()):
        if len(pairs) < int(args.min_branch_samples):
            print(f"branch {branch}: {len(pairs)} samples < min — keep base coeffs")
            continue
        raws = [x[0] for x in pairs]
        ys = [x[1] for x in pairs]
        t = grid_temperature(raws, ys)
        tempered = [_clamp01(r) ** (1.0 / max(t, EPS)) for r in raws]
        feats = [_logit(x) for x in tempered]
        a, b = fit_logistic_platt(feats, ys)
        temps[branch] = round(t, 4)
        platts[branch] = {"A": round(a, 6), "B": round(b, 6)}
        print(f"fitted {branch}: n={len(pairs)} T={temps[branch]} Platt A={a:.4f} B={b:.4f}")

    out_bundle["temperature"] = temps
    out_bundle["platt"] = platts
    out_bundle["_history_paths"] = list(out_bundle.get("_history_paths") or [])
    outp = ROOT / Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {outp}")
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
