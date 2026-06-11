"""VLM (Vision-Language Model) client: SenseNova sensenova-6.7-flash-lite.

Uses the same OpenAI-compatible endpoint as the main LLM (llm.py),
but targets the multimodal model for OCR and image understanding.

Base URL: https://token.sensenova.cn/v1
Model:    sensenova-6.7-flash-lite
API keys: Shared with Settings.sensenova_api_keys
"""
from __future__ import annotations

import base64
import logging
import os

from app.config import get_settings
from app.llm import _load_keys, _SENSENOVA_BASE

logger = logging.getLogger(__name__)

_VLM_MODEL = "sensenova-6.7-flash-lite"


def _next_key() -> str:
    """Reuse the same key rotation logic as llm.py."""
    keys = _load_keys()
    if not keys:
        raise RuntimeError(
            "未配置 SENSENOVA_API_KEYS，无法调用 VLM。"
            "请在 .env 中设置：SENSENOVA_API_KEYS='sk-xxx'"
        )
    return keys[0]


def _get_vlm_model() -> str:
    """Get VLM model name from settings."""
    return getattr(get_settings(), "vlm_model", _VLM_MODEL)


def _get_vlm_client():
    """获取 OpenAI 兼容客户端 (SenseNova VLM)."""
    from openai import OpenAI
    api_key = _next_key()
    return OpenAI(api_key=api_key, base_url=_SENSENOVA_BASE)


def ocr_image(
    image_bytes: bytes | None = None,
    image_base64: str | None = None,
    image_url: str | None = None,
    prompt: str = "请识别图片中的所有文字，包括表格内容。保持原始格式和层级关系。",
) -> str:
    """Call the VLM to extract text from an image.

    Args:
        image_bytes: Raw image bytes (PNG, JPEG, etc.)
        image_base64: Base64-encoded image string
        image_url: URL of the image
        prompt: Instruction for the VLM

    Returns:
        Extracted text from the image
    """
    client = _get_vlm_client()
    settings = get_settings()
    timeout_s = getattr(settings, "llm_timeout_seconds", 60.0)

    # Build image content
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_data_url = f"data:image/png;base64,{b64}"
    elif image_base64:
        if image_base64.startswith("data:"):
            image_data_url = image_base64
        else:
            image_data_url = f"data:image/png;base64,{image_base64}"
    elif image_url:
        image_data_url = image_url
    else:
        raise ValueError("Must provide one of: image_bytes, image_base64, or image_url")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        }
    ]

    resp = client.chat.completions.create(
        model=_get_vlm_model(),
        messages=messages,
        temperature=0.1,
        max_tokens=4096,
        timeout=timeout_s,
    )

    return (resp.choices[0].message.content or "").strip()


def ocr_image_for_table(
    image_bytes: bytes | None = None,
    image_base64: str | None = None,
    image_url: str | None = None,
) -> str:
    """Call the VLM specifically for table extraction.

    Returns markdown-formatted table text with cell positions preserved.
    """
    return ocr_image(
        image_bytes=image_bytes,
        image_base64=image_base64,
        image_url=image_url,
        prompt=(
            "请识别图片中的表格，以 Markdown 表格格式输出。"
            "保持表格的行列结构，空单元格用空格表示。"
            "如果图片中有文字说明，也请一并识别。"
        ),
    )


def ocr_image_with_coordinates(
    image_bytes: bytes | None = None,
    image_base64: str | None = None,
    image_url: str | None = None,
) -> str:
    """Call the VLM for OCR with coordinate/bounding box info.

    Returns text with approximate position info for citation tracking.
    """
    return ocr_image(
        image_bytes=image_bytes,
        image_base64=image_base64,
        image_url=image_url,
        prompt=(
            "请识别图片中的所有文字。"
            "对于每个文字块，标注其大致位置（顶部/中部/底部，左侧/中间/右侧）。"
            "格式：[位置] 文字内容。保持原始阅读顺序。"
        ),
    )
