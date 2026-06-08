"""Smoke test: verify CS Agent retrieval pipeline works with the new corpus."""
import os, sys, json, time
os.environ["QDRANT_COLLECTION_NAME"] = "cs_agent"
os.environ["BM25_CORPUS_PATH"] = "data/bm25_cs_corpus.jsonl"
os.environ["QDRANT_PATH"] = "data/qdrant_cs_local"
os.environ["VECTOR_BACKEND"] = "qdrant"
os.environ["INFERENCE_DEVICE"] = "cuda"
os.environ["EVAL_SKIP_DOMAIN_ROUTER"] = "false"

from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.vector_index import get_vector_index
from app.retrieval_pipeline import retrieve_scored_nodes

settings = get_settings()
print(f"Collection: {settings.qdrant_collection_name}")
print(f"BM25:       {Path(settings.bm25_corpus_path).exists()}")

t0 = time.perf_counter()
index = get_vector_index()
print(f"Index loaded: {time.perf_counter()-t0:.1f}s")

queries = [
    "How do I cancel my order?",
    "My credit card was charged twice",
    "VPN stopped working after update",
]

for q in queries:
    t0 = time.perf_counter()
    sr = retrieve_scored_nodes(index, q, 3, settings, skip_domain_router=False)
    dt = time.perf_counter() - t0
    print(f"\nQ: {q}")
    print(f"  Router: {sr.router_result.primary_domain if sr.router_result else 'N/A'}")
    for i, sn in enumerate(sr.nodes[:3]):
        text = (sn.node.get_content() or "")[:100]
        print(f"  #{i+1} [{sn.score:.3f}] domain={sn.node.metadata.get('domain', '?')} | {text}...")
    print(f"  Time: {dt:.2f}s")
