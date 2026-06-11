"""LLM 客户端：SenseNova (商汤) — DeepSeek-V4-Flash

OpenAI 兼容端点: https://token.sensenova.cn/v1
API keys 通过 Settings.sensenova_api_keys 或环境变量 SENSENOVA_API_KEYS 配置（逗号分隔多个 key 用于轮转）。
"""

from __future__ import annotations

import os
import logging
import time
import asyncio

from app.config import get_settings
from app.metrics import record_llm_call

logger = logging.getLogger(__name__)

_SENSENOVA_BASE = "https://token.sensenova.cn/v1"
_SENSENOVA_MODEL = "deepseek-v4-flash"

_SENSENOVA_KEYS: list[str] = []
_key_idx = 0


def _load_keys() -> list[str]:
    """Load API keys from Settings (.env), with OS env fallback."""
    raw = getattr(get_settings(), "sensenova_api_keys", None)
    keys = [k.strip() for k in raw.split(",") if k.strip()] if raw else []
    if not keys:
        raw = os.getenv("SENSENOVA_API_KEYS", "").strip()
        keys = [k.strip() for k in raw.split(",") if k.strip()] if raw else []
    return keys


def _next_key() -> str:
    global _key_idx, _SENSENOVA_KEYS
    if not _SENSENOVA_KEYS:
        _SENSENOVA_KEYS = _load_keys()
    if not _SENSENOVA_KEYS:
        raise RuntimeError(
            "未配置 SENSENOVA_API_KEYS，无法调用 LLM。"
            "请在 .env 中设置：SENSENOVA_API_KEYS='sk-xxx,sk-yyy'"
        )
    key = _SENSENOVA_KEYS[_key_idx]
    _key_idx = (_key_idx + 1) % len(_SENSENOVA_KEYS)
    return key


def _get_client():
    """获取 OpenAI 兼容客户端 (SenseNova DeepSeek-V4)。"""
    from openai import OpenAI
    api_key = _next_key()
    return OpenAI(api_key=api_key, base_url=_SENSENOVA_BASE), _SENSENOVA_MODEL


def _get_async_client():
    """获取异步 OpenAI 兼容客户端。"""
    from openai import AsyncOpenAI
    api_key = _next_key()
    return AsyncOpenAI(api_key=api_key, base_url=_SENSENOVA_BASE), _SENSENOVA_MODEL


def chat_completion(system_prompt: str, user_prompt: str) -> str:
    """调用 LLM 聊天补全 (DeepSeek-V4-Flash @ SenseNova)。"""
    settings = get_settings()
    max_retries = getattr(settings, "llm_max_retries", 2)
    timeout_s = getattr(settings, "llm_timeout_seconds", 60.0)
    last_exc = None
    t0 = time.perf_counter()

    for attempt in range(max_retries + 1):
        try:
            client, model = _get_client()
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                timeout=timeout_s,
            )
            choice = resp.choices[0].message
            result = (choice.content or "").strip()
            record_llm_call(success=True, duration_s=time.perf_counter() - t0, model=model)
            return result
        except Exception as exc:
            last_exc = exc
            err_str = str(exc)
            if "429" in err_str or "503" in err_str or "502" in err_str or attempt < max_retries:
                wait = 1.0 * (2 ** attempt)
                logger.warning(
                    "LLM attempt %d/%d failed: %s, retrying in %.1fs",
                    attempt + 1, max_retries + 1, exc, wait,
                )
                time.sleep(wait)
            else:
                break

    record_llm_call(success=False, duration_s=time.perf_counter() - t0, model=_SENSENOVA_MODEL)
    raise RuntimeError(f"LLM call failed after {max_retries + 1} attempts: {last_exc}") from last_exc


async def achat_completion(system_prompt: str, user_prompt: str) -> str:
    """Async LLM chat completion — non-blocking, uses AsyncOpenAI + asyncio.sleep."""
    settings = get_settings()
    max_retries = getattr(settings, "llm_max_retries", 2)
    timeout_s = getattr(settings, "llm_timeout_seconds", 60.0)
    last_exc = None
    t0 = time.perf_counter()

    for attempt in range(max_retries + 1):
        try:
            client, model = _get_async_client()
            resp = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                timeout=timeout_s,
            )
            choice = resp.choices[0].message
            result = (choice.content or "").strip()
            record_llm_call(success=True, duration_s=time.perf_counter() - t0, model=model)
            return result
        except Exception as exc:
            last_exc = exc
            err_str = str(exc)
            if "429" in err_str or "503" in err_str or "502" in err_str or attempt < max_retries:
                wait = 1.0 * (2 ** attempt)
                logger.warning(
                    "LLM async attempt %d/%d failed: %s, retrying in %.1fs",
                    attempt + 1, max_retries + 1, exc, wait,
                )
                await asyncio.sleep(wait)
            else:
                break

    record_llm_call(success=False, duration_s=time.perf_counter() - t0, model=_SENSENOVA_MODEL)
    raise RuntimeError(f"LLM async call failed after {max_retries + 1} attempts: {last_exc}") from last_exc
