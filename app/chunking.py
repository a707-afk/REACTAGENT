"""Markdown 标题切分 + 过长段落二次切分（token overlap）。"""
from __future__ import annotations

import logging
from pathlib import Path

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import BaseNode

from app.config import Settings

# 访问控制与索引 payload 期望字段；front matter 缺省时在 load 阶段补全
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


def _ensure_access_metadata(metadata: dict) -> dict:
    """保证 enterprise chunk 写入 Chroma/BM25 时 access 字段非空（缺省 tenant 用 corp-default）。"""
    out = dict(metadata)
    if not str(out.get("tenant_id") or "").strip():
        out["tenant_id"] = _DEFAULT_TENANT_ID
    return out


def _rel_path_under_docs(file_path: str, docs_dir: Path) -> str:
    """得到相对 docs_dir 的 POSIX 风格相对路径；避免子节点只剩 basename。"""
    if not (file_path or "").strip():
        return ""
    dd = docs_dir.resolve()
    raw = file_path.strip()
    logger = logging.getLogger(__name__)
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
    """Parse a small YAML-like frontmatter block without adding a dependency."""
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

    body = "\n".join(lines[end_idx + 1 :]).lstrip()
    return meta, body


def load_documents(docs_dir: Path) -> list[Document]:
    if not docs_dir.is_dir():
        raise FileNotFoundError(f"docs_dir 不存在: {docs_dir}")
    documents: list[Document] = []
    for path in sorted(docs_dir.rglob("*.md")):
        raw = path.read_text(encoding="utf-8")
        frontmatter, body = _parse_frontmatter(raw)
        rel_path = _rel_path_under_docs(str(path), docs_dir)
        metadata = _ensure_access_metadata(
            {
                **frontmatter,
                "file_name": path.name,
                "file_path": rel_path,
                "source_path": rel_path,
                "doc_group": Path(rel_path).parts[0] if Path(rel_path).parts else "",
            }
        )
        documents.append(Document(text=body, metadata=metadata))
    return documents


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
            {
                str(k): _normalize_metadata_value(v)
                for k, v in raw.items()
            }
        )


def _doc_metadata_by_path(documents: list[Document], docs_dir: Path) -> dict[str, dict[str, str]]:
    """按相对路径索引文档级 front matter，供分块后回填到每个 chunk。"""
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
    """MarkdownNodeParser / SentenceSplitter 会丢掉 front matter，从源文档 metadata 回填。"""
    for node in nodes:
        raw = dict(node.metadata or {})
        fp = str(raw.get("file_path") or "").replace("\\", "/")
        inherited = doc_lookup.get(fp, {})
        merged = {**inherited, **raw}
        node.metadata = merged


def build_nodes(documents: list[Document], settings: Settings) -> list[BaseNode]:
    if not documents:
        return []

    docs_dir = Path(settings.docs_dir).resolve()
    doc_lookup = _doc_metadata_by_path(documents, docs_dir)

    if settings.chunk_strategy == "heading_only":
        md_parser = MarkdownNodeParser.from_defaults(header_path_separator=" > ")
        nodes = md_parser.get_nodes_from_documents(documents)
        _inherit_doc_metadata(nodes, doc_lookup)
        _normalize_node_metadata(nodes)
        return nodes

    if settings.chunk_strategy != "markdown_heading_overlap":
        raise ValueError(
            f"未知 chunk_strategy={settings.chunk_strategy!r}；"
            "可选: markdown_heading_overlap, heading_only"
        )

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
