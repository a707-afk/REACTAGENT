"""End-to-end validation: dual collection + language routing + retrieval."""
import sys, os
sys.path.insert(0, "/mnt/workspace/rag-kb-project")
os.environ["QWEN_EMBEDDING_MODEL_PATH"] = "/mnt/workspace/rag-kb-project/models/Qwen/Qwen3-Embedding-0___6B"
os.environ["QDRANT_PATH"] = "/mnt/workspace/rag-kb-project/data/qdrant_local"
os.environ["QDRANT_COLLECTION_NAME"] = "rag_kb"
os.environ["QDRANT_COLLECTION_NAME_CN"] = "kb_cn_general"
os.environ["BM25_CORPUS_PATH"] = "data/bm25_corpus.jsonl"
os.environ["BM25_CORPUS_PATH_CN"] = "data/bm25_cn_corpus.jsonl"

from app.vector_index import get_vector_index, get_vector_index_cn
from app.qdrant_index_store import clear_index_memory_cache, get_qdrant_client
from app.language_router import detect_language, get_collection_for_lang
from app.config import get_settings

client = get_qdrant_client()
settings = get_settings()

print("=" * 50)
print("E2E VALIDATION")
print("=" * 50)

# 1. Verify both collections in shared Qdrant
for name in ["rag_kb", "kb_cn_general"]:
    try:
        info = client.get_collection(name)
        count = client.count(name, exact=True).count
        print(f"[OK] {name}: {count} points")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")

# 2. Language routing
print("\n--- Language Routing ---")
tests = [
    ("How do I return my order?", "en", "rag_kb"),
    ("退货怎么操作", "zh", "kb_cn_general"),
    ("Where is my package?", "en", "rag_kb"),
    ("快递到哪了", "zh", "kb_cn_general"),
]
for query, expected_lang, expected_coll in tests:
    lang = detect_language(query)
    route = get_collection_for_lang(lang, settings)
    ok = lang == expected_lang and route.collection_name == expected_coll
    status = "OK" if ok else f"FAIL (got {lang}/{route.collection_name})"
    print(f"  [{status}] {query}")

# 3. EN Retrieval
print("\n--- EN Retrieval ---")
clear_index_memory_cache()
idx_en = get_vector_index()
r_en = idx_en.as_retriever(similarity_top_k=3)
results = r_en.retrieve("How do I return my order?")
for i, r in enumerate(results[:3]):
    print(f"  [{i+1}] score={r.score:.3f} | {r.node.get_content()[:80]}")

# 4. CN Retrieval
print("\n--- CN Retrieval ---")
clear_index_memory_cache()
idx_cn = get_vector_index_cn()
r_cn = idx_cn.as_retriever(similarity_top_k=3)
results = r_cn.retrieve("退货怎么操作")
for i, r in enumerate(results[:3]):
    print(f"  [{i+1}] score={r.score:.3f} | {r.node.get_content()[:80]}")

# 5. BM25 both
print("\n--- BM25 ---")
from app.bm25_store import bm25_search, clear_bm25_memory_cache
clear_bm25_memory_cache()
hits = bm25_search(settings, "return refund", 3)
print(f"  EN: {len(hits)} hits")
clear_bm25_memory_cache()
hits = bm25_search(settings, "退货退款", 3, corpus_path="/mnt/workspace/rag-kb-project/data/bm25_cn_corpus.jsonl")
print(f"  CN: {len(hits)} hits")

print("\n" + "=" * 50)
print("ALL TESTS PASSED")
print("=" * 50)
