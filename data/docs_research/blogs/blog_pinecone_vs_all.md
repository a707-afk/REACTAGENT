<!-- blog: Pinecone vs Weaviate vs Qdrant vs Milvus -->
<!-- url: https://medium.com/data-science-collective/pinecone-vs-weaviate-vs-qdrant-vs-milvus-66d5bfbcc460 -->
<!-- fetched: 2026-06-14 -->

# Pinecone vs Weaviate vs Qdrant vs Milvus: Where Do You Put a Billion Vectors?

Your team just shipped a RAG prototype. The embeddings are solid. Retrieval quality is good enough to demo. The CTO wants it in production by next quarter. Now the real question hits: **where do you actually store a billion vectors?**

This is the decision that determines your latency budget, your cloud bill, your on-call rotation, and whether your search stays fast at 3am Black Friday traffic. Let's dissect the four contenders.

## The Four Contenders at a Glance

| Feature | Pinecone | Weaviate | Qdrant | Milvus |
|---|---|---|---|---|
| **Deployment** | Fully managed SaaS | Self-host / managed | Self-host / managed | Self-host / Zilliz Cloud |
| **Language** | Proprietary | Go | Rust | Go + C++ |
| **License** | Commercial | BSD-3 | Apache 2.0 | Apache 2.0 |
| **Max vectors tested** | ~billions | billions | billions | 10B+ |
| **Hybrid search** | Yes (sparse+dense) | Yes (BM25+vector) | Yes (sparse+dense) | Yes (sparse+dense) |
| **Filtering** | Metadata filter | GraphQL-style | Payload filter (boolean) | Expression-based |
| **GPU index** | No | No | No | Yes (GPU_CAGRA, GPU_IVF) |

## Real-World Scale Stories

### TripAdvisor: 10 Billion Vectors
TripAdvisor migrated from Elasticsearch to **Milvus** for their recommendation engine. Key reasons:
- Milvus DiskANN index allowed them to keep 10B vectors on NVMe SSDs, not RAM
- GPU acceleration (GPU_CAGRA) gave 10x throughput vs CPU HNSW
- Cost: ~$8K/month on AWS g5.12xlarge vs estimated $40K/month for all-RAM solution

### Reddit Engineering: Qdrant for Search
Reddit's search team evaluated Milvus, Qdrant, and Weaviate. They chose **Qdrant**:
- Payload filter performance: filtered queries (e.g., "posts in r/MachineLearning from 2024") stayed under 20ms even with 50M vectors
- Rust's memory safety eliminated a class of crashes they hit with C++ alternatives
- Simpler ops: single binary, no etcd/MinIO/Pulsar dependencies

### Shopify: Weaviate for Product Search
Shopify uses **Weaviate** for semantic product search across merchant catalogs:
- GraphQL-style schema fit their existing API conventions
- Built-in modules (text2vec, qna) reduced pipeline complexity
- BM25 + vector hybrid search improved recall on long-tail queries

## Performance Benchmarks (VectorDBBench 2026)

### Upload Throughput (vectors/sec, 768-dim, 1M vectors)

| DB | QPS | Notes |
|---|---|---|
| Milvus (HNSW) | 18,500 | Highest raw throughput |
| Qdrant (HNSW) | 15,200 | Close second |
| Weaviate | 9,800 | Slower due to module overhead |
| Pinecone | N/A | Managed, opaque |

### Search Latency p99 (ms, 768-dim, 1M vectors, top-10)

| DB | No filter | 50% filter | 99% filter |
|---|---|---|---|
| Milvus (HNSW) | 8ms | 15ms | 45ms |
| Qdrant (HNSW) | 5ms | 6ms | 12ms |
| Weaviate | 12ms | 25ms | 80ms |
| Pinecone (s1) | 20ms | 22ms | 25ms |

**Key insight**: Qdrant's filtered search barely degrades as filter selectivity increases — this is its ACORN algorithm. Milvus degrades more steeply. If your workload is heavy on metadata-filtered search, Qdrant wins decisively.

### Cost Comparison (1M vectors, 768-dim, always-on)

| Option | Monthly Cost | Notes |
|---|---|---|
| Pinecone s1 | $70 | Managed, no ops |
| Qdrant Cloud (1GB free, then $25/GB) | ~$50 | Managed |
| Self-hosted Qdrant (2GB RAM VPS) | $12 | You handle ops |
| Self-hosted Milvus (4GB RAM, etcd+MinIO) | $25 | More components |
| Self-hosted Weaviate (2GB RAM) | $12 | Single binary |

## Decision Framework

### Choose Pinecone if:
- You want zero ops, pure SaaS
- Budget is not the primary constraint
- Team has no infrastructure engineers

### Choose Qdrant if:
- **Filtered search is your primary workload** (its killer feature)
- You want simplicity (single binary, Rust, no external deps)
- Scale is 1M–500M vectors
- You're cost-conscious

### Choose Milvus if:
- **Scale is 1B+ vectors**
- You need GPU acceleration
- You have a data engineering team comfortable with distributed systems
- DiskANN (disk-based index) is important for cost

### Choose Weaviate if:
- Your team likes GraphQL conventions
- You want built-in NLP modules (text2vec, qna, summarization)
- Hybrid search (BM25 + vector) is core to your use case
- You're in the JS/TS ecosystem (first-class JS client)

## The Honest Take

There's no "best" vector database — there's the best one **for your specific constraints**. The questions that actually matter:

1. **How many vectors?** <100M → Qdrant/Weaviate; 100M-1B → all viable; >1B → Milvus or Pinecone
2. **How much filtering?** Heavy filtering → Qdrant (ACORN); light filtering → all fine
3. **Who runs it?** No infra team → Pinecone; small team → Qdrant; big team → Milvus
4. **What's the budget?** $0 → self-host Qdrant; $100/mo → any managed; enterprise → all viable