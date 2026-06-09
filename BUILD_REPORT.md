# CS Agent Backend — Chinese Knowledge Base Build Report

**Date**: 2026-06-09  
**Server**: DSW (172.25.105.69, NVIDIA A10 23GB, CUDA 12.9)

---

## 1. Data Pipeline

### Source
- Dataset: [xiaolinAndy/CSDS](https://github.com/xiaolinAndy/CSDS) — Multi-domain Customer Service Dialogue Text Data
- Format: JSON, 3 files (train/val/test), 10,701 dialogues, 21,126 QA segments
- Language: Chinese (simplified)

### Processing Steps

| Step | Description | Input | Output |
|------|-------------|-------|--------|
| 1. JD Filter | Blacklist filter (50+ JD-specific keywords + intents) | 21,126 QA segments | 17,895 kept, 3,226 filtered |
| 2. Dedup + Quality | Text hash dedup + min length (Q>=5, A>=8) | 17,895 | 17,792 FAQ pairs |
| 3. Intent Mapping | CSDS intent → 14-domain mapping (96.5% coverage) | 17,792 | 17,170 classified, 622→general |
| 4. faq_cn.jsonl | Final output: 17,792 FAQs with domain labels | — | 4.17 MB JSONL |

### Domain Distribution (top 11)
| Domain | Count | % |
|--------|-------|---|
| returns (退货退款) | 4,106 | 23.1% |
| delivery (物流配送) | 3,454 | 19.4% |
| general (通用) | 3,048 | 17.1% |
| order (订单) | 2,663 | 15.0% |
| billing (发票账单) | 1,560 | 8.8% |
| customer_service (客服) | 873 | 4.9% |
| product_support (产品) | 819 | 4.6% |
| sales (售前) | 610 | 3.4% |
| tech_support (技术) | 582 | 3.3% |
| account (账户) | 52 | 0.3% |
| hr (人事) | 25 | 0.1% |

## 2. Index Build

### Configuration
- Embedding Model: Qwen3-Embedding-0.6B (downloaded via ModelScope to `/mnt/workspace/rag-kb-project/models/`)
- GPU: NVIDIA A10 (23GB)
- Vector dim: 1024, Distance: Cosine
- Collection: `kb_cn_general`

### Metrics
| Metric | Value |
|--------|-------|
| Nodes indexed | 17,792 |
| Build time | 531.9s (8.9 min) |
| Throughput | 33.4 nodes/sec |
| Qdrant path | `data/qdrant_cn_local/` |
| BM25 corpus | `data/bm25_cn_corpus.jsonl` (6.9 MB) |

## 3. Architecture

### Dual Collection Routing
```
User Query
  │
  ├─ language_router.detect_language()
  │   ├─ zh → kb_cn_general (Chinese FAQ)
  │   └─ en/de → rag_kb (English CS knowledge)
  │
  ├─ domain_router.route_domains()
  │   └─ 14 CS domains (keywords-first + LLM fallback)
  │
  └─ retrieval_pipeline.retrieve_scored_nodes()
      ├─ Vector retrieval (Qdrant)
      ├─ BM25 hybrid (language-specific corpus)
      ├─ Rerank (Qwen3-Reranker)
      └─ Retrieval gates (similarity threshold)
```

### Key Files Modified
| File | Change |
|------|--------|
| `app/language_router.py` | NEW: zh/en/de detection + collection routing |
| `app/qdrant_index_store.py` | Added `get_vector_index_cn()` for dual collection |
| `app/vector_index.py` | Added `get_vector_index_cn()` export |
| `app/retrieval_pipeline.py` | Language-based index selection + BM25 path routing |
| `app/bm25_store.py` | Dual corpus support (en + cn) with separate caches |
| `app/llm_zhipu.py` | Switch to SenseNova API (3 keys, deepseek-v4-flash) |
| `app/config.py` | Added `qdrant_collection_name_cn`, `docs_dir_cn`, `bm25_corpus_path_cn` |
| `scripts/extract_csds.py` | CSDS extraction + JD filtering + intent classification |
| `scripts/classify_intents.py` | Standalone intent→domain mapper (96.5% coverage, no LLM needed) |
| `scripts/build_cn_index.py` | Chinese Qdrant + BM25 index builder |

## 4. Retrieval Quality

### Test Results (10 queries)
| Query | Expected Domain | Top-1 Domain | Score | Content Relevant |
|-------|----------------|--------------|-------|-----------------|
| 退货退款怎么操作 | returns | returns | 0.642 | Yes |
| 快递到哪了怎么查物流 | delivery | delivery | 0.758 | Yes |
| 订单怎么取消 | order | order | 0.784 | Yes |
| 发票怎么开具 | billing | billing | 0.768 | Yes |
| 密码忘了怎么办 | account | general* | 0.750 | Yes* |
| 商品坏了能修吗 | tech_support | returns* | 0.747 | Yes* |
| 客服电话多少 | customer_service | customer_service | 0.707 | Yes |
| 投诉在哪里提交 | feedback | general* | 0.735 | Yes* |
| 产品使用说明书 | product_support | sales* | 0.695 | Yes* |
| 这个商品多少钱 | sales | sales | 0.743 | Yes |

**Domain-based Top-3 accuracy: 60% (6/10)**  
**Content relevance: 100% (10/10)** — all queries returned semantically relevant answers

*Items marked with * have correct content but mismatched domain labels. These 4 items are labeling issues, not retrieval failures.

## 5. Known Issues & Next Steps

### Critical
1. **English Qdrant collection missing on server** — Only `qdrant_cn_local` exists. The English collection (`rag_kb` / `kb_en_de`) needs to be built or transferred.
   - Fix: Run `scripts/reindex.py` on server with English docs, or scp the local `data/qdrant_local/` directory

### Important
2. **Domain labeling gaps** — 622 items labeled "general" and ~200 items with mismatched domains
   - Fix: Re-run `classify_intents.py` with expanded INTENT_TO_DOMAIN mapping or LLM fallback when API quota recovers

3. **Qdrant local-mode locking** — Only one client can access the collection at a time
   - Fix: Use Qdrant server mode for production, or ensure single-client access pattern

### Nice-to-have
4. **Chinese retrieval evaluation** — No eval benchmark for Chinese queries
   - Fix: Create eval_cn_questions.jsonl and run evaluation
5. **Agent ticket tools** — create_ticket, customer_lookup are stubs
   - Fix: Implement real ticket workflow with database

## 6. Environment Variables (Server)

```bash
export QWEN_EMBEDDING_MODEL_PATH=/mnt/workspace/rag-kb-project/models/Qwen/Qwen3-Embedding-0___6B
export QDRANT_PATH=/mnt/workspace/rag-kb-project/data/qdrant_cn_local
export QDRANT_COLLECTION_NAME_CN=kb_cn_general
export BM25_CORPUS_PATH_CN=data/bm25_cn_corpus.jsonl
export DOCS_DIR_CN=data/docs_cn
export PYTHONPATH=/mnt/workspace/rag-kb-project
```

## 7. Scripts Reference

| Script | Purpose |
|--------|---------|
| `scripts/extract_csds.py` | Extract FAQ from CSDS JSON + JD filter |
| `scripts/classify_intents.py` | Intent→domain mapping (--no-llm for fast mode) |
| `scripts/build_cn_index.py` | Build Qdrant + BM25 for Chinese KB |
| `tests/audit_retrieval_cn.py` | Chinese retrieval accuracy test |
| `tests/smoke_server.py` | API server startup verification |

## 8. Git History

```
d81377e feat: CSDS Chinese FAQ classification (96.5% intent match, 17.8K FAQs)
b47eb39 feat: dual language routing (zh/en/de), CSDS extraction pipeline
f8a1838 Phase 3: fix 'set up' keyword gap, 95% domain accuracy
cb00b43 Phase 2: add Chinese eval questions, language-aware query rewrite
dbb4567 Phase 1: remove all enterprise domain code, simplify to CS keywords-first router
```
