"""Fetch official documentation pages for the research knowledge base.

Goes beyond README to fetch actual docs pages covering:
- Filtering / payload filter
- Performance / benchmark / QPS
- Scaling / sharding / clustering
- Indexing (HNSW configuration)

Uses raw.githubusercontent.com for docs stored in repos, and qdrant.tech
documentation site for Qdrant. Each page is saved as markdown.

Output: data/docs_research/official_docs/*.md
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from urllib.request import urlopen, Request

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("fetch_docs")

OUT_DIR = Path("data/docs_research/official_docs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Curated URLs — each chosen for research value (not just marketing pages).
# Format: (filename, url, source_label)
DOCS = [
    # ── Qdrant ──
    ("qdrant_filtering.md",
     "https://raw.githubusercontent.com/qdrant/qdrant/master/docs/concepts/filtering/index.md",
     "Qdrant Filtering"),
    ("qdrant_payload.md",
     "https://raw.githubusercontent.com/qdrant/qdrant/master/docs/concepts/storage/payload.md",
     "Qdrant Payload"),
    ("qdrant_hnsw.md",
     "https://raw.githubusercontent.com/qdrant/qdrant/master/docs/concepts/indexing/hnsw.md",
     "Qdrant HNSW Index"),
    ("qdrant_quantization.md",
     "https://raw.githubusercontent.com/qdrant/qdrant/master/docs/concepts/quantization.md",
     "Qdrant Quantization"),
    ("qdrant_sharding.md",
     "https://raw.githubusercontent.com/qdrant/qdrant/master/docs/concepts/distributed-sharding.md",
     "Qdrant Sharding"),
    ("qdrant_multitenancy.md",
     "https://raw.githubusercontent.com/qdrant/qdrant/master/docs/guides/multiple-partitions.md",
     "Qdrant Multi-tenancy"),
    ("qdrant_hybrid_search.md",
     "https://raw.githubusercontent.com/qdrant/qdrant/master/docs/concepts/hybrid-queries.md",
     "Qdrant Hybrid Queries"),
    ("qdrant_benchmark.md",
     "https://raw.githubusercontent.com/qdrant/qdrant/master/docs/benchmarks/README.md",
     "Qdrant Benchmarks"),

    # ── Milvus ──
    ("milvus_index_overview.md",
     "https://raw.githubusercontent.com/milvus-io/milvus-docs/master/site/en/userGuide/manage-indexes/index-parameters.md",
     "Milvus Index Parameters"),
    ("milvus_hnsw.md",
     "https://raw.githubusercontent.com/milvus-io/milvus-docs/master/site/en/userGuide/manage-indexes/index-with-gpu.md",
     "Milvus GPU Index"),
    ("milvus_partitioning.md",
     "https://raw.githubusercontent.com/milvus-io/milvus-docs/master/site/en/userGuide/manage-collections/manage-partitions.md",
     "Milvus Partitions"),
    ("milvus_scalability.md",
     "https://raw.githubusercontent.com/milvus-io/milvus-docs/master/site/en/userGuide/deploy_scalescaleout.md",
     "Milvus Scaling"),
    ("milvus_dense_sparse.md",
     "https://raw.githubusercontent.com/milvus-io/milvus-docs/master/site/en/userGuide/full-text-search.md",
     "Milvus Full-text Search"),

    # ── pgvector ──
    ("pgvector_readme.md",
     "https://raw.githubusercontent.com/pgvector/pgvector/master/README.md",
     "pgvector Overview"),

    # ── Chroma ──
    ("chroma_usage_guide.md",
     "https://raw.githubusercontent.com/chroma-core/docs/main/docs/guides.md",
     "Chroma Guides"),

    # ── Weaviate ──
    ("weaviate_hnsw.md",
     "https://raw.githubusercontent.com/weaviate/weaviate/main/docs/en/concepts/storage.md",
     "Weaviate Storage"),

    # ── Embedding models ──
    ("bge_m3_details.md",
     "https://raw.githubusercontent.com/FlagOpen/FlagEmbedding/master/docs/source/En/FAQ.md",
     "BGE-M3 FAQ"),
    ("bge_m3_dense_sparse.md",
     "https://raw.githubusercontent.com/FlagOpen/FlagEmbedding/master/README.md",
     "FlagEmbedding Dense+Sparse+Colbert"),

    # ── LangGraph ──
    ("langgraph_concepts.md",
     "https://raw.githubusercontent.com/langchain-ai/langgraph/main/docs/docs/concepts/low_level.md",
     "LangGraph Low-level Concepts"),
    ("langgraph_persistence.md",
     "https://raw.githubusercontent.com/langchain-ai/langgraph/main/docs/docs/concepts/persistence.md",
     "LangGraph Persistence"),
    ("langgraph_agent_architecture.md",
     "https://raw.githubusercontent.com/langchain-ai/langgraph/main/docs/docs/concepts/agentic_concepts.md",
     "LangGraph Agentic Concepts"),

    # ── CrewAI ──
    ("crewai_core_concepts.md",
     "https://raw.githubusercontent.com/crewAIInc/crewAI/main/docs/core-concepts/Agents.md",
     "CrewAI Agents"),
    ("crewai_flows.md",
     "https://raw.githubusercontent.com/crewAIInc/crewAI/main/docs/core-concepts/Flows.md",
     "CrewAI Flows"),

    # ── LlamaIndex ──
    ("llamaindex_agent.md",
     "https://raw.githubusercontent.com/run-llama/llama_index/main/docs/docs/docs/understanding/agent/index.md",
     "LlamaIndex Agents"),
    ("llamaindex_workflow.md",
     "https://raw.githubusercontent.com/run-llama/llama_index/main/docs/docs/docs/understanding/agent/workflow.md",
     "LlamaIndex Workflows"),

    # ── AutoGen ──
    ("autogen_agentchat.md",
     "https://raw.githubusercontent.com/microsoft/autogen/main/python/packages/autogen-agentchat/docs/user-guide/agentchat-user-guide/tutorial/teams.md",
     "AutoGen Teams"),

    # ── Reranker ──
    ("bge_reranker.md",
     "https://raw.githubusercontent.com/FlagOpen/FlagEmbedding/master/docs/source/En/Guide/CrossEncoder.md",
     "BGE CrossEncoder / Reranker"),
]


def fetch_url(url: str) -> str | None:
    """Fetch URL content with proper headers and error handling."""
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (research-kb-builder)"})
    try:
        with urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                logger.warning("HTTP %d for %s", resp.status, url)
                return None
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("Fetch failed for %s: %s", url[:60], e)
        return None


def main() -> None:
    logger.info("Fetching %d official doc pages...", len(DOCS))
    fetched = 0
    manifest_lines = ["# Official Docs Manifest", "", "| # | File | Source | Size |", "|---|---|---|---|"]

    for i, (fname, url, label) in enumerate(DOCS, 1):
        logger.info("[%d/%d] %s", i, len(DOCS), label)
        content = fetch_url(url)
        if content is None or len(content.strip()) < 200:
            logger.warning("  -> skipped (too short or failed)")
            continue

        # Add source metadata header
        full = f"""<!-- source: {label} -->
<!-- url: {url} -->
<!-- fetched: {time.strftime('%Y-%m-%d')} -->

{content}
"""
        path = OUT_DIR / fname
        path.write_text(full, encoding="utf-8")
        fetched += 1
        manifest_lines.append(f"| {fetched} | {fname} | {label} | {len(content)} chars |")
        time.sleep(1)  # Be polite

    manifest_path = OUT_DIR / "_manifest.md"
    manifest_path.write_text("\n".join(manifest_lines), encoding="utf-8")
    logger.info("Fetched %d/%d doc pages. Manifest: %s", fetched, len(DOCS), manifest_path)


if __name__ == "__main__":
    main()
