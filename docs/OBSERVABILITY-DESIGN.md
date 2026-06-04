# 可观测性设计（阶段 F + J）

> 更新：2026-06-04。Trace 设计 + **OTel/Langfuse SDK 可选切片** + **Prometheus 风格指标（阶段 J）**。

---

## 设计原则

1. **一条请求一个 `trace_id`**：由 `X-Trace-ID` 中间件写入 `request.state`，下游透传。
2. **事件粒度 = 可排障的最小单元**：每个阶段一条 `event=...` JSON，避免把整段 Prompt 写入日志。
3. **Eval 可复现**：Router 离线评测 CSV 已含 `domain_weights`、`raw_confidence`、`routing_trace.confidence_branch`（`scripts/run_eval_router.py`）。
4. **策略与 Agent 审计字段对齐**：便于从 `policy_eval` 跳到 `agent_ticket` 同一 `trace_id`。

---

## Trace 粒度一览

| 阶段 | 触发点 | 建议 `event` | 关键字段 |
|------|--------|--------------|----------|
| **request** | 任意 HTTP 入口 | （中间件） | `trace_id`、path、method |
| **router** | `route_domains` / 检索管线 | 内嵌 `router_trace` | `allowed_domains`、`primary_domain`、`confidence`、`method`、`domain_weights`、`raw_confidence`、`routing_trace` |
| **rewrite** | `query_rewrite` | `query_rewrite` | `original_query`、`retrieval_query`、`mode` |
| **retrieve** | `retrieve_scored_nodes` | `retrieve` | `hits`、`retrieval_query`、`primary_domain` |
| **rerank** | `rerank_nodes` | `rerank` | `method`、top scores（摘要） |
| **guard** | `evaluate_similarity_gate` | `gate` | `passed`、`error_code`、`best_score` |
| **LLM** | `chat_completion` / draft | `llm_call` | `model`、latency、token 估算（可选） |
| **citation** | `/chat` 生成后 | `citation_verify` | `citation_overlap_ratio` |
| **access control** | Pre-filter | `access_prefilter` | `tenant_id`、`roles`（脱敏）、filtered count |
| **agent_ticket** | `POST /agent/ticket` | `agent_ticket` | 见下节 |

在线 `/retrieve`、`/chat` 已在响应中带 `router_trace`；Agent 图在 `audit_trace` 中逐步追加 `{step, ...detail}`。

---

## 已实现日志

### 0. SDK 切片 — `app/telemetry.py`（2026-06-03）

| 组件 | 说明 |
|------|------|
| `setup_telemetry(settings)` | `app/main.py` lifespan 启动时调用 |
| `trace_span(name, trace_id, **attrs)` | 上下文管理器；用于 `retrieve_scored_nodes`、`evaluate_policy` |
| OTel | `OTEL_ENABLED=true` + 可选 `OTEL_EXPORTER_OTLP_ENDPOINT` |
| Langfuse | `LANGFUSE_ENABLED=true` + public/secret key |
| 依赖 | `requirements-observability.txt`（未安装则 log 一次并 no-op） |

### 1. 检索链路 — `app/observability.py`（JSON 行，无外部后端）

`log_structured_event()` 由以下位置调用（**与 OTel 并存**）：

| `event` | 触发 | 字段 |
|---------|------|------|
| `retrieve` | `retrieve_scored_nodes` 每次返回前 | `hits`、`retrieval_query`、`primary_domain`、`trace_id` |
| `gate` | `evaluate_similarity_gate` | `passed`、`error_code`、`best_score`、`trace_id` |
| `query_rewrite` | `resolve_retrieval_query` 发生改写时 | `original_query`、`retrieval_query`、`mode`、`trace_id` |

HTTP `/retrieve`、`/chat` 与 Agent `node_retrieve` / `node_evidence_gate` 透传 `trace_id`（中间件 `X-Trace-ID`）。

### 1. 策略审计 — `app/policy/audit_log.py`

`log_policy_event()` 输出 **logger `app.policy.audit`**，一行 JSON：

| 字段 | 说明 |
|------|------|
| `event` | 固定 `policy_eval` |
| `trace_id` | 请求追踪 ID |
| `endpoint` | 如 `agent_ticket`、`/chat` |
| `final_action` | `PolicyAction` 字符串（intercept / warn / allow_log 等） |
| `should_skip_rag` | 是否短路 RAG |
| `policy_risk_level` | low / medium / high |
| `requires_human_review` | 是否需人工 |
| `matched_rules` / `winning_rule_id` | 规则层命中 |
| `embedding_max_sim` / `embedding_hit` | 向量护栏 |
| `llm_class` / `llm_confidence` / `llm_hit` | LLM 分类护栏 |
| `policy_warnings` | warn 路径警告列表 |
| `user_context` | **脱敏摘要**：`tenant_id`、`roles`、`department`、`security_clearance`（不含 `user_id`） |

Agent 的 `node_policy` 调用 `evaluate_policy(..., endpoint="agent_ticket")`，策略命中时同样写此审计行。

### 2. 工单 Agent — `app/routes_agent.py`

成功路径 **logger 默认** 一行 JSON：

| 字段 | 说明 |
|------|------|
| `event` | `agent_ticket` |
| `trace_id` | 与中间件一致 |
| `ticket_id` | 工单号 |
| `final_action` | `policy_intercept` / `no_evidence` / `gate_fail` / `draft_ready` / `await_human_review` |
| `human_review_required` | 是否需二线 |

图内 **`audit_trace`**（API 响应字段，非 stdout）：按节点追加：

| `step` | 典型 detail |
|--------|-------------|
| `policy` | `skip_rag`、`action` |
| `retrieve` | `hits`、`primary_domain` 或 `skipped` |
| `gate` | `passed`、`code`、`best` |
| `draft` | `chars` 或 `skipped` |
| `finalize` | `action`、`human` |

---

## Router 离线评测扩展（已实现）

`scripts/run_eval_router.py` 的 `*_predictions.csv` 列：

- `domain_weights` — `domain:weight` 管道分隔
- `raw_confidence` — 校准前分数
- `confidence_branch` — 来自 `routing_trace.confidence_branch`

用于排查 router bad case，无需重跑在线 API。

---

## 阶段 J — Prometheus 指标（2026-06-04）

实现见 `app/metrics.py`、`app/main.py`（`GET /metrics` + HTTP 延迟中间件）、`app/retrieval_pipeline.py`（检索耗时与 cache hit）。

| 指标名 | 类型 | 标签 | 说明 |
|--------|------|------|------|
| `rag_http_requests_total` | Counter | `method`, `endpoint`, `status` | 每个 HTTP 请求计数 |
| `rag_http_request_duration_seconds` | Histogram | `endpoint` | 请求墙钟延迟 |
| `rag_retrieve_duration_seconds` | Histogram | — | `retrieve_scored_nodes` 单次耗时（含缓存未命中全路径） |
| `rag_cache_hits_total` | Counter | `level` | `l1` / `l2` 检索缓存命中 |

- **依赖**：`requirements-observability.txt` 中的 `prometheus_client`；未安装时 stub 仍输出合法文本，便于本地 curl / CI。
- **与 JSON 日志关系**：stdout `event=retrieve` 等保留；指标用于聚合看板，日志用于单条排障。
- **缓存统计**：进程内 `cache_stats()`（`l1_entries` / `l2_entries`）未单独暴露为 metric，可按需在后续加 gauge。

抓取示例：`curl -s http://127.0.0.1:8000/metrics`。

---

## 后续接入建议

| 优先级 | 项 | 说明 |
|--------|-----|------|
| P1 | 结构化 handler | 将 `app.policy.audit` / root logger 接到 Loki / ELK |
| P2 | Grafana | 基于上表指标：P99 延迟、cache hit rate、QPS |
| P3 | Langfuse | 全链路 LLM + Agent 决策树（SDK 已可选，需开启并设采样率） |
| P4 | 业务 counter | pass_rate、gate_fail 率、`final_action` 分布 |

---

## 与评估脚本关系

| 脚本 | 可观测性产出 |
|------|----------------|
| `run_eval_router.py` | Router CSV + summary JSON |
| `run_eval_agent_ticket.py` | Agent 路径 pass_rate、`audit_steps` 校验 |
| `run_eval_behavior_guard.py` | `policy_eval` 行为 recall |

检索/gate/rewrite **stdout JSON 已落地**；**`/metrics` + 检索/cache 延迟 histogram 已落地（阶段 J）**；**Grafana 与业务 counter** 见 `docs/NEXT-MILESTONE.md`、`docs/PHASE-J-PROGRESS.md`。
