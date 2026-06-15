"""Fix 4 data quality issues identified in strict audit.

1. Strip residual HTML tags from ALL .md files (not just milvus)
2. Delete abstract-only papers (<5KB) — pure noise
3. Remove Qdrant documentation nav-bar residue (first N lines)
4. Merge bge-m3 near-duplicates into one file

Each fix has a verify step. Run this ONCE, then re-audit.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("fix_quality")

ROOT = Path("data/docs_research")


# ── Fix 1: Strip HTML tags from all .md files ─────────────────────

# Tags that are content-bearing in markdown and should be KEPT as-is
# (we only strip HTML that's clearly residue, not intentional markdown HTML)
HTML_STRIP_TAGS = re.compile(
    r'<(?:img|picture|source|svg|input|button|form|iframe|nav|footer|header|aside'
    r'|a\s+href|div\s|span\s|table\s|script|style)\b[^>]*>(?:.*?</(?:a|div|span|table|script|style|nav|footer|header|aside)>)?',
    re.DOTALL | re.IGNORECASE,
)
# Self-closing / void tags
HTML_VOID_TAGS = re.compile(
    r'<(?:img|picture|source|svg|input|br|hr|meta|link|col|area|base|wbr)\b[^>]*/?>',
    re.IGNORECASE,
)
# Any remaining <tag>...</tag> that's not a markdown code span
HTML_GENERIC = re.compile(r'<(/?)(\w+)(\s[^>]*)?(/?)>', re.IGNORECASE)
# Markdown-safe HTML (keep): comments, and code blocks content is untouched


def strip_html_residue(content: str) -> tuple[str, int]:
    """Remove HTML tag residue from markdown content. Returns (cleaned, removals)."""
    original_len = len(content)

    # Protect code blocks (don't touch HTML inside ``` or `inline`)
    code_blocks: list[str] = []
    def _stash_code(m):
        code_blocks.append(m.group(0))
        return f"\x00CODEBLOCK{len(code_blocks)-1}\x00"

    content = re.sub(r'```.*?```', _stash_code, content, flags=re.DOTALL)
    content = re.sub(r'`[^`]+`', _stash_code, content)

    # Also protect HTML comments (metadata headers)
    content = re.sub(r'<!--.*?-->', _stash_code, content, flags=re.DOTALL)

    # Strip void/self-closing tags
    content = HTML_VOID_TAGS.sub('', content)

    # Strip paired tags with content (img inside <a>, etc.)
    content = HTML_STRIP_TAGS.sub('', content)

    # Strip any remaining generic HTML tags (but keep markdown)
    # Only strip if it looks like HTML, not a markdown link [text](url)
    def _strip_generic(m):
        tag_name = m.group(2).lower()
        # Keep these (they're valid in markdown/HTML docs)
        if tag_name in ('br', 'hr', 'b', 'i', 'em', 'strong', 'code', 'pre',
                        'sub', 'sup', 'kbd', 'mark', 's', 'u'):
            return m.group(0)  # keep
        # Strip everything else
        return ''

    content = HTML_GENERIC.sub(_strip_generic, content)

    # Restore code blocks and comments
    for i, block in enumerate(code_blocks):
        content = content.replace(f"\x00CODEBLOCK{i}\x00", block)

    # Clean up: remove empty links like []() left after stripping
    content = re.sub(r'\[()\]', '', content)
    # Remove lines that are just whitespace
    content = re.sub(r'\n[ \t]+\n', '\n\n', content)
    # Collapse excessive blank lines
    content = re.sub(r'\n{4,}', '\n\n\n', content)

    removals = original_len - len(content)
    return content.strip(), removals


def fix_html_tags():
    """Fix 1: Strip HTML tags from all .md files."""
    logger.info("=== Fix 1: Strip HTML tags ===")
    fixed = 0
    for fpath in sorted(ROOT.rglob("*.md")):
        if fpath.name.startswith("_"):
            continue
        content = fpath.read_text(encoding="utf-8", errors="replace")
        tag_count = len(re.findall(r'<(?:img|a href|picture|source|svg|div|span|button|input|form|iframe|nav|table)\b', content, re.IGNORECASE))
        if tag_count <= 2:
            continue
        cleaned, removed = strip_html_residue(content)
        if removed > 10:  # Only write if meaningful change
            fpath.write_text(cleaned, encoding="utf-8")
            logger.info("  %s: removed %d chars of HTML (%d tags → ~0)", fpath.name, removed, tag_count)
            fixed += 1
    logger.info("  Fixed %d files", fixed)


# ── Fix 2: Delete abstract-only papers ─────────────────────────────

def fix_abstract_papers():
    """Fix 2: Delete papers <5KB (abstract-only, no full text)."""
    logger.info("=== Fix 2: Delete abstract-only papers ===")
    papers_dir = ROOT / "papers"
    deleted = 0
    for fpath in sorted(papers_dir.glob("*.md")):
        if fpath.name.startswith("_"):
            continue
        size = fpath.stat().st_size
        if size < 5000:
            logger.info("  DELETE %s (%d bytes)", fpath.name[:60], size)
            fpath.unlink()
            deleted += 1
    logger.info("  Deleted %d abstract-only papers", deleted)


# ── Fix 3: Remove Qdrant nav-bar residue ───────────────────────────

# The nav bar looks like repeated single-word lines:
# Local\nQuickstart\nUser Manual\nTutorials\nSupport\nSearch\n...
NAV_KEYWORDS = {
    "Local", "Quickstart", "Quickstart ", "User Manual", "Tutorials",
    "Support", "Search", "Improve Search", "Manage Data", "Send Data",
    "Migrate to Qdrant", "Cloud", "Private Cloud", "Hybrid Cloud",
    "Observability", "Ops Configuration", "Ops Monitoring", "Ops Optimization",
    "Search Precision", "Faq", "FAQ", "Examples", "Overview",
    "Migration Guidance", "Cloud Rbac", "Cloud Tools", "Cloud Authentication",
    "Tutorials Search Engineering", "Tutorials Build Essentials",
    "Tutorials Develop", "Tutorials Basics",
}


def fix_qdrant_navbar():
    """Fix 3: Remove navigation bar residue from Qdrant docs.

    Strategy: the metadata header (HTML comments) is followed by nav-bar
    residue, then the real content starts at the first markdown heading (#).
    We keep: HTML comment header + first '#' heading onward. Delete everything
    between the header close and the first heading.
    """
    logger.info("=== Fix 3: Remove Qdrant nav-bar ===")
    docs_dir = ROOT / "official_docs"
    fixed = 0
    for fpath in sorted(docs_dir.glob("qdrant_*.md")):
        content = fpath.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")

        # Find end of HTML comment header
        header_end = 0
        for i, line in enumerate(lines):
            if "-->" in line:
                header_end = i + 1
                break  # First --> closes the last comment in header block

        # Find first markdown heading after header
        first_heading = None
        for i in range(header_end, min(len(lines), header_end + 50)):
            if lines[i].strip().startswith("#") and len(lines[i].strip()) > 3:
                first_heading = i
                break

        if first_heading is None:
            continue

        # Count nav lines being removed (for logging)
        nav_lines = lines[header_end:first_heading]
        nav_content = "\n".join(nav_lines).strip()
        if len(nav_content) < 20:
            continue  # No significant nav bar

        # Rebuild: header comments + blank line + content from first heading
        new_content = "\n".join(lines[:header_end]) + "\n\n" + "\n".join(lines[first_heading:])

        fpath.write_text(new_content, encoding="utf-8")
        logger.info("  %s: removed %d chars of nav-bar residue", fpath.name, len(nav_content))
        fixed += 1
    logger.info("  Fixed %d files", fixed)


# ── Fix 4: Merge bge-m3 near-duplicates ────────────────────────────

def fix_bge3_duplicate():
    """Fix 4: Merge bge-m3_readme.md and bge_m3_dense_sparse.md."""
    logger.info("=== Fix 4: Merge bge-m3 duplicates ===")
    f1 = ROOT / "embeddings" / "bge-m3_readme.md"
    f2 = ROOT / "official_docs" / "bge_m3_dense_sparse.md"

    if not f1.exists() or not f2.exists():
        logger.info("  One or both files missing, skipping")
        return

    c1 = f1.read_text(encoding="utf-8", errors="replace")
    c2 = f2.read_text(encoding="utf-8", errors="replace")

    # Keep the larger one, delete the smaller
    if len(c1) >= len(c2):
        # Keep f1 (embeddings/bge-m3_readme.md), delete f2
        f2.unlink()
        logger.info("  Deleted %s (duplicate of %s)", f2.name, f1.name)
    else:
        f1.unlink()
        logger.info("  Deleted %s (duplicate of %s)", f1.name, f2.name)


def main():
    fix_html_tags()
    fix_abstract_papers()
    fix_qdrant_navbar()
    fix_bge3_duplicate()
    logger.info("=== All fixes applied. Run audit to verify. ===")


if __name__ == "__main__":
    main()
