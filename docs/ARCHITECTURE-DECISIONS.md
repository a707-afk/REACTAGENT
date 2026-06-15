# Deep Research Agent — Architecture Decisions & Build Plan

> **这份文档是 goal 模式下的操作手册。** 每个阶段包含：目标、具体命令、预期输出、失败处理。
> 按顺序执行，每个阶段做完验证再进下一个。

---

## 一、项目定位（一句话）

**企业级 Deep Research Agent —— 面向"AI 技术选型调研"场景的自主多步研究助手。**
自主分解复杂问题 → 多步检索（本地 7.2MB 知识库 + 可选 Tavily Web 搜索）→ 交叉验证 → 生成带引用溯源的研究结论。

### 目标用户
企业研发团队（架构师/SRE/AI 工程师），需要做技术选型调研（如"对比 Qdrant 和 Milvus""评估 LangGraph vs CrewAI"）。

### 30K 面试要展示的 5 个能力
| 能力 | 体现 |
|---|---|
| Eval | 真实 faithfulness/fact_coverage 指标，可量化 |
| Context Engineering | Working + Long-term Memory 两级记忆 + compaction |
| Agents in Production | Loop Engineering（非 ReAct 单循环）+ Verification Gate |
| LLMOps | OpenTelemetry trace + 成本追踪 + 本地/云端 LLM 混合部署 |
| 系统设计 | 多租户 ACL + HITL + 异步任务 + 可观测 |

---

## 二、技术选型决策（全部基于调研，非凭感觉）

### 1. LLM：本地 Qwen3.6-35B-A3B（Q4）+ 云端 DeepSeek-V4 fallback

**模型**：[Qwen3.6-35B-A3B](https://modelscope.cn/models/Qwen/Qwen3.6-35B-A3B)
- 35B 总参数，**仅 3B 激活**（MoE），SWE-bench 73.4%
- Apache 2.0 开源，2026年4月发布
- 编码能力对标 Claude-Sonnet-4.5
- ModelScope 有原版 + AWQ + GGUF Q4_K_M 量化版

**3060 12GB 部署方案**（基于 [Reddit LocalLLaMA 实测](https://www.reddit.com/r/LocalLLaMA/comments/1tjh7az/)）：
- iQ4_XS 量化 + ik_llama.cpp + 部分 CPU offload → 30-110 tok/s
- 显存预算：BGE-M3 ~2GB + reranker ~1GB + Qwen3.6 Q4 ~8GB = ~11GB（刚好 12GB）
- 用 llama-server 暴露 OpenAI 兼容 API（`localhost:8080`）

**双卡 3060（24GB）**：Q4_K_M 全 GPU，100-240 tok/s

**云端 fallback**：本地 LLM 失败/质量不够 → SenseNova DeepSeek-V4

**面试话术**："混合部署——常规推理用本地 Qwen3.6-35B-A3B（3B 激活的 MoE，单卡 3060 可跑），复杂推理 fallback 到云端 DeepSeek-V4。这种架构降低 API 成本，同时保证质量。"

### 2. Agent 架构：Loop Engineering 三阶段（不用 LangGraph/CrewAI）

**基于**：[Data Science Dojo Loop Engineering 指南](https://datasciencedojo.com/blog/agentic-loops-explained-from-react-to-loop-engineering-2026-guide/)、[Egnyte Deep Research 架构](https://www.egnyte.com/blog/post/inside-the-architecture-of-a-deep-research-agent)、[Claude Code 源码分析](https://github.com/VILA-Lab/Dive-into-Claude-Code)

**Loop Engineering 核心公式**：`Loop = Trigger + Verifiable Goal + Agent + Verification + Guardrails + Memory`

**三阶段架构**：
```
阶段 1: PLANNER
  用户问题 → LLM 分解成子问题列表（线性，预留 DAG 升级）
  例："对比 Qdrant 和 Milvus" →
    ["Qdrant 的架构和特性", "Milvus 的架构和特性", "性能 benchmark 对比", "适用场景对比"]

阶段 2: RESEARCHER（每子问题一个独立 subagent）
  for each sub_question:
    ReAct 循环:
      Think → local_search → Observe
      → Reflect: "信息够了吗?" → 不够就换 query 再搜
    够了 → 存入 Verified Facts（去重 + 优先级）
  Compaction: 上下文超限时智能摘要（参考 Claude Code）

阶段 3: SYNTHESIZER + VERIFICATION GATE
  LLM 综合 Verified Facts → 带引用 [1][2] 的回答
  sentence_level_grounding 检查 faithfulness
  gold_fact 匹配检查 coverage
  没通过 → 回到阶段 2 补搜（Loop Engineering 的核心：不信任 LLM 自评）
```

**为什么不用 LangGraph**：
- LangGraph 适合复杂有状态工作流（多节点分支），但 Deep Research 的核心是三阶段顺序流程
- LangGraph 把状态绑死在 StateGraph，自定义 memory 层受限
- commit 75655b8 已 kill LangGraph，不再回头

**为什么自研**：
- Claude Code 的循环也是简单的 while-loop（[VILA-Lab 源码分析确认](https://github.com/VILA-Lab/Dive-into-Claude-Code)）
- 自研 = 每行代码都能讲清楚为什么
- 面试加分：理解底层比用框架重要

### 3. 向量库：Qdrant（保留）

- payload filter 支持 ACL 预过滤（向量检索时过滤，不是事后过滤）
- 单机 Rust 实现，内存安全
- 单二进制部署，无外部依赖（对比 Milvus 需要 etcd+MinIO+Pulsar）

### 4. Embedding：BGE-M3（统一，清掉 Qwen3 混乱）

- 支持 dense + sparse + ColBERT 三路向量
- nDCG@10=0.674（[Agentset benchmark](https://agentset.ai/embeddings/compare/baaibge-m3-vs-qwen3-embedding-06b)），优于 Qwen3 的 0.656
- 3060 上 ~2GB 显存

### 5. Reranker：bge-reranker-v2-m3

- 默认设置下优于 Qwen3-Reranker-0.6B（[GitHub issue #82](https://github.com/QwenLM/Qwen3-Embedding/issues/82)）
- 轻量 ~1GB 显存

### 6. Chunking：按格式适配

| 格式 | 策略 |
|---|---|
| Markdown | 层次化标题递归（已有 chunking.py） |
| HTML | html2text 转 MD → 递归 |
| PDF | pymupdf4llm 转 MD → 递归 |

所有格式最终统一到 Markdown 再切。chunk size 512 tokens + 64 overlap。

### 7. 数据源：4 类（已构建完成）

| 来源 | 文件数 | 大小 |
|---|---|---|
| papers/（arXiv 全文） | 126 | 6.3 MB |
| official_docs/（Qdrant/Milvus 深度页） | 31 | 577 KB |
| agent_frameworks/（8 个框架 README） | 8 | 114 KB |
| vector_dbs/ + embeddings/ + blogs/ | 12 | 192 KB |
| **总计** | **178** | **7.2 MB** |

---

## 三、阶段执行计划

### 阶段 2-A：reindex 入库（让 local_search 有真数据）

**目标**：把 178 个研究文档切分、embed、写入 Qdrant + BM25。

**命令**：
```bash
# 确认 .env 指向正确的文档目录
# DOCS_DIR=data/docs_research (已设)
# QDRANT_PATH=data/qdrant_local (已设)

# 确保 embedding 模型路径正确
# .env 里 EMBEDDING_MODEL_NAME 或 QWEN_EMBEDDING_MODEL_PATH
# 建议统一为 BGE-M3：EMBEDDING_MODEL_NAME=BAAI/bge-m3

# 跑 reindex
python scripts/reindex.py
```

**预期输出**：
- "无节点可索引" → 不应出现（178 个文件存在）
- "embedding 进度 50/XXX" → 正常
- "Qdrant 索引完成: XXX 个节点" → XXX 应 > 500（178 文件 × 平均 4-6 chunk）
- "BM25 语料已写入" → 正常

**验证**：
```python
from app.vector_index import get_vector_index
from app.retrieval_pipeline import retrieve_scored_nodes
from app.config import get_settings
idx = get_vector_index()
r = retrieve_scored_nodes(idx, "Qdrant filtering", 5, get_settings())
print(f"Retrieved {len(r.nodes)} chunks")
for n in r.nodes[:3]:
    print(f"  score={n.score:.3f} {n.node.metadata.get('file_name','')}")
```
预期：返回 ≥3 chunks，score > 0，file_name 是 qdrant_filtering.md 等。

**失败处理**：
- "Qdrant collection not found" → 先跑 reindex
- "embedding model not found" → 检查 EMBEDDING_MODEL_NAME 或本地路径
- OOM → 降低 batch_size 或用 CPU 模式（INFERENCE_DEVICE=cpu）

### 阶段 2-B：实现 Loop Engineering 三阶段架构

**新增文件**：
- `app/agent/research_harness.py`（三阶段主循环）
- `app/agent/memory.py`（Working + Long-term Memory + compaction）
- `app/agent/planner.py`（子问题分解）
- `app/routes_research.py`（/agent/research SSE 端点）

**research_harness.py 核心逻辑**：
```python
async def run_research(question: str, ...) -> ResearchResult:
    # 阶段 1: Plan
    sub_questions = await planner.decompose(question)

    # 阶段 2: Research (每子问题一个 ReAct 循环)
    memory = ResearchMemory()
    for sq in sub_questions:
        facts = await researcher.investigate(sq, memory, max_steps=4)
        memory.add_verified_facts(facts)

    # 阶段 3: Synthesize + Verify
    answer = await synthesizer.compose(question, memory)
    faithfulness = sentence_level_grounding(answer, memory.all_evidence)
    if faithfulness.passed:
        return ResearchResult(answer, memory.citations, faithfulness)
    else:
        # Loop Engineering: 没通过就补搜
        # 回到阶段 2 补一个子问题
```

**验证**：输入"对比 Qdrant 和 Milvus 的写入性能"，Agent 应：
1. 分解出 2-4 个子问题
2. 每个子问题检索 3-5 个 chunk
3. 综合成带 [1][2] 引用的回答
4. faithfulness 检查通过

### 阶段 3：评测体系

**新增文件**：
- `data/eval/research/*.jsonl`（30 个研究问题 + gold facts）
- `scripts/run_eval_research.py`（faithfulness + fact_coverage + avg_steps）

**评测流程**：
1. 用 LLM 从知识库反向生成 50 个问题 + 预期事实
2. 人工筛选 30 个高质量评测 case
3. 跑评测，记录 baseline 数字
4. 产出 `docs/RESEARCH-EVAL.md`

### 阶段 4：Tavily + 结构化报告 + 面试包装

- 接入 Tavily API（web_search + fetch_page 实现）
- 升级输出为 Markdown 报告（背景→对比→结论→参考文献）
- OpenTelemetry trace
- 重写 README + 面试话术

---

## 四、LLM 部署配置（服务器）

### 本地 Qwen3.6-35B-A3B（3060 服务器）

```bash
# 1. 装 ik_llama.cpp（比官方 llama.cpp 在 MoE 上快 ~1.4x）
git clone https://github.com/ikawrakow/ik_llama.cpp
cd ik_llama.cpp && mkdir build && cd build
cmake .. -DGGML_NATIVE=ON -DGGML_LTO=ON -DGGML_CUDA=ON
make -j

# 2. 下载 Qwen3.6-35B-A3B GGUF iQ4_XS（~17GB，12GB VRAM 可用）
# 从 ModelScope: modelscope.cn/models/Merkyor/Qwen3.6-35B-A3B-GGUF-imatrix
# 选 iQ4_XS 版本

# 3. 启动 OpenAI 兼容 API 服务
./llama-server -m Qwen3.6-35B-A3B-iQ4_XS.gguf \
  --host 0.0.0.0 --port 8080 \
  -ngl 99 -c 8192 \
  --mlock

# 4. 配置项目 .env
# LLM_BASE_URL=http://<server-ip>:8080/v1
# LLM_MODEL=qwen3.6-35b-a3b
```

### 云端 fallback（SenseNova DeepSeek-V4）
- 已配置在 app/llm.py
- 本地 LLM 失败时自动切换

---

## 五、goal 模式操作清单

当用户暂离、我需要独立运行时，按以下顺序执行：

### Step 1: reindex
```bash
cd "E:/经项目/rag-kb-project"
python scripts/reindex.py
# 预期：500+ chunks 写入 Qdrant + BM25
```

### Step 2: 验证检索
```python
python -c "
from app.vector_index import get_vector_index
from app.retrieval_pipeline import retrieve_scored_nodes
from app.config import get_settings
idx = get_vector_index()
r = retrieve_scored_nodes(idx, 'Qdrant vs Milvus performance', 5, get_settings())
print(f'{len(r.nodes)} chunks retrieved')
for n in r.nodes: print(f'  {n.score:.3f} {n.node.metadata.get(\"file_name\",\"\")[:40]}')
"
```

### Step 3: 实现三阶段架构
- 写 `app/agent/planner.py`（~80 行）
- 写 `app/agent/memory.py`（~120 行）
- 写 `app/agent/research_harness.py`（~250 行）
- 写 `app/routes_research.py`（~100 行）

### Step 4: 端到端测试
```python
python -c "
import asyncio
from app.agent.research_harness import run_research
result = asyncio.run(run_research('对比 Qdrant 和 Milvus 的写入性能'))
print(result.answer[:500])
print(f'\\nFaithfulness: {result.faithfulness_score}')
print(f'Citations: {len(result.citations)}')
print(f'Steps: {result.total_steps}')
"
```

### Step 5: 构建评测集
```bash
python scripts/build_research_eval.py  # 生成 50 个候选问题
# 人工筛选 30 个
python scripts/run_eval_research.py    # 跑评测
```

### Step 6: commit + push 每个阶段

### 失败回滚
- 如果某步报错，不跳过——先修复再继续
- 如果 LLM 调用失败，fallback 到云端 DeepSeek-V4
- 如果 Qdrant 不可用，用 SQLite 内存模式兜底

---

## 六、面试话术模板（3 分钟讲稿）

> "我做了一个企业级 Deep Research Agent，面向技术选型调研场景。
>
> **架构**是 Loop Engineering 三阶段：Planner 分解问题 → Researcher 对每个子问题跑 ReAct 循环（搜→读→反思→存记忆）→ Synthesizer 综合并做句级引用验证。这个架构参考了 OpenAI Deep Research 和 Claude Code 的源码分析。
>
> **技术选型**上，LLM 用本地 Qwen3.6-35B-A3B——3B 激活的 MoE，单卡 3060 可跑，云端 fallback 到 DeepSeek-V4。向量库用 Qdrant（payload filter 做 ACL）。Embedding 用 BGE-M3（dense+sparse 混合）。全部有数据支撑的选型，不是拍脑袋。
>
> **评测**上，我构建了 30 个研究问题的 golden set，用 faithfulness + fact_coverage 两个维度评测。不是 dry-run 假数据。
>
> **工程化**上，有多租户 ACL、HITL 审批、OpenTelemetry trace、成本追踪。这些都是生产级 Agent 的必需品。"
