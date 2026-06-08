"""智谱 GLM（OpenAI 兼容端点）。"""
from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.metrics import record_llm_call

logger = logging.getLogger(__name__)


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
    max_retries = getattr(settings, "llm_max_retries", 2)
    timeout_s = getattr(settings, "llm_timeout_seconds", 60.0)
    last_exc = None
    t0 = time.perf_counter()
    for attempt in range(max_retries + 1):
        try:
            # Langfuse trace (disabled by default; set LANGFUSE_ENABLED=true)
            _langfuse_generation = None
            lf_client = None
            if getattr(settings, "langfuse_enabled", False):
                try:
                    from app.telemetry import _langfuse
                    if _langfuse is not None:
                        lf_client = _langfuse
                except Exception:
                    pass

            resp = client.chat.completions.create(
                model=settings.zhipu_chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                timeout=timeout_s,
            )
            if lf_client is not None:
                try:
                    lf_client.generation(
                        name="chat_completion",
                        model=settings.zhipu_chat_model,
                        input=f"sys:{system_prompt[:200]}\nuser:{user_prompt[:500]}",
                        output=(choice.content or "")[:1000],
                        metadata={"model": settings.zhipu_chat_model, "attempt": attempt},
                    )
                except Exception:
                    pass
            choice = resp.choices[0].message
            result = (choice.content or "").strip()
            record_llm_call(success=True, duration_s=time.perf_counter() - t0, model=settings.zhipu_chat_model)
            return result
        except Exception as exc:
            last_exc = exc
            err_str = str(exc)
            if "429" in err_str or "503" in err_str or "502" in err_str or attempt < max_retries:
                wait = 1.0 * (2 ** attempt)
                logger.warning("LLM attempt %s/%s failed: %s, retrying in %.1fs", attempt + 1, max_retries + 1, exc, wait)
                time.sleep(wait)
            else:
                break
    record_llm_call(success=False, duration_s=time.perf_counter() - t0, model=settings.zhipu_chat_model)
    raise RuntimeError(f"LLM call failed after {max_retries + 1} attempts: {last_exc}") from last_exc


def get_zhipu_client():
    settings = get_settings()
    if not settings.zhipuai_api_key:
        raise RuntimeError("未配置 ZHIPUAI_API_KEY 或 ZHIPU_API_KEY")
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("请安装 openai 包: pip install openai") from e
    return OpenAI(
        api_key=settings.zhipuai_api_key,
        base_url=settings.zhipu_api_base,
    )
