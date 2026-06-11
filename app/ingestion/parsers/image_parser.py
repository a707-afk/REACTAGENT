"""Image parser: uses VLM (sensenova-6.7-flash-lite) for OCR and content extraction."""
from __future__ import annotations

import logging
from typing import Any

from app.ingestion.parsers.base import BaseParser, ParsedDocument, ParsedPage

logger = logging.getLogger(__name__)


class ImageParser(BaseParser):
    """Parse image files using VLM for OCR."""

    supported_mimes = [
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
        "image/bmp",
        "image/tiff",
    ]

    def parse(self, file_path: str, *, extract_tables: bool = True, **kwargs) -> ParsedDocument:
        """Parse an image file using VLM OCR.

        Args:
            file_path: Path to the image file
            extract_tables: If True, also extract table content
        """
        from PIL import Image

        # Read image bytes
        with open(file_path, "rb") as f:
            image_bytes = f.read()

        # Get image dimensions
        img = Image.open(file_path)
        width, height = img.size

        # General OCR
        ocr_text = self._ocr(image_bytes)

        # Table extraction (separate VLM call for better results)
        table_text = ""
        tables = []
        if extract_tables:
            table_text = self._ocr_table(image_bytes)
            if table_text and table_text != ocr_text:
                tables.append(table_text)

        # Coordinate-aware OCR
        coord_text = ""
        images_meta = []
        try:
            coord_text = self._ocr_with_coordinates(image_bytes)
            if coord_text:
                images_meta.append({
                    "page": 1,
                    "bbox": [0, 0, width, height],
                    "ocr_text": coord_text,
                })
        except Exception as e:
            logger.warning("Coordinate OCR failed: %s", e)
            # Fallback: just use basic OCR result
            if ocr_text:
                images_meta.append({
                    "page": 1,
                    "bbox": [0, 0, width, height],
                    "ocr_text": ocr_text,
                })

        # Combine text
        combined_text = ocr_text
        if table_text and table_text != ocr_text:
            combined_text = f"{ocr_text}\n\n{table_text}"

        return ParsedDocument(
            pages=[
                ParsedPage(
                    page_number=1,
                    text=combined_text,
                    tables=tables,
                    images=images_meta,
                    metadata={"width": width, "height": height, "format": img.format},
                )
            ],
            total_pages=1,
            metadata={"file_path": file_path},
        )

    def _ocr(self, image_bytes: bytes) -> str:
        """Run general OCR on image bytes."""
        try:
            from app.vlm import ocr_image
            return ocr_image(image_bytes=image_bytes)
        except Exception as e:
            logger.error("VLM OCR failed: %s", e)
            return ""

    def _ocr_table(self, image_bytes: bytes) -> str:
        """Run table-specific OCR on image bytes."""
        try:
            from app.vlm import ocr_image_for_table
            return ocr_image_for_table(image_bytes=image_bytes)
        except Exception as e:
            logger.warning("VLM table OCR failed: %s", e)
            return ""

    def _ocr_with_coordinates(self, image_bytes: bytes) -> str:
        """Run coordinate-aware OCR on image bytes."""
        try:
            from app.vlm import ocr_image_with_coordinates
            return ocr_image_with_coordinates(image_bytes=image_bytes)
        except Exception as e:
            logger.warning("VLM coordinate OCR failed: %s", e)
            return ""
