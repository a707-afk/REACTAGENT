"""Parser factory: selects the appropriate parser based on MIME type."""
from __future__ import annotations

import logging
import os

from app.ingestion.parsers.base import BaseParser, ParsedDocument

logger = logging.getLogger(__name__)

# Registry of all available parsers
_PARSERS: list[BaseParser] = []

# Extension → MIME type mapping
_EXT_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


def _ensure_parsers() -> list[BaseParser]:
    """Lazy-load all parsers (avoid circular imports at module level)."""
    global _PARSERS
    if _PARSERS:
        return _PARSERS

    from app.ingestion.parsers.pdf_parser import PDFParser
    from app.ingestion.parsers.docx_parser import DOCXParser
    from app.ingestion.parsers.image_parser import ImageParser
    from app.ingestion.parsers.markdown_parser import MarkdownParser

    _PARSERS = [
        PDFParser(),
        DOCXParser(),
        ImageParser(),
        MarkdownParser(),
    ]
    return _PARSERS


def get_parser(mime_type: str) -> BaseParser | None:
    """Get the appropriate parser for a MIME type.

    Args:
        mime_type: MIME type of the document

    Returns:
        A parser instance, or None if no parser supports this MIME type
    """
    for parser in _ensure_parsers():
        if parser.can_parse(mime_type):
            return parser
    return None


def mime_type_from_filename(file_name: str) -> str:
    """Guess MIME type from file extension.

    Args:
        file_name: File name with extension

    Returns:
        Guessed MIME type, or "application/octet-stream" if unknown
    """
    ext = os.path.splitext(file_name)[1].lower()
    return _EXT_TO_MIME.get(ext, "application/octet-stream")


def is_supported_mime(mime_type: str) -> bool:
    """Check if a MIME type is supported by any parser."""
    return get_parser(mime_type) is not None


def parse_document(file_path: str, *, mime_type: str | None = None, **kwargs) -> ParsedDocument:
    """Parse a document using the appropriate parser.

    Args:
        file_path: Path to the document
        mime_type: Optional MIME type override (auto-detected if not provided)
        **kwargs: Parser-specific options

    Returns:
        ParsedDocument with pages and metadata

    Raises:
        ValueError: If no parser supports this file type
    """
    if mime_type is None:
        file_name = os.path.basename(file_path)
        mime_type = mime_type_from_filename(file_name)

    parser = get_parser(mime_type)
    if parser is None:
        raise ValueError(f"Unsupported file type: {mime_type}")

    logger.info("Parsing %s with %s (mime=%s)", file_path, type(parser).__name__, mime_type)
    return parser.parse(file_path, **kwargs)


def parse_document_bytes(
    data: bytes,
    *,
    file_name: str = "",
    mime_type: str | None = None,
    **kwargs,
) -> ParsedDocument:
    """Parse a document from raw bytes.

    Args:
        data: Raw file bytes
        file_name: Original file name (for extension detection)
        mime_type: Optional MIME type override
        **kwargs: Parser-specific options

    Returns:
        ParsedDocument with pages and metadata
    """
    if mime_type is None:
        mime_type = mime_type_from_filename(file_name)

    parser = get_parser(mime_type)
    if parser is None:
        raise ValueError(f"Unsupported file type: {mime_type}")

    return parser.parse_bytes(data, file_name=file_name, **kwargs)
