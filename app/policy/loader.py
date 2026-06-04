"""Load behavior rules JSON with mtime-based invalidation."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Settings
from app.policy.models import PolicyAction, PolicyRuleModel, RiskLevel

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES_PATH = REPO_ROOT / "data" / "behavior_rules.default.json"


@dataclass(frozen=True)
class RulesBundle:
    category_order: list[str]
    canonical_phrases: dict[str, list[str]]
    rules: tuple[PolicyRuleModel, ...]


_cache_path: str | None = None
_cache_mtime: float | None = None
_cache_bundle: RulesBundle | None = None


def resolve_rules_file(settings: Settings) -> Path:
    raw = settings.behavior_guard_rules_path
    if raw and str(raw).strip():
        p = Path(raw)
        if p.is_file():
            return p
    return DEFAULT_RULES_PATH


def load_rules_bundle(settings: Settings, *, force_reload: bool = False) -> RulesBundle:
    global _cache_path, _cache_mtime, _cache_bundle
    path = resolve_rules_file(settings).resolve()
    key = str(path)
    try:
        mtime = os.path.getmtime(path) if path.is_file() else None
    except OSError:
        mtime = None

    if (
        not force_reload
        and _cache_bundle is not None
        and _cache_path == key
        and _cache_mtime == mtime
    ):
        return _cache_bundle

    if not path.is_file():
        # shipped default must exist; fail soft with empty bundle
        bundle = RulesBundle(category_order=[], canonical_phrases={}, rules=tuple())
    else:
        raw = json.loads(path.read_text(encoding="utf-8"))
        bundle = _parse_bundle(raw)

    _cache_path = key
    _cache_mtime = mtime
    _cache_bundle = bundle
    return bundle


def _parse_bundle(raw: dict[str, Any]) -> RulesBundle:
    category_order = list(raw.get("category_order") or [])
    canonical_raw = raw.get("canonical_phrases") or {}
    canonical_phrases: dict[str, list[str]] = {}
    if isinstance(canonical_raw, dict):
        for cat, vals in canonical_raw.items():
            if isinstance(vals, list):
                canonical_phrases[str(cat)] = [
                    str(x).strip() for x in vals if str(x).strip()
                ]

    rule_objs = raw.get("rules")
    rules_list: list[PolicyRuleModel] = []
    if isinstance(rule_objs, list):
        for item in rule_objs:
            if not isinstance(item, dict):
                continue
            rid = str(item.get("id") or item.get("code") or "").strip()
            if not rid:
                continue
            cat = str(item.get("category") or "general").strip() or "general"
            prio = int(item.get("priority", 50))
            rlv = _parse_risk(item.get("risk_level"))
            act = _parse_action(item.get("action", "intercept"))
            pat = item.get("pattern")
            patterns = item.get("template_patterns") or []
            tmpl: list[str] = []
            if isinstance(patterns, list):
                tmpl = [str(p) for p in patterns if str(p).strip()]
            elif isinstance(patterns, str) and patterns.strip():
                tmpl = [patterns.strip()]
            msg = str(item.get("message_zh") or "").strip() or _default_msg()
            rules_list.append(
                PolicyRuleModel(
                    id=rid,
                    category=cat,
                    priority=prio,
                    risk_level=rlv,
                    action=act,
                    pattern=str(pat).strip() if pat else None,
                    template_patterns=tuple(tmpl),
                    message_zh=msg,
                )
            )

    if not category_order:
        seen: list[str] = []
        for r in rules_list:
            if r.category not in seen:
                seen.append(r.category)
        category_order = seen

    return RulesBundle(
        category_order=category_order,
        canonical_phrases=canonical_phrases,
        rules=tuple(rules_list),
    )


def _parse_risk(v: Any) -> RiskLevel:
    s = str(v or "high").strip().lower()
    if s in ("medium", "med"):
        return RiskLevel.medium
    if s in ("low",):
        return RiskLevel.low
    return RiskLevel.high


def _parse_action(v: Any) -> PolicyAction:
    s = str(v or "intercept").strip().lower()
    if s in ("warn", "warning"):
        return PolicyAction.warn
    if s in ("allow_log", "allow", "audit"):
        return PolicyAction.allow_log
    return PolicyAction.intercept


def _default_msg() -> str:
    return (
        "该问题涉及需人工复核的合规或安全场景，无法由自动助手直接作答。请转人工处理。"
    )


def compile_rule_patterns(rule: PolicyRuleModel) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    if rule.pattern:
        try:
            compiled.append(re.compile(rule.pattern, flags=re.IGNORECASE | re.DOTALL))
        except re.error:
            pass
    for tp in rule.template_patterns:
        try:
            compiled.append(re.compile(tp, flags=re.IGNORECASE | re.DOTALL))
        except re.error:
            continue
    return compiled
