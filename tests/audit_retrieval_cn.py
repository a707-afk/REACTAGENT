# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, "/mnt/workspace/rag-kb-project")
os.environ["QWEN_EMBEDDING_MODEL_PATH"] = "/mnt/workspace/rag-kb-project/models/Qwen/Qwen3-Embedding-0___6B"
os.environ["QDRANT_PATH"] = "/mnt/workspace/rag-kb-project/data/qdrant_cn_local"
os.environ["QDRANT_COLLECTION_NAME_CN"] = "kb_cn_general"
os.environ["BM25_CORPUS_PATH_CN"] = "data/bm25_cn_corpus.jsonl"

from app.vector_index import get_vector_index_cn
from app.qdrant_index_store import get_qdrant_client

client = get_qdrant_client()
count = client.count("kb_cn_general", exact=True)
print(f"Qdrant: kb_cn_general = {count.count} points")

idx = get_vector_index_cn()
retriever = idx.as_retriever(similarity_top_k=5)

queries = [
    ("退货退款怎么操作", "returns"),
    ("快递到哪了怎么查物流", "delivery"),
    ("订单怎么取消", "order"),
    ("发票怎么开具", "billing"),
    ("密码忘了怎么办", "account"),
    ("商品坏了能修吗", "tech_support"),
    ("客服电话多少", "customer_service"),
    ("投诉在哪里提交", "feedback"),
    ("产品使用说明书在哪里", "product_support"),
    ("这个商品多少钱", "sales"),
]

print("\n=== Retrieval Accuracy ===")
hits = 0
for query, expected in queries:
    results = retriever.retrieve(query)
    domains = [r.node.metadata.get("domain", "?") for r in results]
    scores = [r.score for r in results]
    hit = expected in domains[:3]
    if hit: hits += 1
    print(f"\nQ: {query} (expect: {expected})")
    print(f"  Top-3 domains: {domains[:3]} | hit={hit}")
    print(f"  Scores: {[round(s,3) for s in scores[:3]]}")
    for i, r in enumerate(results[:2]):
        t = r.node.get_content()[:120].replace('\n', ' ')
        print(f"  [{i+1}] {t}")

print(f"\n=== Top-3 Accuracy: {hits}/{len(queries)} ({100.0*hits/len(queries):.0f}%) ===")

# BM25 comparison
print("\n=== BM25 ===")
from app.bm25_store import bm25_search
for query, expected in queries[:4]:
    hits_bm = bm25_search(None, query, 5, corpus_path="/mnt/workspace/rag-kb-project/data/bm25_cn_corpus.jsonl")
    print(f"Q: {query}")
    for nid, score in hits_bm[:3]:
        print(f"  {nid[:20]}... score={score:.4f}")
