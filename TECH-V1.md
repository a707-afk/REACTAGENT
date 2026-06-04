# RAG V1 技术选型与数据源（最小闭环）

> 与《AI应用开发项目建议与注意事项》第 1 步～第 3 步衔接；每一步可单独验收后再扩展。

## 1. 数据源（第一期）

| 项 | 决策 |
|----|------|
| **内容** | 本项目仓库及学习用 **Markdown**（讲义、学习记录、RAG 笔记等）。 |
| **目录约定** | 待索引文件放在 `rag-kb-project/data/docs/**/*.md`。 |
| **后续替换** | 可平移为企业制度、产品手册等，主链路接口保持不变。 |

## 2. 后端与工程

| 项 | 选型 | 理由（面试可讲） |
|----|------|------------------|
| **RAG 框架** | **LlamaIndex** | 专注文档索引、检索与查询引擎，RAG 迭代成本低；Agent 阶段再考虑 LangGraph。 |
| **API 框架** | **FastAPI** | 类型与 OpenAPI；与 Uvicorn 本地/容器通用。 |
| **配置** | **pydantic-settings** + 环境变量 / `.env` | 智谱密钥、模型路径均可从环境注入，适配 Conda。 |
| **Python 环境** | **Conda `rags`** | 统一管理 PyTorch / CUDA（与本地 Embedding 推理一致）。 |
| **日志** | **标准库 logging** | 便于后续接结构化日志。 |

## 3. 模型与向量库

| 项 | 选型 | 理由（面试可讲） |
|----|------|------------------|
| **向量库** | **Chroma**（持久化 `data/chroma/`） | 学习曲线低、本地可跑；规模大或要强运维时再迁 **Qdrant**（已预留演进方向）。 |
| **Embedding** | **Qwen3-Embedding-0.6B**（本地目录） | 向量不出网、成本可控；默认路径为 ModelScope 缓存目录，可通过 `QWEN_EMBEDDING_MODEL_PATH` 覆盖。 |
| **LLM** | **智谱 `glm-4-flash`** | 延迟与成本适合开发；密钥从 **`ZHIPUAI_API_KEY`** 或 **`ZHIPU_API_KEY`** 读取。 |
| **Rerank（K2 前置）** | **Qwen3-Reranker-0.6B**（本地 CausalLM yes/no 分）或 **CrossEncoder**（如 BGE） | 宽召回 + 可选 BM25 合并后精排；**门控阈值作用在重排分（Top-1）** 上。 |

LlamaIndex 侧：`HuggingFace Embedding` 加载上述本地目录（Sentence-Transformers `modules.json` 布局）。

## 4. 切片策略（P0 与对照）

| `CHUNK_STRATEGY` | 说明 |
|------------------|------|
| `markdown_heading_overlap`（默认） | `MarkdownNodeParser` 按标题切分；过长节用 `SentenceSplitter` 按 **token** 再切，带 overlap。 |
| `heading_only` | 仅标题切分，不做二次切分（做 ablation 用）。 |

相关环境变量见 [`app/config.py`](app/config.py)：`CHUNK_STRATEGY`、`CHUNK_SIZE_TOKENS`、`CHUNK_OVERLAP_TOKENS`。改完后需重新执行 `python scripts/reindex.py`。

评估问题集：[data/eval_questions.jsonl](data/eval_questions.jsonl)；对比记录模板：[docs/CHUNK_EVAL.md](docs/CHUNK_EVAL.md)。

## 5. API 与脚本（闭环）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/retrieve` | **向量宽召回 →（可选）CrossEncoder 重排 → Top-K**；`chunk.score` 在 rerank 开启时为 **重排分**。响应含 **`gate_passed`**、**`error_code`**、**`ranked_quality_scores`**（用于对照阈值校准）。 |
| POST | `/chat` | 同上链路；门控通过后拼上下文调智谱；**无结果或重排分低于阈值时不调用 LLM**，返回 **`refused`** + **`error_code`** + 固定拒答（默认「知识库中无相关内容」）。 |
| 脚本 | `python scripts/reindex.py` | 读取 `data/docs` 下 `.md`，写入 `data/chroma`（脚本内 `chdir` 到项目根） |

开发用静态页：启动服务后访问 `http://127.0.0.1:8000/` → `/static/index.html`。

## 6. 检索与 **K2（Rerank 后门控）**

**K2（产品/实现语义）**：指 **重排之后** 的门控，**不是**「向量召回结果里排名第 2 的 chunk」。流程：**向量宽召回**（`max(请求 top_k, RERANK_CANDIDATE_TOP_K)`） + **可选 BM25（`HYBRID_BM25_ENABLED`）候选合并去重** → **Rerank**（默认本地 **Qwen3-Reranker** CausalLM yes/no 分，或 `RERANK_BACKEND=cross_encoder`）→ 截断到 `top_k` → 取 **重排分最优（Top-1）** 与阈值比较；**低于阈值则视为无有效依据**，`/retrieve` 标记 `gate_passed=false`，`/chat` **不调 LLM** 并返回默认「知识库中无相关内容」。

| 配置项（env） | 默认 | 说明 |
|---------------|------|------|
| `HYBRID_BM25_ENABLED` | `true` | `false` 时仅向量宽召回 + Rerank |
| `BM25_CANDIDATE_TOP_K` | `20` | BM25 补充候选；与向量结果按 `node_id` 合并 |
| `BM25_CORPUS_PATH` | `data/bm25_corpus.jsonl` | `python scripts/reindex.py` 时自动生成 |
| `RERANK_ENABLED` | `true` | `false` 时不重排，门控作用在向量/BM25 分上（仅调试） |
| `RERANK_BACKEND` | `auto` | `auto`｜`qwen3_causal`｜`cross_encoder` |
| `RERANK_MODEL` | 本机 Qwen3-Reranker 路径 | Qwen 为 CausalLM；BGE 等为 HF id 或目录 |
| `RERANK_CANDIDATE_TOP_K` | `20` | 向量宽召回深度 |
| `QWEN_RERANK_MAX_LENGTH` | `8192` | 仅 Qwen Rerank |
| `QWEN_RERANK_BATCH_SIZE` | `4` | 仅 Qwen Rerank |
| `RETRIEVAL_GATE_ENABLED` | `true` | 关闭则跳过阈值门控 |
| `RETRIEVAL_SIMILARITY_THRESHOLD` | `0.6` | 与 **重排后** 最优分比较；Qwen 多为概率，务必跑 eval 看 `gate_score_*` |
| `RETRIEVAL_SCORE_HIGHER_IS_BETTER` | `true` | 通常保持 `true` |
| `REFUSAL_NO_RESULTS` / `REFUSAL_GATE_FAIL` | 默认均为「知识库中无相关内容」 | 拒答固定模板 |

批量打印 **向量分 / 重排分** 分布：`python scripts/run_eval_retrieve.py` → `docs/eval_retrieve_autorun.json`（`summary.vector_raw_*` vs `summary.gate_score_*`）。

## 7. 环境变量（摘要）

| 变量 | 说明 |
|------|------|
| `ZHIPUAI_API_KEY` 或 `ZHIPU_API_KEY` | 智谱开放平台 API Key（与仓库根 [`llm_factory.py`](../llm_factory.py) 习惯一致）。 |
| `QWEN_EMBEDDING_MODEL_PATH` | 可选；不设置时使用本机默认 ModelScope 路径（见 `app/config.py`）。 |
| `ZHIPU_CHAT_MODEL` | 可选；默认 `glm-4-flash`。 |
| `ZHIPU_API_BASE` | 可选；默认智谱 OpenAI 兼容 Base URL。 |
| `RERANK_*` / `QWEN_RERANK_*` / `HYBRID_BM25_*` / `BM25_*` | 见 §6 表格 |

## 8. 暂不纳入 V1 的内容

- **外部商业 Rerank API**、多阶段 Rerank 编排、Query Rewrite、LangGraph 多 Agent、MCP、复杂长期记忆。

## 9. 依赖与安装

- 依赖见 [requirements.txt](requirements.txt)；**在已激活的 Conda 环境 `rags` 中** `pip install -r requirements.txt`。
- 若 `rags` 中尚无 **PyTorch**，请按本机 CPU/GPU 用 Conda 或官方指引单独安装，再装本项目依赖。

---
| 日期 | 变更 |
|------|------|
| 2026-05-06 | 初稿：FastAPI + Chroma + 智谱 Embedding/LLM。 |
| 2026-05-06 | 修订：LlamaIndex；本地 Qwen3-Embedding；智谱仅对话；Conda `rags`；可切换 Qdrant 的规划。 |
| 2026-05-06 | 切片 P0、`/retrieve` 与 `/chat`、`reindex.py`、静态测试页、eval 与 CHUNK_EVAL。 |
| 2026-05-06 | 检索门控 K2+阈值、拒答路径不调 LLM、`run_eval_retrieve.py`、响应字段 `gate_passed` / `refused` / `error_code`。 |
| 2026-05-07 | **K2 = Rerank 后门控**：CrossEncoder 重排；Top-1 重排分 ≥ 阈值；统一拒答「知识库中无相关内容」；eval 输出向量分与 gate 分量纲。 |
| 2026-05-07 | **BM25 + 向量混合**（jieba + rank_bm25）；**Qwen3-Reranker** CausalLM 重排；`reindex` 写入 `bm25_corpus.jsonl`。 |
