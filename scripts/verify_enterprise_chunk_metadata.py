"""读取 Chroma enterprise 集合中一条 chunk，校验 access 元数据非空。

用法（企业索引已 reindex 后）::

    $env:DOCS_DIR="data/docs/enterprise_ai_ops"
    $env:CHROMA_COLLECTION_NAME="enterprise_ai_ops"
    python scripts/verify_enterprise_chunk_metadata.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_REQUIRED = ("domain", "security_level", "audience", "tenant_id")


def main() -> None:
    import chromadb

    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    client = chromadb.PersistentClient(path=str(Path(settings.chroma_persist_dir)))
    coll_name = settings.chroma_collection_name
    coll = client.get_collection(coll_name)
    sample = coll.get(limit=50, include=["metadatas"])
    picked = None
    for md in sample.get("metadatas") or []:
        if md.get("file_path") and "sla-and-escalation.md" in str(md.get("file_path")):
            picked = md
            break
        if md.get("domain") and md.get("security_level"):
            picked = md
            break
    if picked is None and sample.get("metadatas"):
        picked = sample["metadatas"][0]
    if not picked:
        print(f"集合 {coll_name!r} 为空，请先 reindex", file=sys.stderr)
        sys.exit(2)
    md = picked
    missing = [k for k in _REQUIRED if not md.get(k)]
    print("collection:", coll_name)
    print("sample file_path:", md.get("file_path"))
    for k in _REQUIRED:
        print(f"  {k}: {md.get(k)!r}")
    if missing:
        print("FAIL missing:", missing, file=sys.stderr)
        sys.exit(1)
    print("OK enterprise chunk metadata")


if __name__ == "__main__":
    main()
