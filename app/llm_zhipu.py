"""智谱 GLM（OpenAI 兼容端点）。"""
from __future__ import annotations

from app.config import get_settings


def chat_completion(system_prompt: str, user_prompt: str) -> str:
    settings = get_settings()
    if not settings.zhipuai_api_key:
        raise RuntimeError("未配置 ZHIPUAI_API_KEY 或 ZHIPU_API_KEY")
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("请安装 openai 包: pip install openai") from e

    client = OpenAI(
        api_key=settings.zhipuai_api_key,
        base_url=settings.zhipu_api_base,
    )
    resp = client.chat.completions.create(
        model=settings.zhipu_chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    choice = resp.choices[0].message
    return (choice.content or "").strip()
