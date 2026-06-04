"""检索缓存 L1 序列化与命中。"""
from __future__ import annotations

from llama_index.core.schema import NodeWithScore, TextNode

from app.cache import (
    build_retrieval_cache_key,
    cache_clear,
    cache_get_retrieval,
    cache_put_retrieval,
    cache_stats,
)
from app.config import Settings
from app.retrieval_pipeline import ScoredRetrieval


def _settings(**kwargs) -> Settings:
    return Settings(**kwargs)


def _sample_sr(text: str = "退款流程") -> ScoredRetrieval:
    node = TextNode(text=text, id_="n-cache-1", metadata={"domain": "cs"})
    return ScoredRetrieval(
        nodes=[NodeWithScore(node=node, score=0.88)],
        retrieval_query="如何退款",
        router_result=None,
    )


def test_build_cache_key_stable_for_same_inputs():
    s = _settings()
    k1 = build_retrieval_cache_key(user_query="  hello ", top_k=5, settings=s)
    k2 = build_retrieval_cache_key(user_query="hello", top_k=5, settings=s)
    assert k1 == k2


def test_l1_cache_hit_and_miss():
    cache_clear()
    s = _settings(cache_enabled=True, cache_semantic_enabled=False)
    key = build_retrieval_cache_key(user_query="q1", top_k=3, settings=s)
    sr = _sample_sr()

    miss, lvl = cache_get_retrieval(key, user_query="q1", settings=s)
    assert miss is None and lvl is None

    cache_put_retrieval(key, "q1", sr, s)
    hit, lvl = cache_get_retrieval(key, user_query="q1", settings=s)
    assert hit is not None
    assert lvl == "l1"
    assert hit.nodes[0].node.get_content() == "退款流程"
    assert cache_stats()["l1_entries"] == 1


def test_cache_disabled_skips_storage():
    cache_clear()
    # 构造参数优先于 .env 中的 CACHE_ENABLED（pydantic-settings 源顺序）
    s = Settings.model_construct(cache_enabled=False)
    key = build_retrieval_cache_key(user_query="q2", top_k=3, settings=s)
    cache_put_retrieval(key, "q2", _sample_sr("x"), s)
    hit, lvl = cache_get_retrieval(key, user_query="q2", settings=s)
    assert hit is None and lvl is None
    assert cache_stats()["l1_entries"] == 0


def test_cache_clear_empties_l1():
    cache_clear()
    s = _settings(cache_enabled=True)
    key = build_retrieval_cache_key(user_query="q3", top_k=3, settings=s)
    cache_put_retrieval(key, "q3", _sample_sr(), s)
    assert cache_stats()["l1_entries"] == 1
    cache_clear()
    assert cache_stats()["l1_entries"] == 0
