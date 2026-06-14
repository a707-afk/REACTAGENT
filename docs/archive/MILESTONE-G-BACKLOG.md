# Milestone G — Backlog 交付摘要

> 2026-06-03。本迭代完成权限评测 bad case 检索意图加权、Qdrant 生产默认 auto、OPA / 多 Agent / 可观测性 SDK 骨架。

---

## 1. 检索意图加权（AC02 / AC07 / AC28）

| 项 | 说明 |
|----|------|
| 模块 | `app/retrieval_intent_boost.py` |
| 接入点 | `retrieve_scored_nodes`：混合 merge + access post-filter **之后**，domain soft boost **之前** |
| 开关 | `RETRIEVAL_INTENT_BOOST_ENABLED=true`（默认） |
| 调参 | `RETRIEVAL_INTENT_BOOST_DELTA=0.08`、`RETRIEVAL_INTENT_PENALTY=0.05`、`RETRIEVAL_INTENT_BOOST_MAX_CHUNKS=8` |

AC07 规则：`prompt`+`inject` 或 `注入`+`应对`；排除问法含「案例」「工单叙事」。

---

## 2. Qdrant 生产默认

| 项 | 说明 |
|----|------|
| 默认 | `VECTOR_BACKEND=auto` |
| 解析 | `app/vector_backend.py` → `resolve_vector_backend()` |
| 逻辑 | 显式 chroma/qdrant 优先；auto 时若 `QDRANT_PATH` 或 `QDRANT_URL` 上 collection 有点则 qdrant，否则 chroma |
| 默认路径 | 未设 `QDRANT_PATH` 时使用 `data/qdrant_local` |

详见 `docs/QDRANT-NEXT.md`。

---

## 3. OPA（可选，fail-open）

| 环境变量 | 默认 | 说明 |
|----------|------|------|
| `OPA_ENABLED` | false | 开启外部策略 |
| `OPA_URL` | http://localhost:8181 | OPA 服务 |
| `OPA_POLICY_PATH` | rag/allow | data API 路径 |
| `OPA_FAIL_OPEN` | true | OPA 不可用时放行 |

策略示例：`data/opa/rag_allow.rego`。文档：`docs/OPA.md`。

---

## 4. 多 Agent 骨架

| 环境变量 | 默认 | 说明 |
|----------|------|------|
| `AGENT_MULTI_AGENT_ENABLED` | false | 启用 supervisor 图 |
| `AGENT_GRAPH_MODE` | linear | 设为 `multi` 也可启用 |

`app/agent_graph/multi_graph.py`：supervisor → 线性 policy/retrieve/gate/draft **或** escalation 桩 → finalize。

---

## 5. 可观测性 SDK（未配置时 no-op）

| 环境变量 | 说明 |
|----------|------|
| `OTEL_ENABLED` | OpenTelemetry |
| `OTEL_SERVICE_NAME` | 服务名 |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP HTTP 端点 |
| `LANGFUSE_ENABLED` | Langfuse |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | Langfuse 凭据 |

`app/telemetry.py`：`setup_telemetry` 在 `app/main.py` lifespan；`trace_span` 用于 `retrieve_scored_nodes`、`evaluate_policy`。

可选依赖：`pip install -r requirements-observability.txt`。

---

## 验证命令

```powershell
cd rag-kb-project
$env:INFERENCE_DEVICE="auto"
D:\conda\envs\rags\python.exe -c "from app.inference_device import resolve_inference_device; d=resolve_inference_device(); print(d); assert str(d).startswith('cuda')"

$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
$env:VECTOR_BACKEND="auto"

D:\conda\envs\rags\python.exe -m pytest tests/test_retrieval_intent_boost.py tests/test_agent_graph_compile.py -q
D:\conda\envs\rags\python.exe scripts/run_eval_access_control.py
```

---

## 文件索引

| 路径 | 用途 |
|------|------|
| `app/retrieval_intent_boost.py` | 意图加权 |
| `app/vector_backend.py` | auto 后端解析 |
| `app/opa/` | OPA 客户端 |
| `app/agent_graph/multi_graph.py` | 多 Agent 图 |
| `app/telemetry.py` | OTel / Langfuse |
