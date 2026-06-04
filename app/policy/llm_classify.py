"""Optional Zhipu JSON classifier for policy risk tier."""
from __future__ import annotations

import json
import re
from typing import Any

from app.config import get_settings


_POLICY_SYSTEM = """你是企业客服/工单场景的策略分类器。
只输出一个 JSON 对象（不要 markdown），字段：
{"risk":"none|low|medium|high","confidence":0到1之间小数}
risk 含义：none=无合规/越权关切；low=低风险提示；medium=可能需要人工复核；high=明确应拦截或转人工。"""


def classify_policy_risk_llm(query: str) -> tuple[str | None, float | None]:
    settings = get_settings()
    if not settings.zhipuai_api_key:
        return None, None
    try:
        from openai import OpenAI
    except ImportError:
        return None, None

    client = OpenAI(
        api_key=settings.zhipuai_api_key,
        base_url=settings.zhipu_api_base,
    )
    user_prompt = f"用户问题：\n{query.strip()[:4000]}"

    try:
        msgs = [
            {"role": "system", "content": _POLICY_SYSTEM},
            {"role": "user", "content": user_prompt},
        ]
        base_kw: dict[str, Any] = {
            "model": settings.zhipu_chat_model,
            "messages": msgs,
            "temperature": 0.1,
        }
        try:
            resp = client.chat.completions.create(
                **base_kw,
                response_format={"type": "json_object"},
            )
        except Exception:
            resp = client.chat.completions.create(**base_kw)
        raw = (resp.choices[0].message.content or "").strip()
    except Exception:
        return None, None

    return _parse_risk_json(raw)


def _parse_risk_json(raw: str) -> tuple[str | None, float | None]:
    blob = raw
    try:
        data = json.loads(blob)
        if isinstance(data, dict):
            return _normalize_dict_result(data)
    except json.JSONDecodeError:
        pass
    # fence or extra text
    m = re.search(r"\{[^{}]*\}", blob, flags=re.DOTALL)
    if m:
        try:
            data = json.loads(m.group())
            if isinstance(data, dict):
                return _normalize_dict_result(data)
        except json.JSONDecodeError:
            pass
    return None, None


def _normalize_dict_result(data: dict[str, Any]) -> tuple[str | None, float | None]:
    risk = data.get("risk") or data.get("level") or data.get("class")
    conf = data.get("confidence")
    rs = str(risk).strip().lower() if risk is not None else None
    if rs not in ("none", "low", "medium", "high"):
        # partial match zh
        if rs:
            fix = "".join(rs.split())
            if "高" in fix:
                rs = "high"
            elif "中" in fix:
                rs = "medium"
            elif "低" in fix:
                rs = "low"
            elif "无" in fix or "none" in fix.lower():
                rs = "none"
            else:
                rs = None
    try:
        cf = float(conf) if conf is not None else None
        if cf is not None:
            cf = max(0.0, min(1.0, cf))
    except (TypeError, ValueError):
        cf = None
    return rs, cf
