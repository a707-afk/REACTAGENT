"""Fetch arXiv papers for the Deep Research Agent knowledge base.

Fetches papers on 3 topics relevant to technology-selection research:
1. Retrieval-Augmented Generation (RAG)
2. Vector search / ANN / embedding
3. LLM Agent / tool use / reasoning

For each paper we store: title, authors, abstract, date, arxiv_id, url.
We do NOT download full PDFs (too large; abstracts are information-dense
for RAG). Each paper is stored as a markdown file for easy chunking.

Output: data/docs_research/papers/*.md
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from pathlib import Path

import arxiv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("fetch_arxiv")

OUT_DIR = Path("data/docs_research/papers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Topic queries — kept focused to avoid irrelevant papers.
# arXiv search syntax: see https://info.arxiv.org/help/api/user-manual.html
QUERIES = [
    # RAG
    'ti:"retrieval augmented generation"',
    'abs:"retrieval augmented generation"',
    # Vector search / ANN
    'ti:"approximate nearest neighbor" AND abs:"search"',
    'abs:"vector database" AND abs:"retrieval"',
    'ti:"dense retrieval"',
    # Embedding
    'abs:"text embedding" AND abs:"retrieval"',
    'ti:"hybrid retrieval" AND abs:"search"',
    # LLM Agent / tool use
    'ti:"tool use" AND abs:"language model" AND abs:"agent"',
    'abs:"ReAct" AND abs:"reasoning" AND abs:"language model"',
    'ti:"agent" AND abs:"planning" AND abs:"language model"',
    # Chunking / retrieval quality
    'abs:"chunking" AND abs:"retrieval"',
    'abs:"reranking" AND abs:"retrieval"',
]

MAX_PER_QUERY = 15  # ~12 queries × 15 = up to 180 candidates (before dedup)
SORT_BY = arxiv.SortCriterion.Relevance


def _safe_filename(title: str, arxiv_id: str) -> str:
    """Make a filesystem-safe filename from title + arxiv id."""
    # Keep first 60 chars of title, strip non-alphanumeric (keep CJK)
    clean = re.sub(r'[\\/:*?"<>|]', "", title)[:60].strip()
    clean = re.sub(r"\s+", "_", clean)
    return f"{arxiv_id.replace('/', '_')}_{clean}.md"


def fetch_papers() -> list[dict]:
    """Fetch papers from arXiv for all queries. Returns list of dicts."""
    client = arxiv.Client(num_retries=3, page_size=50)
    all_results: list[dict] = []
    seen_ids: set[str] = set()

    for query in QUERIES:
        logger.info("Querying arXiv: %s", query)
        search = arxiv.Search(query=query, max_results=MAX_PER_QUERY, sort_by=SORT_BY)
        try:
            for result in client.results(search):
                aid = result.entry_id.split("/")[-1]
                if aid in seen_ids:
                    continue
                # Filter: only papers from 2022 onwards (relevant to modern RAG)
                published = result.published.date() if result.published else None
                if published and published.year < 2022:
                    continue

                seen_ids.add(aid)
                all_results.append({
                    "arxiv_id": aid,
                    "title": result.title.strip().replace("\n", " "),
                    "authors": [str(a) for a in result.authors][:5],
                    "abstract": result.summary.strip().replace("\n", " "),
                    "published": str(published),
                    "url": result.entry_id,
                    "categories": [str(c) for c in result.primary_category] if result.primary_category else [],
                })
        except Exception as e:
            logger.warning("Query failed '%s': %s", query[:50], e)
        time.sleep(3.5)  # Respect arXiv rate limit (1 req / 3 sec)

    return all_results


def write_paper_markdown(paper: dict) -> Path:
    """Write a single paper as a markdown file."""
    fname = _safe_filename(paper["title"], paper["arxiv_id"])
    path = OUT_DIR / fname

    authors = ", ".join(paper["authors"])
    cats = ", ".join(paper.get("categories") or [])

    content = f"""# {paper['title']}

**arXiv ID**: {paper['arxiv_id']}
**Authors**: {authors}
**Published**: {paper['published']}
**Categories**: {cats}
**URL**: {paper['url']}

## Abstract

{paper['abstract']}
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    logger.info("Fetching arXiv papers for research knowledge base...")
    papers = fetch_papers()
    logger.info("Fetched %d unique papers (after dedup and date filter)", len(papers))

    written = 0
    for p in papers:
        try:
            path = write_paper_markdown(p)
            written += 1
        except Exception as e:
            logger.warning("Failed to write %s: %s", p["arxiv_id"], e)

    logger.info("Wrote %d paper markdown files to %s", written, OUT_DIR)

    # Write a manifest for auditing
    manifest_path = OUT_DIR / "_manifest.md"
    lines = ["# arXiv Papers Manifest", "", "| # | arXiv ID | Title | Published |", "|---|---|---|---|"]
    for i, p in enumerate(papers, 1):
        lines.append(f"| {i} | {p['arxiv_id']} | {p['title'][:80]} | {p['published']} |")
    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Manifest written to %s", manifest_path)


if __name__ == "__main__":
    main()
