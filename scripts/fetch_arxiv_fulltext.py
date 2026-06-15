"""Fetch arXiv papers as FULL TEXT via ar5iv.org (one-step).

Queries arXiv API for paper IDs on RAG/vector/agent topics, then fetches
each paper's full text from ar5iv (HTML→markdown). Papers not on ar5iv
fall back to abstract-only via the arxiv API.

Output: data/docs_research/papers/*.md (full text where available)
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("fetch_fulltext")

PAPERS_DIR = Path("data/docs_research/papers")
PAPERS_DIR.mkdir(parents=True, exist_ok=True)

AR5IV_BASE = "https://ar5iv.labs.arxiv.org/html/"
MIN_FULLTEXT_CHARS = 5000
RATE_LIMIT_SEC = 2.0

# Focused queries — high-signal papers on RAG, retrieval, embedding, agents
QUERIES = [
    'ti:"retrieval augmented generation"',
    'abs:"retrieval augmented generation" AND abs:"survey"',
    'ti:"approximate nearest neighbor" AND abs:"search"',
    'abs:"vector database" AND abs:"retrieval"',
    'abs:"text embedding" AND abs:"retrieval" AND abs:"benchmark"',
    'abs:"reranking" AND abs:"retrieval" AND abs:"language model"',
    'abs:"ReAct" AND abs:"reasoning" AND abs:"tool"',
    'abs:"agent" AND abs:"planning" AND abs:"language model" AND abs:"survey"',
    'ti:"chunking" OR ti:"chunk" AND abs:"retrieval"',
    'abs:"hybrid retrieval" AND abs:"dense" AND abs:"sparse"',
]


# ── arXiv API: get paper IDs + metadata ──────────────────────────

def query_arxiv_ids() -> list[dict]:
    """Query arXiv for paper IDs and metadata. Returns list of dicts."""
    import arxiv
    client = arxiv.Client(num_retries=3, page_size=50)
    results = []
    seen = set()

    for q in QUERIES:
        logger.info("arXiv query: %s", q[:60])
        search = arxiv.Search(query=q, max_results=20, sort_by=arxiv.SortCriterion.Relevance)
        try:
            for r in client.results(search):
                aid = r.entry_id.split("/")[-1]
                clean_id = aid.split("v")[0]
                if clean_id in seen:
                    continue
                published = r.published.date() if r.published else None
                if published and published.year < 2022:
                    continue
                seen.add(clean_id)
                results.append({
                    "arxiv_id": aid,
                    "clean_id": clean_id,
                    "title": r.title.strip().replace("\n", " "),
                    "authors": [str(a) for a in r.authors][:5],
                    "abstract": r.summary.strip().replace("\n", " "),
                    "published": str(published),
                    "url": r.entry_id,
                })
        except Exception as e:
            logger.warning("  query failed: %s", str(e)[:60])
        time.sleep(3.5)

    logger.info("Found %d unique papers from arXiv", len(results))
    return results


# ── ar5iv: fetch full text ────────────────────────────────────────

def _fetch_html(url: str) -> str | None:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (research-kb-builder)"})
    try:
        with urlopen(req, timeout=40) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        if e.code == 404:
            return None
        logger.warning("  HTTP %d", e.code)
    except (URLError, Exception) as e:
        logger.warning("  error: %s", str(e)[:60])
    return None


def _strip_tags(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s).strip()


def _ar5iv_to_markdown(html: str, paper: dict) -> str:
    """Convert ar5iv HTML to clean markdown."""
    # Remove MathJax complex rendering, keep alt text
    html = re.sub(r'<math[^>]*alttext="([^"]*)"[^>]*>.*?</math>',
                  lambda m: f" `{m.group(1)}` ", html, flags=re.DOTALL)
    html = re.sub(r'<math[^>]*>.*?</math>', ' `[formula]` ', html, flags=re.DOTALL)

    # Remove figures (keep captions), tables, scripts
    html = re.sub(r'<figure[^>]*>(.*?)</figure>',
                  lambda m: re.search(r'<figcaption[^>]*>(.*?)</figcaption>',
                                      m.group(0), re.DOTALL) and
                            f"\n*[Figure: {_strip_tags(re.search(r'<figcaption[^>]*>(.*?)</figcaption>', m.group(0), re.DOTALL).group(1)).strip()[:150]}]*\n"
                            or '', html, flags=re.DOTALL)
    html = re.sub(r'<table[^>]*>.*?</table>', '[table]', html, flags=re.DOTALL)
    for tag in ['script', 'style', 'nav', 'footer', 'header', 'svg']:
        html = re.sub(rf'<{tag}\b[^>]*>.*?</{tag}>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Convert headings
    html = re.sub(r'<h([1-6])[^>]*>', lambda m: '\n\n' + '#' * int(m.group(1)) + ' ', html, flags=re.IGNORECASE)
    html = re.sub(r'</h[1-6]>', '\n', html, flags=re.IGNORECASE)

    # Structure tags
    html = re.sub(r'<p[^>]*>', '\n\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<li[^>]*>', '\n- ', html, flags=re.IGNORECASE)
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<code[^>]*>', '`', html, flags=re.IGNORECASE)
    html = re.sub(r'</code>', '`', html, flags=re.IGNORECASE)

    text = re.sub(r'<[^>]+>', '', html)
    for entity, char in [('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                          ('&quot;', '"'), ('&#39;', "'"), ('&nbsp;', ' ')]:
        text = text.replace(entity, char)

    # Remove ar5iv chrome
    text = re.sub(r'View PDF.*?(?=\n#|\n##|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'\[arXiv.*?\]', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    authors = ", ".join(paper["authors"])
    header = f"""# {paper['title']}

**arXiv ID**: {paper['arxiv_id']}
**Authors**: {authors}
**Published**: {paper['published']}
**URL**: {paper['url']}
**Source**: ar5iv full-text rendering

"""
    return header + text.strip()


def _safe_filename(title: str, arxiv_id: str) -> str:
    clean = re.sub(r'[\\/:*?"<>|]', "", title)[:60].strip()
    clean = re.sub(r"\s+", "_", clean)
    return f"{arxiv_id.split('v')[0].replace('/', '_')}_{clean}.md"


def main() -> None:
    papers = query_arxiv_ids()
    logger.info("Fetching full text from ar5iv for %d papers...", len(papers))

    fulltext = 0
    fallback = 0
    failed = 0

    for i, p in enumerate(papers, 1):
        if i % 10 == 0:
            logger.info("Progress: %d/%d (full=%d, abstract=%d, fail=%d)",
                        i, len(papers), fulltext, fallback, failed)

        url = AR5IV_BASE + p["clean_id"]
        html = _fetch_html(url)

        if html and len(html) > 10000:
            md = _ar5iv_to_markdown(html, p)
            if len(md) > MIN_FULLTEXT_CHARS:
                fname = _safe_filename(p["title"], p["arxiv_id"])
                (PAPERS_DIR / fname).write_text(md, encoding="utf-8")
                fulltext += 1
                logger.debug("  [FULL] %s (%d chars)", p["clean_id"], len(md))
            else:
                _write_abstract_only(p)
                fallback += 1
        elif html:
            _write_abstract_only(p)
            fallback += 1
        else:
            _write_abstract_only(p)
            failed += 1

        time.sleep(RATE_LIMIT_SEC)

    logger.info("=== DONE: %d full-text, %d abstract-only, %d failed (no ar5iv)",
                fulltext, fallback, failed)


def _write_abstract_only(paper: dict) -> None:
    """Write abstract-only fallback."""
    fname = _safe_filename(paper["title"], paper["arxiv_id"])
    authors = ", ".join(paper["authors"])
    content = f"""# {paper['title']}

**arXiv ID**: {paper['arxiv_id']}
**Authors**: {authors}
**Published**: {paper['published']}
**URL**: {paper['url']}
**Source**: arXiv abstract (full text not available on ar5iv)

## Abstract

{paper['abstract']}
"""
    (PAPERS_DIR / fname).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
