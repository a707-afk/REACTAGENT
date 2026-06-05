"""?????????Qdrant??"""
from __future__ import annotations

from llama_index.core import VectorStoreIndex

from app.config import Settings, get_settings


def rebuild_index() -> int:
    from app.cache import cache_clear
    from app.qdrant_index_store import rebuild_index as _rebuild
    n = _rebuild()
    cache_clear()
    return n


def get_vector_index() -> VectorStoreIndex:
    from app.qdrant_index_store import get_vector_index as _get
    return _get()


def clear_index_memory_cache() -> None:
    from app.qdrant_index_store import clear_index_memory_cache as _clear
    _clear()
