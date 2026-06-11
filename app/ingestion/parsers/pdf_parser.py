"""PDF parser using pdfplumber for text extraction and table detection.

For scanned PDFs (no text layer), falls back to VLM-based OCR.
"""
from __future__ import annotations

import logging
from typing import Any

from app.ingestion.parsers.base import BaseParser, ParsedDocument, ParsedPage

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """Parse PDF files using pdfplumber."""

    supported_mimes = [
        "application/pdf",
    ]

    def parse(self, file_path: str, *, ocr_fallback: bool = True, **kwargs) -> ParsedDocument:
        """Parse a PDF file.

        Args:
            file_path: Path to the PDF file
            ocr_fallback: If True, use VLM OCR for pages with no text
        """
        import pdfplumber

        pages: list[ParsedPage] = []
        total_pages = 0

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                page_number = i + 1
                text = page.extract_text() or ""
                tables = []

                # Extract tables
                extracted_tables = page.extract_tables()
                for table in extracted_tables:
                    if not table:
                        continue
                    md_table = self._table_to_markdown(table)
                    if md_table:
                        tables.append(md_table)

                # OCR fallback for pages with very little text
                images = []
                if ocr_fallback and len(text.strip()) < 20 and total_pages > 0:
                    try:
                        ocr_text = self._ocr_page(page, file_path, page_number)
                        if ocr_text:
                            images.append({
                                "page": page_number,
                                "bbox": [0, 0, page.width, page.height],
                                "ocr_text": ocr_text,
                            })
                    except Exception as e:
                        logger.warning("OCR fallback failed for page %d: %s", page_number, e)

                pages.append(ParsedPage(
                    page_number=page_number,
                    text=text,
                    tables=tables,
                    images=images,
                    metadata={"width": page.width, "height": page.height},
                ))

        return ParsedDocument(
            pages=pages,
            total_pages=total_pages,
            metadata={"file_path": file_path},
        )

    def _table_to_markdown(self, table: list[list[str | None]]) -> str:
        """Convert a pdfplumber-extracted table to Markdown format."""
        if not table:
            return ""

        # Filter out completely empty rows
        rows = []
        for row in table:
            if any(cell and str(cell).strip() for cell in row):
                rows.append([str(cell or "").strip() for cell in row])

        if not rows:
            return ""

        # Normalize column count
        max_cols = max(len(row) for row in rows)
        for row in rows:
            while len(row) < max_cols:
                row.append("")

        # Build markdown table
        lines = []
        # Header
        lines.append("| " + " | ".join(rows[0]) + " |")
        lines.append("| " + " | ".join(["---"] * max_cols) + " |")
        # Body
        for row in rows[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def _ocr_page(self, page, file_path: str, page_number: int) -> str:
        """Use VLM to OCR a page with no text layer."""
        try:
            from app.vlm import ocr_image
            from PIL import Image
            import io

            # Render page to image
            img = page.to_image(resolution=200)
            # Convert to bytes
            buf = io.BytesIO()
            img.original.save(buf, format="PNG")
            img_bytes = buf.getvalue()

            return ocr_image(image_bytes=img_bytes)
        except ImportError:
            logger.warning("VLM or PIL not available for OCR fallback")
            return ""
        except Exception as e:
            logger.warning("VLM OCR failed for page %d: %s", page_number, e)
            return ""
