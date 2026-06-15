"""Fix Qdrant nav-bar: find first '#' heading, delete everything before it.

The HTML comment header was already damaged by Fix 1 (HTML tag stripper
removed the <!-- url --> and <!-- fetched --> lines). So we can't rely on
finding --> to locate the header end.

New strategy: scan for the first line starting with '#' that has >3 chars
of content. Everything before that is either damaged comments or nav-bar.
Replace the entire pre-heading section with a clean metadata header.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("fix_nav")

DOCS_DIR = Path("data/docs_research/official_docs")


def fix_file(fpath: Path) -> bool:
    """Remove nav-bar residue. Returns True if changed."""
    content = fpath.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")

    # Find first TOP-LEVEL markdown heading ("# Title", not "### Nav")
    # Nav-bar uses ### which we must skip. Real content starts with # or ##.
    first_heading_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Only accept "# " (h1) or "## " (h2) — NOT "###" which is nav-bar
        if (stripped.startswith("# ") or stripped.startswith("## ")) and len(stripped) > 5:
            first_heading_idx = i
            break

    if first_heading_idx is None:
        return False
    if first_heading_idx <= 1:
        return False  # Heading at line 0 or 1 = no nav bar

    # Count what's being removed (for logging)
    removed_content = "\n".join(lines[:first_heading_idx]).strip()
    if len(removed_content) < 20:
        return False  # Not enough to be a nav bar

    # Extract title from the heading
    title = lines[first_heading_idx].strip().lstrip("#").strip()
    source_name = fpath.stem.replace("_", " ").title()

    # New content: clean metadata + original content from heading onward
    new_header = f"""<!-- source: {source_name} -->
<!-- cleaned: nav-bar removed -->

"""
    new_content = new_header + "\n".join(lines[first_heading_idx:])
    new_content = re.sub(r"\n{4,}", "\n\n\n", new_content)

    if len(new_content) < len(content):
        fpath.write_text(new_content.strip() + "\n", encoding="utf-8")
        logger.info("  %s: removed %d chars before heading '%s'",
                    fpath.name, len(removed_content), title[:40])
        return True
    return False


def main():
    logger.info("=== Fix Qdrant nav-bar (final) ===")
    fixed = 0
    for fpath in sorted(DOCS_DIR.glob("qdrant_*.md")):
        if fix_file(fpath):
            fixed += 1
    logger.info("Fixed %d files", fixed)


if __name__ == "__main__":
    main()
