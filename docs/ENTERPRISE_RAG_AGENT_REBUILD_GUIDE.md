# 企业级 RAG+Agent 项目严苛审计与重建执行手册

> 审计日期：2026-06-11  
> 审计对象：本地仓库 `E:\经项目\rag-kb-project`，分支 `feature/ecom-agent`  
> 参考材料：本地代码、`README.md`、`docs/`、`.github/workflows/`、桌面工作日志 `C:\Users\Lenovo\Desktop\EcomAgent-工作日志-全流程.md`  
> 目标：把当前项目从“高级 Demo”升级为可解释、可运行、可评测、可部署、可扩展的企业级 RAG+Agent 项目。

---

## 0. 结论

当前项目不能按“企业级 RAG+Agent”对外宣称。它更接近一个把 FastAPI、Qdrant、LangGraph、BM25、策略拦截、SSE、React 等技术名词串起来的高级演示项目。

它有一些可保留基础：基础 RAG 管线、Qdrant/BM25 混合召回、部分 citation/grounding、FastAPI 路由、LangGraph 图壳、Mock 电商售后工具、少量评测脚本、基础 metrics。但企业级关键能力大量缺失或只是文档里写了：

- 后端没有真正落库，`/api/tickets` 仍是内存字典。
- 没有 Redis、队列、异步摄入任务、文件上传、PDF/图片/OCR/多模态解析。
- Agent 主要是关键词路由到固定流程，缺少严谨的 observe-plan-act-verify 状态机、工具权限、工具选择、恢复策略、HITL 审批和可审计执行轨迹。
- Worker 节点绕过检索、证据门控和 grader，并把自己生成的回复塞进 `retrieved_chunks`，这会让 grounding 变成自证。
- 测试体系已经与代码不同步，关键测试失败，CI 还显式忽略 Agent 测试。
- Docker/配置/文档存在过时字段和不一致，例如仍有 `ZHIPUAI_API_KEY`。
- 压测只是 5 并发、16 请求的小脚本，不能代表生产性能。

严苛评分：**28/100**。

| 维度 | 当前状态 | 分数 |
|---|---:|---:|
| RAG 检索基础 | 有混合召回、rerank、gate，但数据规模和评测不稳定 | 45 |
| Agent 能力 | 固定路由和脚本化工具调用，缺少真正 harness | 20 |
| 企业后端 | 模型有，接口未落库，迁移为空，依赖不完整 | 15 |
| 文件/多模态摄入 | 基本没有 | 5 |
| 安全与权限 | 有规则拦截雏形，缺少生产鉴权、ABAC 全链路、审计闭环 | 35 |
| 降级与容灾 | 有少量 LLM fallback，缺少系统级故障策略 | 25 |
| 评测与 CI | 有脚本，但 mock 多、过期多、CI 不硬 | 20 |
| 部署与运维 | 有 Docker 壳，缺 Redis/worker/migration/health gating | 25 |

---

## 1. 关键证据

这些不是主观感受，而是代码层面的硬缺口。

### 1.1 工单 API 没有真实数据库

证据：

- `app/api/tickets.py:19` 写着 `In-memory store for demo`。
- `app/api/tickets.py:20` 使用 `_tickets: dict[str, dict[str, Any]] = {}`。
- `app/api/tickets.py:27` 虽然注入了 `db=Depends(get_db_session)`，但后续没有用 DB CRUD。
- `alembic/versions/` 为空，没有任何迁移文件。

判定：数据库模型只是摆设，接口层没有企业级持久化、事务、并发控制、审计、分页、查询过滤。

### 1.2 Agent Worker 绕过 RAG 质量链路

证据：

- `app/agent_graph/graph.py:92` 注释明确写着 `All worker nodes go directly to draft (skip retrieve/gate/grader pipeline)`。
- `app/agent_graph/nodes.py:594`、`646`、`662`、`702`、`739` 将 Worker 生成的回复或摘要写入 `retrieved_chunks`。
- `app/agent_graph/nodes.py:285` 的 `node_grader` 是 gate 通过 + chunks 数量判断。
- `app/agent_graph/nodes.py:463` 写着 `Always go to draft - simplified for demo`。
- `app/agent_graph/nodes.py:469` 写着 `draft retry loop removed for stability`。

判定：这不是严谨 Agent，而是 LangGraph 包了一层固定流程。所谓 grounding 对 Worker 路径没有可信意义，因为 evidence 是 Worker 自己构造的。

### 1.3 测试已经失效

我实际运行：

```powershell
.\.venv\Scripts\python.exe -m compileall -q app
.\.venv\Scripts\python.exe -m pytest -q tests\test_agent_graph_compile.py tests\test_api_guard.py tests\test_db_async.py
```

结果：

- 编译通过。
- Pytest：`15 passed, 2 failed`。

失败原因：

- `tests/test_agent_graph_compile.py:39` 仍按同步函数调用 `run_ticket_agent()`，但现在它是 async coroutine。
- `tests/test_agent_graph_compile.py:86` 和 `scripts/run_eval_agent_ticket.py:137` 仍 patch `app.llm_zhipu.chat_completion`，但代码已改为 `app.llm`。

判定：不能继续用“测试通过”描述当前项目。评测脚本与代码已经脱节。

### 1.4 CI 不是质量门

证据：

- `.github/workflows/test.yml:5` 和 `:7` 只对 `main` 触发，不覆盖当前 `feature/ecom-agent` 分支。
- `.github/workflows/test.yml:47` 使用 `--timeout=60`，但 workflow 没安装 `pytest-timeout`。
- `.github/workflows/test.yml:48` 显式忽略 `tests/test_agent_graph_compile.py`。
- `requirements.txt` 缺少 SQLAlchemy、Alembic、asyncpg、aiosqlite、pytest-timeout、locust、Redis 客户端等后端/测试依赖。

判定：CI 不能证明项目可用，反而掩盖了核心测试失败。

### 1.5 Docker/配置过期

证据：

- `docker-compose.yml:22` 仍有 `ZHIPUAI_API_KEY`。
- `docker-compose.yml:21` 给 app 设置 `QDRANT_PATH=/data/qdrant_local`，这会让 app 用嵌入式 Qdrant 路径，而不是连接 `qdrant` 服务。
- `app/config.py` 默认 `app_name` 仍是 `cs-agent-backend`。

判定：部署配置没有经过真实 compose 验证，不能宣称生产部署就绪。

### 1.6 无用户上传与多模态

搜索 `UploadFile`、`python-multipart`、PDF parser、OCR、docx parser 后，未发现应用层上传摄入链路。现有脚本主要处理 Markdown/TXT/JSONL。文档也承认 PDF/Word 需要先人工转 Markdown。

判定：用户上传 PDF、Word、图片、扫描件、多模态资料目前不支持。

### 1.7 Redis 和队列只是文档愿景

证据：

- `app/cache.py` 是进程内 LRU + 可选语义缓存。
- `docs/DECISION-LOG.md` 明确写了“进程内缓存不跨 worker/多机；未做 Redis”。
- `docker-compose.yml` 没有 Redis。
- 没有 Celery/RQ/Arq/Dramatiq worker。

判定：没有企业级异步任务、分布式缓存、限流共享状态、任务重试和队列可观测性。

---

## 2. 当前代码中可保留的部分

不要全部推倒重来。以下可以作为基础，但要重构和补验收：

- `app/retrieval_pipeline.py`：混合召回、RRF/max fusion、ACL prefilter 的结构可以保留。
- `app/qdrant_index_store.py` 与 `app/vector_index.py`：Qdrant 封装可以保留，但生产只允许 server mode。
- `app/chunking.py`：Markdown heading overlap 思路可保留，但要扩展到 PDF/DOCX/HTML/图片 OCR。
- `app/citation_verify.py`：可以作为轻量 grounding baseline，但不能作为唯一 hallucination judge。
- `app/policy/`：规则型 guardrail 可以保留，但要 fail-closed、落审计、支持规则版本和管理。
- `app/metrics.py`：Prometheus 文本端点可以保留，但要接真实指标和 dashboard。
- `frontend/`：可以作为演示 UI，但不能作为企业后台。

---

## 3. 企业级目标架构

### 3.1 目标系统边界

项目应定义为：

> 企业知识库 RAG + 可审计 Agent 执行平台，以电商售后为业务场景。支持用户上传资料、自动解析入库、权限过滤检索、多轮对话、Agent 工具执行、人工审批、降级策略、评测闭环和容器化部署。

不要只做“客服聊天”。企业级项目必须体现：

- 数据从上传到索引的完整生命周期。
- 查询从权限到检索再到回答的完整链路。
- Agent 从任务识别到工具执行再到人工审批的完整状态机。
- 每一步可观测、可回放、可评测、可回滚。

### 3.2 目标服务拓扑

本地 Docker Compose 至少包括：

| 服务 | 用途 | 必须状态 |
|---|---|---|
| `api` | FastAPI 网关，REST/SSE | 必须 |
| `worker` | 摄入、评测、长任务、异步 Agent job | 必须 |
| `postgres` | 业务数据、审计、任务、配置 | 必须 |
| `redis` | 队列、限流、分布式缓存、任务锁 | 必须 |
| `qdrant` | 向量库 server mode | 必须 |
| `frontend` | 简单管理/演示界面 | 可选但建议 |
| `opa` | 外部策略引擎 | 可选，若启用必须 fail-closed |
| `prometheus/grafana` | 指标与看板 | 可选但建议 |

生产禁止把嵌入式 Qdrant 当服务共享使用。

### 3.3 目标模块划分

```text
app/
  api/
    auth.py
    documents.py
    ingestion_jobs.py
    chat.py
    agent_runs.py
    tickets.py
    evals.py
  core/
    config.py
    security.py
    errors.py
    idempotency.py
  db/
    models/
    repositories/
    migrations/
  ingestion/
    validators.py
    parsers/
    chunkers.py
    pipeline.py
    jobs.py
  rag/
    retriever.py
    reranker.py
    query_analyzer.py
    grounding.py
    citations.py
  agent/
    state.py
    graph.py
    planner.py
    tool_registry.py
    permission_gate.py
    memory.py
    checkpointer.py
    evaluator.py
  tools/
    order.py
    ticket.py
    refund.py
    logistics.py
    knowledge.py
  policy/
    engine.py
    rules.py
    audit.py
  observability/
    logs.py
    metrics.py
    tracing.py
  eval/
    datasets.py
    rag_eval.py
    agent_eval.py
    regression.py
```

---

## 4. 数据库与持久化要求

### 4.1 必须落库的实体

PostgreSQL 至少建这些表，并提供 Alembic migration：

| 表 | 说明 |
|---|---|
| `tenants` | 租户 |
| `users` | 用户 |
| `api_keys` | API key hash、权限、过期时间 |
| `documents` | 上传文件元数据、版本、状态、hash、租户、ACL |
| `document_blobs` 或对象存储索引 | 文件存储位置、mime、size |
| `document_pages` | PDF/Word 页或段落级解析结果 |
| `chunks` | chunk 文本、metadata、embedding 状态、qdrant point id |
| `ingestion_jobs` | 摄入任务状态、进度、错误、重试次数 |
| `chat_sessions` | 会话 |
| `messages` | 消息、引用、grounding、token/cost |
| `agent_runs` | Agent 执行实例 |
| `agent_steps` | plan/action/observation summary、工具调用、耗时 |
| `tool_calls` | 工具名、参数 hash、结果、幂等键、权限结果 |
| `tickets` | 售后工单 |
| `ticket_events` | 状态变更审计 |
| `policy_rules` | 策略规则版本 |
| `policy_audit_logs` | 拦截、放行、人工复核记录 |
| `eval_runs` | 评测运行记录 |
| `eval_cases` | 金标样本与结果 |

### 4.2 数据库验收标准

必须满足：

- `alembic upgrade head` 在空库成功。
- `alembic downgrade -1` 至少对最近迁移可用。
- API 创建工单后重启服务，数据仍存在。
- 所有列表接口支持分页、租户过滤、状态过滤。
- 所有写接口使用事务。
- 所有跨租户查询有测试证明 0 泄露。
- 禁止生产路径使用内存字典保存业务数据。

命令：

```powershell
docker compose up -d postgres redis qdrant
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest -q tests\db tests\api
```

---

## 5. 文件上传、摄入与多模态

### 5.1 必须支持的输入

MVP 必须支持：

- `.pdf`
- `.docx`
- `.txt`
- `.md`
- `.csv`
- `.xlsx`
- `.png` / `.jpg`，至少 OCR

PDF 必须区分：

- 可复制文本 PDF：走文本抽取。
- 扫描 PDF：走 OCR。
- 表格型 PDF：抽取表格为 Markdown table 或结构化 JSON。

### 5.2 上传 API

必须实现：

| 接口 | 说明 |
|---|---|
| `POST /api/documents/upload` | 上传文件，返回 `document_id` 和 `job_id` |
| `GET /api/documents/{id}` | 查看文件状态 |
| `GET /api/ingestion-jobs/{id}` | 查看摄入进度 |
| `POST /api/documents/{id}/reindex` | 重建索引 |
| `DELETE /api/documents/{id}` | 软删文档并删除向量 |
| `GET /api/documents` | 分页列表 |

### 5.3 摄入流水线

每个文件必须经历：

1. MIME 与扩展名校验。
2. 文件大小限制。
3. SHA256 hash 去重。
4. 病毒/危险内容预留接口，MVP 可 stub，但必须有状态。
5. 解析成 pages/sections。
6. 清洗文本。
7. chunk。
8. 写 DB。
9. 写 Qdrant。
10. 写 BM25。
11. 更新 job 进度。
12. 失败可重试，重试有上限。
13. 删除时 DB 与向量库一致。

### 5.4 多模态最低标准

不要宣称“多模态”除非满足：

- 上传图片或扫描 PDF 后能 OCR 出文本并进入检索。
- 能保留页码、图片坐标或块级位置。
- 回答引用能指向文件、页码、chunk。
- 对表格问题能从表格内容回答，而不是只读段落。
- 至少 20 个多模态金标问题通过评测。

验收指标：

| 指标 | 最低值 |
|---|---:|
| PDF 文本抽取成功率 | >= 95% |
| 扫描 PDF OCR 可用率 | >= 85% |
| 表格问答 Top5 召回 | >= 80% |
| 引用页码准确率 | >= 90% |

---

## 6. RAG 管线重建要求

### 6.1 检索链路

标准链路：

```text
用户问题
  -> Auth / Tenant / Policy pre-check
  -> Query analysis: language, intent, domain, required evidence type
  -> Query rewrite or expansion
  -> ACL prefilter
  -> Dense retrieval from Qdrant
  -> Sparse retrieval from BM25
  -> Hybrid fusion: RRF default
  -> Domain/source-type boosting
  -> Rerank
  -> Similarity/evidence gate
  -> Context packing
  -> Answer generation
  -> Grounding verification
  -> Citation validation
  -> Post-policy guard
  -> Response
```

### 6.2 检索必须保留 metadata

每个 chunk 必须有：

- `tenant_id`
- `document_id`
- `document_version`
- `source_uri`
- `file_name`
- `mime_type`
- `page_start`
- `page_end`
- `section_path`
- `chunk_id`
- `chunk_index`
- `source_type`
- `domain`
- `security_level`
- `allowed_roles`
- `created_at`
- `content_hash`

### 6.3 RAG 评测指标

必须建立 `data/eval/rag/*.jsonl`，每条包含：

```json
{
  "id": "RAG-001",
  "query": "...",
  "tenant_id": "t_demo",
  "roles": ["support_agent"],
  "gold_document_ids": ["doc_..."],
  "gold_chunk_ids": ["chunk_..."],
  "answer_facts": ["..."],
  "forbidden_document_ids": [],
  "category": "pdf_table|policy|faq|multi_turn|security"
}
```

最低验收：

| 指标 | P0 门槛 |
|---|---:|
| Recall@5 | >= 0.85 |
| MRR@10 | >= 0.70 |
| nDCG@10 | >= 0.75 |
| Citation precision | >= 0.90 |
| Unsupported sentence rate | <= 0.08 |
| Unauthorized chunk in TopK | 0 |
| No-evidence refusal accuracy | >= 0.90 |

---

## 7. Agent Harness 要求

当前项目最大问题是没有严谨 harness。企业级 Agent 不是几个 if/else worker，也不是“LangGraph 图能 compile”。

### 7.1 必须实现的 Agent 状态

`AgentRunState` 至少包含：

```python
class AgentRunState(TypedDict, total=False):
    run_id: str
    tenant_id: str
    user_id: str
    session_id: str
    objective: str
    user_query: str
    risk_level: str
    plan: list[dict]
    current_step_index: int
    tool_calls: list[dict]
    observations: list[dict]
    evidence: list[dict]
    memory_refs: list[dict]
    approvals: list[dict]
    errors: list[dict]
    final_answer: str
    final_action: str
    human_review_required: bool
    budget: dict
    audit_trace: list[dict]
```

注意：不要记录或暴露模型内部 chain-of-thought。审计里只记录可读的 plan、action、observation summary、decision reason summary。

### 7.2 标准 Agent 循环

```text
Start
  -> Policy pre-check
  -> Understand task
  -> Build plan
  -> For each step:
       -> Select tool or retrieval
       -> Permission gate
       -> Execute with timeout/retry/idempotency
       -> Validate observation
       -> Update plan if needed
       -> Stop if loop/budget/risk threshold reached
  -> Draft answer or action proposal
  -> Grounding and policy post-check
  -> Human approval if needed
  -> Finalize
```

### 7.3 Tool Registry

每个工具必须注册：

- name
- description
- JSON schema
- side effect level：`read_only` / `write_internal` / `external_side_effect`
- required scopes
- timeout
- retry policy
- idempotency key builder
- concurrency rule
- mock implementation
- real implementation
- eval fixtures

工具执行必须统一经过：

```text
ToolCall -> Schema validate -> Permission gate -> Idempotency check -> Execute -> Result validate -> Audit log
```

禁止在节点里直接 `execute_tool("xxx", ...)` 绕过权限。

### 7.4 Permission Gate

实现类似：

| 风险 | 行为 |
|---|---|
| 只读查询 | 可自动执行 |
| 写内部草稿 | 可自动执行但记录审计 |
| 创建工单 | 需要权限 scope |
| 退款/补偿/发券 | 必须 HITL 或 sandbox |
| 删除/导出/外发 | 默认拒绝或人工审批 |

验收：

- 高风险工具未经批准不会执行。
- 工具参数含越权 tenant_id 时拒绝。
- 所有拒绝写入 `policy_audit_logs`。
- prompt injection 不能让 Agent 绕过 permission gate。

### 7.5 记忆系统

分三层：

| 层 | 用途 | 存储 | 审批 |
|---|---|---|---|
| Session memory | 当前会话上下文 | Postgres/Redis | 自动 |
| User memory | 用户偏好、历史摘要 | Postgres + vector | 可自动但可删除 |
| Org/project memory | 企业规则、业务事实 | 文档库/配置 | 人工审核后进入 |

不能让 Agent 随便把未经审核的回答写成企业知识。

### 7.6 Multi-Agent 设计

推荐先实现 coordinator 模式，而不是 swarm。

角色：

| Agent | 责任 |
|---|---|
| Supervisor | 判断任务、风险、是否需要人工 |
| Retrieval Agent | 制定检索策略、召回证据 |
| Tool Agent | 执行业务工具 |
| Policy Agent | 权限和风险判断 |
| Answer Agent | 基于证据生成草稿 |
| Critic/Evaluator | 检查 grounding、遗漏、格式 |

关键原则：

- Coordinator 必须综合各 worker 结果，不允许“worker 说什么就直接输出”。
- worker 输入必须是完整 prompt，不依赖隐藏上下文。
- worker 输出必须结构化。
- 每个 worker 的工具权限最小化。
- 子 Agent 失败要可恢复，不得让整条链路无说明地失败。

### 7.7 Agent 评测指标

必须有 `data/eval/agent/*.jsonl`：

```json
{
  "id": "AG-001",
  "scenario": "refund_requires_policy_and_order",
  "turns": [
    {"role": "user", "content": "我要退这件T恤"},
    {"role": "assistant_expect": "ask_order_or_lookup"}
  ],
  "expected_tools": ["order_lookup", "policy_check"],
  "forbidden_tools": ["issue_refund"],
  "expected_final_action": "need_human_approval",
  "must_cite": true,
  "risk_level": "medium"
}
```

最低验收：

| 指标 | P0 门槛 |
|---|---:|
| Scenario success rate | >= 0.85 |
| Required tool call accuracy | >= 0.90 |
| Forbidden tool call rate | 0 |
| High-risk HITL recall | 1.00 |
| Loop termination | 1.00 |
| Invalid tool args rate | <= 0.03 |
| Recovery from tool timeout | >= 0.80 |
| Multi-turn state accuracy | >= 0.85 |

---

## 8. 降级与容灾策略

必须文档化并实现：

| 故障 | 行为 |
|---|---|
| LLM provider 超时 | 重试、切备用 key/provider、fallback 草稿、标记人工 |
| Embedding 模型不可用 | 暂停摄入，查询只走 BM25，返回降级标记 |
| Reranker OOM | 自动关闭 rerank，本次响应标记 degraded |
| Qdrant 不可用 | 查询 503 或 BM25-only 受控降级，不能静默空结果 |
| Redis 不可用 | 队列任务不可提交，限流 fail-closed 或配置化 |
| Postgres 不可用 | 写接口 503，不能落回内存伪成功 |
| Tool 超时 | 标记步骤失败，按策略重试或人工 |
| OCR 失败 | 文档状态 `parse_failed`，可人工重跑 |
| Prompt injection | policy intercept 或 HITL |

每个降级都要有：

- 结构化日志。
- metrics counter。
- 用户可理解的错误。
- eval case。

---

## 9. 安全与保护机制

### 9.1 认证和授权

最低要求：

- API 默认开启认证。
- 支持 API key hash 存储，不存明文。
- 支持 tenant isolation。
- 支持 RBAC + ABAC：role、department、security_level、document ACL。
- SSE、upload、download、agent tool 都走同一鉴权依赖。
- OpenAPI 文档在生产默认需要认证或关闭。

### 9.2 Prompt Injection 防护

必须覆盖：

- 忽略系统指令。
- 要求导出系统 prompt。
- 要求绕过权限。
- 文档内恶意指令。
- 工具参数注入。
- 多轮上下文注入。

防护位置：

```text
Input guard -> Retrieval document sanitizer -> Tool permission gate -> Output guard
```

### 9.3 审计

所有关键动作必须有 audit log：

- 登录/API key 使用。
- 上传/删除文档。
- 访问受限文档。
- Agent tool call。
- HITL 审批。
- 策略拦截。
- 退款/补偿/外发等高风险动作。

审计日志必须不可被普通业务接口删除。

---

## 10. 观测与运维

### 10.1 必须指标

Prometheus metrics 至少包括：

- `http_requests_total`
- `http_request_duration_seconds`
- `rag_retrieve_duration_seconds`
- `rag_recall_eval_score`
- `rag_cache_hits_total`
- `llm_call_duration_seconds`
- `llm_call_errors_total`
- `agent_run_total`
- `agent_step_duration_seconds`
- `agent_tool_call_total`
- `agent_tool_error_total`
- `policy_intercept_total`
- `ingestion_job_total`
- `ingestion_job_duration_seconds`
- `qdrant_errors_total`
- `redis_errors_total`
- `db_errors_total`

### 10.2 Trace

每次请求必须有：

- `trace_id`
- `tenant_id`
- `user_id`
- `session_id`
- `agent_run_id`
- `document_id` 或 `ticket_id`

Trace 应覆盖：

```text
HTTP -> policy -> retrieval -> rerank -> LLM -> tool -> DB -> response
```

### 10.3 健康检查

| Endpoint | 说明 |
|---|---|
| `/health/live` | 进程活着 |
| `/health/ready` | DB/Redis/Qdrant/模型可用 |
| `/health/config` | 只返回脱敏配置 |

`ready` 失败时容器不能接流量。

---

## 11. CI/CD 与质量门

CI 必须对所有分支和 PR 生效。

最低 workflow：

```yaml
on:
  push:
    branches: ["**"]
  pull_request:
```

必须执行：

```powershell
python -m compileall -q app
python -m ruff check app tests scripts
python -m pytest -q
npm --prefix frontend ci
npm --prefix frontend run build
docker compose config
docker compose up -d postgres redis qdrant
python -m alembic upgrade head
python scripts/run_eval_rag.py
python scripts/run_eval_agent.py
```

质量门：

- 单测失败：禁止完成。
- 评测低于门槛：禁止完成。
- CI 显式 ignore 核心测试：禁止完成。
- 文档指标没有对应 JSON 产物：禁止完成。
- 只跑 happy path：禁止完成。

---

## 12. 分阶段执行计划

### Phase 0：冻结事实与清理战场

目标：停止“边修边吹”，先建立真实基线。

任务：

- 记录当前分支、commit、dirty files。
- 跑 compile、pytest、frontend build、docker compose config。
- 列出所有失败，不修饰结果。
- 删除或归档临时脚本：`block_start.txt`、`ccx_replacer.py` 等必须确认是否需要。
- 修正 README 中明显不真实描述，标注当前是 WIP。
- 建立 `docs/audit/enterprise-gap-ledger.md`。

验收：

- 有一份基线报告。
- 所有失败命令有原始输出。
- 后续 AI 不能再引用旧的 15/15 mock 评测当当前结果。

### Phase 1：依赖、测试、CI 修复

目标：先让项目可验证。

任务：

- 补齐 `requirements.txt`：SQLAlchemy、alembic、asyncpg、aiosqlite、python-multipart、redis、队列库、pytest-timeout、locust 等。
- 修复 async 测试：`pytest.mark.asyncio` + `await run_ticket_agent(...)`。
- 全文替换过期 `app.llm_zhipu` patch。
- CI 去掉核心测试 ignore。
- CI 覆盖当前工作分支。
- 增加 `make` 或 PowerShell 脚本统一执行质量门。

验收：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend run build
```

全部通过。

### Phase 2：真实后端持久化

目标：业务 API 不再使用内存。

任务：

- 完善 DB models。
- 写 Alembic migration。
- 新建 repository/service 层。
- `/api/tickets` 改为 DB CRUD。
- `agent_runs`、`agent_steps`、`tool_calls` 落库。
- `chat_sessions/messages` 落库。
- 所有写接口事务化。

验收：

- 重启服务后 ticket/session/agent run 仍存在。
- 100 并发创建 ticket 不重复、不丢失。
- 跨租户不能读到对方数据。

### Phase 3：Redis 与异步任务

目标：长任务不阻塞 API，多进程状态共享。

任务：

- Docker Compose 增加 Redis。
- 选择队列：建议 `arq` 或 `dramatiq`，也可 Celery。
- ingestion、reindex、eval、长 Agent run 都进入队列。
- API 返回 `job_id`。
- worker 支持 retry、timeout、dead letter。
- rate limit 改 Redis。
- cache L1/L2 改 Redis 或至少支持 Redis backend。

验收：

- API 上传文件后 202 返回 job。
- worker 挂掉重启后任务可恢复或标记失败。
- 多 API worker 限流共享。

### Phase 4：上传与知识库摄入

目标：支持用户上传 PDF/Word/图片并检索。

任务：

- 实现 upload API。
- 加 `python-multipart`。
- 加解析器：PDF、DOCX、TXT、MD、CSV/XLSX、图片 OCR。
- 建 pages/chunks 表。
- Qdrant point id 与 DB chunk id 双向映射。
- 支持 delete/reindex/version。
- 前端做最小上传页面。

验收：

- 上传一份 PDF 后可查 job 进度。
- 摄入完成后能通过 `/retrieve` 找到页码引用。
- 删除文档后检索不到对应 chunk。

### Phase 5：RAG 质量硬化

目标：让检索和回答可量化。

任务：

- 建 100 条以上 RAG 金标集，覆盖 FAQ、PDF、表格、无答案、权限。
- 实现 `scripts/run_eval_rag.py`。
- 统一输出 JSON + Markdown 报告。
- 校准 gate threshold。
- 校准 rerank 和 fusion。
- citation 必须指向真实文档 chunk，不允许 Worker 自造 evidence。

验收：

- Recall@5 >= 0.85。
- Unauthorized TopK = 0。
- Unsupported sentence rate <= 0.08。

### Phase 6：Agent Harness 重建

目标：从固定工作流升级为可审计 Agent。

任务：

- 重建 `agent/state.py`。
- 建 tool registry。
- 所有工具走 permission gate。
- 加 planner 节点。
- 加 executor 节点。
- 加 evaluator/critic 节点。
- 加 checkpointer。
- 加 HITL approval API。
- Worker 不得直接跳过 gate/grader。
- Agent step 落库。

验收：

- Agent run 可在 DB 中回放每一步。
- 高风险工具未经审批不会执行。
- 工具超时能恢复。
- 30 条多轮 agent eval 通过率 >= 85%。

### Phase 7：降级、安全和防护

目标：故障时可控，不伪成功。

任务：

- LLM provider failover。
- Qdrant/BM25/embedding/rerank 故障策略。
- DB down 写接口 503。
- Redis down 队列接口 503。
- prompt injection eval。
- OPA 可选接入，生产 fail-closed。
- API auth 默认开启。
- 审计日志不可随业务删除。

验收：

- 故障注入测试通过。
- 高风险拦截 recall = 1.00。
- 跨租户泄漏 = 0。

### Phase 8：前端最小企业后台

目标：前端不需要好看，但要覆盖核心操作。

页面：

- 登录/API key 输入。
- 文档上传与 job 状态。
- 知识库文档列表。
- Chat/RAG 测试页。
- Agent run 时间线。
- 工单列表。
- 人工审批页。
- Eval run 报告页。

验收：

- 非开发者能上传文档、提问、查看引用、审批 Agent 动作。

### Phase 9：部署与项目包装

目标：项目可以被面试官或评审按文档跑起来。

任务：

- `docker compose up --build` 一键启动。
- `.env.example` 完整。
- README 重写为真实状态。
- 架构图更新。
- demo 数据和 eval 数据可复现。
- 录制 3 个端到端场景。

验收：

```powershell
docker compose up -d --build
python -m alembic upgrade head
python scripts/seed_demo.py
python scripts/run_eval_rag.py
python scripts/run_eval_agent.py
```

全部成功，并产出报告。

---

## 13. 交给 AI 执行时的硬规则

把下面这段作为后续 AI 的执行规则。

```text
你不能只改 README 或只新增文档来宣称完成。
每个任务必须包含：代码变更、测试、评测或明确说明为什么不能测试。
任何“已完成”必须附命令、退出码、关键输出、产物路径。
禁止把 mock eval 当 live eval。
禁止把内存 dict 当数据库。
禁止把 Worker 自己生成的回复塞进 retrieved_chunks 当证据。
禁止在 CI 中 ignore 当前失败的核心测试。
禁止在 Docker 配置中保留过期变量或无法启动的服务。
禁止说“企业级”除非 Docker、DB、Redis、Qdrant、worker、upload、eval 至少有可运行闭环。
遇到失败必须先修失败或记录为 blocker，不能绕过。
所有状态写入 docs/audit/enterprise-gap-ledger.md。
```

每个任务完成时必须更新：

```markdown
## Task ID

- Status: todo | doing | blocked | done
- Files changed:
- Tests run:
- Exit code:
- Evidence:
- Remaining risk:
```

---

## 14. 第一条应交给 AI 的具体任务

不要一上来就“重构全部”。第一条任务应该是：

```text
请先执行 Phase 0 和 Phase 1：

1. 不改业务功能，先建立当前真实基线。
2. 运行 compile、pytest、frontend build、docker compose config。
3. 修复已经失效的 Agent 测试和评测脚本：
   - run_ticket_agent 改为 async 后，测试必须 await。
   - 所有 app.llm_zhipu patch 改为 app.llm。
4. 补齐测试依赖和 CI 缺失。
5. CI 不允许 ignore tests/test_agent_graph_compile.py。
6. 产出 docs/audit/baseline-2026-06-11.md 和 docs/audit/enterprise-gap-ledger.md。

验收：
- .\.venv\Scripts\python.exe -m compileall -q app 通过。
- .\.venv\Scripts\python.exe -m pytest -q 通过，或只剩需要外部模型/服务的测试被明确标记 integration 并默认跳过。
- npm --prefix frontend run build 通过。
- docker compose config 通过。
- 文档中不得宣称尚未实现的 Redis、上传、多模态、真实 DB 持久化。
```

---

## 15. 当前项目的定位建议

短期不要再包装成“企业级完整项目”。更诚实、更专业的说法是：

> 当前是企业级 RAG+Agent 平台的技术原型，已经有混合检索、基础策略拦截、LangGraph 工单流、SSE 演示和部分评测脚本。下一阶段重点是补齐真实持久化、上传摄入、Agent harness、Redis/worker、质量门和生产部署闭环。

真正升级完成后，项目卖点应是：

- 支持 PDF/Word/图片上传的企业知识库。
- 多租户权限过滤的 hybrid RAG。
- 可审计 Agent harness，而不是脚本化流程。
- 工具权限和 HITL 审批。
- Redis/worker/Postgres/Qdrant 的完整后端。
- 降级和故障注入。
- 可复现的 RAG + Agent + 多模态评测报告。

这才是能支撑高难度 RAG+Agent 项目的工程深度。
