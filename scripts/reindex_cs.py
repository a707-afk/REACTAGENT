"""Build Qdrant + BM25 indices from the unified customer service corpus.

Reads data/docs_cs/corpus.jsonl, chunks documents, generates embeddings with GPU
(Qwen3-Embedding-0.6B, batched), indexes into Qdrant, and builds BM25 sparse index.

Usage:
    python scripts/reindex_cs.py

Environment:
    QDRANT_COLLECTION_NAME=cs_agent    (default)
    BM25_CORPUS_PATH=data/bm25_cs_corpus.jsonl
    QDRANT_PATH=data/qdrant_cs_local
    INFERENCE_DEVICE=cuda
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- Config overrides for the new CS corpus ---
os.environ.setdefault("QDRANT_COLLECTION_NAME", "cs_agent")
os.environ.setdefault("BM25_CORPUS_PATH", "data/bm25_cs_corpus.jsonl")
os.environ.setdefault("QDRANT_PATH", "data/qdrant_cs_local")
os.environ.setdefault("VECTOR_BACKEND", "qdrant")
os.environ.setdefault("INFERENCE_DEVICE", "cuda")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reindex_cs")

EMBEDDING_BATCH_SIZE = 64  # Qwen3-0.6B on RTX 5070 can handle this


def load_corpus(corpus_path: Path) -> list[dict]:
    docs = []
    with open(corpus_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            docs.append(json.loads(line))
    logger.info("Loaded %d docs from %s", len(docs), corpus_path)
    return docs


def main() -> None:
    from llama_index.core import Document, Settings as LlamaSettings, VectorStoreIndex, StorageContext
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient

    from app.config import get_settings
    from app.embeddings import get_embedding_model
    from app.bm25_store import persist_bm25_corpus, clear_bm25_memory_cache

    settings = get_settings()
    logger.info("=== Reindex CS Agent Corpus ===")
    logger.info("Collection: %s", settings.qdrant_collection_name)
    logger.info("Qdrant path: %s", settings.qdrant_path)
    logger.info("BM25 path: %s", settings.bm25_corpus_path)
    logger.info("Chunk: size=%d overlap=%d", settings.chunk_size_tokens, settings.chunk_overlap_tokens)
    logger.info("Device: %s", os.environ.get("INFERENCE_DEVICE", "cuda"))

    # --- Load corpus ---
    corpus_path = ROOT / "data" / "docs_cs" / "corpus.jsonl"
    if not corpus_path.exists():
        logger.error("Corpus not found: %s", corpus_path)
        sys.exit(1)
    raw_docs = load_corpus(corpus_path)

    # --- Convert to llama_index Documents ---
    logger.info("Converting to llama_index Documents ...")
    llama_docs: list[Document] = []
    for d in raw_docs:
        text = d.get("text", "")
        if not text or len(text) < 10:
            continue
        llama_docs.append(Document(text=text, metadata=dict(d.get("metadata", {}))))
    logger.info("%d valid Documents", len(llama_docs))

    # --- Load embedding model ---
    logger.info("Loading Qwen3-Embedding (GPU) ...")
    embed_model = get_embedding_model()
    LlamaSettings.embed_model = embed_model
    LlamaSettings.chunk_size = settings.chunk_size_tokens
    LlamaSettings.chunk_overlap = settings.chunk_overlap_tokens

    # --- Chunk ---
    logger.info("Chunking (%d docs) ...", len(llama_docs))
    t0 = time.perf_counter()
    parser = SentenceSplitter(
        chunk_size=settings.chunk_size_tokens,
        chunk_overlap=settings.chunk_overlap_tokens,
    )
    nodes = parser.get_nodes_from_documents(llama_docs)
    logger.info("Chunked: %d nodes (%.1fs)", len(nodes), time.perf_counter() - t0)

    # --- Batch Embedding with GPU ---
    logger.info("Generating embeddings (batch_size=%d) ...", EMBEDDING_BATCH_SIZE)
    t0 = time.perf_counter()
    texts_for_embed: list[str] = []
    for node in nodes:
        texts_for_embed.append(node.get_content(metadata_mode="none") or "")

    total = len(texts_for_embed)
    for i in range(0, total, EMBEDDING_BATCH_SIZE):
        batch = texts_for_embed[i : i + EMBEDDING_BATCH_SIZE]
        embeddings = embed_model.get_text_embedding_batch(batch)
        for j, emb in enumerate(embeddings):
            nodes[i + j].embedding = emb
        if (i + EMBEDDING_BATCH_SIZE) % (EMBEDDING_BATCH_SIZE * 10) == 0:
            elapsed = time.perf_counter() - t0
            pct = min(i + EMBEDDING_BATCH_SIZE, total) / total * 100
            rate = min(i + EMBEDDING_BATCH_SIZE, total) / elapsed
            logger.info("  Embedding: %d/%d (%.0f%%), %.0f nodes/s", min(i + EMBEDDING_BATCH_SIZE, total), total, pct, rate)

    elapsed = time.perf_counter() - t0
    logger.info("Embeddings done: %d nodes in %.1fs (%.0f nodes/s)", total, elapsed, total / elapsed)

    # --- Build Qdrant index ---
    logger.info("Building Qdrant index (collection=%s) ...", settings.qdrant_collection_name)
    t0 = time.perf_counter()

    qdrant_path = settings.qdrant_path or "data/qdrant_cs_local"
    Path(qdrant_path).mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=qdrant_path)

    # Delete old collection if exists
    try:
        client.delete_collection(settings.qdrant_collection_name)
    except Exception:
        pass

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection_name,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    idx = VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=False,
    )
    logger.info("Qdrant indexed: %d nodes in %.1fs", len(nodes), time.perf_counter() - t0)

    # --- Build BM25 corpus ---
    logger.info("Building BM25 corpus -> %s ...", settings.bm25_corpus_path)
    persist_bm25_corpus(nodes, settings)
    clear_bm25_memory_cache()

    # --- Stats ---
    bm25_path = Path(settings.bm25_corpus_path)
    logger.info("=== Done ===")
    logger.info("Nodes: %d", len(nodes))
    logger.info("Qdrant: %s (collection=%s)", qdrant_path, settings.qdrant_collection_name)
    logger.info("BM25:  %s (%.1f MB)", bm25_path, bm25_path.stat().st_size / 1024 / 1024 if bm25_path.exists() else 0)


if __name__ == "__main__":
    main()
