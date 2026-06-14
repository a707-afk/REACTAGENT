# 阶段 K：交付层 — 进度说明

> 更新：2026-06-04。SSE 流式 API + React 前端 + Docker 多阶段构建。

## 架构

```
Browser (React /app/)
    │  POST /retrieve | /chat/stream | /agent/ticket/stream
    ▼
FastAPI (app/main.py)
    ├── routes_rag.py      → 检索 + 问答（JSON + SSE）
    ├── routes_agent.py    → 工单 Agent（JSON + SSE）
    └── static/app/        ← frontend npm run build
```

### SSE 协议

**Content-Type**：`text/event-stream`  
**帧格式**（每条事件）：

```
event: <type>
data: <JSON>

```

#### POST `/chat/stream`

| event | data 字段 | 说明 |
|-------|-----------|------|
| `token` | `{ "text": "..." }` | 答案草稿增量（无真 LLM 流式时分块模拟） |
| `done` | 完整 `ChatResponse` JSON | 与 `POST /chat` 响应字段一致 |
| `error` | `{ "message", "status_code?" }` | 异常 |

#### POST `/agent/ticket/stream`

| event | data 字段 | 说明 |
|-------|-----------|------|
| `step` | `{ "step": "policy\|retrieve\|gate\|grader\|rewrite_query\|draft\|hallucination\|finalize", ... }` | `audit_trace` 单步 |
| `token` | `{ "text": "..." }` | `draft_reply` 增量（若有） |
| `done` | 完整 `TicketAgentResponse` JSON | 终态摘要 |
| `error` | `{ "message" }` | 异常 |

**向后兼容**：原 `POST /chat`、`POST /agent/ticket` 不变。

## 已实现文件

| 模块 | 路径 |
|------|------|
| SSE 工具 | `app/sse.py` |
| 问答流式 | `app/routes_rag.py` → `/chat/stream` |
| Agent 流式 | `app/routes_agent.py`、`app/agent_graph/graph.py` → `iter_ticket_agent_sse` |
| React 前端 | `frontend/`（Vite + TS） |
| 静态挂载 | `app/main.py` → `/app/`（旧版 `/static/index.html` 保留） |
| Docker | `Dockerfile`、`docker-compose.yml`、`.dockerignore`、`scripts/run_docker.ps1` |
| 测试 | `tests/test_sse_routes.py` |

## 本地启动

### 1. API

```powershell
cd c:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project
$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
& "D:\conda\envs\rags\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. 前端开发（proxy → :8000）

```powershell
cd frontend
npm install
npm run dev
# 浏览器 http://127.0.0.1:5173
```

### 3. 生产静态（由 FastAPI 托管）

```powershell
cd frontend
npm install
npm run build
# 产物 → static/app/；访问 http://127.0.0.1:8000/app/
```

### 4. SSE 自检

```powershell
curl -N -X POST http://127.0.0.1:8000/chat/stream `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"测试\",\"top_k\":3}"

curl -N -X POST http://127.0.0.1:8000/agent/ticket/stream `
  -H "Content-Type: application/json" `
  -d "{\"ticket_id\":\"T-1\",\"user_query\":\"退款流程\",\"top_k\":3}"
```

## Docker 启动

```powershell
.\scripts\run_docker.ps1
# 或
docker compose up -d --build
```

- **API**：http://127.0.0.1:8000/health  
- **UI**：http://127.0.0.1:8000/app/  
- **Qdrant**：http://127.0.0.1:6333/  

环境变量示例见 `docker-compose.yml`（`DOCS_DIR`、`CHROMA_COLLECTION_NAME`、`VECTOR_BACKEND` 等）。Redis 服务块已注释，待 J+ 接入。

## 验证

```powershell
D:\conda\envs\rags\python.exe -m pytest tests/ -q
cd frontend && npm run build
```

## 已知限制

1. **token 事件为模拟分块**，非智谱原生 stream；接真流式只需改 `chat_completion` 层。
2. **Docker 镜像未内置 GPU / 大 embedding 权重**，生产需挂载模型目录或换推理服务。
3. **索引数据**：首次运行需在本机构建 Chroma 或挂载 `chroma_data` volume。
4. **Agent 流式**与 JSON 路径共用同一 LangGraph，长耗时请求仍会占 worker 直至图结束。

## 面试讲法（30 秒）

> 交付层用 **SSE** 把问答草稿和 Agent 审计步骤推到前端，协议上 `token/step/done/error` 四类事件，REST 老接口不动。前端是 **Vite React** 三 Tab 演示检索、流式问答、流式工单；build 进 `static/app` 由 FastAPI 挂 `/app`。Docker 多阶段先 build 前端再跑 Python API，compose 里 api 依赖 qdrant，Chroma 持久化用 volume。
