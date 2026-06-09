"""语言检测 + 双知识库路由。

策略：
1. 检测输入语言（zh / en / de / other）
2. 中文 → Qdrant kb_cn_general + 中文 Domain Router
3. 英文/德文 → Qdrant kb_en_de + 英文 Domain Router

用法：
    from app.language_router import detect_language, get_collection_for_lang
    lang = detect_language(query)
    collection = get_collection_for_lang(lang, settings)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.config import Settings

Language = Literal["zh", "en", "de", "other"]

# CJK 统一码范围
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
# 德语特有字符
_DE_RE = re.compile(r"[äöüßÄÖÜ]")


def detect_language(text: str) -> Language:
    """基于字符集启发式检测语言。"""
    if not text or not text.strip():
        return "other"

    chars = text.strip()
    total = len(chars)
    cjk_count = len(_CJK_RE.findall(chars))

    # 中文：> 20% CJK 字符
    if cjk_count / max(total, 1) > 0.20:
        return "zh"

    # 德文：有德语特有字符
    if _DE_RE.search(chars):
        return "de"

    # 英文：ASCII 为主
    ascii_count = sum(1 for c in chars if ord(c) < 128)
    if ascii_count / max(total, 1) > 0.70:
        return "en"

    return "other"


@dataclass(frozen=True)
class LanguageRoute:
    """语言路由结果。"""

    language: Language
    collection_name: str
    docs_dir: str
    bm25_path: str


def get_collection_for_lang(lang: Language, settings: Settings) -> LanguageRoute:
    """根据语言返回对应的 Qdrant Collection 和数据路径。"""
    if lang == "zh":
        return LanguageRoute(
            language="zh",
            collection_name=getattr(settings, "qdrant_collection_name_cn", "kb_cn_general"),
            docs_dir=getattr(settings, "docs_dir_cn", "data/docs_cn"),
            bm25_path=getattr(settings, "bm25_corpus_path_cn", "data/bm25_cn_corpus.jsonl"),
        )
    else:
        return LanguageRoute(
            language="en",
            collection_name=settings.qdrant_collection_name,
            docs_dir=settings.docs_dir,
            bm25_path=settings.bm25_corpus_path,
        )
