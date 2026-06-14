# 当前状态（与代码库 / 文档交叉核对）

> 交叉核对依据：`docs/PROJECT-STRATEGY-HANDOFF.md`、`README.md`、`docs/EVAL-RERUN-NOTES.md`、`.planning/ROADMAP.md` / `STATE.md`，以及 `app/*.py`、`scripts/run_eval_retrieve.py`、`docs/eval*.json` 摘要字段。  
> 更新时间：2026-06-04（阶段 K 交付层：SSE + React 前端 + Docker）。

---

## 阶段 K 完成项（2026-06-04）

| 能力 | 状态 | 说明 |
|------|------|------|
| `POST /chat/stream`（SSE） | **已落地** | `app/routes_rag.py`；`token` / `done` / `error` |
| `POST /agent/ticket/stream`（SSE） | **已落地** | `app/routes_agent.py` + `iter_ticket_agent_sse`；`step` / `token` / `done` |
| React 前端（Vite + TS） | **已落地** | `frontend/` → build 至 `static/app/`，挂载 `/app/` |
| Docker 多阶段镜像 | **已落地** | `Dockerfile` + `docker-compose.yml`（api + qdrant） |
| 旧版静态页 | **保留** | `/static/index.html`；无 `static/app` 时根路径仍跳转旧页 |

详见 [PHASE-K-PROGRESS.md](PHASE-K-PROGRESS.md)、[G-K-METRICS-SUMMARY.md](G-K-METRICS-SUMMARY.md)、[INTERVIEW-PREP.md](INTERVIEW-PREP.md)。

---

## 明确回答（交接文档要求）

**项目有哪些功能？**  
下文「当前功能清单」中标注为 **已落地** 的条目即为当前已实现的能力（FastAPI、`/retrieve` 与 `/chat`、LlamaIndex + Chroma、本地 Qwen Embedding、BM25 混合检索、可选 Qwen Rerank、Query Rewrite、领域路由、检索后门控、behavior guard、`trace_id` / `router_trace`、引用重叠度、citation 等）。

**哪些只是雏形？**  
标注为 **雏形** 的条目：领域路由（生产默认 trace-only，可选 hard filter）、**企业策略引擎**（规则/向量/LLM 分层已有，**尚无** DB 规则表、管理 UI、OPA、输出侧 post-generation guard）、可观测性（`policy_eval` 审计 logger 未接集中式后端，非完整 LLMOps）。**阶段 E MVP**：LangGraph + `POST /agent/ticket`（`docs/PHASE-E-PROGRESS.md`）。**Qdrant**：代码就绪，默认仍 Chroma（`docs/QDRANT-NEXT.md`）。四组检索矩阵 **已填满**；权限评测 **已落地**。

**哪些已经跑过评估？**  

- **企业检索评测**（`data/eval_enterprise_questions.jsonl`，50 条）：**router × rerank 四组合**已落盘（`docs/eval_enterprise_r0_k0.json` … `r1_k1.json`，汇总 `docs/eval_four_baselines_summary.json`，表格见 `[EVAL-BASELINE-COMPARISON.md](EVAL-BASELINE-COMPARISON.md)`）；历史 **2026-05-11 双基线**（仅 rerank 关）仍以 `docs/EVAL-RERUN-NOTES.md` 为附录参照，勿与矩阵单元格混读。  
- **学习文档评测**：`docs/eval_retrieve_autorun.json`（默认 `eval_questions.jsonl`，与 README 描述一致）。  
- **路线图 A–F checklist**：`[docs/ROADMAP-PHASES-A-F.md](ROADMAP-PHASES-A-F.md)`（与交接 §6 对齐；**不含** OPA / 全量 LangGraph / Qdrant 生产默认 / 管理 UI 等本 Pass 范围）。  
- **行为护栏**：`scripts/run_eval_behavior_guard.py` 评估 `**evaluate_policy`** 的 **intercept**（`should_skip_rag`）；产物 `docs/eval_behavior_guard.json`、`docs/BEHAVIOR-GUARD-EVAL.md`。可选 `**POLICY_EMBEDDING_GUARD` / `POLICY_LLM_GUARD`** 已在里程碑跑批中验证（summary 标志见 JSON）；应答类误杀抽检见 `[PHASE3-EMBEDDING-NOTES.md](PHASE3-EMBEDDING-NOTES.md)`。
- **权限评测**（企业索引）：**Forbidden 4/4**，**Expect 23/26（88.5%）**，**Domain 22/24（91.7%）** — `docs/ACCESS-CONTROL-EVAL.md`（2026-06-03）。AC02/07/28 **暂缓**，见 `docs/ACCESS-CONTROL-BADCASE.md` §8、`docs/PHASE-C-CLOSURE.md`。
- **Agent 路径评测**（mock policy/retrieve）：`scripts/run_eval_agent_ticket.py`；**15/15 pass** — `docs/eval_agent_ticket.json`、`docs/AGENT-TICKET-EVAL.md`、`docs/PHASE-E-CLOSURE.md`。

---

## 当前功能清单


| 能力                                                                                       | 状态         | 说明                                                                                |
| ---------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------- |
| FastAPI、`/health`、`/health/config`、`X-Trace-ID` 中间件                                      | **已落地**    | `app/main.py`                                                                     |
| `POST /retrieve`、`POST /chat`、静态页 / Swagger                                              | **已落地**    | `app/routes_rag.py`                                                               |
| LlamaIndex + Chroma 持久化、本地 Qwen3 Embedding                                               | **已落地**    | `app/index_store.py`、`app/embeddings.py`、`app/config.py`                          |
| Markdown front matter + 分块                                                               | **已落地**    | `app/chunking.py`                                                                 |
| BM25 混合检索 + 可选 Qwen3 Rerank                                                              | **已落地**    | `app/retrieval_pipeline.py`、`app/config.py`                                       |
| Query Rewrite（智谱，`QUERY_REWRITE_MODE`）                                                   | **已落地**    | 配置与管线已实现                                                                          |
| 领域路由（规则 + 可选 LLM，`router_trace`）；**可选** `DOMAIN_ROUTER_HARD_FILTER` rerank 前收窄（默认 **关**） | **雏形**     | `app/domain_router.py`、`app/retrieval_pipeline.py`、`ADR-domain-router-default.md` |
| `UserContext` / tenant / audience / 密级 **检索前 Pre-filter**                                  | **已落地**   | `app/access_prefilter.py` + `app/access_control.py`；Chroma ids + BM25 子集；可选 `ACCESS_POST_FILTER_SAFETY_NET` |
| 检索相似度门控（rerank 后阈值）                                                                      | **已落地**    | `app/retrieval_gates.py`                                                          |
| 企业策略引擎（规则优先级 + 可选 embedding / 智谱分类 + 审计）                                                 | **雏形→可升级** | `app/policy/`、`data/behavior_rules.default.json`；`app/behavior_guard.py` 为兼容入口    |
| `citation_overlap_ratio`（chat 生成后）                                                       | **已落地**    | `app/citation_verify.py`、`routes_rag.py`                                          |
| 结构化日志（`trace_id`、`event`）                                                                | **设计完成** | JSON line 日志 + `docs/OBSERVABILITY-DESIGN.md`；SDK 接入 backlog                         |
| Docker Compose Qdrant（可选本地服务）                                                            | **已落地**    | `docker-compose.yml`；应用默认仍 Chroma                                                 |
| 向量后端门面（`VECTOR_BACKEND` chroma \| qdrant）                                              | **已落地**    | `app/vector_index.py`、`app/qdrant_index_store.py`；切换见 `docs/QDRANT-NEXT.md`      |
| LangGraph 工单 Agent + `POST /agent/ticket`                                                | **MVP + E4 评测完成** | `app/agent_graph/`、`app/routes_agent.py`；`docs/PHASE-E-CLOSURE.md`（15/15 pass）           |
| Gradio 简易前端                                                                              | **已落地**    | README 所述脚本                                                                       |
| SSE 流式 `/chat/stream`、`/agent/ticket/stream`                                              | **已落地**    | 阶段 K；见 `docs/PHASE-K-PROGRESS.md`                                                  |
| React 演示前端 `/app/`                                                                       | **已落地**    | `frontend/` + `static/app/`                                                          |
| Docker Compose（api + qdrant）                                                               | **已落地**    | `Dockerfile`、`scripts/run_docker.ps1`                                               |


---

## 数据规模（与仓库一致）

- **企业文档池**：`data/docs/enterprise_ai_ops/` 下 **41** 个 Markdown 文件（含 `00-README.md`）。交接文档写「41 篇」一致。  
- **企业评估集**：`data/eval_enterprise_questions.jsonl`，**50** 条非空问题。  
- **默认 Chroma collection**：`app/config.py` 默认 `rag_kb`；企业索引需 `CHROMA_COLLECTION_NAME=enterprise_ai_ops`（README / 交接文档一致）。

---

## 当前评估结果

### `docs/*.json` 产物一览


| 文件                                              | 概要                                                                                                                 | 备注                                                                                           |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `docs/eval_enterprise_retrieve.json`            | `summary.rerank_enabled: true`，`expect_top1_hit_rate: 0.8`（40/50）                                                  | JSON **未**包含 `eval_skip_domain_router` / top5 / domain 字段；对应较早一次企业检索导出                       |
| `docs/eval_enterprise_retrieve_router_off.json` | 磁盘摘要：`rerank_enabled: true`，**Top-1 命中率 0.0**，top hit 为学习文档                                                        | 与 `EVAL-RERUN-NOTES`（2026-05-11）**不一致**，疑似 **未设置企业 `DOCS_DIR`/collection** 时生成；**勿当作有效基线 A** |
| `docs/eval_enterprise_retrieve_router_on.json`  | `rerank_enabled: false`，`eval_skip_domain_router: false`，Top-1 **0.54**（27/50），Top-5 **0.60**，domain top1 **0.62** | 与重跑笔记中「基线 B」一致                                                                               |
| `docs/eval_four_baselines_summary.json`         | 四组合（router×rerank）企业检索 summary 聚合                                                                                  | 2026-05-15；单组详情见 `eval_enterprise_r0_k0.json` … `r1_k1.json`                                 |


### README / `EVAL-RERUN-NOTES.md` 中的指标（可信双基线）

**日期**：2026-05-11（见 `docs/EVAL-RERUN-NOTES.md`）

**运行配置（两条基线相同部分）**：

- 解释器：文档示例为 `D:\conda\envs\rags\python.exe`  
- `DOCS_DIR=data/docs/enterprise_ai_ops`  
- `CHROMA_COLLECTION_NAME=enterprise_ai_ops`  
- `BM25_CORPUS_PATH=data/bm25_enterprise_corpus.jsonl`  
- `EVAL_QUESTIONS_PATH=data/eval_enterprise_questions.jsonl`  
- `**RERANK_ENABLED=false`**（为缩短 CPU 耗时；与默认「开 Rerank」生产配置 **不可直接横向对比**）  
- `QUERY_REWRITE_MODE`：按当时 Settings（笔记未强制改写开关；JSON 显示 `auto`）  
- Router：**基线 A** `EVAL_SKIP_DOMAIN_ROUTER=true`；**基线 B** `EVAL_SKIP_DOMAIN_ROUTER=false` **且** `**DOMAIN_ROUTER_HARD_FILTER=true`**（重跑时需显式；2026-05-11 JSON 均无 `domain_router_hard_filter` 摘要字段）。

**指标摘要**：


| 指标                     | 基线 A（跳过推断）      | 基线 B（推断 + `DOMAIN_ROUTER_HARD_FILTER=true`） |
| ---------------------- | --------------- | ------------------------------------------- |
| `expect_top1_hit_rate` | **0.64**（32/50） | **0.54**（27/50）                             |
| `expect_top5_hit_rate` | **0.80**（40/50） | **0.60**（30/50）                             |
| `domain_top1_hit_rate` | **0.72**（36/50） | **0.62**（31/50）                             |


**四组合矩阵（2026-05-15）**：已由 `scripts/run_eval_four_baselines.py` 生成四份 JSON + `docs/eval_four_baselines_summary.json`，表格见 `[EVAL-BASELINE-COMPARISON.md](EVAL-BASELINE-COMPARISON.md)`。**Router 默认**：见 `[ADR-domain-router-default.md](ADR-domain-router-default.md)`（当前数据下 **不建议** 默认开启 domain 硬性过滤）。历史 **rerank 关** 双基线仍以 `EVAL-RERUN-NOTES.md` 为附录。

---

## 已知问题

与 **交接文档 §4** 对齐：

1. **评估基线必须与 `DOCS_DIR`/collection/BM25 路径对齐** — `scripts/run_eval_retrieve.py` 在运行 **企业问题集**（`eval_enterprise_questions.jsonl`）或 `EVAL_ENTERPRISE_STRICT=1` 时，会校验路径/collection 是否指向 `enterprise_ai_ops`；未对齐则 **stderr WARNING**，设置 `EVAL_STRICT_ENTERPRISE=1` 时 **退出码 2**，降低误用默认 `rag_kb` 的静默污染风险（仍需人工保证 BM25 语料等与索引一致）。
2. **Hard domain filter**（`DOMAIN_ROUTER_HARD_FILTER=true`，**非**默认）在数据中曾降低 Top-1/Top-5；控制台可出现「过滤后无候选，回退全库」（`domain_router_fallback_all`）。
3. **Behavior / policy intercept**：独立脚本 `scripts/run_eval_behavior_guard.py`；边界 / high-risk recall **1.0** 在规则层与「向量 + LLM 开关开启」的 summary 配置下均保持（见 `docs/BEHAVIOR-GUARD-EVAL.md`、`eval_behavior_guard.json`）；应答类抽检见 `[PHASE3-EMBEDDING-NOTES.md](PHASE3-EMBEDDING-NOTES.md)`。Phase 3–6 验收见 `[POLICY-MILESTONE-ACCEPTANCE.md](POLICY-MILESTONE-ACCEPTANCE.md)`。
4. **Rerank**：最近一次文档化企业双基线为 **关 Rerank**；与 `eval_enterprise_retrieve.json`（rerank on、Top-1 0.8）**不可混为一谈**。

### Query Rewrite 常见误解（与 `app/config.py` / `app/query_rewrite.py` 一致）

**1）默认是不是「关改写」？**  
**不是。** `query_rewrite_mode` 在 `**app/config.py` 中默认为 `auto`**（不是 `off`）。若在运行日志或 `/health/config` 里看到 `off`，多半是本机 `**.env` 或环境变量显式覆盖了 `QUERY_REWRITE_MODE`**，请核对。

**2）`auto` 是不是「智谱先判断是否改写」？**  
**不是。** `auto` 走的是 `**should_use_llm_rewrite()` 启发式**（口语词、`?`/`？`、长度、疑问短语、短关键词跳过等），用来 **有时跳过** 智谱改写以省延迟与费用；**并非**「由 LLM 裁决要不要改写」。  
三种模式：`**off`** 永不调用智谱改写；`**on`** 在配置了 Key 时 **每次都** 走智谱改写；`**auto`** 为 **启发式门控 + 条件性** 调用智谱。

**3）若想要「由 LLM 决定是否改写」？**  
当前代码路径下：**没有** 单独的「轻量判别」接口。可选做法：`**on`** = 每次都改写（成本高）；`**auto`** = 启发式门控（省成本）。若要做 **真正的 LLM 门控**（例如单独一次 yes/no 或分类再决定是否全量改写），属于 **新能力**，已列入下文「下一阶段」中的可选项。

**4）无智谱 Key 时？**  
即便模式为 `on`/`auto` 且启发式允许改写，**未配置 `ZHIPUAI_API_KEY`（或等价变量）时整条改写链路退回原句**，不调用智谱（与 `resolve_retrieval_query` 行为一致）。

**方向说明（选型，非 Bug）**：启发式 `auto` 在成本与延迟上是 **合理默认**。若要「更好」，可考虑：(a) 用评测迭代调整启发式；(b) 增加基于智谱的 **廉价 yes/no 判别** 再决定是否全量改写；(c) 高 stakes 场景对 API 传入 `**use_query_rewrite`**（强制开/关）而生产默认仍用 `auto`。

#### Query Rewrite 配置速查

- `**QUERY_REWRITE_MODE`**：`off` | `on` | `auto`；代码默认 `**auto**`（勿与「默认关闭」混淆）。  
- **单次请求**：`/retrieve`、`/chat` 请求体 `**use_query_rewrite`**：`true` 强制改写、`false` 禁用、`null` 跟随 Settings（见 `app/schemas.py`）。  
- **依赖**：实际调用智谱改写需要 Key；否则始终使用原始检索句。

从 **代码/README** 额外可见：

- 默认 `EVAL_SKIP_DOMAIN_ROUTER=true`（eval 脚本：跳过推断、无 router_trace）；**生产 API**默认 `skip_domain_router=false`，配合 `**DOMAIN_ROUTER_HARD_FILTER=false`** 即有 trace 且无硬性收窄。若要复现矩阵 **r1** 或笔记「基线 B」，脚本需 `EVAL_SKIP_DOMAIN_ROUTER=false` 且 `**DOMAIN_ROUTER_HARD_FILTER=true`**。  
- `QUERY_REWRITE_ENABLED` 已废弃；须使用 `**QUERY_REWRITE_MODE`**（`STATE.md` / README）。  
- `langchain-chroma` 与 `chromadb` 版本冲突风险提示（README）。

---

## 下一阶段目标（2026-06-03 更新）

**当前阶段：E — LangGraph 工单 Agent**（详见 `docs/PHASE-E-NEXT.md`）

1. **E1**：`app/agent_graph/state.py` + 可编译 hello graph + 单测。
2. **E2**：串联 `evaluate_policy` → `retrieve_scored_nodes` → evidence gate → draft（可先 mock LLM）。
3. **E3**：暴露 `POST /agent/ticket`（或等价入口）与 `audit_trace`。

**阶段 C 已收口**：`docs/PHASE-C-CLOSURE.md`；权限 Bad Case AC02/07/28 **本迭代不改**。

**并行 backlog（不阻塞 E）**：路线图 D（Qdrant）、路线图 F（可观测性设计稿）、Router profile 加厚、改写门控升级。

---

## 常用运行命令

### 环境与依赖

```powershell
cd c:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project
conda activate rags
# 若未激活 conda，可使用固定解释器：
# & "D:\conda\envs\rags\python.exe" -m pip install -r requirements.txt
```

### 重建索引（企业库）

```powershell
$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
& "D:\conda\envs\rags\python.exe" scripts/reindex.py
```

### 启动 API

```powershell
$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
& "D:\conda\envs\rags\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 检索评估（企业集）

```powershell
$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
$env:EVAL_QUESTIONS_PATH="data/eval_enterprise_questions.jsonl"
$env:EVAL_OUTPUT_PATH="docs/eval_enterprise_retrieve_router_off.json"
$env:EVAL_SKIP_DOMAIN_ROUTER="true"   # 或 false
# $env:RERANK_ENABLED="false"           # 可按笔记缩短耗时
& "D:\conda\envs\rags\python.exe" scripts/run_eval_retrieve.py
```

### 环境变量示例（企业索引 + 可选护栏）

```powershell
$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
$env:EVAL_QUESTIONS_PATH="data/eval_enterprise_questions.jsonl"
$env:QUERY_REWRITE_MODE="auto"          # off | on | auto（代码默认 auto；见上文「Query Rewrite 常见误解」）
$env:RERANK_ENABLED="true"             # true | false
$env:EVAL_SKIP_DOMAIN_ROUTER="true"    # 评估脚本默认语义
$env:BEHAVIOR_GUARD_ENABLED="true"
# $env:BEHAVIOR_GUARD_RULES_PATH="path\to\rules.json"
# $env:ZHIPUAI_API_KEY="..."           # 改写 / LLM 路由 / chat
```

### 可选自检

```powershell
& "D:\conda\envs\rags\python.exe" -m compileall app
```

---

## 与交接文档不一致之处（已核实）


| 交接陈述                                                 | 核实结果                                                    |
| ---------------------------------------------------- | ------------------------------------------------------- |
| 存在 `eval_enterprise_retrieve_router_off.json` 且用于双基线 | 文件存在，但 **当前磁盘内容与 2026-05-11 笔记矛盾**，应以笔记为准并重跑 router_off |
| 旧 `eval_enterprise_retrieve.json` Top-1 0.8          | JSON **summary** 一致；但无 router 维度、且为 rerank **on** 的一次运行 |
| 企业文档 41 篇、eval 50 条                                  | 与仓库一致                                                   |


