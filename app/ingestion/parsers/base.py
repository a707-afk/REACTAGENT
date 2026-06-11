"""Base parser interface: all parsers must implement this contract."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedPage:
    """A single parsed page from a document."""
    page_number: int  # 1-based
    text: str
    tables: list[str] = field(default_factory=list)  # Markdown-formatted tables
    images: list[dict[str, Any]] = field(default_factory=list)  # {"page": n, "bbox": [...], "ocr_text": "..."}
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Full parsed output from a document."""
    pages: list[ParsedPage]
    total_pages: int
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """Concatenated text from all pages."""
        parts = []
        for page in self.pages:
            if page.text.strip():
                parts.append(page.text)
            for table in page.tables:
                parts.append(table)
            for img in page.images:
                if img.get("ocr_text"):
                    parts.append(img["ocr_text"])
        return "\n\n".join(parts)


class BaseParser:
    """Abstract base class for document parsers."""

    #: Supported MIME types
    supported_mimes: list[str] = []

    def can_parse(self, mime_type: str) -> bool:
        """Check if this parser supports the given MIME type."""
        return mime_type in self.supported_mimes

    def parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """Parse a document at the given file path.

        Args:
            file_path: Absolute path to the document
            **kwargs: Parser-specific options

        Returns:
            ParsedDocument with pages and metadata
        """
        raise NotImplementedError

    def parse_bytes(self, data: bytes, file_name: str = "", **kwargs) -> ParsedDocument:
        """Parse a document from raw bytes.

        Default implementation writes to a temp file and delegates to parse().
        Subclasses may override for better efficiency.

        Args:
            data: Raw file bytes
            file_name: Original file name (for extension detection)
            **kwargs: Parser-specific options

        Returns:
            ParsedDocument with pages and metadata
        """
        import tempfile
        import os

        ext = os.path.splitext(file_name)[1] if file_name else ".tmp"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(data)
            tmp_path = f.name
        try:
            return self.parse(tmp_path, **kwargs)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
