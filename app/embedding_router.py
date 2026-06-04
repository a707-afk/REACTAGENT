"""基于 query embedding 与各域原型文本 embedding 的余弦相似度做软路由打分。"""
from __future__ import annotations

import math
from collections import OrderedDict
from typing import Any

from app.config import Settings

# prototype → centroid 嵌入缓存（按 domain / 原型集合 / 模型路径键控），Phase B / 长跑评测降费。
_CENTROID_LRU_MAX = 96
_centroid_emb_cache: OrderedDict[tuple[str, str, tuple[str, ...]], list[float]] = (
    OrderedDict()
)


def clear_embedding_router_centroid_cache() -> None:
    """profiles 或嵌入模型切换后清空；单测可调。"""
    _centroid_emb_cache.clear()


def _centroid_cache_key(
    dom: str, protos: tuple[str, ...], model_hint: str
) -> tuple[str, str, tuple[str, ...]]:
    canon = tuple(sorted((p.strip() for p in protos if (p or "").strip())))
    return (dom, model_hint, canon)


def _cache_put_centroid(key: tuple[str, str, tuple[str, ...]], vec: list[float]) -> None:
    if key in _centroid_emb_cache:
        _centroid_emb_cache.move_to_end(key)
        _centroid_emb_cache[key] = vec
        return
    if len(_centroid_emb_cache) >= _CENTROID_LRU_MAX:
        _centroid_emb_cache.popitem(last=False)
    _centroid_emb_cache[key] = vec


def _cosine_sim(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=False):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _embedding_list(text: str, settings: Settings) -> list[float]:
    from app.embeddings import get_embedding_model

    model = get_embedding_model()
    return list(model.get_query_embedding(text.strip()))


def _centroid_vectors_for_domain(
    dom: str, prototypes: tuple[str, ...], settings: Settings
) -> list[float]:
    mp = ((settings.qwen_embedding_model_path or "").strip())[:512]
    ckey = _centroid_cache_key(dom, prototypes, mp)
    if ckey in _centroid_emb_cache:
        hit = list(_centroid_emb_cache[ckey])
        _centroid_emb_cache.move_to_end(ckey)
        return hit

    mats: list[list[float]] = []
    for proto in prototypes:
        if not (proto or "").strip():
            continue
        mats.append(_embedding_list(proto, settings))
    if not mats:
        return []
    dim = len(mats[0])
    acc = [0.0] * dim
    for row in mats:
        if len(row) != dim:
            continue
        for i, v in enumerate(row):
            acc[i] += v
    inv = 1.0 / float(len(mats))
    out = [inv * acc[i] for i in range(dim)]
    _cache_put_centroid(ckey, out)
    return out


def score_domains_via_embedding(
    query: str,
    *,
    settings: Settings,
    domains: tuple[str, ...],
    prototypes: dict[str, tuple[str, ...]],
) -> tuple[dict[str, float], dict[str, Any]]:
    """返回 ({domain: similarity 0..1}, diagnostics)."""
    text = (query or "").strip()
    diag: dict[str, Any] = {"skipped": False, "reason": None}
    if not text:
        diag["skipped"] = True
        diag["reason"] = "empty_query"
        return ({}, diag)

    try:
        qv = _embedding_list(text, settings)
    except Exception as exc:  # noqa: BLE001
        diag["skipped"] = True
        diag["reason"] = f"embedding_error:{exc!r}"
        return ({}, diag)

    scores: dict[str, float] = {}
    centroid_meta: dict[str, Any] = {}
    for dom in domains:
        protos = prototypes.get(dom) or ()
        cen = _centroid_vectors_for_domain(dom, protos, settings)
        if not cen:
            scores[dom] = 0.0
            continue
        s = max(0.0, float(_cosine_sim(qv, cen)))
        scores[dom] = s
        centroid_meta[dom] = {"prototype_count": len(protos)}
    diag["centroids"] = centroid_meta
    diag["cache_size"] = len(_centroid_emb_cache)
    return (scores, diag)
