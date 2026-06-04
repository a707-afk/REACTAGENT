"""向量索引统一入口：按 ``vector_backend`` 分发 Chroma / Qdrant。"""
from __future__ import annotations

from llama_index.core import VectorStoreIndex

from app.config import Settings, get_settings
from app.vector_backend import resolve_vector_backend


def _effective_backend(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return resolve_vector_backend(settings)


def rebuild_index() -> int:
    from app.cache import cache_clear

    settings = get_settings()
    if _effective_backend(settings) == "qdrant":
        from app.qdrant_index_store import rebuild_index as _rebuild

        n = _rebuild()
    else:
        from app.index_store import rebuild_index as _rebuild

        n = _rebuild()
    cache_clear()
    return n


def get_vector_index() -> VectorStoreIndex:
    settings = get_settings()
    if _effective_backend(settings) == "qdrant":
        from app.qdrant_index_store import get_vector_index as _get

        return _get()
    from app.index_store import get_vector_index as _get

    return _get()


def clear_index_memory_cache() -> None:
    settings = get_settings()
    if _effective_backend(settings) == "qdrant":
        from app.qdrant_index_store import clear_index_memory_cache as _clear

        _clear()
    from app.index_store import clear_index_memory_cache as _clear

    _clear()
