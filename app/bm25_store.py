"""BM25 词法检索：与向量候选合并；语料在 reindex 时落盘。"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from llama_index.core.schema import BaseNode, TextNode
from llama_index.core.schema import NodeWithScore
from rank_bm25 import BM25Okapi

from app.config import Settings

logger = logging.getLogger(__name__)

_bm25: BM25Okapi | None = None
_bm25_ids: list[str] | None = None
_bm25_meta: dict[str, dict] | None = None


def clear_bm25_memory_cache() -> None:
    global _bm25, _bm25_ids, _bm25_meta
    _bm25 = None
    _bm25_ids = None
    _bm25_meta = None


def persist_bm25_corpus(nodes: list[BaseNode], settings: Settings) -> Path:
    """将节点写入 JSONL，供 BM25 加载。"""
    path = Path(settings.bm25_corpus_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for n in nodes:
        nid = n.node_id
        text = n.get_content() or ""
        meta = dict(n.metadata or {})
        lines.append(
            json.dumps(
                {"id": nid, "text": text, "metadata": meta},
                ensure_ascii=False,
            )
        )
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    logger.info("BM25 语料已写入 %s (%s 条)", path, len(lines))
    clear_bm25_memory_cache()
    return path


def _tokenize_zh(text: str) -> list[str]:
    import jieba

    text = text.lower()
    # jieba + 英文/数字连续片段，兼顾 Markdown
    raw = list(jieba.cut(text, cut_all=False))
    out: list[str] = []
    for t in raw:
        t = t.strip()
        if not t:
            continue
        out.append(t)
        for m in re.findall(r"[a-z0-9]+", t, flags=re.I):
            if len(m) > 1:
                out.append(m)
    return out if out else [" "]


def _load_corpus_disk(corpus_path: str) -> tuple[BM25Okapi, list[str], dict[str, dict]]:
    p = Path(corpus_path)
    if not p.is_file():
        raise FileNotFoundError(f"BM25 语料不存在: {p}（请先 python scripts/reindex.py）")
    ids: list[str] = []
    tokenized_corpus: list[list[str]] = []
    meta: dict[str, dict] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        nid = str(obj["id"])
        text = str(obj.get("text") or "")
        ids.append(nid)
        tokenized_corpus.append(_tokenize_zh(text))
        meta[nid] = dict(obj.get("metadata") or {})
        meta[nid]["_bm25_text"] = text
    if not tokenized_corpus:
        return BM25Okapi([["empty"]]), [], {}
    return BM25Okapi(tokenized_corpus), ids, meta


def _get_bm25(settings: Settings) -> tuple[BM25Okapi, list[str], dict[str, dict]]:
    global _bm25, _bm25_ids, _bm25_meta
    if _bm25 is not None and _bm25_ids is not None and _bm25_meta is not None:
        return _bm25, _bm25_ids, _bm25_meta
    path = str(Path(settings.bm25_corpus_path).resolve())
    _bm25, _bm25_ids, _bm25_meta = _load_corpus_disk(path)
    logger.info("BM25 已加载: %s 条文档", len(_bm25_ids))
    return _bm25, _bm25_ids, _bm25_meta


def bm25_search(
    settings: Settings,
    query: str,
    top_k: int,
    *,
    allowed_ids: frozenset[str] | None = None,
) -> list[tuple[str, float]]:
    """返回 (node_id, bm25_raw_score) 降序。``allowed_ids`` 非空时仅在可访问子集上排序。"""
    if top_k < 1:
        return []
    try:
        bm25, ids, _ = _get_bm25(settings)
    except FileNotFoundError:
        logger.warning("BM25 语料缺失，跳过 BM25 分支")
        return []
    if not ids:
        return []
    q_tokens = _tokenize_zh(query)
    if not q_tokens:
        return []
    scores = bm25.get_scores(q_tokens)
    if allowed_ids is not None:
        ranked = sorted(
            (i for i in range(len(ids)) if ids[i] in allowed_ids),
            key=lambda i: float(scores[i]),
            reverse=True,
        )[:top_k]
    else:
        ranked = sorted(
            range(len(ids)), key=lambda i: float(scores[i]), reverse=True
        )[:top_k]
    return [(ids[i], float(scores[i])) for i in ranked]


def node_with_score_from_bm25(
    node_id: str, bm25_score: float, meta_lookup: dict[str, dict]
) -> NodeWithScore | None:
    m = meta_lookup.get(node_id)
    if not m:
        return None
    text = str(m.get("_bm25_text") or "")
    meta = {k: v for k, v in m.items() if k != "_bm25_text"}
    node = TextNode(text=text, metadata=meta, id_=node_id)
    return NodeWithScore(node=node, score=bm25_score)
