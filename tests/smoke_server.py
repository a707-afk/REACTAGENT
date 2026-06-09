"""Smoke test: verify API server loads correctly."""
import sys, os
sys.path.insert(0, "/mnt/workspace/rag-kb-project")
os.environ["QWEN_EMBEDDING_MODEL_PATH"] = "/mnt/workspace/rag-kb-project/models/Qwen/Qwen3-Embedding-0___6B"
os.environ["QDRANT_PATH"] = "/mnt/workspace/rag-kb-project/data/qdrant_local"
os.environ["QDRANT_COLLECTION_NAME_CN"] = "kb_cn_general"
os.environ["BM25_CORPUS_PATH_CN"] = "data/bm25_cn_corpus.jsonl"
os.environ["DOCS_DIR_CN"] = "data/docs_cn"

print("Loading FastAPI app...")
from app.main import app
print(f"OK - {len(app.routes)} routes registered")

print("\nRoutes:")
for r in app.routes:
    path = getattr(r, "path", "")
    methods = getattr(r, "methods", set())
    name = getattr(r, "name", "")
    if path and methods:
        print(f"  {methods} {path}")

# Test language router import
from app.language_router import detect_language
print(f"\nLanguage router: zh={detect_language('退货')} en={detect_language('refund')}")

# Test domain router import  
from app.domain_router import route_domains
from app.config import get_settings
settings = get_settings()
result = route_domains("退货怎么操作", settings)
print(f"Domain router: primary={result.primary_domain} domains={result.allowed_domains}")

print("\n=== All imports OK ===")
