"""Multi-strategy chunking: hierarchical markdown → recursive sentence split → parent-child structure.

Strategies (configurable via chunk_strategy):
- `hierarchical_recursive` (default): Heading-aware split + recursive sentence split +
  overlap + parent-child metadata.
- `markdown_heading_overlap`: Heading split + SentenceSplitter (legacy).
- `heading_only`: Heading split only (no further subdivision).

All strategies preserve tenant_id, access-control metadata, and heading-path tracking.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import BaseNode, TextNode

from app.config import Settings

_DEFAULT_TENANT_ID = "corp-default"
_ACCESS_METADATA_KEYS = (
    "domain",
    "subdomain",
    "security_level",
    "audience",
    "tenant_id",
    "owner",
    "status",
    "version",
)

logger = logging.getLogger(__name__)


# ── Metadata helpers (preserved from original) ────────────────────

def _ensure_access_metadata(metadata: dict) -> dict:
    out = dict(metadata)
    if not str(out.get("tenant_id") or "").strip():
        out["tenant_id"] = _DEFAULT_TENANT_ID
    return out


def _rel_path_under_docs(file_path: str, docs_dir: Path) -> str:
    if not (file_path or "").strip():
        return ""
    dd = docs_dir.resolve()
    raw = file_path.strip()
    try:
        p = Path(raw).resolve()
        return str(p.relative_to(dd))
    except ValueError:
        pass
    p2 = Path(raw)
    if not p2.is_absolute():
        cand = (dd / raw).resolve()
        try:
            return str(cand.relative_to(dd))
        except ValueError:
            pass
    name = p2.name
    if name:
        matches = [m for m in dd.rglob(name) if m.is_file() and m.suffix.lower() == ".md"]
        if len(matches) == 1:
            return str(matches[0].relative_to(dd))
        if len(matches) > 1:
            matches.sort(key=lambda x: str(x))
            logger.warning(
                "同 basename 多文件命中，取字典序第一个: %s (candidates=%s)",
                name,
                [str(m.relative_to(dd)) for m in matches[:5]],
            )
            return str(matches[0].relative_to(dd))
    return name


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    text = raw.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}, raw
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw
    end_idx: int | None = None
    for i in range(1, len(lines)):
        stripped = lines[i].strip()
        if stripped == "---" or stripped.startswith("---"):
            end_idx = i
            break
    if end_idx is None:
        return {}, raw
    meta: dict[str, str] = {}
    for line in lines[1:end_idx]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            meta[key] = value
    body = "\n".join(lines[end_idx + 1:]).lstrip()
    return meta, body


def _normalize_metadata_value(value) -> str | int | float | bool | None:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(v) for v in value)
    return str(value)


def _normalize_node_metadata(nodes: list[BaseNode]) -> None:
    for node in nodes:
        raw = dict(node.metadata or {})
        node.metadata = _ensure_access_metadata(
            {str(k): _normalize_metadata_value(v) for k, v in raw.items()}
        )


def _doc_metadata_by_path(documents: list[Document], docs_dir: Path) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for doc in documents:
        fp = doc.metadata.get("file_path") or doc.metadata.get("file_name") or ""
        if fp:
            rel = _rel_path_under_docs(fp, docs_dir).replace("\\", "/")
            doc.metadata["file_name"] = Path(rel).name
            doc.metadata["file_path"] = rel
        else:
            rel = ""
            doc.metadata.setdefault("file_name", "unknown")
            doc.metadata.setdefault("file_path", "")
        base = _ensure_access_metadata(dict(doc.metadata or {}))
        if rel:
            lookup[rel] = base
    return lookup


def _inherit_doc_metadata(nodes: list[BaseNode], doc_lookup: dict[str, dict[str, str]]) -> None:
    for node in nodes:
        raw = dict(node.metadata or {})
        fp = str(raw.get("file_path") or "").replace("\\", "/")
        inherited = doc_lookup.get(fp, {})
        merged = {**inherited, **raw}
        node.metadata = merged


def load_documents(docs_dir: Path) -> list[Document]:
    if not docs_dir.is_dir():
        raise FileNotFoundError(f"docs_dir 不存在: {docs_dir}")
    documents: list[Document] = []
    for path in sorted(docs_dir.rglob("*.md")):
        raw = path.read_text(encoding="utf-8")
        frontmatter, body = _parse_frontmatter(raw)
        rel_path = _rel_path_under_docs(str(path), docs_dir)
        metadata = _ensure_access_metadata({
            **frontmatter,
            "file_name": path.name,
            "file_path": rel_path,
            "source_path": rel_path,
            "doc_group": Path(rel_path).parts[0] if Path(rel_path).parts else "",
        })
        documents.append(Document(text=body, metadata=metadata))
    return documents


# ── New: Heading-aware chunking with heading-path metadata ────────

def _extract_heading_path(heading_node: BaseNode) -> str:
    """Return the heading-path string from a heading node's metadata."""
    return str(heading_node.metadata.get("header_path", "") or "").strip()


def _heading_level(heading_path: str) -> int:
    """Infer heading depth from the path separator count."""
    if not heading_path:
        return 0
    return heading_path.count(" > ") + 1


def _truncate_at_sentence_boundary(text: str, max_chars: int) -> int:
    """Find the best split point near max_chars, preferring sentence/line breaks."""
    if len(text) <= max_chars:
        return len(text)
    # Try to find the last sentence boundary within max_chars
    candidate = max_chars
    # Look for sentence-ending punctuation followed by space/newline
    for sep in ("。\n", "！\n", "？\n", ".\n", "\n\n", "。", "！", "？", ". ", ".\n", "\n"):
        idx = text.rfind(sep, 0, candidate)
        if idx != -1 and idx > candidate * 0.6:
            return idx + len(sep)
    # Fallback: line break
    idx = text.rfind("\n", 0, candidate)
    if idx != -1 and idx > candidate * 0.5:
        return idx + 1
    # Last resort: space boundary
    idx = text.rfind(" ", 0, candidate)
    if idx != -1 and idx > candidate * 0.4:
        return idx + 1
    return candidate


def _recursive_split_text(
    text: str,
    max_chars: int,
    overlap_chars: int,
    min_chunk_chars: int = 50,
) -> list[dict]:
    """Recursively split text at sentence boundaries with overlap.

    Returns list of {"text": str, "overlap_prev": str, "overlap_next": str}.
    """
    if not text.strip():
        return []
    if len(text) <= max_chars:
        return [{"text": text.strip(), "overlap_prev": "", "overlap_next": ""}]

    chunks = []
    start = 0
    while start < len(text):
        end = _truncate_at_sentence_boundary(text, start + max_chars)
        if end <= start:
            end = min(start + max_chars, len(text))
        chunk_text = text[start:end].strip()
        if len(chunk_text) < min_chunk_chars and chunks:
            # Merge tiny leftover with previous chunk
            chunks[-1]["text"] += "\n" + chunk_text
            start = end
            continue

        # Overlap with previous chunk
        overlap_prev = ""
        if chunks and overlap_chars > 0:
            prev = chunks[-1]["text"]
            overlap_prev = prev[-overlap_chars:] if len(prev) > overlap_chars else prev

        # Overlap with next segment (preview next ~overlap_chars)
        overlap_next = ""
        if overlap_chars > 0 and end < len(text):
            next_preview = text[end:end + overlap_chars]
            # Extend to sentence boundary
            sep_idx = -1
            for sep in ("。", "\n", ".", " ", "！", "？"):
                idx = next_preview.find(sep)
                if idx != -1:
                    sep_idx = idx
                    break
            if sep_idx != -1:
                overlap_next = next_preview[:sep_idx + 1]
            else:
                overlap_next = next_preview

        chunks.append({
            "text": chunk_text,
            "overlap_prev": overlap_prev,
            "overlap_next": overlap_next,
        })
        start = end - overlap_chars if overlap_chars > 0 else end
        if start >= len(text) or (start == end and overlap_chars == 0):
            break
    return chunks


def _build_hierarchical_nodes(
    documents: list[Document],
    settings: Settings,
    doc_lookup: dict[str, dict[str, str]],
) -> list[BaseNode]:
    """Build nodes using hierarchical heading + recursive sentence split.

    Strategy:
    1. Parse markdown headings → heading_path nodes.
    2. For each heading node, create a parent node (full section).
    3. Recursively split oversized sections into child nodes with overlap.
    4. All nodes carry metadata: heading_path, parent_heading_path, heading_level,
       is_parent_chunk, overlap_prev, overlap_next.
    """
    md_parser = MarkdownNodeParser.from_defaults(header_path_separator=" > ")
    heading_nodes = md_parser.get_nodes_from_documents(documents)
    _inherit_doc_metadata(heading_nodes, doc_lookup)

    # Estimate token ↔ char ratio (Chinese text ~1.5 chars/token, English ~5 chars/token)
    # Use a conservative estimate: 2 chars / token for mixed content
    CHAR_PER_TOKEN = 2.0
    chunk_chars = int(settings.chunk_size_tokens * CHAR_PER_TOKEN)
    overlap_chars = int(settings.chunk_overlap_tokens * CHAR_PER_TOKEN)
    min_chunk_chars = max(50, chunk_chars // 8)

    all_nodes: list[BaseNode] = []

    for heading_node in heading_nodes:
        text = heading_node.get_content() or ""
        if not text.strip():
            continue

        heading_path = _extract_heading_path(heading_node)
        h_level = _heading_level(heading_path)

        # Base metadata from heading node
        base_meta = dict(heading_node.metadata)
        base_meta["heading_path"] = heading_path
        base_meta["heading_level"] = h_level

        if len(text) <= chunk_chars:
            # Short section → single node (both parent and child)
            node = TextNode(
                text=text.strip(),
                metadata={
                    **base_meta,
                    "is_parent_chunk": True,
                    "is_child_chunk": True,
                    "parent_heading_path": heading_path,
                },
            )
            all_nodes.append(node)
        else:
            # Create parent node (full section text, stored for retrieval context)
            parent_node = TextNode(
                text=text.strip(),
                metadata={
                    **base_meta,
                    "is_parent_chunk": True,
                    "is_child_chunk": False,
                    "parent_heading_path": heading_path,
                    "chunk_count": 0,  # filled below
                },
            )
            all_nodes.append(parent_node)

            # Recursively split into child nodes
            raw_chunks = _recursive_split_text(
                text, chunk_chars, overlap_chars, min_chunk_chars
            )

            for i, rc in enumerate(raw_chunks):
                child_text = rc["text"]
                if not child_text.strip():
                    continue
                child_node = TextNode(
                    text=child_text,
                    metadata={
                        **base_meta,
                        "is_parent_chunk": False,
                        "is_child_chunk": True,
                        "parent_heading_path": heading_path,
                        "child_index": i,
                        "child_total": len(raw_chunks),
                        "overlap_prev": rc["overlap_prev"],
                        "overlap_next": rc["overlap_next"],
                    },
                )
                all_nodes.append(child_node)
            # Update parent chunk count
            parent_node.metadata["chunk_count"] = len(raw_chunks)

    _normalize_node_metadata(all_nodes)
    return all_nodes


# ── Public entrypoint ─────────────────────────────────────────────

def build_nodes(documents: list[Document], settings: Settings) -> list[BaseNode]:
    """Build chunks from documents using the configured strategy.

    Supports strategies:
    - ``hierarchical_recursive`` (default): heading-aware + recursive sentence split
      + parent-child structure with overlap metadata.
    - ``markdown_heading_overlap``: heading split + SentenceSplitter (legacy).
    - ``heading_only``: heading split only.
    """
    if not documents:
        return []

    docs_dir = Path(settings.docs_dir).resolve()
    doc_lookup = _doc_metadata_by_path(documents, docs_dir)
    strategy = (settings.chunk_strategy or "hierarchical_recursive").strip().lower()

    if strategy == "heading_only":
        md_parser = MarkdownNodeParser.from_defaults(header_path_separator=" > ")
        nodes = md_parser.get_nodes_from_documents(documents)
        _inherit_doc_metadata(nodes, doc_lookup)
        _normalize_node_metadata(nodes)
        return nodes

    if strategy == "markdown_heading_overlap":
        md_parser = MarkdownNodeParser.from_defaults(header_path_separator=" > ")
        heading_nodes = md_parser.get_nodes_from_documents(documents)
        splitter = SentenceSplitter(
            chunk_size=settings.chunk_size_tokens,
            chunk_overlap=settings.chunk_overlap_tokens,
        )
        nodes = splitter(heading_nodes)
        _inherit_doc_metadata(nodes, doc_lookup)
        _normalize_node_metadata(nodes)
        return nodes

    if strategy == "hierarchical_recursive":
        return _build_hierarchical_nodes(documents, settings, doc_lookup)

    raise ValueError(
        f"未知 chunk_strategy={settings.chunk_strategy!r}；"
        "可选: hierarchical_recursive, markdown_heading_overlap, heading_only"
    )
