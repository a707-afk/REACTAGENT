"""路由置信 calibration：temperature + Platt 风格系数（离线拟合写入 JSON）。 """
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, float(x)))


def _logit_clip(p: float, eps: float = 1e-6) -> float:
    pc = _clamp01(p)
    pc = max(eps, min(1.0 - eps, pc))
    return math.log(pc / (1.0 - pc))


def _sigmoid(x: float) -> float:
    if x >= 35:
        return 1.0
    if x <= -35:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


@lru_cache(maxsize=1)
def load_calibration_bundle(path_resolved: str) -> dict[str, Any]:
    p = Path(path_resolved)
    if not p.is_file():
        return {}
    try:
        return dict(json.loads(p.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return {}


def _resolve_calibration_path(settings) -> Path:
    cal_path = (settings.domain_router_calibration_path or "").strip()
    root = Path(__file__).resolve().parent.parent
    fb = root / "data" / "router_calibration.default.json"
    if not cal_path:
        return fb.resolve()
    cand = Path(cal_path)
    return cand.resolve() if cand.is_absolute() else (root / cand).resolve()


def get_calibration_temperature(branch: str) -> float:
    settings = get_settings()
    path = _resolve_calibration_path(settings)
    bundle = load_calibration_bundle(str(path))
    temps = bundle.get("temperature") or {}
    t = temps.get(branch) or temps.get("merged") or 1.0
    try:
        tv = float(t)
        return max(tv, 1e-3)
    except (TypeError, ValueError):
        return 1.0


def get_platt_params(branch: str) -> tuple[float, float]:
    settings = get_settings()
    path = _resolve_calibration_path(settings)
    bundle = load_calibration_bundle(str(path))
    platt = bundle.get("platt") or {}
    block = platt.get(branch) or {}
    try:
        a = float(block.get("A", 1.0))
        b = float(block.get("B", 0.0))
        return (a, b)
    except (TypeError, ValueError):
        return (1.0, 0.0)


def calibrate_probability(raw_prob: float, *, branch: str) -> tuple[float, float]:
    """对 [0,1] 区间的原始置信做 temperature→Platt 风格映射。返回 (calibrated, raw)."""
    raw = _clamp01(raw_prob)
    t = get_calibration_temperature(branch)
    tempered = raw ** (1.0 / max(t, 1e-6))
    tempered = _clamp01(tempered)
    a, b = get_platt_params(branch)
    logit_raw = _logit_clip(tempered)
    out = _clamp01(_sigmoid(a * logit_raw + b))
    return (out, raw)
