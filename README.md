# 企业知识库 RAG（渐进实现）

见 [REQUIREMENTS-ONEPAGER.md](REQUIREMENTS-ONEPAGER.md)、[TECH-V1.md](TECH-V1.md) 与 **[架构说明 docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**。

## 环境：Conda `rags`

```bash
conda activate rags
cd rag-kb-project
```

### GPU（RTX 5070 / NVIDIA 50 系）

- **`INFERENCE_DEVICE=auto`**（默认）：有 CUDA 用 GPU，否则 CPU，**不写死**。
- 若 `rags` 里是 `torch *+cpu`，评测/API 会极慢。50 系显卡需 **PyTorch cu128**（sm_120）：

```powershell
.\scripts\setup_pytorch_cuda.ps1
```

详见 [docs/CUDA-SETUP.md](docs/CUDA-SETUP.md)。装好后 `/health/config` 应见 `inference_device_resolved: cuda`。

若环境中还没有 PyTorch，先完成上一步或安装 CPU 版，再执行：

```bash
pip install -r requirements.txt
```

其中包含 **rank-bm25**、**jieba**（BM25 混合检索）与 **transformers>=4.51**（Qwen3-Reranker）。**改文档或切片后务必** `python scripts/reindex.py`，以同步 Chroma 与 **`data/bm25_corpus.jsonl`**。

### PowerShell：不显式 `conda activate` 时（推荐本机路径）

若终端里找不到 `conda`，可直接用 **环境中的 `python.exe`**（路径按你机器修改；以下为当前常用示例）：

```powershell
cd c:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project
& "D:\conda\envs\rags\python.exe" -m pip install -r requirements.txt
& "D:\conda\envs\rags\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

或一键启动（脚本内已固定 `rags` 解释器路径，你若换环境请改 [scripts/run_uvicorn.ps1](scripts/run_uvicorn.ps1)）：

```powershell
.\scripts\run_uvicorn.ps1
```

这样不依赖「Scripts 是否在 PATH」；`uvicorn` 用 `-m` 方式调用即可。

**说明**：若 `pip install` 提示 **`langchain-chroma` 与 `chromadb` 版本冲突**，是因为 `rags` 里已装有旧版 LangChain-Chroma 约束；仅使用本项目的 LlamaIndex + Chroma 时一般仍可运行。若你在同一环境里同时跑依赖旧版 `chromadb` 的脚本，需单独用虚拟环境或统一版本。

可选：复制 [.env.example](.env.example) 为 `.env`，填写 `ZHIPUAI_API_KEY`；也可只在系统/用户环境变量里设置 **`ZHIPUAI_API_KEY`** 或 **`ZHIPU_API_KEY`**，应用同样会读取。

本地 Qwen3 Embedding 默认路径为 ModelScope 缓存（见 [app/config.py](app/config.py)）；若你的模型在其他目录，请设置环境变量 **`QWEN_EMBEDDING_MODEL_PATH`**。

- **`INFERENCE_DEVICE`**（可选）：`auto` | `cuda` | `cpu` — 见 [docs/CUDA-SETUP.md](docs/CUDA-SETUP.md)；`cuda` 不可用时会**自动回退 CPU**。
- **`QUERY_REWRITE_MODE`**（可选）：`auto`（默认）— 按启发式决定是否为检索调用智谱改写；`on` 总是改写、`off` 关闭改写（`on`/`auto` 在需改写时依赖智谱 Key）。

## RAG 闭环（索引 + 检索 + 问答）

1. **建立向量索引**（改文档或切片配置后需重做）：

```powershell
cd c:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project
& "D:\conda\envs\rags\python.exe" scripts/reindex.py
```

2. **启动 API**（必须在 `rag-kb-project` 目录下，保证 `data/` 相对路径正确）：

```powershell
& "D:\conda\envs\rags\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. **调用接口**（见 Swagger `/docs`）：
   - `POST /retrieve`：`{"query":"...","top_k":5}` — 可选 `"use_query_rewrite": true|false`（`null` 则跟随环境变量 **`QUERY_REWRITE_MODE`**：`off` / `on` / `auto`）；宽召回 → Rerank → chunk；响应中若有 **`retrieval_query`** 表示检索使用了改写后的语句。
   - `POST /chat`：同上；**门控**不通过则拒答（不调 LLM）；通过则走智谱，返回 `answer` 与 **`citations`**（与正文 **[1]、[2]** 对应）。

4. **简易前端**：浏览器打开 `http://127.0.0.1:8000/`（重定向到 `static/index.html`），含 **检索/问答** 与 **工单 Agent** 表单（`POST /agent/ticket`）；或 **Gradio**（需另开终端，且 API 已在 8000 运行）：

```powershell
cd c:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project
pip install -r requirements.txt
.\scripts\run_gradio.ps1
```

浏览器访问 **http://127.0.0.1:7860** 。环境变量 **`RAG_API_BASE`**（默认 `http://127.0.0.1:8000`）、**`GRADIO_SERVER_PORT`**（默认 `7860`）可按需修改。

5. **评估**：问题列表 [data/eval_questions.jsonl](data/eval_questions.jsonl)（含可选 `expect_top1_file_contains` 弱标签）；切片对比记录 [docs/CHUNK_EVAL.md](docs/CHUNK_EVAL.md)。

6. **检索校准脚本**（需已建立索引；**首次会加载 Embedding / Rerank**）：

```powershell
cd c:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project
& "D:\conda\envs\rags\python.exe" scripts/run_eval_retrieve.py
```

生成 `docs/eval_retrieve_autorun.json`：`summary.expect_top1_hit_rate` 为 **Top-1 文件名是否包含期望子串** 的命中率（仅供参考）；请仍以 **`gate_score_*`** 与门控阈值为主。

**Query Rewrite**：在 `.env` 中设置 **`QUERY_REWRITE_MODE=off|on|auto`**（默认 `auto`）；`on` 时每次检索前可走智谱改写（需配置 Key）。也可用 API 请求体 **`use_query_rewrite`** 单次覆盖。评估脚本与 API 输出中的 `retrieval_query` 便于对比是否改写。

### 工单 Agent API

- **`POST /agent/ticket`**：`{"ticket_id":"T-001","user_query":"…","top_k":5,"user_context":{"tenant_id":"corp-default","roles":["support_agent"]}}`
- 响应：`final_action`、`draft_reply`、`audit_trace`、`gate_passed` 等（见 Swagger `/docs`）。
- **路径评测（mock，不加载索引）**：`python scripts/run_eval_agent_ticket.py` → `docs/eval_agent_ticket.json`
- **真实联调（Chroma 企业索引）**：与企业评测相同环境变量后 `python scripts/run_eval_agent_ticket_live.py` → `docs/eval_agent_ticket_live.json`（缺索引 exit 2）

### 向量后端与 Qdrant

| 变量 | 默认 | 说明 |
|------|------|------|
| `VECTOR_BACKEND` | `chroma` | `chroma` \| `qdrant` |
| `QDRANT_PATH` | — | 嵌入式本地目录（如 `data/qdrant_local`） |
| `QDRANT_URL` | — | Docker/远程 Qdrant（与 `QDRANT_PATH` 二选一） |
| `QDRANT_API_KEY` | — | 可选 |

切换 Qdrant 后须 `VECTOR_BACKEND=qdrant` 并 **重新 `reindex.py`**。操作见 [docs/QDRANT-NEXT.md](docs/QDRANT-NEXT.md)。

### 可观测性（stdout JSON）

检索结束 `event=retrieve`、门控 `event=gate`、改写 `event=query_rewrite`；策略 `event=policy_eval`、工单 `event=agent_ticket`。设计见 [docs/OBSERVABILITY-DESIGN.md](docs/OBSERVABILITY-DESIGN.md)。下一里程碑见 [docs/NEXT-MILESTONE.md](docs/NEXT-MILESTONE.md)。

## 快速验证（约 5 分钟）

在 `rag-kb-project` 根目录、已 `pip install -r requirements.txt` 的 `rags` 环境中：

```powershell
cd c:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project

# 1) 单元 + mock Agent 路径（不加载向量）
& "D:\conda\envs\rags\python.exe" -m pytest tests/test_agent_graph_compile.py -q
& "D:\conda\envs\rags\python.exe" scripts/run_eval_agent_ticket.py

# 2) 企业索引（Agent live / 带 user_context 的检索）
$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:QDRANT_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
& "D:\conda\envs\rags\python.exe" scripts/reindex.py
& "D:\conda\envs\rags\python.exe" scripts/run_eval_agent_ticket_live.py

# 3) 启动 API + 静态页 / Agent 冒烟
$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:QDRANT_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
Start-Process -NoNewWindow -FilePath "D:\conda\envs\rags\python.exe" -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000"
# 另开终端：
& "D:\conda\envs\rags\python.exe" scripts/smoke_agent_ticket.py
# 浏览器：http://127.0.0.1:8000/static/index.html
```

`smoke_agent_ticket.py` 默认**不传** `user_context`（减轻 Pre-filter 对索引对齐的依赖）；索引未建时 HTTP 503 会 **skip** 而非失败。要测权限上下文：`AGENT_SMOKE_WITH_CONTEXT=1`。

**cmd 注意**：不要用 PowerShell 的 `&`；请先 `cd` 到 `rag-kb-project`，再 `python scripts/reindex.py` / `python -m uvicorn ...`。

## 健康检查与配置

在已激活的 `rags` 下：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

若未激活、沿用上一节「显式 python.exe」：

```powershell
& "D:\conda\envs\rags\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- `GET http://127.0.0.1:8000/health` → `{"status":"ok","app":"enterprise-rag-kb"}`
- `GET http://127.0.0.1:8000/health/config` → 检查 Qwen 目录是否存在、智谱 Key 是否已配置（**不返回密钥**）
- Swagger：`http://127.0.0.1:8000/docs`

> **说明**：当前终端若未把 `conda` 加入 PATH，请在 **Anaconda Prompt** 或已初始化 conda 的 shell 中执行 `conda activate rags`。

## 日常记录

每日条目写在 [docs/DAILY-LOG.md](docs/DAILY-LOG.md)。

## 验证本地 Embedding（可选）

在 `rags` 中、项目根目录执行（会加载模型，首次较慢）：

```bash
python -c "from app.embeddings import get_embedding_model; e=get_embedding_model(); v=e.get_query_embedding('ping'); print('dim', len(v))"
```

PowerShell 显式解释器示例：

```powershell
& "D:\conda\envs\rags\python.exe" -c "from app.embeddings import get_embedding_model; e=get_embedding_model(); v=e.get_query_embedding('ping'); print('dim', len(v))"
```

## 企业场景知识库

目录：`data/docs/enterprise_ai_ops/`（含 `00-README.md` 元信息与各子域 Markdown）。每条业务文档建议使用简单 YAML front matter（`---` 包裹，仅单行 `键: 值`，避免 YAML 复合结构），示例字段：`domain`、`subdomain`、`source_type`、`audience`、`security_level`、`owner`、`workflow`、`version`、`status`。

**仅用企业文集建立隔离索引并重跑评测**（在 `rag-kb-project` 根目录）。

若提示符是 `C:\...>`、命令以 `>` 结尾，一般是 **CMD（命令提示符）**：不要用 `$env:...`，请用下面的 **`set`** 写法，或改用 **PowerShell**（蓝色窗口 / 提示符常含 `PS`）。

**PowerShell：**

```powershell
cd c:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project
$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:QDRANT_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
& "D:\conda\envs\rags\python.exe" scripts/reindex.py

$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:QDRANT_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
$env:EVAL_QUESTIONS_PATH="data/eval_enterprise_questions.jsonl"
$env:EVAL_OUTPUT_PATH="docs/eval_enterprise_retrieve.json"
& "D:\conda\envs\rags\python.exe" scripts/run_eval_retrieve.py
```

**CMD（命令提示符）：**

```bat
cd /d C:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project
set DOCS_DIR=data/docs/enterprise_ai_ops
set QDRANT_COLLECTION_NAME=enterprise_ai_ops
set BM25_CORPUS_PATH=data/bm25_enterprise_corpus.jsonl
"D:\conda\envs\rags\python.exe" scripts\reindex.py

set DOCS_DIR=data/docs/enterprise_ai_ops
set QDRANT_COLLECTION_NAME=enterprise_ai_ops
set BM25_CORPUS_PATH=data/bm25_enterprise_corpus.jsonl
set EVAL_QUESTIONS_PATH=data/eval_enterprise_questions.jsonl
set EVAL_OUTPUT_PATH=docs/eval_enterprise_retrieve.json
"D:\conda\envs\rags\python.exe" scripts\run_eval_retrieve.py
```

**启动 API（需与企业索引同一套变量）— CMD：**

```bat
cd /d C:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project
set DOCS_DIR=data/docs/enterprise_ai_ops
set QDRANT_COLLECTION_NAME=enterprise_ai_ops
set BM25_CORPUS_PATH=data/bm25_enterprise_corpus.jsonl
"D:\conda\envs\rags\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

若出现 `WinError 10013`：**先改 `--host 127.0.0.1`**（上例已用）；仍失败则换端口，例如 `--port 8008`，并检查占用：`netstat -ano | findstr :8000`。

## 下一步（实现要点）

- **策略护栏**：见 `app/behavior_guard.py`，环境变量 **`BEHAVIOR_GUARD_ENABLED`**（默认 true）、可选 **`BEHAVIOR_GUARD_RULES_PATH`** 指向自定义规则 JSON。命中后 `/chat`、`/retrieve` 返回 `behavior: human_review` 与 `refusal_reason_code`，且不调用完整 RAG。
- **企业评测对照**：跳过推断 vs 推断+硬性收窄：`EVAL_SKIP_DOMAIN_ROUTER`、`DOMAIN_ROUTER_HARD_FILTER`，详见 [docs/EVAL-RERUN-NOTES.md](docs/EVAL-RERUN-NOTES.md)与 [docs/ADR-domain-router-default.md](docs/ADR-domain-router-default.md)。
- **路由增强离线评测**：`python scripts/run_eval_router.py`（输出 `*_predictions.csv`、混淆矩阵、F1 等）；**校准拟合**：`python scripts/fit_router_calibration.py`（基于 golden 或评测 CSV）；环境变量摘要见 [.env.example](.env.example) 与 `DOMAIN_ROUTER_*` / `ROUTER_CALIBRATION_PATH`。
