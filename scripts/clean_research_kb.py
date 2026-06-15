"""Clean and normalize the research knowledge base (v2).

Improvements over v1:
  - Processes .html files too (converts them to .md, removes original)
  - Full HTML-entity decoding via html.unescape (was: 9 hardcoded entities)
  - Strips PowerShell backtick-escape residue (``n` from `Write-Host`)
  - Removes runs of empty markdown list dashes (nav-bar residue: 5+ bare "- " lines)
  - Drops empty markdown table cells / pipe-only lines
  - Generates an audit manifest with per-category stats

Output: cleaned files in-place + data/docs_research/_audit_manifest.md
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("clean_kb")

ROOT = Path("data/docs_research")
MIN_CONTENT_CHARS = 300  # raised from 200: abstract-only papers are ~1KB


def _is_html(content: str) -> bool:
    """Heuristic: is this file HTML rather than markdown?"""
    lower = content[:3000].lower()
    if "<!doctype html" in lower or "<html" in lower:
        return True
    tag_count = len(re.findall(r"<(?:div|span|p|script|style|head|body|nav|ul|li|table)\b", lower))
    return tag_count > 8


def _html_to_text(htmlsrc: str) -> str:
    """Convert HTML to clean markdown-ish text with structure preserved."""
    # Drop script/style/nav/footer/header/aside/svg blocks entirely
    for tag in ["script", "style", "nav", "footer", "header", "aside", "noscript",
                "svg", "form", "iframe"]:
        htmlsrc = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", htmlsrc,
                         flags=re.DOTALL | re.IGNORECASE)
    # Headings
    htmlsrc = re.sub(r"<h([1-6])[^>]*>", lambda m: "\n\n" + "#" * int(m.group(1)) + " ",
                     htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"</h[1-6]>", "\n", htmlsrc, flags=re.IGNORECASE)
    # Lists
    htmlsrc = re.sub(r"<li[^>]*>", "\n- ", htmlsrc, flags=re.IGNORECASE)
    # Paragraphs and breaks
    htmlsrc = re.sub(r"<p[^>]*>", "\n\n", htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"<br\s*/?>", "\n", htmlsrc, flags=re.IGNORECASE)
    # Code
    htmlsrc = re.sub(r"<code[^>]*>", "`", htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"</code>", "`", htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"<pre[^>]*>", "\n```\n", htmlsrc, flags=re.IGNORECASE)
    htmlsrc = re.sub(r"</pre>", "\n```\n", htmlsrc, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", htmlsrc)
    # Full entity decode (handles named, decimal, hex)
    text = html.unescape(text)
    return _normalize(text)


def _normalize(text: str) -> str:
    """Common post-processing for both markdown and html-sourced text."""
    # PowerShell backtick-escape residue (e.g. ``n, ``t, `r) from Write-Host dumps
    text = text.replace("`n", "").replace("`r", "").replace("`t", "  ")
    text = text.replace("`0", "").replace("`a", "").replace("`b", "")
    # Decode HTML entities that leaked into markdown text (e.g. &nbsp; from blog scrapes)
    text = html.unescape(text)
    # Drop single bare list-dash lines (sidebar residue from qdrant.tech etc.)
    text = re.sub(r"^[ \t]*[-*][ \t]*$\n", "", text, flags=re.MULTILINE)
    # Collapse runs of bare list-dash lines (nav-bar residue): 2+ consecutive "- " or "* "
    text = re.sub(r"(?:^[ \t]*[-*][ \t]*$\n){2,}", "", text, flags=re.MULTILINE)
    # Page-control residue (from doc-site footers/sidebars)
    text = re.sub(r"^[ \t]*(?:View as Markdown|Edit on Github|On this page:|Last edited.*?)$\n",
                  "", text, flags=re.MULTILINE | re.IGNORECASE)
    # Markdown pipe-only table rows (empty cells): "|  |  |" with nothing inside
    text = re.sub(r"^\s*\|(?:\s*\|)+\s*$\n", "", text, flags=re.MULTILINE)
    # Strip BOM / zero-width chars at the very start
    text = text.lstrip("\ufeff\u200b\u200c\u200d")
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    # Strip trailing whitespace per line
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    return text.strip()


def _extract_metadata(content: str, filepath: Path) -> dict:
    meta = {
        "source": "", "url": "", "fetched": "",
        "category": filepath.parent.name, "filename": filepath.name,
    }
    m = re.search(r"<!--\s*source:\s*(.+?)\s*-->", content[:500])
    if m:
        meta["source"] = m.group(1)
    m = re.search(r"<!--\s*url:\s*(.+?)\s*-->", content[:500])
    if m:
        meta["url"] = m.group(1)
    m = re.search(r"<!--\s*fetched:\s*(.+?)\s*-->", content[:500])
    if m:
        meta["fetched"] = m.group(1)
    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    meta["title"] = (m.group(1).strip()[:100] if m
                     else filepath.stem.replace("_", " ").title()[:100])
    return meta


def main() -> None:
    logger.info("Cleaning %s ...", ROOT)
    targets = sorted(ROOT.rglob("*.md")) + sorted(ROOT.rglob("*.html"))
    cleaned = skipped = removed = converted_html = 0
    audit_rows: list[dict] = []

    for fpath in targets:
        if fpath.name.startswith("_"):
            continue
        content = fpath.read_text(encoding="utf-8", errors="replace")
        is_html_ext = fpath.suffix == ".html"
        header = ""
        header_match = re.match(r"(<!--.*?-->\s*)+", content[:500], re.DOTALL)
        if header_match:
            header = header_match.group(0)

        was_html = is_html_ext or _is_html(content)

        if was_html:
            text = _html_to_text(content)
            if len(text) < MIN_CONTENT_CHARS:
                logger.warning("  REMOVED (HTML too short): %s (%d chars)",
                               fpath.name, len(text))
                fpath.unlink()
                removed += 1
                continue
            final_text = (header + "\n\n" + text).strip() if header else text
            out_path = fpath.with_suffix(".md")
            out_path.write_text(final_text, encoding="utf-8")
            if is_html_ext:
                fpath.unlink()  # remove .html original
                converted_html += 1
                logger.info("  HTML->MD: %s -> %s (%d chars)", fpath.name, out_path.name, len(text))
            else:
                fpath.write_text(final_text, encoding="utf-8")
                cleaned += 1
            final_path = out_path
        else:
            text = _normalize(content)
            if len(text) < MIN_CONTENT_CHARS:
                logger.warning("  REMOVED (too short): %s (%d chars)",
                               fpath.name, len(text))
                fpath.unlink()
                removed += 1
                continue
            if text != content:
                fpath.write_text(text, encoding="utf-8")
                cleaned += 1
            else:
                skipped += 1
            final_path = fpath
            final_text = text

        meta = _extract_metadata(final_text, final_path)
        meta["size_chars"] = len(final_text)
        meta["was_html"] = was_html
        audit_rows.append(meta)

    # Deduplicate: if two files have the same normalized content, keep the one
    # with more metadata (the official_docs copy usually has a source header).
    by_norm: dict[str, list[dict]] = {}
    for r in audit_rows:
        key = re.sub(r"\s+", "", r["title"]).lower()
        by_norm.setdefault(key, []).append(r)
    for key, grp in by_norm.items():
        if len(grp) > 1:
            logger.info("  NOTE: title duplicate across %d files: %s",
                        len(grp), [g["filename"] for g in grp])

    _write_manifest(audit_rows, cleaned, skipped, removed, converted_html)


def _write_manifest(rows: list[dict], cleaned: int, skipped: int,
                    removed: int, converted_html: int) -> None:
    from collections import defaultdict
    lines = [
        "# Research Knowledge Base — Audit Manifest",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Total files**: {len(rows)}",
        f"**Cleaned**: {cleaned}",
        f"**Converted HTML→MD**: {converted_html}",
        f"**Already clean**: {skipped}",
        f"**Removed (too short)**: {removed}",
        "",
        "## Files by Category",
        "",
    ]
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    for cat in sorted(by_cat.keys()):
        cat_rows = by_cat[cat]
        total_kb = sum(r["size_chars"] for r in cat_rows) / 1024
        lines.append(f"### {cat} ({len(cat_rows)} files, {total_kb:.1f} KB)")
        lines.append("")
        lines.append("| # | Filename | Title | Source | Size |")
        lines.append("|---|---|---|---|---|")
        for i, r in enumerate(sorted(cat_rows, key=lambda x: x["filename"]), 1):
            title = r["title"][:60].replace("|", "/")
            source = r["source"][:30].replace("|", "/")
            lines.append(f"| {i} | {r['filename']} | {title} | {source} | {r['size_chars']} |")
        lines.append("")
    (ROOT / "_audit_manifest.md").write_text("\n".join(lines), encoding="utf-8")
    logger.info("Manifest: %s", ROOT / "_audit_manifest.md")
    logger.info("Done: %d cleaned, %d html-converted, %d skipped, %d removed. Total: %d",
                cleaned, converted_html, skipped, removed, len(rows))


if __name__ == "__main__":
    main()
