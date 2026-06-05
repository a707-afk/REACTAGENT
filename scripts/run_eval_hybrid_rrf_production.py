"""生产环境 RRF 矩阵评测：rerank on + router on 下 max vs rrf。"""
import json
import os
import sys

# 设置生产环境
os.environ.setdefault("QDRANT_COLLECTION_NAME", "enterprise_ai_ops")
os.environ.setdefault("BM25_CORPUS_PATH", "data/bm25_enterprise_corpus.jsonl")
os.environ.setdefault("VECTOR_BACKEND", "qdrant")
os.environ.setdefault("RERANK_ENABLED", "true")
os.environ.setdefault("EVAL_SKIP_DOMAIN_ROUTER", "false")

from app.config import get_settings
from scripts.run_eval_retrieve import run_eval_retrieve

CONFIGS = [
    {"HYBRID_FUSION": "max", "HYBRID_RRF_K": 60, "name": "max_rerank_on"},
    {"HYBRID_FUSION": "rrf", "HYBRID_RRF_K": 60, "name": "rrf_k60_rerank_on"},
]

def main():
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results = {}
    for cfg in CONFIGS:
        for k, v in cfg.items():
            os.environ[k] = str(v)
        
        # 重新加载配置
        import importlib
        import app.config
        importlib.reload(app.config)
        settings = app.config.get_settings()
        
        metrics = run_eval_retrieve(settings)
        results[cfg["name"]] = metrics
        print(f"{cfg['name']}: Top-1={metrics.get('top1_hit_rate', 'N/A')}, Top-5={metrics.get('top5_hit_rate', 'N/A')}")
    
    summary_path = os.path.join(ROOT, "docs", "eval_hybrid_prod_matrix_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"configs": CONFIGS, "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存至 {summary_path}")


if __name__ == "__main__":
    main()
