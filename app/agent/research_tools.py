"""Research tools for the Deep Research Agent.

Replaces the deleted e-commerce tools (order_lookup, process_refund, etc.)
with research-domain tools that the ReAct loop can call:

1. ``local_search``  — retrieve from the local research corpus (Qdrant+BM25)
2. ``web_search``    — query the web via Tavily (stub in Phase 1, real in Phase 4)
3. ``fetch_page``    — fetch a specific URL's content (stub in Phase 1)
4. ``synthesize``    — LLM-synthesize gathered facts into a cited answer

All tools share a ``ToolResult`` contract and are registered in
``tool_registry._register_default_tools``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Tool schema definitions (OpenAI function-calling compatible) ──

TOOL_LOCAL_SEARCH = {
    "type": "function",
    "function": {
        "name": "local_search",
        "description": (
            "检索本地研究文档库（向量+BM25 混合检索）。用于查找技术文档、"
            "官方 README、benchmark 报告中的信息。返回带引用编号的相关片段。"
            "适合回答'XX 的特性是什么''XX 和 YY 有什么区别'类问题。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索查询词，用技术术语而非口语（如 'Qdrant HNSW payload filter'）。",
                },
                "top_k": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 5,
                    "description": "返回的片段数量",
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_WEB_SEARCH = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "联网搜索实时网页信息（通过 Tavily API）。用于本地库没有覆盖的"
            "时效性问题或最新动态。当前为 stub，阶段 4 接入 Tavily。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询词",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_FETCH_PAGE = {
    "type": "function",
    "function": {
        "name": "fetch_page",
        "description": (
            "抓取指定 URL 的网页内容并转为可检索文本。用于深入阅读 web_search "
            "返回的某个具体页面。当前为 stub，阶段 4 接入。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的网页 URL",
                },
            },
            "required": ["url"],
        },
    },
}

TOOL_SYNTHESIZE = {
    "type": "function",
    "function": {
        "name": "synthesize",
        "description": (
            "将已收集的多条检索结果综合成一段连贯的、带引用标注 [1][2] 的分析回答。"
            "用于在 local_search/web_search 收集足够证据后，生成最终回复。"
            "调用此工具前应已通过 local_search 收集至少 2 条相关片段。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "要回答的研究问题",
                },
                "evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "已收集的证据片段列表（来自 local_search/web_search 的结果）",
                },
            },
            "required": ["question", "evidence"],
        },
    },
}

ALL_RESEARCH_TOOLS = [
    TOOL_LOCAL_SEARCH, TOOL_WEB_SEARCH, TOOL_FETCH_PAGE, TOOL_SYNTHESIZE,
]


# ── Tool result contract ──────────────────────────────────────────

@dataclass
class ToolResult:
    """Unified result for all research tools."""
    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


# ── Tool implementations ──────────────────────────────────────────

def _execute_local_search(args: dict[str, Any]) -> ToolResult:
    """检索本地研究文档库。

    复用现有 retrieve_scored_nodes（Qdrant + BM25 hybrid + rerank + gate），
    把 NodeWithScore 结果转为带引用编号的片段列表。
    """
    query = str(args.get("query", "")).strip()
    top_k = int(args.get("top_k", 5))
    if not query:
        return ToolResult("local_search", False, error="query is required")

    try:
        from app.config import get_settings
        from app.vector_index import get_vector_index
        from app.retrieval_pipeline import retrieve_scored_nodes

        settings = get_settings()
        index = get_vector_index()
        if index is None:
            return ToolResult("local_search", False, error="Vector index not loaded")

        scored = retrieve_scored_nodes(
            index=index,
            user_query=query,
            top_k=top_k,
            settings=settings,
            skip_domain_router=True,  # domain router was deleted; always skip
        )

        snippets: list[dict[str, Any]] = []
        for i, sn in enumerate(scored.nodes[:top_k], start=1):
            node = sn.node
            meta = dict(node.metadata or {})
            text = (node.get_content() or "").strip()
            snippets.append({
                "index": i,
                "citation_id": node.node_id or f"src-{i}",
                "file_name": meta.get("file_name", ""),
                "heading": meta.get("header_path") or meta.get("heading") or "",
                "score": round(float(sn.score or 0.0), 4),
                "text": text[:800],  # cap snippet length for context window
            })

        return ToolResult(
            "local_search",
            success=True,
            data={
                "query": query,
                "retrieval_query": scored.retrieval_query,
                "count": len(snippets),
                "snippets": snippets,
            },
        )
    except Exception as e:
        logger.exception("local_search failed for query='%s'", query[:80])
        return ToolResult("local_search", False, error=str(e))


def _execute_web_search(args: dict[str, Any]) -> ToolResult:
    """联网搜索（Tavily）。

    Phase 1 stub: returns a clear 'not enabled' message so the ReAct loop
    can fall back to local_search. Phase 4 will implement the real call.
    """
    return ToolResult(
        "web_search",
        success=False,
        error=(
            "web_search 尚未启用（Phase 4 接入 Tavily）。"
            "请改用 local_search 检索本地研究文档库。"
        ),
    )


def _execute_fetch_page(args: dict[str, Any]) -> ToolResult:
    """抓取指定 URL。

    Phase 1 stub. Phase 4 will use httpx + html-to-markdown.
    """
    url = str(args.get("url", "")).strip()
    if not url:
        return ToolResult("fetch_page", False, error="url is required")
    return ToolResult(
        "fetch_page",
        success=False,
        error=f"fetch_page 尚未启用（Phase 4 接入）。无法抓取 {url}",
    )


def _execute_synthesize(args: dict[str, Any]) -> ToolResult:
    """LLM 综合多条证据为带引用的回答。

    输入：question + evidence（来自 local_search 的 snippets text）。
    输出：一段带 [1][2] 引用标注的分析回答。
    """
    question = str(args.get("question", "")).strip()
    evidence = args.get("evidence") or []
    if not question:
        return ToolResult("synthesize", False, error="question is required")
    if not evidence or not isinstance(evidence, list):
        return ToolResult("synthesize", False, error="evidence (non-empty list) is required")

    try:
        from app.llm import chat_completion

        # Build numbered evidence block
        evidence_block = "\n\n".join(
            f"[{i+1}] {str(ev).strip()}" for i, ev in enumerate(evidence)
        )

        system = (
            "你是一个技术研究分析综合器。根据给定的研究问题和证据片段，"
            "生成一段连贯、客观、带引用标注的分析回答。\n"
            "规则：\n"
            "1. 每个事实陈述必须标注引用 [1][2] 等，对应证据序号\n"
            "2. 只使用证据中的信息，禁止编造\n"
            "3. 证据不足时明确说明\n"
            "4. 客观中立，适合技术人员阅读"
        )
        user = (
            f"研究问题：{question}\n\n"
            f"证据片段：\n{evidence_block}\n\n"
            "请生成带引用的分析回答："
        )

        answer = chat_completion(system, user)
        if not answer or len(answer) < 10:
            return ToolResult("synthesize", False, error="LLM returned empty answer")

        return ToolResult(
            "synthesize",
            success=True,
            data={
                "question": question,
                "answer": answer,
                "evidence_count": len(evidence),
            },
        )
    except Exception as e:
        logger.exception("synthesize failed for question='%s'", question[:80])
        return ToolResult("synthesize", False, error=str(e))


# ── Dispatch table ────────────────────────────────────────────────

RESEARCH_TOOL_DISPATCH: dict[str, Any] = {
    "local_search": _execute_local_search,
    "web_search": _execute_web_search,
    "fetch_page": _execute_fetch_page,
    "synthesize": _execute_synthesize,
}


def execute_research_tool(tool_name: str, args: dict[str, Any]) -> ToolResult:
    """Dispatch a research tool call by name."""
    handler = RESEARCH_TOOL_DISPATCH.get(tool_name)
    if handler is None:
        return ToolResult(tool_name, False, error=f"Unknown research tool: {tool_name}")
    try:
        return handler(args)
    except Exception as e:
        logger.exception("Research tool %s failed", tool_name)
        return ToolResult(tool_name, False, error=str(e))
