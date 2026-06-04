"""HTTP 冒烟：健康检查 + POST /agent/ticket（不加载 pytest/Chroma 时可跳过向量路径）。

用法（需 API 已启动）::

    python scripts/smoke_agent_ticket.py

环境变量::

    RAG_API_BASE=http://127.0.0.1:8000
    AGENT_SMOKE_SKIP=1          # 仅打 /health，不测 Agent
    AGENT_SMOKE_WITH_CONTEXT=0  # 默认 0：不传 user_context，避免 Pre-filter 依赖索引对齐

退出码：0=通过，1=HTTP/断言失败，2=服务不可达。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.getenv("RAG_API_BASE", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = float(os.getenv("AGENT_SMOKE_TIMEOUT", "120"))


def _get(path: str) -> tuple[int, str]:
    req = urllib.request.Request(f"{BASE}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接 {BASE}{path}: {e}") from e


def _post(path: str, body: dict) -> tuple[int, str]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接 {BASE}{path}: {e}") from e


def main() -> int:
    skip_agent = os.getenv("AGENT_SMOKE_SKIP", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    try:
        status, body = _get("/health")
    except RuntimeError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        print(
            "请先启动: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
            file=sys.stderr,
        )
        return 2

    if status != 200:
        print(f"FAIL: /health HTTP {status}\n{body}", file=sys.stderr)
        return 1
    print(f"OK /health HTTP {status}")

    if skip_agent:
        print("SKIP /agent/ticket (AGENT_SMOKE_SKIP=1)")
        return 0

    payload: dict = {
        "ticket_id": "T-smoke-001",
        "user_query": "客户要退款怎么办",
        "top_k": 3,
    }
    if os.getenv("AGENT_SMOKE_WITH_CONTEXT", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        payload["user_context"] = {
            "tenant_id": "corp-default",
            "roles": ["support_agent"],
        }

    status, raw = _post("/agent/ticket", payload)
    if status == 503:
        print(
            "SKIP /agent/ticket: 向量索引未就绪 (HTTP 503)。"
            " 请先 reindex 后重试，或设 AGENT_SMOKE_SKIP=1。",
            file=sys.stderr,
        )
        print(raw[:500], file=sys.stderr)
        return 0
    if status != 200:
        print(f"FAIL: /agent/ticket HTTP {status}\n{raw}", file=sys.stderr)
        return 1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"FAIL: 响应非 JSON\n{raw}", file=sys.stderr)
        return 1

    fa = data.get("final_action")
    steps = [t.get("step") for t in (data.get("audit_trace") or [])]
    if not fa:
        print(f"FAIL: 缺少 final_action\n{raw}", file=sys.stderr)
        return 1
    if not steps:
        print(f"FAIL: audit_trace 为空\n{raw}", file=sys.stderr)
        return 1

    print(f"OK /agent/ticket final_action={fa!r} audit_steps={steps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
