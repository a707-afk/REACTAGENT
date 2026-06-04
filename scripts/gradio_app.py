#!/usr/bin/env python3
"""Gradio 联调 FastAPI（请先在本机启动 uvicorn）。

环境变量：
  RAG_API_BASE  默认 http://127.0.0.1:8000
  GRADIO_SERVER_PORT  默认 7860

项目根目录执行::

    python scripts/gradio_app.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API = os.environ.get("RAG_API_BASE", "http://127.0.0.1:8000").rstrip("/")
GRADIO_PORT = int(os.environ.get("GRADIO_SERVER_PORT", "7860"))


def _rewrite_body_param(mode: str):
    if mode == "on":
        return True
    if mode == "off":
        return False
    return None


def _post(path: str, body: dict) -> tuple[str, str]:
    try:
        import httpx
    except ImportError as e:
        return f"请安装 httpx: pip install httpx\n{e}", "{}"
    try:
        r = httpx.post(
            f"{API}{path}",
            json=body,
            timeout=httpx.Timeout(600.0, connect=30.0),
        )
        text = r.text
        if r.status_code >= 400:
            return f"HTTP {r.status_code}\n{text[:4000]}", text
        data = r.json()
        pretty = json.dumps(data, ensure_ascii=False, indent=2)
        rq = data.get("retrieval_query")
        note = ""
        if rq:
            note = f"**实际用于检索的查询**（改写后）：\n\n{rq}\n\n---\n\n"
        elif path == "/retrieve":
            note = "（`retrieval_query` 为空表示与原问题相同）\n\n---\n\n"
        return note + "完整响应见下方 JSON。", pretty
    except Exception as e:
        return f"请求失败: {e!r}\n\n请确认已 `cd rag-kb-project` 并启动 API。", "{}"


def ui_retrieve(question: str, top_k: int, rewrite_mode: str) -> tuple[str, str]:
    q = (question or "").strip()
    if not q:
        return "请输入问题", "{}"
    body = {
        "query": q,
        "top_k": max(1, min(30, int(top_k))),
        "use_query_rewrite": _rewrite_body_param(rewrite_mode),
    }
    return _post("/retrieve", body)


def ui_chat(question: str, top_k: int, rewrite_mode: str) -> tuple[str, str]:
    q = (question or "").strip()
    if not q:
        return "请输入问题", "{}"
    body = {
        "query": q,
        "top_k": max(1, min(30, int(top_k))),
        "use_query_rewrite": _rewrite_body_param(rewrite_mode),
    }
    md, raw = _post("/chat", body)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return md, raw
    ans = data.get("answer")
    if data.get("refused"):
        return md + "\n\n**系统拒答**（见 JSON 中 `error_code`）", raw
    if isinstance(ans, str) and ans:
        cite_md = "\n\n**引用条目**（`citations`）\n"
        for c in (data.get("citations") or [])[:12]:
            fn = c.get("file_name") or ""
            cite_md += f"- [{c.get('index')}] {fn} — {c.get('heading') or ''}\n"
        return f"{md}\n\n### 回答正文\n\n{ans}{cite_md}", raw
    return md, raw


def main() -> None:
    import gradio as gr

    head = f"""
### 知识库 RAG（Gradio）

后端：**{API}**（须已启动 `uvicorn app.main:app`）。

引用由 `/chat` 返回的 `citations` 与正文中的 [1]、[2] 对应；`/retrieve` 仅返回 chunk 列表。
"""
    with gr.Blocks(title="RAG KB") as demo:
        gr.Markdown(head)
        q = gr.Textbox(label="问题", lines=3, placeholder="输入要写进检索/对话的用户问题…")
        k = gr.Slider(1, 15, value=5, step=1, label="Top-K")
        rw = gr.Radio(
            choices=[
                ("跟随服务配置（QUERY_REWRITE_MODE / .env）", "default"),
                ("强制开启检索改写", "on"),
                ("强制关闭检索改写", "off"),
            ],
            value="default",
            label="Query rewrite",
        )
        with gr.Row():
            b1 = gr.Button("仅检索", variant="secondary")
            b2 = gr.Button("问答（智谱）", variant="primary")
        out_md = gr.Markdown(label="摘要")
        out_json = gr.Code(label="JSON", language="json")

        b1.click(fn=ui_retrieve, inputs=[q, k, rw], outputs=[out_md, out_json])
        b2.click(fn=ui_chat, inputs=[q, k, rw], outputs=[out_md, out_json])

    demo.launch(server_name="127.0.0.1", server_port=GRADIO_PORT)


if __name__ == "__main__":
    main()
