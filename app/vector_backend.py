"""向量后端解析：auto 模式下在 Chroma / Qdrant 间自动选择。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from app.config import Settings

logger = logging.getLogger(__name__)

ResolvedBackend = Literal["chroma", "qdrant"]


def _qdrant_collection_has_points(settings: Settings) -> bool:
    """检测 Qdrant 本地目录或远程 URL 上目标 collection 是否有点。"""
    coll = (settings.chroma_collection_name or "").strip()
    if not coll:
        return False
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        return False

    def _check(client: QdrantClient) -> bool:
        info = client.get_collection(coll)
        count = getattr(info, "points_count", None)
        if count is None:
            status = getattr(info, "status", None)
            if status is not None:
                count = getattr(status, "points_count", None)
        return bool(count and int(count) > 0)

    qpath = settings.qdrant_path
    if qpath:
        path = Path(qpath)
        if path.is_dir():
            client: QdrantClient | None = None
            try:
                client = QdrantClient(path=str(path))
                if _check(client):
                    return True
            except Exception as exc:
                logger.debug("Qdrant local auto-detect failed: %s", exc)
            finally:
                if client is not None:
                    try:
                        client.close()
                    except Exception:
                        pass

    client = None
    try:
        kwargs: dict = {"url": settings.qdrant_url, "timeout": 2.0}
        if settings.qdrant_api_key:
            kwargs["api_key"] = settings.qdrant_api_key
        client = QdrantClient(**kwargs)
        return _check(client)
    except Exception as exc:
        logger.debug("Qdrant URL auto-detect failed for %s: %s", coll, exc)
        return False
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def resolve_vector_backend(settings: Settings) -> ResolvedBackend:
    """解析实际向量后端。explicit chroma/qdrant 直接返回；auto 优先可用 Qdrant。"""
    raw = getattr(settings, "vector_backend", "auto")
    if raw in ("chroma", "qdrant"):
        return raw

    if _qdrant_collection_has_points(settings):
        logger.info(
            "vector_backend=auto -> qdrant (collection %s has points)",
            settings.chroma_collection_name,
        )
        return "qdrant"

    logger.debug(
        "vector_backend=auto -> chroma (no usable Qdrant collection %s)",
        settings.chroma_collection_name,
    )
    return "chroma"
