"""Tests for document parsers: PDF, DOCX, Image, Markdown."""
from __future__ import annotations

import io
import os
import tempfile
import unittest

from app.ingestion.parsers.base import ParsedDocument, ParsedPage, BaseParser
from app.ingestion.parsers.factory import (
    get_parser,
    mime_type_from_filename,
    is_supported_mime,
    parse_document,
)
from app.ingestion.parsers.markdown_parser import MarkdownParser


class TestMimeTypeDetection(unittest.TestCase):
    """Test MIME type detection from file extensions."""

    def test_pdf(self):
        assert mime_type_from_filename("test.pdf") == "application/pdf"

    def test_docx(self):
        assert mime_type_from_filename("report.docx") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_png(self):
        assert mime_type_from_filename("scan.png") == "image/png"

    def test_jpg(self):
        assert mime_type_from_filename("photo.jpg") == "image/jpeg"

    def test_md(self):
        assert mime_type_from_filename("faq.md") == "text/markdown"

    def test_unknown(self):
        assert mime_type_from_filename("data.xyz") == "application/octet-stream"


class TestParserFactory(unittest.TestCase):
    """Test parser factory selection."""

    def test_pdf_parser(self):
        parser = get_parser("application/pdf")
        assert parser is not None
        assert "PDF" in type(parser).__name__

    def test_docx_parser(self):
        parser = get_parser("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert parser is not None
        assert "DOCX" in type(parser).__name__

    def test_image_parser(self):
        parser = get_parser("image/png")
        assert parser is not None
        assert "Image" in type(parser).__name__

    def test_markdown_parser(self):
        parser = get_parser("text/markdown")
        assert parser is not None
        assert "Markdown" in type(parser).__name__

    def test_unsupported_returns_none(self):
        parser = get_parser("application/zip")
        assert parser is None


class TestSupportedMimes(unittest.TestCase):
    """Test is_supported_mime function."""

    def test_supported_types(self):
        assert is_supported_mime("application/pdf")
        assert is_supported_mime("image/png")
        assert is_supported_mime("text/markdown")

    def test_unsupported_types(self):
        assert not is_supported_mime("application/zip")
        assert not is_supported_mime("video/mp4")


class TestMarkdownParser(unittest.TestCase):
    """Test Markdown parser with real files."""

    def test_parse_simple_md(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", encoding="utf-8", delete=False) as f:
            f.write("# Test Heading\n\nThis is a test paragraph.\n\n## Sub Heading\n\nAnother paragraph.")
            f.flush()
            path = f.name

        try:
            parser = MarkdownParser()
            result = parser.parse(path)
            assert isinstance(result, ParsedDocument)
            assert result.total_pages == 1
            assert "Test Heading" in result.full_text
            assert "Another paragraph" in result.full_text
        finally:
            os.unlink(path)

    def test_parse_md_with_frontmatter(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", encoding="utf-8", delete=False) as f:
            f.write("---\ndomain: shipping\ntenant_id: t_test\n---\n\n# Content\n\nBody text here.")
            f.flush()
            path = f.name

        try:
            parser = MarkdownParser()
            result = parser.parse(path)
            assert "Body text here" in result.full_text
            assert result.pages[0].metadata.get("domain") == "shipping"
            assert result.pages[0].metadata.get("tenant_id") == "t_test"
        finally:
            os.unlink(path)

    def test_parse_plain_text(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", encoding="utf-8", delete=False) as f:
            f.write("This is plain text.\nLine two.")
            f.flush()
            path = f.name

        try:
            parser = MarkdownParser()
            assert parser.can_parse("text/plain")
            result = parser.parse(path)
            assert "This is plain text" in result.full_text
        finally:
            os.unlink(path)


class TestPDFParser(unittest.TestCase):
    """Test PDF parser (basic structure tests without real PDFs)."""

    def test_can_parse_pdf(self):
        from app.ingestion.parsers.pdf_parser import PDFParser
        parser = PDFParser()
        assert parser.can_parse("application/pdf")
        assert not parser.can_parse("image/png")

    def test_table_to_markdown(self):
        from app.ingestion.parsers.pdf_parser import PDFParser
        parser = PDFParser()
        table = [
            ["Name", "Age", "City"],
            ["Alice", "30", "Beijing"],
            ["Bob", "25", "Shanghai"],
        ]
        result = parser._table_to_markdown(table)
        assert "| Name | Age | City |" in result
        assert "| --- | --- | --- |" in result
        assert "| Alice | 30 | Beijing |" in result

    def test_table_to_markdown_empty(self):
        from app.ingestion.parsers.pdf_parser import PDFParser
        parser = PDFParser()
        assert parser._table_to_markdown([]) == ""
        assert parser._table_to_markdown([[]]) == ""


class TestDOCXParser(unittest.TestCase):
    """Test DOCX parser."""

    def test_can_parse_docx(self):
        from app.ingestion.parsers.docx_parser import DOCXParser
        parser = DOCXParser()
        assert parser.can_parse("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert not parser.can_parse("application/pdf")

    def test_table_to_markdown(self):
        from app.ingestion.parsers.docx_parser import DOCXParser
        # We can't easily create a docx.table object, so just test the parser exists
        parser = DOCXParser()
        assert hasattr(parser, "_table_to_markdown")


class TestImageParser(unittest.TestCase):
    """Test Image parser."""

    def test_can_parse_image(self):
        from app.ingestion.parsers.image_parser import ImageParser
        parser = ImageParser()
        assert parser.can_parse("image/png")
        assert parser.can_parse("image/jpeg")
        assert parser.can_parse("image/webp")
        assert not parser.can_parse("application/pdf")


class TestParsedDocument(unittest.TestCase):
    """Test ParsedDocument data class."""

    def test_full_text(self):
        doc = ParsedDocument(
            pages=[
                ParsedPage(page_number=1, text="Hello world"),
                ParsedPage(page_number=2, text="Second page"),
            ],
            total_pages=2,
        )
        assert "Hello world" in doc.full_text
        assert "Second page" in doc.full_text

    def test_full_text_with_tables(self):
        doc = ParsedDocument(
            pages=[
                ParsedPage(
                    page_number=1,
                    text="Some text",
                    tables=["| A | B |\n| --- | --- |\n| 1 | 2 |"],
                ),
            ],
            total_pages=1,
        )
        assert "Some text" in doc.full_text
        assert "| A | B |" in doc.full_text

    def test_full_text_with_images(self):
        doc = ParsedDocument(
            pages=[
                ParsedPage(
                    page_number=1,
                    text="Page text",
                    images=[{"page": 1, "bbox": [0, 0, 100, 100], "ocr_text": "OCR result"}],
                ),
            ],
            total_pages=1,
        )
        assert "OCR result" in doc.full_text


if __name__ == "__main__":
    unittest.main()
