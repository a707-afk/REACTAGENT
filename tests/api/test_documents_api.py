"""Tests for the documents API: upload, list, get, reindex, delete."""
from __future__ import annotations

import io
import json
import pytest

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.api.deps import get_db_session
from app.main import create_app


@pytest.fixture
async def app_with_db():
    """Create an app with an in-memory SQLite DB for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db_session():
        async with factory() as session:
            yield session
            await session.commit()

    app = create_app()
    app.dependency_overrides[get_db_session] = _override_get_db_session

    yield app

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(app_with_db):
    """Create an async test client."""
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestUploadDocument:
    """Test POST /api/documents/upload."""

    @pytest.mark.asyncio
    async def test_upload_markdown_file(self, client):
        """Upload a simple markdown file."""
        file_content = b"# Test FAQ\n\nThis is a test FAQ document."
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("test.md", io.BytesIO(file_content), "text/markdown")},
            data={"tenant_id": "t_test"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "document_id" in data
        assert "job_id" in data
        assert data["message"] == "File uploaded and ingestion job queued"

    @pytest.mark.asyncio
    async def test_upload_text_file(self, client):
        """Upload a plain text file."""
        file_content = b"Simple plain text content for testing."
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("notes.txt", io.BytesIO(file_content), "text/plain")},
            data={"tenant_id": "t_test"},
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_upload_unsupported_file(self, client):
        """Upload an unsupported file type should fail."""
        file_content = b"executable content"
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("malware.exe", io.BytesIO(file_content), "application/x-msdownload")},
            data={"tenant_id": "t_test"},
        )
        assert response.status_code == 400


class TestGetDocument:
    """Test GET /api/documents/{id}."""

    @pytest.mark.asyncio
    async def test_get_existing_document(self, client):
        """Get a document that was uploaded."""
        # Upload first
        file_content = b"# FAQ\n\nTest content."
        upload_resp = await client.post(
            "/api/documents/upload",
            files={"file": ("faq.md", io.BytesIO(file_content), "text/markdown")},
            data={"tenant_id": "t_test"},
        )
        doc_id = upload_resp.json()["document_id"]

        # Get it
        response = await client.get(
            f"/api/documents/{doc_id}",
            params={"tenant_id": "t_test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == doc_id
        assert data["file_name"] == "faq.md"
        assert data["mime_type"] == "text/markdown"

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(self, client):
        """Get a document that doesn't exist."""
        response = await client.get(
            "/api/documents/nonexistent-id",
            params={"tenant_id": "t_test"},
        )
        assert response.status_code == 404


class TestListDocuments:
    """Test GET /api/documents."""

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        """List documents when none exist."""
        response = await client.get(
            "/api/documents/",
            params={"tenant_id": "t_test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_after_upload(self, client):
        """List documents after uploading one."""
        # Upload
        file_content = b"# Test\n\nContent here."
        await client.post(
            "/api/documents/upload",
            files={"file": ("test.md", io.BytesIO(file_content), "text/markdown")},
            data={"tenant_id": "t_test"},
        )

        # List
        response = await client.get(
            "/api/documents/",
            params={"tenant_id": "t_test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, client):
        """List documents with pagination."""
        response = await client.get(
            "/api/documents/",
            params={"tenant_id": "t_test", "offset": 0, "limit": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["offset"] == 0
        assert data["limit"] == 5


class TestDeleteDocument:
    """Test DELETE /api/documents/{id}."""

    @pytest.mark.asyncio
    async def test_delete_existing_document(self, client):
        """Delete a document that exists."""
        # Upload first
        file_content = b"# To Delete\n\nThis will be deleted."
        upload_resp = await client.post(
            "/api/documents/upload",
            files={"file": ("delete_me.md", io.BytesIO(file_content), "text/markdown")},
            data={"tenant_id": "t_test"},
        )
        doc_id = upload_resp.json()["document_id"]

        # Delete
        response = await client.delete(
            f"/api/documents/{doc_id}",
            params={"tenant_id": "t_test"},
        )
        assert response.status_code == 200
        assert response.json()["deleted"] is True

        # Verify it's gone (should return 410)
        get_resp = await client.get(
            f"/api/documents/{doc_id}",
            params={"tenant_id": "t_test"},
        )
        assert get_resp.status_code == 410

    @pytest.mark.asyncio
    async def test_delete_nonexistent_document(self, client):
        """Delete a document that doesn't exist."""
        response = await client.delete(
            "/api/documents/nonexistent-id",
            params={"tenant_id": "t_test"},
        )
        assert response.status_code == 404


class TestTenantIsolation:
    """Test that tenants can only access their own documents."""

    @pytest.mark.asyncio
    async def test_tenant_cannot_see_other_tenant_docs(self, client):
        """Upload as tenant A, try to read as tenant B."""
        # Upload as tenant A
        file_content = b"# Secret\n\nTenant A's private document."
        upload_resp = await client.post(
            "/api/documents/upload",
            files={"file": ("secret.md", io.BytesIO(file_content), "text/markdown")},
            data={"tenant_id": "tenant_A"},
        )
        doc_id = upload_resp.json()["document_id"]

        # Try to read as tenant B
        response = await client.get(
            f"/api/documents/{doc_id}",
            params={"tenant_id": "tenant_B"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_tenant_cannot_delete_other_tenant_docs(self, client):
        """Upload as tenant A, try to delete as tenant B."""
        # Upload as tenant A
        file_content = b"# Protected\n\nCannot delete this."
        upload_resp = await client.post(
            "/api/documents/upload",
            files={"file": ("protected.md", io.BytesIO(file_content), "text/markdown")},
            data={"tenant_id": "tenant_A"},
        )
        doc_id = upload_resp.json()["document_id"]

        # Try to delete as tenant B
        response = await client.delete(
            f"/api/documents/{doc_id}",
            params={"tenant_id": "tenant_B"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_only_shows_own_tenant_docs(self, client):
        """Upload docs for two tenants, list should only show own docs."""
        # Upload for tenant A
        await client.post(
            "/api/documents/upload",
            files={"file": ("a.md", io.BytesIO(b"Tenant A doc"), "text/markdown")},
            data={"tenant_id": "tenant_A"},
        )
        # Upload for tenant B
        await client.post(
            "/api/documents/upload",
            files={"file": ("b.md", io.BytesIO(b"Tenant B doc"), "text/markdown")},
            data={"tenant_id": "tenant_B"},
        )

        # List for tenant A
        response = await client.get(
            "/api/documents/",
            params={"tenant_id": "tenant_A"},
        )
        data = response.json()
        # All returned docs should belong to tenant_A
        for item in data["items"]:
            assert item["tenant_id"] == "tenant_A"
