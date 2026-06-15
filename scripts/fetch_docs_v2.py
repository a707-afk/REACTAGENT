"""Fetch official docs v2 — uses verified URLs from sitemaps/GitHub API.

All URLs below were verified to exist (no guessing). Each is chosen for
research information density, not marketing.

Output: data/docs_research/official_docs/*.md (HTML→text, cleaned)
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from urllib.request import urlopen, Request

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("fetch_docs_v2")

OUT_DIR = Path("data/docs_research/official_docs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Verified URLs — grouped by project. All confirmed via sitemap or GitHub tree API.
PAGES = [
    # ── Qdrant (from sitemap) ──
    ("qdrant_filtering.md", "https://qdrant.tech/documentation/search/filtering/", "Qdrant Filtering"),
    ("qdrant_search.md", "https://qdrant.tech/documentation/search/search/", "Qdrant Search"),
    ("qdrant_overview.md", "https://qdrant.tech/documentation/overview/what-is-qdrant/", "Qdrant Overview"),
    ("qdrant_optimize.md", "https://qdrant.tech/documentation/ops-optimization/optimize/", "Qdrant Optimization"),
    ("qdrant_memory.md", "https://qdrant.tech/documentation/ops-monitoring/memory-usage/", "Qdrant Memory Usage"),
    ("qdrant_monitoring.md", "https://qdrant.tech/documentation/ops-monitoring/monitoring/", "Qdrant Monitoring"),
    ("qdrant_retrieval_relevance.md", "https://qdrant.tech/documentation/improve-search/retrieval-relevance/", "Qdrant Retrieval Relevance"),
    ("qdrant_output_quality.md", "https://qdrant.tech/documentation/improve-search/pipeline-output-quality/", "Qdrant Pipeline Output Quality"),
    ("qdrant_reranking.md", "https://qdrant.tech/documentation/search-precision/reranking-semantic-search/", "Qdrant Reranking"),
    ("qdrant_ann_recall.md", "https://qdrant.tech/documentation/tutorials-search-engineering/ann-recall/", "Qdrant ANN Recall"),
    ("qdrant_multivector.md", "https://qdrant.tech/documentation/tutorials-search-engineering/using-multivector-representations/", "Qdrant Multivector"),
    ("qdrant_pdf_retrieval.md", "https://qdrant.tech/documentation/tutorials-search-engineering/pdf-retrieval-at-scale/", "Qdrant PDF Retrieval at Scale"),
    ("qdrant_agentic_rag.md", "https://qdrant.tech/documentation/tutorials-build-essentials/agentic-rag-crewai-zoom/", "Qdrant Agentic RAG"),
    ("qdrant_graphrag.md", "https://qdrant.tech/documentation/examples/graphrag-qdrant-neo4j/", "Qdrant GraphRAG + Neo4j"),
    ("qdrant_admin.md", "https://qdrant.tech/documentation/ops-configuration/administration/", "Qdrant Administration"),
    ("qdrant_config.md", "https://qdrant.tech/documentation/ops-configuration/configuration/", "Qdrant Configuration"),
    ("qdrant_migration_pg.md", "https://qdrant.tech/documentation/data-synchronization/with-postgres/", "Qdrant Sync with Postgres"),
    ("qdrant_fundamentals.md", "https://qdrant.tech/documentation/faq/qdrant-fundamentals/", "Qdrant Fundamentals FAQ"),
    ("qdrant_db_optimization.md", "https://qdrant.tech/documentation/faq/database-optimization/", "Qdrant Database Optimization FAQ"),

    # ── Milvus (from milvus.io sitemap) ──
    ("milvus_overview.md", "https://milvus.io/docs/overview.md", "Milvus Overview"),
    ("milvus_index.md", "https://milvus.io/docs/index.md", "Milvus Vector Index"),
    ("milvus_gpu.md", "https://milvus.io/docs/gpu_index.md", "Milvus GPU Index"),
    ("milvus_schema.md", "https://milvus.io/docs/schema.md", "Milvus Schema"),
    ("milvus_dynamic.md", "https://milvus.io/docs/enable-dynamic-field.md", "Milvus Dynamic Field"),
    ("milvus_dense_sparse.md", "https://milvus.io/docs/full-text-search.md", "Milvus Full-text Search (Dense+Sparse)"),
    ("milvus_partition.md", "https://milvus.io/docs/manage-partitions.md", "Milvus Partitions"),
    ("milvus_multivector.md", "https://milvus.io/docs/multi-vector-search.md", "Milvus Multi-vector Search"),
    ("milvus_reranking.md", "https://milvus.io/docs/reranking.md", "Milvus Reranking"),
    ("milvus_collections.md", "https://milvus.io/docs/manage-collections.md", "Milvus Collections"),
    ("milvus_tune.md", "https://milvus.io/docs/performance_faq.md", "Milvus Performance FAQ"),
    ("milvus_scale.md", "https://milvus.io/docs/scaleout.md", "Milvus Scale-out"),
    ("milvus_consistency.md", "https://milvus.io/docs/consistency.md", "Milvus Consistency Levels"),
]


def _html_to_text(html: str) -> str:
    """Minimal HTML→text: strip tags, keep text content, collapse whitespace."""
    # Remove script/style/nav/footer/header blocks
    html = re.sub(r"<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>",
                  "", html, flags=re.DOTALL | re.IGNORECASE)
    # Convert some tags to markdown-ish
    html = re.sub(r"<h([1-6])[^>]*>", lambda m: "\n" + "#" * int(m.group(1)) + " ",
                  html, flags=re.IGNORECASE)
    html = re.sub(r"</h[1-6]>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<li[^>]*>", "\n- ", html, flags=re.IGNORECASE)
    html = re.sub(r"<p[^>]*>", "\n\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<code[^>]*>", "`", html, flags=re.IGNORECASE)
    html = re.sub(r"</code>", "`", html, flags=re.IGNORECASE)
    # Strip all remaining tags
    text = re.sub(r"<[^>]+>", "", html)
    # Decode basic entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def fetch_and_save(fname: str, url: str, label: str) -> bool:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (research-kb-builder)"})
    try:
        with urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                logger.warning("  HTTP %d", resp.status)
                return False
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("  FAIL: %s", e)
        return False

    # Check if it's already markdown (GitHub raw) or HTML
    if raw.lstrip().startswith("#") or "<html" not in raw.lower()[:500]:
        text = raw  # Already markdown
    else:
        text = _html_to_text(raw)

    if len(text) < 300:
        logger.warning("  too short (%d chars), skipping", len(text))
        return False

    header = f"""<!-- source: {label} -->
<!-- url: {url} -->
<!-- fetched: {time.strftime('%Y-%m-%d')} -->

"""
    (OUT_DIR / fname).write_text(header + text, encoding="utf-8")
    logger.info("  OK: %d chars", len(text))
    return True


def main() -> None:
    logger.info("Fetching %d verified doc pages...", len(PAGES))
    ok = 0
    manifest = ["# Official Docs Manifest (v2)", "",
                "| # | File | Source | Status |", "|---|---|---|---|"]
    for i, (fname, url, label) in enumerate(PAGES, 1):
        logger.info("[%d/%d] %s", i, len(PAGES), label)
        success = fetch_and_save(fname, url, label)
        status = "OK" if success else "FAILED"
        if success:
            ok += 1
        manifest.append(f"| {i} | {fname} | {label} | {status} |")
        time.sleep(1.5)  # Be polite

    (OUT_DIR / "_manifest_v2.md").write_text("\n".join(manifest), encoding="utf-8")
    logger.info("Done: %d/%d pages fetched. Manifest at %s", ok, len(PAGES),
                OUT_DIR / "_manifest_v2.md")


if __name__ == "__main__":
    main()
