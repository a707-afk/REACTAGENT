"""Re-fetch arXiv papers as FULL TEXT (not just abstract) via ar5iv.org.

ar5iv.labs.arxiv.org renders arXiv papers as HTML with full text.
This replaces the abstract-only papers in data/docs_research/papers/.

Strategy:
1. Read the existing manifest to get the 162 arxiv_ids
2. For each, fetch ar5iv HTML full text
3. Convert HTML → markdown (preserve section structure)
4. Skip if ar5iv returns 404 or content too short (keep abstract-only version as fallback)
5. Target: keep only papers with >5KB of full text (real content)

Output: overwrites data/docs_research/papers/*.md with full-text versions
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("refetch_arxiv")

PAPERS_DIR = Path("data/docs_research/papers")
AR5IV_BASE = "https://ar5iv.labs.arxiv.org/html/"
MIN_FULLTEXT_CHARS = 5000  # Papers with <5KB full text are kept as abstract fallback
RATE_LIMIT_SEC = 2.0  # Be polite to ar5iv
MAX_RETRIES = 2


def _ar5iv_url(arxiv_id: str) -> str:
    """Convert arxiv_id to ar5iv URL. Handle versioned IDs like 2401.12345v2."""
    clean = arxiv_id.split("v")[0]  # ar5iv wants unversioned IDs
    return AR5IV_BASE + clean


def _fetch_html(url: str) -> str | None:
    """Fetch HTML with retries."""
    for attempt in range(MAX_RETRIES + 1):
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (research-kb-builder)"})
        try:
            with urlopen(req, timeout=40) as resp:
                if resp.status == 200:
                    return resp.read().decode("utf-8", errors="replace")
                if resp.status == 404:
                    return None
        except HTTPError as e:
            if e.code == 404:
                return None
            logger.warning("  HTTP %d (attempt %d)", e.code, attempt + 1)
        except URLError as e:
            logger.warning("  URL error (attempt %d): %s", attempt + 1, e.reason)
        except Exception as e:
            logger.warning("  Error (attempt %d): %s", attempt + 1, str(e)[:80])
        time.sleep(3)
    return None


def _ar5iv_to_markdown(html: str, arxiv_id: str) -> tuple[str, int]:
    """Convert ar5iv HTML to clean markdown. Returns (markdown, char_count)."""
    # Extract title
    title_match = re.search(r'<h1[^>]*ltx_title[^>]*>(.*?)</h1>', html, re.DOTALL)
    title = _strip_tags(title_match.group(1)).strip() if title_match else f"arXiv:{arxiv_id}"

    # Extract authors
    author_match = re.search(r'<div[^>]*ltx_authors[^>]*>(.*?)</div>', html, re.DOTALL)
    authors_text = _strip_tags(author_match.group(1)).strip() if author_match else ""

    # Remove LaTeX rendering junk, math formulas (keep text), figures, tables captions
    # ar5iv uses MathJax; remove the complex math spans but keep alt text
    html = re.sub(r'<math[^>]*alttext="([^"]*)"[^>]*>.*?</math>',
                  lambda m: f" `{m.group(1)}` ", html, flags=re.DOTALL)
    html = re.sub(r'<math[^>]*>.*?</math>', ' `[formula]` ', html, flags=re.DOTALL)

    # Remove figures (keep captions)
    html = re.sub(r'<figure[^>]*class="ltx_figure"[^>]*>(.*?)</figure>',
                  lambda m: _extract_caption(m.group(0)), html, flags=re.DOTALL)
    html = re.sub(r'<figure[^>]*>.*?</figure>', '', html, flags=re.DOTALL)

    # Remove tables (keep as text if simple)
    html = re.sub(r'<table[^>]*>.*?</table>', '[table omitted]', html, flags=re.DOTALL)

    # Remove script/style/nav
    for tag in ['script', 'style', 'nav', 'footer', 'header']:
        html = re.sub(rf'<{tag}\b[^>]*>.*?</{tag}>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Convert headings (ar5iv uses ltx_title classes)
    html = re.sub(r'<h([1-6])[^>]*>', lambda m: '\n\n' + '#' * int(m.group(1)) + ' ', html, flags=re.IGNORECASE)
    html = re.sub(r'</h[1-6]>', '\n', html, flags=re.IGNORECASE)

    # Paragraphs, lists, breaks
    html = re.sub(r'<p[^>]*>', '\n\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<li[^>]*>', '\n- ', html, flags=re.IGNORECASE)
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)

    # Code
    html = re.sub(r'<code[^>]*>', '`', html, flags=re.IGNORECASE)
    html = re.sub(r'</code>', '`', html, flags=re.IGNORECASE)
    html = re.sub(r'<pre[^>]*>', '\n```\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</pre>', '\n```\n', html, flags=re.IGNORECASE)

    # Strip remaining tags
    text = re.sub(r'<[^>]+>', '', html)

    # Decode entities
    for entity, char in [('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                          ('&quot;', '"'), ('&#39;', "'"), ('&nbsp;', ' ')]:
        text = text.replace(entity, char)

    # Remove ar5iv boilerplate
    text = re.sub(r'View PDF.*?(?=\n#|\n##|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'\[arXiv.*?\]', '', text)

    # Clean whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    text = text.strip()

    # Build header
    header = f"""# {title}

**arXiv ID**: {arxiv_id}
**Authors**: {authors_text[:300]}
**Source**: ar5iv full-text rendering

"""
    return header + text, len(text)


def _strip_tags(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s).strip()


def _extract_caption(figure_html: str) -> str:
    """Extract figure caption text."""
    cap = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', figure_html, re.DOTALL)
    if cap:
        return f"\n*[Figure: {_strip_tags(cap.group(1)).strip()[:200]}]*\n"
    return ""


def _get_arxiv_ids() -> list[tuple[str, str]]:
    """Get list of (arxiv_id, filename) from existing paper files."""
    results = []
    for f in sorted(PAPERS_DIR.glob("*.md")):
        if f.name.startswith("_"):
            continue
        # Extract arxiv_id from filename (format: {id}_{title}.md)
        arxiv_id = f.name.split("_")[0].replace(".", "/", 1) if "/" in f.name else f.name.split("_")[0]
        # Also try reading from file content (more reliable)
        content = f.read_text(encoding="utf-8", errors="replace").split("\n")
        for line in content[:10]:
            if line.startswith("**arXiv ID**:"):
                arxiv_id = line.split(":", 1)[1].strip()
                break
        results.append((arxiv_id, f.name))
    return results


def main() -> None:
    papers = _get_arxiv_ids()
    logger.info("Re-fetching full text for %d papers via ar5iv...", len(papers))

    fulltext_count = 0
    abstract_fallback = 0
    not_found = 0

    for i, (arxiv_id, fname) in enumerate(papers, 1):
        if i % 20 == 0:
            logger.info("Progress: %d/%d (fulltext=%d, fallback=%d, notfound=%d)",
                        i, len(papers), fulltext_count, abstract_fallback, not_found)

        url = _ar5iv_url(arxiv_id)
        html = _fetch_html(url)

        if html is None:
            not_found += 1
            continue  # Keep existing abstract-only file

        md, char_count = _ar5iv_to_markdown(html, arxiv_id)

        if char_count < MIN_FULLTEXT_CHARS:
            abstract_fallback += 1
            continue  # Too short, keep abstract version

        # Write full-text version (overwrite)
        fpath = PAPERS_DIR / fname
        fpath.write_text(md, encoding="utf-8")
        fulltext_count += 1

        time.sleep(RATE_LIMIT_SEC)

    logger.info("=== DONE ===")
    logger.info("Full text fetched: %d/%d (%.0f%%)", fulltext_count, len(papers),
                100 * fulltext_count / len(papers))
    logger.info("Kept abstract-only (ar5iv content too short): %d", abstract_fallback)
    logger.info("Not found on ar5iv: %d", not_found)


if __name__ == "__main__":
    main()
