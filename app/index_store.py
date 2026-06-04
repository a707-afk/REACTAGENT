"""Chroma 向量索引：构建、加载、检索。"""
from __future__ import annotations

import logging
from pathlib import Path

import chromadb
from chromadb.errors import NotFoundError as ChromaNotFoundError
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.chunking import build_nodes, load_documents
from app.config import Settings, get_settings
from app.embeddings import get_embedding_model
from app.bm25_store import persist_bm25_corpus

logger = logging.getLogger(__name__)

_index: VectorStoreIndex | None = None


def _paths(settings: Settings) -> tuple[Path, Path]:
    docs = Path(settings.docs_dir).resolve()
    chroma = Path(settings.chroma_persist_dir).resolve()
    return docs, chroma


def rebuild_index() -> int:
    """清空集合并写入当前 docs_dir；返回节点数。"""
    global _index
    settings = get_settings()
    docs_dir, chroma_dir = _paths(settings)
    documents = load_documents(docs_dir)
    nodes = build_nodes(documents, settings)
    if not nodes:
        logger.warning("无节点可索引: %s", docs_dir)
        return 0

    embed_model = get_embedding_model()
    # 先完成全部 embedding，再删/建 Chroma 集合，避免 Windows 上长时间 embed 后 collection UUID 失效
    logger.info("预计算 embedding: %s 个节点", len(nodes))
    for i, node in enumerate(nodes):
        if node.embedding is None:
            text = node.get_content(metadata_mode="none") or ""
            node.embedding = embed_model.get_text_embedding(text)
        if (i + 1) % 50 == 0:
            logger.info("embedding 进度 %s/%s", i + 1, len(nodes))

    chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_dir))
    try:
        client.delete_collection(settings.chroma_collection_name)
    except ChromaNotFoundError:
        pass
    coll = client.get_or_create_collection(settings.chroma_collection_name)
    vector_store = ChromaVectorStore(chroma_collection=coll)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    idx = VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=False,
    )
    persist_bm25_corpus(nodes, settings)
    _index = idx
    logger.info("索引完成: %s 个节点", len(nodes))
    return len(nodes)


def get_vector_index() -> VectorStoreIndex:
    global _index
    if _index is not None:
        return _index
    settings = get_settings()
    _, chroma_dir = _paths(settings)
    if not chroma_dir.is_dir():
        raise RuntimeError("未找到 Chroma 目录，请先运行: python scripts/reindex.py")
    embed_model = get_embedding_model()
    client = chromadb.PersistentClient(path=str(chroma_dir))
    try:
        coll = client.get_collection(settings.chroma_collection_name)
    except Exception as e:
        raise RuntimeError(
            "Chroma 集合不存在，请先运行: python scripts/reindex.py"
        ) from e
    vector_store = ChromaVectorStore(chroma_collection=coll)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    _index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
        embed_model=embed_model,
    )
    return _index


def clear_index_memory_cache() -> None:
    global _index
    _index = None
