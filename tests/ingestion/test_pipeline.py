"""Tests for the ingestion pipeline: validation, hashing, chunking, dedup."""
from __future__ import annotations

import hashlib
import os
import tempfile
import unittest

from app.ingestion.pipeline import (
    validate_file,
    compute_content_hash,
    check_dedup,
    scan_for_threats,
    clean_text,
    chunk_parsed_document,
    IngestionError,
    MAX_FILE_SIZE_BYTES,
)
from app.ingestion.parsers.base import ParsedDocument, ParsedPage


class TestFileValidation(unittest.TestCase):
    """Test file validation (extension, MIME, size)."""

    def test_valid_pdf(self):
        mime = validate_file("test.pdf", 1024)
        assert mime == "application/pdf"

    def test_valid_docx(self):
        mime = validate_file("report.docx", 5000)
        assert "wordprocessingml" in mime

    def test_valid_image(self):
        mime = validate_file("scan.png", 2048)
        assert mime == "image/png"

    def test_unsupported_extension(self):
        with self.assertRaises(IngestionError) as ctx:
            validate_file("malware.exe", 1024)
        assert "Unsupported file extension" in str(ctx.exception)

    def test_file_too_large(self):
        with self.assertRaises(IngestionError) as ctx:
            validate_file("big.pdf", MAX_FILE_SIZE_BYTES + 1)
        assert "too large" in str(ctx.exception).lower()

    def test_empty_file(self):
        with self.assertRaises(IngestionError) as ctx:
            validate_file("empty.pdf", 0)
        assert "Empty" in str(ctx.exception)

    def test_custom_mime_type(self):
        mime = validate_file("data.pdf", 1024, mime_type="application/pdf")
        assert mime == "application/pdf"


class TestContentHash(unittest.TestCase):
    """Test SHA-256 content hashing."""

    def test_hash_deterministic(self):
        data = b"hello world"
        h1 = compute_content_hash(data)
        h2 = compute_content_hash(data)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex length

    def test_hash_different_data(self):
        h1 = compute_content_hash(b"hello")
        h2 = compute_content_hash(b"world")
        assert h1 != h2

    def test_hash_matches_sha256(self):
        data = b"test data"
        expected = hashlib.sha256(data).hexdigest()
        assert compute_content_hash(data) == expected


class TestThreatScanning(unittest.TestCase):
    """Test threat scanning stub."""

    def test_stub_returns_clean(self):
        result = scan_for_threats(b"benign data", "test.pdf")
        assert result["clean"] is True
        assert result["threats"] == []
        assert result["scanner"] == "stub"
        assert "scanned_at" in result


class TestTextCleaning(unittest.TestCase):
    """Test text cleaning utilities."""

    def test_removes_null_bytes(self):
        assert clean_text("hello\x00world") == "hello world"

    def test_normalizes_whitespace(self):
        assert clean_text("hello   world") == "hello world"

    def test_removes_excessive_newlines(self):
        result = clean_text("line1\n\n\n\nline2")
        assert result == "line1\n\nline2"

    def test_strips_lines(self):
        result = clean_text("  hello  \n  world  ")
        assert "hello" in result
        assert "world" in result

    def test_empty_input(self):
        assert clean_text("") == ""
        assert clean_text("   ") == ""


class TestChunking(unittest.TestCase):
    """Test document chunking."""

    def test_simple_document(self):
        doc = ParsedDocument(
            pages=[
                ParsedPage(page_number=1, text="This is a test sentence. And another one. Third sentence here."),
            ],
            total_pages=1,
        )
        chunks = chunk_parsed_document(doc, chunk_size=100, chunk_overlap=20)
        assert len(chunks) >= 1
        assert all("text" in c for c in chunks)
        assert all("chunk_id" in c for c in chunks)
        assert all("chunk_index" in c for c in chunks)

    def test_multi_page_document(self):
        doc = ParsedDocument(
            pages=[
                ParsedPage(page_number=1, text="Page one content with some text."),
                ParsedPage(page_number=2, text="Page two content with more text."),
            ],
            total_pages=2,
        )
        chunks = chunk_parsed_document(doc, chunk_size=200, chunk_overlap=20)
        assert len(chunks) >= 2

    def test_document_with_tables(self):
        doc = ParsedDocument(
            pages=[
                ParsedPage(
                    page_number=1,
                    text="Some regular text on this page.",
                    tables=["| A | B |\n| --- | --- |\n| 1 | 2 |"],
                ),
            ],
            total_pages=1,
        )
        chunks = chunk_parsed_document(doc, chunk_size=200, chunk_overlap=20)
        # Should have text chunk + table chunk
        has_table = any(c.get("is_table") for c in chunks)
        assert has_table, f"No table chunk found in {len(chunks)} chunks"

    def test_document_with_ocr(self):
        doc = ParsedDocument(
            pages=[
                ParsedPage(
                    page_number=1,
                    text="",
                    images=[{"page": 1, "bbox": [0, 0, 100, 100], "ocr_text": "OCR extracted text from image"}],
                ),
            ],
            total_pages=1,
        )
        chunks = chunk_parsed_document(doc, chunk_size=200, chunk_overlap=20)
        has_ocr = any(c.get("is_ocr") for c in chunks)
        assert has_ocr, f"No OCR chunk found in {len(chunks)} chunks"

    def test_empty_document(self):
        doc = ParsedDocument(pages=[], total_pages=0)
        chunks = chunk_parsed_document(doc)
        assert chunks == []

    def test_chunk_indices_sequential(self):
        doc = ParsedDocument(
            pages=[
                ParsedPage(page_number=1, text="First sentence. Second sentence. Third sentence. Fourth sentence."),
            ],
            total_pages=1,
        )
        chunks = chunk_parsed_document(doc, chunk_size=50, chunk_overlap=10)
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_chunks_have_unique_ids(self):
        doc = ParsedDocument(
            pages=[
                ParsedPage(page_number=1, text="Unique test content for chunk ID generation."),
            ],
            total_pages=1,
        )
        chunks = chunk_parsed_document(doc)
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs must be unique"


class TestDedupCheck(unittest.TestCase):
    """Test deduplication check with in-memory SQLite."""

    def test_no_duplicate(self):
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.db.base import Base
        from app.db.models.document import Document

        async def _test():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                result = await check_dedup("abc123", "t_test", session)
                assert result is None
            await engine.dispose()

        import asyncio
        asyncio.run(_test())

    def test_duplicate_exists(self):
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.db.base import Base
        from app.db.models.document import Document

        async def _test():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                # Create an existing document
                doc = Document(
                    id="doc-1",
                    tenant_id="t_test",
                    file_name="test.pdf",
                    mime_type="application/pdf",
                    file_size=100,
                    content_hash="abc123",
                    storage_path="/tmp/test.pdf",
                    status="active",
                )
                session.add(doc)
                await session.commit()

                # Check for duplicate
                result = await check_dedup("abc123", "t_test", session)
                assert result == "doc-1"
            await engine.dispose()

        import asyncio
        asyncio.run(_test())

    def test_deleted_document_not_counted(self):
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.db.base import Base
        from app.db.models.document import Document

        async def _test():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                # Create a deleted document
                doc = Document(
                    id="doc-1",
                    tenant_id="t_test",
                    file_name="test.pdf",
                    mime_type="application/pdf",
                    file_size=100,
                    content_hash="abc123",
                    storage_path="/tmp/test.pdf",
                    status="deleted",
                )
                session.add(doc)
                await session.commit()

                # Deleted doc should NOT count as duplicate
                result = await check_dedup("abc123", "t_test", session)
                assert result is None
            await engine.dispose()

        import asyncio
        asyncio.run(_test())

    def test_different_tenant_not_counted(self):
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.db.base import Base
        from app.db.models.document import Document

        async def _test():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                # Create doc for tenant A
                doc = Document(
                    id="doc-1",
                    tenant_id="tenant_A",
                    file_name="test.pdf",
                    mime_type="application/pdf",
                    file_size=100,
                    content_hash="abc123",
                    storage_path="/tmp/test.pdf",
                    status="active",
                )
                session.add(doc)
                await session.commit()

                # Different tenant should NOT see this as duplicate
                result = await check_dedup("abc123", "tenant_B", session)
                assert result is None
            await engine.dispose()

        import asyncio
        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
