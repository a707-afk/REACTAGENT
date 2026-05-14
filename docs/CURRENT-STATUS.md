# 当前状态（与代码库 / 文档交叉核对）

> 交叉核对依据：`docs/PROJECT-STRATEGY-HANDOFF.md`、`README.md`、`docs/EVAL-RERUN-NOTES.md`、`.planning/ROADMAP.md` / `STATE.md`，以及 `app/*.py`、`scripts/run_eval_retrieve.py`、`docs/eval*.json` 摘要字段。  
> 更新时间：2026-05-14（仓库快照）。

---

## 明确回答（交接文档要求）

**项目有哪些功能？**  
下文「当前功能清单」中标注为 **已落地** 的条目即为当前已实现的能力（FastAPI、`/retrieve` 与 `/chat`、LlamaIndex + Chroma、本地 Qwen Embedding、BM25 混合检索、可选 Qwen Rerank、Query Rewrite、领域路由、检索后门控、behavior guard、`trace_id` / `router_trace`、引用重叠度、citation 等）。

**哪些只是雏形？**  
标注为 **雏形** 的条目：领域路由（规则 + 可选 LLM，非 embedding router）、访问控制（检索后 Python 层过滤）、behavior guard（demo 级正则规则）、可观测性（结构化日志片段，非完整 LLMOps）。**规划中**：Qdrant 默认向量后端、LangGraph 工单 Agent、独立权限/护栏评测流水线等（见交接文档 §6）。

**哪些已经跑过评估？**  
- **企业检索评测**（`data/eval_enterprise_questions.jsonl`，50 条）：已有 JSON 产物与 README/重跑笔记中的指标（见下节）；其中 **2026-05-11 双基线** 的权威数字以 `docs/EVAL-RERUN-NOTES.md` 为准。  
- **学习文档评测**：`docs/eval_retrieve_autorun.json`（默认 `eval_questions.jsonl`，与 README 描述一致）。  
- **未单独脚本化**：`behavior_guard` 命中率评测、`user_context` 权限评测仍 **未** 作为独立 eval 跑批（交接 §4 / §5）。

---

## 当前功能清单

| 能力 | 状态 | 说明 |
|------|------|------|
| FastAPI、`/health`、`/health/config`、`X-Trace-ID` 中间件 | **已落地** | `app/main.py` |
| `POST /retrieve`、`POST /chat`、静态页 / Swagger | **已落地** | `app/routes_rag.py` |
| LlamaIndex + Chroma 持久化、本地 Qwen3 Embedding | **已落地** | `app/index_store.py`、`app/embeddings.py`、`app/config.py` |
| Markdown front matter + 分块 | **已落地** | `app/chunking.py` |
| BM25 混合检索 + 可选 Qwen3 Rerank | **已落地** | `app/retrieval_pipeline.py`、`app/config.py` |
| Query Rewrite（智谱，`QUERY_REWRITE_MODE`） | **已落地** | 配置与管线已实现 |
| 领域路由（规则 + 可选 LLM）、rerank 前过滤、`domain_router_fallback_all` | **雏形** | `app/domain_router.py`；交接文档指出关键词路由不稳定 |
| `UserContext` / tenant / audience / 密级检索后过滤 | **雏形** | `app/access_control.py`；非向量库检索前过滤 |
| 检索相似度门控（rerank 后阈值） | **已落地** | `app/retrieval_gates.py` |
| Behavior guard（短路 RAG/LLM） | **雏形** | `app/behavior_guard.py`（demo-grade） |
| `citation_overlap_ratio`（chat 生成后） | **已落地** | `app/citation_verify.py`、`routes_rag.py` |
| 结构化日志（`trace_id`、`event`） | **雏形** | JSON line 日志；非完整 OTel/Langfuse |
| Docker Compose Qdrant（可选本地服务） | **已落地** | `docker-compose.yml`；应用默认仍 Chroma |
| Qdrant 向量后端迁移 | **规划中** | `docs/QDRANT-NEXT.md`、交接 §6-D |
| LangGraph 工单 Agent | **规划中** | 知识库中有设计文档；代码未在 `app/agent_graph/` |
| Gradio 简易前端 | **已落地** | README 所述脚本 |

---

## 数据规模（与仓库一致）

- **企业文档池**：`data/docs/enterprise_ai_ops/` 下 **41** 个 Markdown 文件（含 `00-README.md`）。交接文档写「41 篇」一致。  
- **企业评估集**：`data/eval_enterprise_questions.jsonl`，**50** 条非空问题。  
- **默认 Chroma collection**：`app/config.py` 默认 `rag_kb`；企业索引需 `CHROMA_COLLECTION_NAME=enterprise_ai_ops`（README / 交接文档一致）。

---

## 当前评估结果

### `docs/*.json` 产物一览

| 文件 | 概要 | 备注 |
|------|------|------|
| `docs/eval_enterprise_retrieve.json` | `summary.rerank_enabled: true`，`expect_top1_hit_rate: 0.8`（40/50） | JSON **未**包含 `eval_skip_domain_router` / top5 / domain 字段；对应较早一次企业检索导出 |
| `docs/eval_enterprise_retrieve_router_off.json` | 磁盘摘要：`rerank_enabled: true`，**Top-1 命中率 0.0**，top hit 为学习文档 | 与 `EVAL-RERUN-NOTES`（2026-05-11）**不一致**，疑似 **未设置企业 `DOCS_DIR`/collection** 时生成；**勿当作有效基线 A** |
| `docs/eval_enterprise_retrieve_router_on.json` | `rerank_enabled: false`，`eval_skip_domain_router: false`，Top-1 **0.54**（27/50），Top-5 **0.60**，domain top1 **0.62** | 与重跑笔记中「基线 B」一致 |
| `docs/eval_retrieve_autorun.json` | 默认学习库问题集；`expect_top1_hit_rate` 约 **0.923**（26 条中带期望标签的子集） | README 所述通用校准输出 |

### README / `EVAL-RERUN-NOTES.md` 中的指标（可信双基线）

**日期**：2026-05-11（见 `docs/EVAL-RERUN-NOTES.md`）

**运行配置（两条基线相同部分）**：

- 解释器：文档示例为 `D:\conda\envs\rags\python.exe`  
- `DOCS_DIR=data/docs/enterprise_ai_ops`  
- `CHROMA_COLLECTION_NAME=enterprise_ai_ops`  
- `BM25_CORPUS_PATH=data/bm25_enterprise_corpus.jsonl`  
- `EVAL_QUESTIONS_PATH=data/eval_enterprise_questions.jsonl`  
- **`RERANK_ENABLED=false`**（为缩短 CPU 耗时；与默认「开 Rerank」生产配置 **不可直接横向对比**）  
- `QUERY_REWRITE_MODE`：按当时 Settings（笔记未强制改写开关；JSON 显示 `auto`）  
- Router：**基线 A** `EVAL_SKIP_DOMAIN_ROUTER=true`；**基线 B** `EVAL_SKIP_DOMAIN_ROUTER=false`

**指标摘要**：

| 指标 | 基线 A（skip router） | 基线 B（router on） |
|------|------------------------|----------------------|
| `expect_top1_hit_rate` | **0.64**（32/50） | **0.54**（27/50） |
| `expect_top5_hit_rate` | **0.80**（40/50） | **0.60**（30/50） |
| `domain_top1_hit_rate` | **0.72**（36/50） | **0.62**（31/50） |

**未完成矩阵（交接 §5 建议）**：尚未在仓库文档中固化 **router on/off × rerank on/off** 四组完整对照；当前仅有 **rerank 关** 下的 router 对照笔记 + 磁盘上单次 JSON。

---

## 已知问题

与 **交接文档 §4** 对齐：

1. **评估基线必须与 `DOCS_DIR`/collection/BM25 路径对齐**，否则会命中默认 `rag_kb` 学习文档（`eval_enterprise_retrieve_router_off.json` 现状即疑似此类污染）。  
2. **Router on** 在笔记中降低 Top-1/Top-5；控制台可出现「过滤后无候选，回退全库」（`domain_router_fallback_all`）。  
3. **无独立 `behavior_guard` 评估脚本**；不应与检索 eval 混谈。  
4. **Rerank**：最近一次文档化企业双基线为 **关 Rerank**；与 `eval_enterprise_retrieve.json`（rerank on、Top-1 0.8）**不可混为一谈**。  

### Query Rewrite 常见误解（与 `app/config.py` / `app/query_rewrite.py` 一致）

**1）默认是不是「关改写」？**  
**不是。** `query_rewrite_mode` 在 **`app/config.py` 中默认为 `auto`**（不是 `off`）。若在运行日志或 `/health/config` 里看到 `off`，多半是本机 **`.env` 或环境变量显式覆盖了 `QUERY_REWRITE_MODE`**，请核对。

**2）`auto` 是不是「智谱先判断是否改写」？**  
**不是。** `auto` 走的是 **`should_use_llm_rewrite()` 启发式**（口语词、`?`/`？`、长度、疑问短语、短关键词跳过等），用来 **有时跳过** 智谱改写以省延迟与费用；**并非**「由 LLM 裁决要不要改写」。  
三种模式：**`off`** 永不调用智谱改写；**`on`** 在配置了 Key 时 **每次都** 走智谱改写；**`auto`** 为 **启发式门控 + 条件性** 调用智谱。

**3）若想要「由 LLM 决定是否改写」？**  
当前代码路径下：**没有** 单独的「轻量判别」接口。可选做法：**`on`** = 每次都改写（成本高）；**`auto`** = 启发式门控（省成本）。若要做 **真正的 LLM 门控**（例如单独一次 yes/no 或分类再决定是否全量改写），属于 **新能力**，已列入下文「下一阶段」中的可选项。

**4）无智谱 Key 时？**  
即便模式为 `on`/`auto` 且启发式允许改写，**未配置 `ZHIPUAI_API_KEY`（或等价变量）时整条改写链路退回原句**，不调用智谱（与 `resolve_retrieval_query` 行为一致）。

**方向说明（选型，非 Bug）**：启发式 `auto` 在成本与延迟上是 **合理默认**。若要「更好」，可考虑：(a) 用评测迭代调整启发式；(b) 增加基于智谱的 **廉价 yes/no 判别** 再决定是否全量改写；(c) 高 stakes 场景对 API 传入 **`use_query_rewrite`**（强制开/关）而生产默认仍用 `auto`。

#### Query Rewrite 配置速查

- **`QUERY_REWRITE_MODE`**：`off` | `on` | `auto`；代码默认 **`auto`**（勿与「默认关闭」混淆）。  
- **单次请求**：`/retrieve`、`/chat` 请求体 **`use_query_rewrite`**：`true` 强制改写、`false` 禁用、`null` 跟随 Settings（见 `app/schemas.py`）。  
- **依赖**：实际调用智谱改写需要 Key；否则始终使用原始检索句。

从 **代码/README** 额外可见：

- 默认 `EVAL_SKIP_DOMAIN_ROUTER=true`（`scripts/run_eval_retrieve.py`），与企业历史 Top-1 对齐；测真实路由过滤需显式 `false`。  
- `QUERY_REWRITE_ENABLED` 已废弃；须使用 **`QUERY_REWRITE_MODE`**（`STATE.md` / README）。  
- `langchain-chroma` 与 `chromadb` 版本冲突风险提示（README）。

---

## 下一阶段目标（对齐交接 §5 / §11）

1. **维持** `docs/CURRENT-STATUS.md` 与评估产物同步（本文档）。  
2. **澄清并完成四组 rerun 基线**：在企业索引与 BM25/collection 对齐前提下，固化 **router on/off × rerank on/off** 全矩阵；与 `docs/EVAL-RERUN-NOTES.md` / `PROJECT-STRATEGY-HANDOFF.md` 口径一致，产出可信对照（含可在本文档引用的摘要或 `docs/EVAL-BASELINE-COMPARISON.md`，交接 §5 任务 2）。  
3. **新增** `scripts/run_eval_behavior_guard.py` 与 `docs/eval_behavior_guard.json`、`docs/BEHAVIOR-GUARD-EVAL.md`（交接 §5 任务 3）。  
4. **根据评估决定** domain router 是否默认仅记录 `router_trace`、不强过滤（交接 §5 任务 4）。  
5. **可选：改写门控升级**——在沿用 **`auto` 启发式** 的基础上，用评测迭代规则；或新增 **轻量 LLM 判别**（廉价 yes/no）再决定是否调用全量改写；高 stakes 亦可依赖 API **`use_query_rewrite`**，与全局默认解耦。  
6. 远期仍按交接 §6：`VECTOR_BACKEND`、embedding router、权限检索前过滤、LangGraph、可观测性等。

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

| 交接陈述 | 核实结果 |
|----------|----------|
| 存在 `eval_enterprise_retrieve_router_off.json` 且用于双基线 | 文件存在，但 **当前磁盘内容与 2026-05-11 笔记矛盾**，应以笔记为准并重跑 router_off |
| 旧 `eval_enterprise_retrieve.json` Top-1 0.8 | JSON **summary** 一致；但无 router 维度、且为 rerank **on** 的一次运行 |
| 企业文档 41 篇、eval 50 条 | 与仓库一致 |
