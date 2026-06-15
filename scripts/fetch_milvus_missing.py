"""Fetch only the missing Milvus doc pages.

Uses the same milvus.io URLs as fetch_docs_v2.py, but skips files that already
exist locally so we don't overwrite the cleaned versions. Each fetched page is
cleaned with the same logic as clean_research_kb.py.
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from urllib.request import urlopen, Request

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("fetch_milvus")

OUT_DIR = Path("data/docs_research/official_docs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Only the missing ones; milvus_overview/index/tune(performance_faq) already exist.
MISSING = [
    ("milvus_gpu.md",          "https://milvus.io/docs/gpu_index.md",          "Milvus GPU Index"),
    ("milvus_schema.md",       "https://milvus.io/docs/schema.md",             "Milvus Schema"),
    ("milvus_dynamic.md",      "https://milvus.io/docs/enable-dynamic-field.md","Milvus Dynamic Field"),
    ("milvus_dense_sparse.md", "https://milvus.io/docs/full-text-search.md",   "Milvus Full-text Search"),
    ("milvus_partition.md",    "https://milvus.io/docs/manage-partitions.md",  "Milvus Partitions"),
    ("milvus_multivector.md",  "https://milvus.io/docs/multi-vector-search.md","Milvus Multi-vector Search"),
    ("milvus_reranking.md",    "https://milvus.io/docs/reranking.md",          "Milvus Reranking"),
    ("milvus_collections.md",  "https://milvus.io/docs/manage-collections.md", "Milvus Collections"),
    ("milvus_scale.md",        "https://milvus.io/docs/scaleout.md",           "Milvus Scale-out"),
    ("milvus_consistency.md",  "https://milvus.io/docs/consistency.md",        "Milvus Consistency Levels"),
]


def _html_to_text(htmlsrc: str) -> str:
    import html as htmlmod
    for tag in ["script", "style", "nav", "footer", "header", "aside", "noscript",
                "svg", "form", "iframe"]:
        htmlsrc = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", htmlsrc,
                         flags=re.DOTALL | re.IGNORECASE)
    htmlsrc = re.sub(r"<h([1-6])[^>]*>", lambda m: "\n\n" + "#" * int(m.group(1)) + " ",
                     htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"</h[1-6]>", "\n", htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"<li[^>]*>", "\n- ", htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"<p[^>]*>", "\n\n", htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"<br\s*/?>", "\n", htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"<code[^>]*>", "`", htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"</code>", "`", htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"<pre[^>]*>", "\n```\n", htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"</pre>", "\n```\n", htmlsrc, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", htmlsrc)
    text = htmlmod.unescape(text)
    text = text.replace("`n", "").replace("`r", "").replace("`t", "  ")
    text = htmlmod.unescape(text)
    text = re.sub(r"^[ \t]*[-*][ \t]*$\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"(?:^[ \t]*[-*][ \t]*$\n){2,}", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*(?:View as Markdown|Edit on Github|On this page:.*?)$\n",
                  "", text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def fetch_and_save(fname: str, url: str, label: str) -> bool:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (research-kb-builder)"})
    try:
        with urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                logger.warning("  HTTP %d for %s", resp.status, url)
                return False
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("  FAIL %s: %s", url, e)
        return False

    if "<html" in raw.lower()[:500]:
        text = _html_to_text(raw)
    else:
        text = raw
    if len(text) < 300:
        logger.warning("  too short (%d chars), skipping", len(text))
        return False
    header = f"<!-- source: {label} -->\n<!-- url: {url} -->\n<!-- fetched: {time.strftime('%Y-%m-%d')} -->\n\n"
    (OUT_DIR / fname).write_text(header + text, encoding="utf-8")
    logger.info("  OK: %d chars -> %s", len(text), fname)
    return True


def main() -> None:
    logger.info("Fetching %d missing Milvus pages...", len(MISSING))
    ok = fail = 0
    for i, (fname, url, label) in enumerate(MISSING, 1):
        if (OUT_DIR / fname).exists():
            logger.info("[%d/%d] %s  (already exists, skip)", i, len(MISSING), label)
            continue
        logger.info("[%d/%d] %s", i, len(MISSING), label)
        if fetch_and_save(fname, url, label):
            ok += 1
        else:
            fail += 1
        time.sleep(1.5)
    logger.info("Done: %d fetched, %d failed, %d skipped", ok, fail, len(MISSING) - ok - fail)


if __name__ == "__main__":
    main()
