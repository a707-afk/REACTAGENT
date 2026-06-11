"""Markdown parser: reads .md files with frontmatter support."""
from __future__ import annotations

import logging
from typing import Any

from app.ingestion.parsers.base import BaseParser, ParsedDocument, ParsedPage

logger = logging.getLogger(__name__)


class MarkdownParser(BaseParser):
    """Parse Markdown files with frontmatter support."""

    supported_mimes = [
        "text/markdown",
        "text/x-markdown",
    ]

    # Also handle plain text
    _text_mimes = [
        "text/plain",
    ]

    def can_parse(self, mime_type: str) -> bool:
        return mime_type in self.supported_mimes or mime_type in self._text_mimes

    def parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """Parse a Markdown file."""
        from pathlib import Path

        path = Path(file_path)
        raw = path.read_text(encoding="utf-8")

        # Parse frontmatter
        metadata = {}
        text = raw
        if raw.lstrip("\ufeff").startswith("---"):
            fm, body = self._parse_frontmatter(raw)
            metadata = fm
            text = body

        # Extract domain/tenant from frontmatter
        if "domain" in metadata:
            metadata.setdefault("source_type", "policy")
        if "tenant_id" not in metadata:
            metadata["tenant_id"] = "corp-default"

        return ParsedDocument(
            pages=[
                ParsedPage(
                    page_number=1,
                    text=text,
                    tables=[],
                    images=[],
                    metadata=metadata,
                )
            ],
            total_pages=1,
            metadata={"file_path": str(file_path), **metadata},
        )

    def _parse_frontmatter(self, raw: str) -> tuple[dict[str, str], str]:
        """Parse YAML-like frontmatter from Markdown."""
        text = raw.lstrip("\ufeff")
        if not text.startswith("---"):
            return {}, raw

        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            return {}, raw

        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break

        if end_idx is None:
            return {}, raw

        meta = {}
        for line in lines[1:end_idx]:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key:
                meta[key] = value

        body = "\n".join(lines[end_idx + 1:]).lstrip()
        return meta, body
