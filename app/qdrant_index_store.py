"""Qdrant 向量索引：构建、加载（用 qdrant_collection_name 配置）。"""
from __future__ import annotations

import logging
from pathlib import Path

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from app.chunking import build_nodes, load_documents
from app.config import Settings, get_settings
from app.embeddings import get_embedding_model
from app.bm25_store import persist_bm25_corpus

logger = logging.getLogger(__name__)

_index: VectorStoreIndex | None = None
_client: QdrantClient | None = None
_client_key: str | None = None


def _qdrant_client(settings: Settings) -> QdrantClient:
    """复用同一 QdrantClient（本地 path 模式不支持多实例并发打开同一目录）。"""
    global _client, _client_key
    key = settings.qdrant_path or settings.qdrant_url
    if _client is not None and _client_key == key:
        return _client
    if settings.qdrant_path:
        _client = QdrantClient(path=settings.qdrant_path)
    else:
        kwargs: dict = {"url": settings.qdrant_url}
        if settings.qdrant_api_key:
            kwargs["api_key"] = settings.qdrant_api_key
        _client = QdrantClient(**kwargs)
    _client_key = key
    return _client


def rebuild_index() -> int:
    """写入 Qdrant collection（先 embed 再建库，）。"""
    global _index
    settings = get_settings()
    docs_dir = Path(settings.docs_dir).resolve()
    documents = load_documents(docs_dir)
    nodes = build_nodes(documents, settings)
    if not nodes:
        logger.warning("无节点可索引: %s", docs_dir)
        return 0

    embed_model = get_embedding_model()
    logger.info("预计算 embedding (Qdrant): %s 个节点", len(nodes))
    for i, node in enumerate(nodes):
        if node.embedding is None:
            text = node.get_content(metadata_mode="none") or ""
            node.embedding = embed_model.get_text_embedding(text)
        if (i + 1) % 50 == 0:
            logger.info("embedding 进度 %s/%s", i + 1, len(nodes))

    client = _qdrant_client(settings)
    coll_name = settings.qdrant_collection_name
    try:
        client.delete_collection(coll_name)
    except Exception:
        pass

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=coll_name,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    idx = VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=False,
    )
    persist_bm25_corpus(nodes, settings)
    _index = idx
    logger.info("Qdrant 索引完成: %s 个节点 -> %s", len(nodes), coll_name)
    return len(nodes)


def get_vector_index() -> VectorStoreIndex:
    global _index
    if _index is not None:
        return _index
    settings = get_settings()
    client = _qdrant_client(settings)
    coll_name = settings.qdrant_collection_name
    try:
        client.get_collection(coll_name)
    except Exception as e:
        raise RuntimeError(
            f"Qdrant 集合 {coll_name!r} 不存在，请先 VECTOR_BACKEND=qdrant python scripts/reindex.py"
        ) from e

    embed_model = get_embedding_model()
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=coll_name,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    _index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
        embed_model=embed_model,
    )
    return _index


def clear_index_memory_cache() -> None:
    global _index, _client, _client_key
    _index = None
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = None
    _client_key = None


def get_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    return _qdrant_client(settings or get_settings())
