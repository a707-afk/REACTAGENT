"""Document upload and management API.

Endpoints:
- POST /api/documents/upload — Upload a file, return document_id and job_id
- GET /api/documents/{id} — View document status
- GET /api/documents — Paginated list
- POST /api/documents/{id}/reindex — Re-index a document
- DELETE /api/documents/{id} — Soft-delete document and its vectors
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends
from pydantic import BaseModel

from app.api.deps import get_db_session
from app.db.models.document import Document
from app.db.models.ingestion_job import IngestionJob

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

# Default tenant for single-tenant deployments
_DEFAULT_TENANT = "corp-default"


# ── Request/Response models ────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: str
    tenant_id: str
    file_name: str
    mime_type: str
    file_size: int
    content_hash: str
    status: str
    page_count: int | None = None
    language: str | None = None
    domain: str | None = None
    security_level: str = "internal"
    version: int = 1
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    offset: int
    limit: int


class UploadResponse(BaseModel):
    document_id: str
    job_id: str
    message: str


class ReindexResponse(BaseModel):
    document_id: str
    job_id: str
    message: str


class DeleteResponse(BaseModel):
    document_id: str
    deleted: bool
    message: str


# ── Endpoints ───────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Form(default=_DEFAULT_TENANT),
    domain: str | None = Form(default=None),
    security_level: str = Form(default="internal"),
    allowed_roles: str | None = Form(default=None),
    db=Depends(get_db_session),
):
    """Upload a file for ingestion.

    The file will be saved and an ingestion job will be queued.
    """
    from app.ingestion.pipeline import validate_file, compute_content_hash

    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    # Read file data
    file_data = await file.read()
    file_name = file.filename or "unknown"
    file_size = len(file_data)

    # Validate
    try:
        mime_type = validate_file(file_name, file_size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {e}")

    # Compute hash
    content_hash = compute_content_hash(file_data)

    # Check dedup
    from app.ingestion.pipeline import check_dedup
    existing_id = await check_dedup(content_hash, tenant_id, db)
    if existing_id:
        raise HTTPException(
            status_code=409,
            detail=f"Document already exists: {existing_id}",
        )

    # Create Document record
    doc_id = str(uuid.uuid4())
    storage_path = f"data/uploads/{tenant_id}/{doc_id}_{file_name}"

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        file_name=file_name,
        mime_type=mime_type,
        file_size=file_size,
        content_hash=content_hash,
        storage_path=storage_path,
        status="draft",
        domain=domain,
        security_level=security_level,
        allowed_roles=allowed_roles,
    )
    db.add(doc)

    # Save file
    from pathlib import Path
    storage_dir = Path(f"data/uploads/{tenant_id}")
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / f"{doc_id}_{file_name}").write_bytes(file_data)

    # Create IngestionJob
    job_id = str(uuid.uuid4())
    job = IngestionJob(
        id=job_id,
        tenant_id=tenant_id,
        document_id=doc_id,
        status="queued",
        progress=0,
        task_type="ingest_document",
        task_params='{"domain": "%s", "security_level": "%s", "allowed_roles": "%s"}' % (
            domain or "", security_level, allowed_roles or ""
        ),
    )
    db.add(job)
    await db.flush()

    # Try to enqueue to arq (non-blocking)
    try:
        from app.worker.queue import enqueue_job
        # Already created the job, so just push to arq
        from app.redis_client import get_redis_pool
        redis = await get_redis_pool()
        from arq import create_pool_from_settings
        from arq.connections import RedisSettings
        from urllib.parse import urlparse
        from app.config import get_settings
        settings = get_settings()
        parsed = urlparse(settings.redis_url)
        redis_settings = RedisSettings(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            database=int(parsed.path.lstrip("/") or "0"),
            password=settings.redis_password or parsed.password or None,
        )
        arq_pool = await create_pool_from_settings(redis_settings)
        await arq_pool.enqueue_job(
            "ingest_document",
            job_id=job_id,
            tenant_id=tenant_id,
            document_id=doc_id,
            params={"domain": domain, "security_level": security_level, "allowed_roles": allowed_roles},
        )
    except Exception as e:
        logger.warning("arq enqueue failed (job will be processed on next worker start): %s", e)

    await db.flush()

    return UploadResponse(
        document_id=doc_id,
        job_id=job_id,
        message="File uploaded and ingestion job queued",
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    tenant_id: str = Query(default=_DEFAULT_TENANT),
    db=Depends(get_db_session),
):
    """Get document details."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    doc = await db.get(Document, document_id)
    if doc is None or doc.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status == "deleted":
        raise HTTPException(status_code=410, detail="Document has been deleted")

    return DocumentResponse(
        id=doc.id,
        tenant_id=doc.tenant_id,
        file_name=doc.file_name,
        mime_type=doc.mime_type,
        file_size=doc.file_size,
        content_hash=doc.content_hash,
        status=doc.status,
        page_count=doc.page_count,
        language=doc.language,
        domain=doc.domain,
        security_level=doc.security_level,
        version=doc.version,
        created_at=doc.created_at.isoformat() if doc.created_at else "",
        updated_at=doc.updated_at.isoformat() if doc.updated_at else "",
    )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    tenant_id: str = Query(default=_DEFAULT_TENANT),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db=Depends(get_db_session),
):
    """List documents with pagination and filtering."""
    from sqlalchemy import select, func

    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    base_filter = (Document.tenant_id == tenant_id) & (Document.status != "deleted")
    if status:
        base_filter = base_filter & (Document.status == status)

    # Count
    count_q = select(func.count()).select_from(Document).where(base_filter)
    total = (await db.execute(count_q)).scalar() or 0

    # Query
    q = (
        select(Document)
        .where(base_filter)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(q)
    docs = list(result.scalars().all())

    items = [
        DocumentResponse(
            id=d.id,
            tenant_id=d.tenant_id,
            file_name=d.file_name,
            mime_type=d.mime_type,
            file_size=d.file_size,
            content_hash=d.content_hash,
            status=d.status,
            page_count=d.page_count,
            language=d.language,
            domain=d.domain,
            security_level=d.security_level,
            version=d.version,
            created_at=d.created_at.isoformat() if d.created_at else "",
            updated_at=d.updated_at.isoformat() if d.updated_at else "",
        )
        for d in docs
    ]

    return DocumentListResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("/{document_id}/reindex", response_model=ReindexResponse)
async def reindex_document(
    document_id: str,
    tenant_id: str = Query(default=_DEFAULT_TENANT),
    db=Depends(get_db_session),
):
    """Re-index a document (creates a new ingestion job)."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    doc = await db.get(Document, document_id)
    if doc is None or doc.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status == "deleted":
        raise HTTPException(status_code=410, detail="Document has been deleted")

    # Create a new ingestion job
    job_id = str(uuid.uuid4())
    job = IngestionJob(
        id=job_id,
        tenant_id=tenant_id,
        document_id=document_id,
        status="queued",
        progress=0,
        task_type="ingest_document",
    )
    db.add(job)
    await db.flush()

    return ReindexResponse(
        document_id=document_id,
        job_id=job_id,
        message="Re-index job queued",
    )


@router.delete("/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str,
    tenant_id: str = Query(default=_DEFAULT_TENANT),
    db=Depends(get_db_session),
):
    """Soft-delete a document and remove its vectors."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    doc = await db.get(Document, document_id)
    if doc is None or doc.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status == "deleted":
        return DeleteResponse(
            document_id=document_id,
            deleted=True,
            message="Document was already deleted",
        )

    # Soft delete in DB
    doc.status = "deleted"
    doc.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Try to delete from Qdrant (non-blocking)
    try:
        from app.ingestion.pipeline import delete_document as pipeline_delete
        # Already soft-deleted above, just clean vectors
        from app.vector_index import get_vector_index
        index = get_vector_index()
        if index:
            from llama_index.core.vector_stores import MetadataFilter, MetadataFilters
            index.delete(
                metadata_filters=MetadataFilters(
                    filters=[MetadataFilter(key="document_id", value=document_id)]
                )
            )
    except Exception as e:
        logger.warning("Qdrant delete failed (non-fatal): %s", e)

    # Delete file from storage
    try:
        from pathlib import Path
        storage_path = Path(doc.storage_path)
        if storage_path.exists():
            storage_path.unlink()
    except Exception as e:
        logger.warning("File delete failed (non-fatal): %s", e)

    return DeleteResponse(
        document_id=document_id,
        deleted=True,
        message="Document deleted successfully",
    )
