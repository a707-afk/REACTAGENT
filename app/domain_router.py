"""EcomAgent domain router: e-commerce after-sales keyword matching + LLM fallback.

Strategy (simple to complex, progressive upgrade):
1. >=2 keyword hits in one domain -> immediate return, confidence 0.90+
2. 1 keyword hit, unique domain -> return, confidence 0.75
3. No hits / multi-domain competition -> LLM classification
4. All fails -> return None, full-search fallback

EcomAgent: changed from 14 generic CS domains to 5 e-commerce after-sales domains.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)

_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "return_policy": (
        "退货政策", "退换政策", "七天无理由", "无理由退货", "退货条件",
        "退换规则", "退货运费", "退款政策", "部分退款", "全额退款",
        "折旧费", "二次销售", "不支持退换", "超过退货期",
        "return policy", "no reason return", "refund policy",
    ),
    "exchange": (
        "换货", "换", "交换", "换尺码", "换颜色", "换型号", "尺寸不合适",
        "大小不合适", "换一个", "调换", "更换", "换L", "换M", "换XL",
        "exchange", "swap", "wrong size",
    ),
    "refund": (
        "退款", "退钱", "退货", "退款到账", "退款时间", "退款金额",
        "原路返回", "优惠券退回", "退款流程", "退",
        "refund", "money back", "return money",
    ),
    "complaint": (
        "投诉", "举报", "不满", "差评", "态度差", "质量差", "欺骗",
        "投诉商家", "投诉客服", "我要投诉", "气死", "垃圾",
        "complaint", "report", "unhappy", "dissatisfied",
    ),
    "shipping": (
        "物流", "快递", "发货", "配送", "到哪", "快递查询", "物流查询",
        "查物流", "包裹", "签收", "延误", "没收到", "丢件",
        "快递单号", "取件", "上门取件", "预约取件",
        "shipping", "tracking", "delivery", "package", "shipment",
    ),
}

_KNOWN_DOMAINS = tuple(sorted(_DOMAIN_KEYWORDS.keys()))


@dataclass(frozen=True)
class RouterResult:
    allowed_domains: tuple[str, ...]
    primary_domain: str | None
    confidence: float
    method: str  # "keywords_strong" | "keywords_weak" | "llm" | "none"
    raw_confidence: float | None = None
    domain_weights: tuple[tuple[str, float], ...] = ()
    routing_trace: dict[str, Any] | None = None


def _rule_scores(query: str) -> dict[str, float]:
    q_lower = query.lower()
    scores: dict[str, float] = {d: 0.0 for d in _KNOWN_DOMAINS}
    for dom, kws in _DOMAIN_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in q_lower:
                scores[dom] += 1.0
    return scores


def _llm_pick_domain(query: str, settings: Settings) -> str | None:
    if not settings.sensenova_api_keys:
        return None
    from app.llm import chat_completion

    dom_list = list(_KNOWN_DOMAINS)
    sys_p = (
        "你是电商售后领域分类器。根据用户问题，从给定的 domain 列表中只选一个最相关的。\n"
        "输出严格 JSON：{\"domain\":\"...\"}，不要其它文字。"
    )
    user_p = f"domain 列表：{dom_list}\n用户问题：{query.strip()}"
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(chat_completion, sys_p, user_p)
            raw = future.result(timeout=10.0)  # 10s timeout for domain routing
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return None
        obj = json.loads(m.group())
        d = obj.get("domain")
        if isinstance(d, str) and d in _DOMAIN_KEYWORDS:
            return d
    except (concurrent.futures.TimeoutError, TimeoutError):
        logger.warning("domain router LLM timed out after 10s")
    except Exception:
        logger.exception("domain router LLM classification failed")
    return None


def route_domains(query: str, settings: Settings) -> RouterResult:
    text = (query or "").strip()
    if not text:
        return RouterResult(
            (), None, 0.0, "none",
            raw_confidence=None,
            routing_trace={"path": "empty"},
        )

    scores = _rule_scores(text)
    active_domains = [(d, s) for d, s in scores.items() if s > 0]
    active_domains.sort(key=lambda x: x[1], reverse=True)

    trace: dict[str, Any] = {
        "path": "keywords_first",
        "rule_scores": {d: s for d, s in active_domains},
        "active_count": len(active_domains),
    }

    if active_domains and active_domains[0][1] >= 2.0:
        best_dom, best_score = active_domains[0]
        trace["confidence_branch"] = "keywords_strong"
        return RouterResult(
            allowed_domains=(best_dom,),
            primary_domain=best_dom,
            confidence=min(0.95, 0.80 + best_score * 0.05),
            raw_confidence=min(1.0, best_score / 5.0),
            method="keywords_strong",
            domain_weights=((best_dom, best_score),),
            routing_trace=trace,
        )

    if len(active_domains) == 1 and active_domains[0][1] >= 1.0:
        best_dom, best_score = active_domains[0]
        trace["confidence_branch"] = "keywords_weak"
        return RouterResult(
            allowed_domains=(best_dom,),
            primary_domain=best_dom,
            confidence=0.75,
            raw_confidence=0.75,
            method="keywords_weak",
            domain_weights=((best_dom, best_score),),
            routing_trace=trace,
        )

    if settings.zhipuai_api_key:
        picked = _llm_pick_domain(text, settings)
        if picked:
            trace["confidence_branch"] = "llm"
            trace["llm_domain"] = picked
            return RouterResult(
                allowed_domains=(picked,),
                primary_domain=picked,
                confidence=0.70,
                raw_confidence=0.70,
                method="llm",
                domain_weights=((picked, 0.70),),
                routing_trace=trace,
            )

    trace["confidence_branch"] = "none"
    return RouterResult(
        (), None, 0.0, "none",
        raw_confidence=None,
        routing_trace=trace,
    )
