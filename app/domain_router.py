"""客服领域路由：中英双语关键词优先 + LLM fallback。

策略（由简到繁，逐级升级）：
1. 关键词直接命中 ≥2 个 → 立即返回，confidence 0.90+
2. 关键词命中 1 个且唯一 → 返回，confidence 0.75
3. 无关键词命中 / 多域竞争 → LLM 分类（如有 API key）
4. 全部失败 → 返回 None，走全库检索

不再使用 embedding fusion —— profiles 缺失域导致准确率 10% 的根因。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)

# ── 14 个客服领域，中文关键词在前（主用户群），英文在后 ──

_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "customer_service": (
        # 中文
        "客服", "人工", "转人工", "热线", "投诉电话", "联系你们",
        # 英文
        "customer service", "support team", "human agent", "callback",
        "speak to", "talk to", "representative", "call me",
    ),
    "tech_support": (
        # 中文
        "崩溃", "闪退", "报错", "打不开", "连不上", "无法连接",
        "驱动", "固件", "卡顿", "死机", "蓝屏", "bug", "故障排查",
        "更新失败", "安装失败", "不兼容", "黑屏", "重启",
        # 英文
        "error", "crash", "not working", "bug", "freeze", "driver",
        "firmware", "connectivity", "connection", "troubleshoot",
        "won't start", "keeps crashing", "broken", "glitch",
    ),
    "billing": (
        # 中文
        "扣费", "扣款", "账单", "发票", "收费", "多扣", "乱扣",
        "支付", "付款", "订阅", "信用卡", "花呗", "微信支付",
        "支付宝", "退款", "费用", "价格", "涨价", "自动续费",
        "取消订阅", "余额", "充值",
        # 英文
        "invoice", "charge", "charged", "payment", "billing", "billed",
        "credit card", "subscription", "overcharge", "pricing", "price",
        "auto renew", "cancel subscription", "refund",
    ),
    "account": (
        # 中文
        "登录", "登入", "密码", "忘记密码", "重置密码", "验证码",
        "注册", "注销", "销户", "账号", "账户", "个人资料",
        "实名认证", "绑定手机", "绑定邮箱", "解锁", "找回账号",
        "修改密码", "安全设置",
        # 英文
        "login", "password", "credential", "reset", "sign in",
        "unlock", "recover account", "create account", "delete account",
        "profile", "2fa", "two factor", "verification",
    ),
    "order": (
        # 中文
        "订单", "下单", "购买", "购物车", "结账", "取消订单",
        "订单号", "查订单", "订单状态", "待付款", "待发货",
        "修改订单", "加购",
        # 英文
        "order", "purchase", "cancel order", "cart", "checkout",
        "track order", "order number", "order status",
    ),
    "returns": (
        # 中文
        "退货", "退款", "换货", "保修", "退钱", "退货运费",
        "退款政策", "七天无理由", "质量有问题", "收到坏",
        "商品破损", "发错货",
        # 英文
        "return", "refund", "exchange", "warranty", "money back",
        "return shipping", "defective", "damaged", "wrong item",
        "refund policy",
    ),
    "delivery": (
        # 中文
        "发货", "配送", "快递", "物流", "包裹", "收货",
        "收货地址", "没收到", "丢件", "送错", "快递单号",
        "查物流", "催发货", "预计到达", "延误", "签收",
        # 英文
        "shipping", "delivery", "tracking", "package", "delivered",
        "not received", "lost package", "delivery address",
        "where is my", "eta", "estimated",
    ),
    "outages": (
        # 中文
        "宕机", "挂了", "故障", "维护", "服务中断", "无法访问",
        "打不开网页", "不能用了", "系统崩了", "降级",
        "服务器", "down",
        # 英文
        "down", "outage", "offline", "disruption", "not accessible",
        "service disruption", "maintenance", "degradation",
        "unavailable", "not responding",
    ),
    "sales": (
        # 中文
        "报价", "询价", "企业版", "折扣", "优惠", "许可证",
        "演示", "试用", "销售", "采购", "多少钱", "怎么收费",
        "套餐", "方案", "合作",
        # 英文
        "pricing", "quote", "enterprise", "discount", "license",
        "demo", "trial", "sales inquiry", "procurement",
        "how much", "cost",
    ),
    "feedback": (
        # 中文
        "投诉", "反馈", "评价", "不满", "不满意", "建议",
        "退订", "取消订阅邮件", "差评",
        # 英文
        "complaint", "feedback", "review", "unhappy", "dissatisfied",
        "suggestion", "unsubscribe",
    ),
    "hr": (
        # 中文
        "入职", "员工", "福利", "工资", "请假", "休假",
        "HR", "离职", "新人", "社保", "公积金", "考勤",
        # 英文
        "onboarding", "employee", "benefits", "payroll", "leave",
        "hr issue", "termination", "new hire",
    ),
    "it_support": (
        # 中文
        "工作站", "笔记本", "打印机", "投影仪", "资产",
        "办公", "激活", "部署", "安装软件", "公司电脑",
        "设备", "硬件", "网络",
        # 英文
        "workstation", "laptop", "printer", "projector", "asset",
        "office", "license activation", "deploy", "software install",
        "hardware", "network",
    ),
    "product_support": (
        # 中文
        "设置", "安装", "配置", "兼容性", "功能", "怎么用",
        "使用说明", "手册", "帮助文档", "教程", "新手",
        "入门", "操作指南", "常见问题",
        # 英文
        "setup", "set up", "install", "configuration", "compatibility",
        "feature", "how to use", "user manual", "guide",
        "documentation", "tutorial", "faq",
    ),
    "general": (
        # 中文
        "其他", "一般", "杂项",
        # 英文
        "generic", "miscellaneous", "other",
    ),
}

_KNOWN_DOMAINS = tuple(sorted(_DOMAIN_KEYWORDS.keys()))


@dataclass(frozen=True)
class RouterResult:
    """路由结果，含多阶段分数用于离线分析。"""

    allowed_domains: tuple[str, ...]
    primary_domain: str | None
    confidence: float
    method: str  # "keywords_strong" | "keywords_weak" | "llm" | "none"
    raw_confidence: float | None = None
    domain_weights: tuple[tuple[str, float], ...] = ()
    routing_trace: dict[str, Any] | None = None


def _rule_scores(query: str) -> dict[str, float]:
    """对 14 域做中英双语关键词计分（大小写不敏感）。"""
    q_lower = query.lower()
    scores: dict[str, float] = {d: 0.0 for d in _KNOWN_DOMAINS}
    for dom, kws in _DOMAIN_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in q_lower:
                scores[dom] += 1.0
    return scores


def _llm_pick_domain(query: str, settings: Settings) -> str | None:
    """LLM 从 14 个域中选最相关的一个。"""
    if not settings.zhipuai_api_key:
        return None
    from app.llm_zhipu import chat_completion

    dom_list = list(_KNOWN_DOMAINS)
    sys_p = (
        "你是客服领域分类器。根据用户问题，从给定的 domain 列表中只选一个最相关的。\n"
        "输出严格 JSON：{\"domain\":\"...\"}，不要其它文字。"
    )
    user_p = f"domain 列表：{dom_list}\n用户问题：{query.strip()}"
    try:
        raw = chat_completion(sys_p, user_p)
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return None
        obj = json.loads(m.group())
        d = obj.get("domain")
        if isinstance(d, str) and d in _DOMAIN_KEYWORDS:
            return d
    except Exception:
        logger.exception("domain router LLM 分类失败")
    return None


def route_domains(query: str, settings: Settings) -> RouterResult:
    """客服领域路由主入口。

    1. 关键词 ≥2 → 强信号直接返回
    2. 关键词 =1 且唯一 → 中等信号返回
    3. 无命中或多域竞争 → LLM 分类
    4. 全失败 → 返回 None
    """
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

    # ── 强信号：≥2 个关键词命中同一域 ──
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

    # ── 中等信号：1 个命中且唯一 ──
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

    # ── 多域竞争（>1 域命中 1 个）或 0 命中 → LLM ──
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

    # ── 全失败 ──
    trace["confidence_branch"] = "none"
    return RouterResult(
        (), None, 0.0, "none",
        raw_confidence=None,
        routing_trace=trace,
    )
