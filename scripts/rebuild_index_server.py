"""
Rebuild Qdrant index from e-commerce FAQ documents.
Loads embedding model, chunks docs, creates vectors, uploads to Qdrant.
"""
import json
import os
import sys
import time
import logging
import uuid
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("rebuild_index")

PROJECT_ROOT = Path("/root/rag-kb-project")
DOCS_DIR = PROJECT_ROOT / "data" / "docs_ecom"
DOC_FILES = [
    "faq_all.md", "faq_complaint.md", "faq_exchange.md",
    "faq_refund.md", "faq_return_policy.md", "faq_shipping.md"
]

# Embedding model config
MODEL_NAME = "BAAI/bge-m3"
MODEL_PATH = "/root/models/BAAI/bge-m3"
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "rag_kb"


def load_docs() -> list[dict]:
    """Load documents as chunks."""
    chunks = []
    for fname in DOC_FILES:
        path = DOCS_DIR / fname
        if not path.exists():
            logger.warning("File not found: %s", path)
            continue
        text = path.read_text(encoding="utf-8")
        # Split by ## Q: for sensible chunks
        sections = text.split("\n## ")
        for i, section in enumerate(sections):
            if not section.strip():
                continue
            if i == 0:
                # Title/header section
                header = section.strip()
                if len(header) < 20:
                    continue  # skip just the title
                chunk_text = header
                section_id = "header"
            else:
                chunk_text = "## " + section.strip()
                # Extract Q from the section for the section_id
                q_line = section.split("\n")[0] if section else ""
                section_id = q_line.replace("Q: ", "").strip()[:40]

            chunk_id = f"{fname}:{section_id}"[:100]
            chunks.append({
                "chunk_id": chunk_id,
                "file_name": fname,
                "text": chunk_text,
                "section_id": section_id,
            })

    logger.info("Loaded %d chunks from %d docs", len(chunks), len(DOC_FILES))
    return chunks


def create_collection():
    """Create or recreate the Qdrant collection."""
    import requests
    # Delete if exists
    requests.delete(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")

    # Create collection with 1024-dim vectors (bge-m3)
    payload = {
        "vectors": {
            "size": 1024,
            "distance": "Cosine"
        },
        "hnsw_config": {
            "m": 16,
            "ef_construct": 100
        },
        "optimizers_config": {
            "default_segment_number": 2
        },
        "wal_config": {
            "wal_capacity_mb": 32
        },
        "on_disk_payload": True
    }
    r = requests.put(f"{QDRANT_URL}/collections/{COLLECTION_NAME}", json=payload)
    if r.status_code not in (200, 201):
        logger.error("Failed to create collection: %s", r.text)
        return False
    logger.info("Collection '%s' created (1024-dim, Cosine)", COLLECTION_NAME)
    return True


def main():
    # Load embedding model
    logger.info("Loading embedding model: %s", MODEL_NAME)
    t0 = time.time()
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_PATH, device="cuda")
    dim = model.get_embedding_dimension()
    logger.info(f"Model loaded in {time.time()-t0:.1f}s, dim={dim}, device=cuda")

    # Load document chunks
    chunks = load_docs()
    if not chunks:
        logger.error("No chunks loaded!")
        sys.exit(1)

    # Create Qdrant collection
    import requests
    if not create_collection():
        sys.exit(1)

    # Generate embeddings
    logger.info("Generating embeddings for %d chunks...", len(chunks))
    t0 = time.time()
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=16, show_progress_bar=True)
    logger.info(f"Embeddings generated in {time.time()-t0:.1f}s")

    # Prepare points
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels

    client = QdrantClient(url=QDRANT_URL)

    points = []
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["chunk_id"]))
        points.append(qmodels.PointStruct(
            id=point_id,
            vector=emb.tolist(),
            payload={
                "file_name": chunk["file_name"],
                "file_path": chunk["file_name"],
                "source_path": chunk["file_name"],
                "doc_group": chunk["file_name"],
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "tenant_id": "corp-default",
            }
        ))

    # Upload in batches
    batch_size = 32
    for i in range(0, len(points), batch_size):
        batch = points[i:i+batch_size]
        client.upsert(collection_name=COLLECTION_NAME, points=batch)
        if (i // batch_size) % 5 == 0:
            logger.info(f"Uploaded {min(i+batch_size, len(points))}/{len(points)} points")

    logger.info(f"Upload complete: {len(points)} points")

    # Verify
    count = client.count(collection_name=COLLECTION_NAME, exact=True)
    logger.info(f"Qdrant collection count: {count.count}")

    # Print unique file_names
    scroll = client.scroll(collection_name=COLLECTION_NAME, limit=100, with_payload=["file_name"], with_vectors=False)
    fnames = set()
    for p in scroll[0]:
        fn = p.payload.get("file_name", "")
        if fn:
            fnames.add(fn)
    logger.info(f"Unique file_names: {sorted(fnames)}")
    print(f"\n=== DONE ===\n{count.count} vectors in '{COLLECTION_NAME}'")


if __name__ == "__main__":
    main()
