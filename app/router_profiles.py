"""加载 domain_router_profiles.json（原型文本 + per-domain 权重乘子）。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import get_settings


@dataclass(frozen=True)
class DomainRouterProfiles:
    version: int
    domains: tuple[str, ...]
    weight_multipliers: dict[str, float]
    prototypes: dict[str, tuple[str, ...]]


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def load_domain_router_profiles_cached(path_str: str) -> DomainRouterProfiles | None:
    p = Path(path_str)
    if not p.is_file():
        return None
    obj = json.loads(p.read_text(encoding="utf-8"))
    protos = {}
    raw_p = obj.get("prototypes") or {}
    for dom, vals in raw_p.items():
        if isinstance(vals, str):
            protos[str(dom)] = (vals,)
        elif isinstance(vals, list):
            protos[str(dom)] = tuple(str(x) for x in vals if x)
        else:
            continue
    order = tuple(str(d) for d in (obj.get("domain_defaults") or sorted(protos.keys())))
    mult = dict(obj.get("domain_weight_multipliers") or {})
    for d in order:
        mult.setdefault(str(d), 1.0)
    return DomainRouterProfiles(
        version=int(obj.get("version", 1)),
        domains=order,
        weight_multipliers=mult,
        prototypes=protos,
    )


def load_domain_router_profiles() -> DomainRouterProfiles | None:
    settings = get_settings()
    raw = (settings.domain_router_profiles_path or "").strip()
    pp = Path(raw) if raw else _project_root() / "data" / "domain_router_profiles.json"
    if not pp.is_absolute():
        pp = (_project_root() / pp).resolve()
    else:
        pp = pp.resolve()
    return load_domain_router_profiles_cached(str(pp))
