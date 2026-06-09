"""构建中文知识库索引：Qdrant kb_cn_general + BM25 语料。

从清洗后的 FAQ JSONL 构建向量索引和 BM25 语料。
与英文 Collection (kb_en_de) 完全独立。

用法：
  python scripts/build_cn_index.py --faq-file data/docs_cn/faq_cn.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def build_cn_index(faq_file: str, settings=None):
    """构建中文 Qdrant 索引 + BM25 语料。

    每个 FAQ 条目生成一个 document chunk：
      text = f"【问题】{q}\\n【解答】{a}"
      metadata = {domain, source, ...}
    """
    faq_path = Path(faq_file)
    if not faq_path.exists():
        logger.error("FAQ file not found: %s", faq_path)
        return 0

    from app.config import get_settings
    from app.embeddings import get_embedding_model
    from app.qdrant_index_store import _qdrant_client
    from llama_index.core import Document, StorageContext, VectorStoreIndex
    from llama_index.vector_stores.qdrant import QdrantVectorStore

    settings = settings or get_settings()
    collection_name = getattr(settings, "qdrant_collection_name_cn", "kb_cn_general")

    # Load FAQs
    faqs: list[dict] = []
    with open(faq_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                faqs.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    logger.info("Building CN index: %d FAQs → Collection '%s'", len(faqs), collection_name)

    if not faqs:
        logger.warning("No FAQs to index")
        return 0

    # Build documents
    documents: list[Document] = []
    for faq in faqs:
        q = faq.get("q", "")
        a = faq.get("a", "")
        domain = faq.get("domain", "general")
        text = f"【问题】{q}\n【解答】{a}"
        doc = Document(
            text=text,
            metadata={
                "domain": domain,
                "language": "zh",
                "source": faq.get("source", "faq_cn"),
                "type": "faq",
            },
        )
        documents.append(doc)

    # Chunk and embed
    from app.chunking import build_nodes

    nodes = build_nodes(documents, settings)
    if not nodes:
        logger.warning("No nodes generated")
        return 0

    embed_model = get_embedding_model()
    logger.info("Embedding %d nodes (GPU)...", len(nodes))
    for i, node in enumerate(nodes):
        if node.embedding is None:
            text = node.get_content(metadata_mode="none") or ""
            node.embedding = embed_model.get_text_embedding(text)
        if (i + 1) % 500 == 0:
            logger.info("  embedding progress: %d/%d", i + 1, len(nodes))

    # Build Qdrant index
    client = _qdrant_client(settings)

    # Delete existing collection if exists
    try:
        client.delete_collection(collection_name)
        logger.info("Deleted existing collection '%s'", collection_name)
    except Exception:
        pass

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
    )

    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(
        nodes=nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True,
    )

    # Build BM25 corpus
    from app.bm25_store import persist_bm25_corpus
    bm25_path = getattr(settings, "bm25_corpus_path_cn", "data/bm25_cn_corpus.jsonl")
    persist_bm25_corpus(nodes, settings, corpus_path=bm25_path)

    logger.info("CN index complete: %d nodes → '%s'", len(nodes), collection_name)
    logger.info("BM25 corpus: %s", bm25_path)
    return len(nodes)


def main():
    parser = argparse.ArgumentParser(description="Build Chinese knowledge base index")
    parser.add_argument("--faq-file", default="data/docs_cn/faq_cn.jsonl", help="Cleaned FAQ JSONL file")
    parser.add_argument("--collection", default="kb_cn_general", help="Qdrant collection name")
    args = parser.parse_args()

    os.environ.setdefault("QDRANT_COLLECTION_NAME_CN", args.collection)
    os.environ.setdefault("QDRANT_PATH", "data/qdrant_cn_local")

    from app.config import get_settings
    settings = get_settings()

    t0 = time.perf_counter()
    count = build_cn_index(args.faq_file, settings)
    elapsed = time.perf_counter() - t0

    logger.info("Build complete: %d nodes in %.1f seconds (%.1f nodes/sec)", count, elapsed, count / max(elapsed, 1))
    logger.info("Collection: %s", args.collection)
    logger.info("Qdrant path: %s", settings.qdrant_path)


if __name__ == "__main__":
    main()
