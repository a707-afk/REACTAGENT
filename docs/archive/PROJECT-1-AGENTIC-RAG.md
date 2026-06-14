# 项目一：Agentic RAG 法律知识智能体（生产级）

> 定位：对标上海 25K+ 的 **RAG 工程方向**岗位
> 一句话：一个以 LLM 为决策中心的法律知识问答系统，能自主判断是否检索、检索哪个库、结果够不够、回答有没有幻觉，并在不够时自我纠正。
> 区别于练手项目：不是"检索→生成"的直线流水线，而是带**自适应检索 + 自纠正闭环**的 Agentic RAG。

---

## 0. 为什么是这个项目（讲给面试官听的立项逻辑）

法律领域天然适合展示 RAG 的所有难点：

1. **语义鸿沟极大**：用户说"欠钱不还多久过期"，知识库里写的是"诉讼时效"。纯向量检索会漏，纯关键词也会漏 → 必须混合检索
2. **文档类型异构**：法条、司法解释、判例、法律问答，四种结构完全不同 → 必须做分库路由
3. **精确性要求高**：法条编号（民法典第188条）必须精确命中 → BM25 不可或缺
4. **幻觉零容忍**：法律回答错了会误导用户 → 必须做引用溯源和幻觉检测
5. **多步推理**：分析一个案情往往需要"先定性→查相关法条→找类案→给建议"多步 → 必须用 Agent 而非单次检索

这 5 个特征让你能在一个项目里把 RAG 的所有核心技术都讲清楚，而且每个技术选择都有真实的业务理由。

---

## 1. 系统总体架构

```
                          ┌─────────────────────────────────────────┐
                          │              客户端 (Web)                 │
                          │     React + TypeScript + SSE 流式接收      │
                          └──────────────────┬──────────────────────┘
                                             │ HTTP / SSE
                          ┌──────────────────▼──────────────────────┐
                          │           API 网关层 (FastAPI)            │
                          │   鉴权 / 限流 / 请求校验 / trace_id 注入   │
                          └──────────────────┬──────────────────────┘
                                             │
          ┌──────────────────────────────────▼─────────────────────────────────┐
          │                  Agentic RAG 编排层 (LangGraph)                       │
          │                                                                      │
          │   ┌─────────┐   ┌──────────┐   ┌─────────┐   ┌──────────┐  ┌───────┐ │
          │   │ Router  │──▶│Retriever │──▶│ Grader  │──▶│Generator │─▶│Halluc.│ │
          │   │ 路由决策 │   │ 自适应检索│   │ 文档评分 │   │ 受约束生成│  │ 检测  │ │
          │   └─────────┘   └────▲─────┘   └────┬────┘   └────▲─────┘  └───┬───┘ │
          │        │             │ 重检索       │ 不够        │ 带反馈重生成 │     │
          │        │             └─────────────┘             └────────────┘     │
          │        │ 直接回答 / 联网                                              │
          │   状态: messages, query, docs, grade, answer, iterations, citations  │
          │   保护: max_iter=3 / 循环检测 / 异常降级                              │
          └──────────────────────────────────┬─────────────────────────────────┘
                                             │
   ┌─────────────────────┬──────────────────┼──────────────────┬─────────────────────┐
   │                     │                  │                  │                     │
┌──▼───────┐    ┌────────▼────────┐  ┌──────▼──────┐   ┌────────▼────────┐  ┌─────────▼────────┐
│ 检索引擎  │    │   向量数据库     │  │  BM25 索引   │   │   Rerank 服务   │  │   LLM 服务        │
│ 混合+RRF  │    │ Qdrant(4分库)    │  │  (倒排)      │   │ bge-reranker    │  │ Qwen2.5 / API    │
└──────────┘    └─────────────────┘  └─────────────┘   └─────────────────┘  └──────────────────┘
   │                     │                  │                  │                     │
   └─────────────────────┴──────────────────┼──────────────────┴─────────────────────┘
                                             │
          ┌──────────────────────────────────▼─────────────────────────────────┐
          │                       横切基础设施                                    │
          │  缓存(Redis三级) │ 可观测(Langfuse+Prometheus) │ 评估(离线评估集)     │
          └──────────────────────────────────────────────────────────────────┘
```

---

## 2. 技术栈（大型项目标准配置）

| 层 | 技术选型 | 为什么选它（面试可讲） |
|----|---------|---------------------|
| 语言 | **Python 3.11** | AI 生态最完整；3.11 性能比 3.9 提升约 25% |
| Web 框架 | **FastAPI** | 原生异步、自动 OpenAPI 文档、Pydantic 校验、SSE 友好 |
| Agent 编排 | **LangGraph** | 图状态机，天然支持循环和条件分支，比 LangChain 的链式更适合 Agentic RAG |
| RAG 框架 | **LlamaIndex** | 数据连接和索引抽象成熟，比纯手写省时间 |
| 向量库 | **Qdrant** | Rust 实现性能好，载荷过滤强（可按分库筛选），支持分布式 |
| 稀疏检索 | **BM25**（自建倒排 / Elasticsearch 可选） | 法条编号精确匹配必需 |
| Embedding | **bge-large-zh-v1.5**（默认）+ 对比实验 | 中文垂直域稳定，CPU 也能跑 |
| Rerank | **bge-reranker-v2-m3** | 开源 Cross-Encoder，精排提升明显 |
| LLM | **Qwen2.5-7B/14B**（本地 vLLM）+ **API 兜底** | 数据合规 + 成本可控；vLLM 提供高吞吐推理 |
| 缓存 | **Redis** | 三级缓存（精确/语义/会话） |
| 可观测 | **Langfuse**（LLM链路）+ **Prometheus + Grafana**（系统指标） | 全链路追踪 + 性能监控 |
| 数据库 | **PostgreSQL**（元数据/会话/反馈） | 成熟稳定，支持 JSON 字段 |
| 部署 | **Docker Compose**（开发）+ **K8s**（生产可选） | 容器化标配 |
| 推理加速 | **vLLM** | PagedAttention，吞吐比原生 transformers 高数倍 |
| 任务队列 | **Celery + Redis**（索引构建等异步任务） | 解耦耗时任务 |
| 前端 | **React + TypeScript + Vite + TailwindCSS** | 现代前端标配 |

> **选型讲法要点**：每一个组件你都要能回答"为什么不用 X"。例如"为什么不用 Chroma？"→ 开发阶段我用 Chroma 因为零运维，但生产选 Qdrant 因为它的载荷过滤能在检索时直接按法律分库筛选，且支持水平扩展。代码里做了 `VectorStore` 抽象层，切换成本很低。

---

## 3. 核心模块详解

### 3.1 数据层：法律语料全流程处理

这是 JD 里反复强调的"知识库数据全流程处理能力"，必须做扎实。

```
数据获取 → 清洗 → 结构化 → 分块 → 向量化 → 索引构建 → 评估就绪
```

**四个分库**：
| 分库 | 内容 | 结构特点 | 分块策略 |
|------|------|---------|---------|
| statute（法条） | 法律条文 | 篇/章/节/条，编号严格 | 按"条"分块，保留章节路径 |
| interpretation（司法解释） | 最高法解释 | 条款式 | 按条分块 |
| case（案例） | 裁判文书 | 案情/争议/判决/依据 | 按语义段落分块（父子块） |
| faq（法律问答） | 常见问题 | 问答对 | 一问一答一块 |

**数据来源**（不用自己造，文档已在 `docs/DATA-SOURCES.md`）：
- 国家法律法规数据库（flk.npc.gov.cn）— 法条
- 中国裁判文书网 — 判例
- 法信、北大法宝公开部分 — 司法解释
- 目标规模：3K-10K 文档（够展示生产级问题，又不会token爆炸）

**关键工程点**：
- **增量索引**：新文档只计算新增部分的 embedding，不全量重建（面试高频问）
- **元数据设计**：每个 chunk 带 `{law_name, article_no, chapter, effective_date, doc_type}`，支持检索时过滤
- **版本管理**：法律会修订，记录 `effective_date`，避免返回已废止条款

### 3.2 理解层：Router（路由决策）

Router 是 Agentic RAG 的第一个决策节点。LLM 判断这个问题该怎么处理：

```python
# 伪代码：路由决策
def router_node(state):
    query = state["query"]
    # 三级级联，快路径优先
    # 1. 规则快判：法条编号正则 → 直接路由到 statute 库
    if re.search(r'第\s*\d+\s*条', query):
        return {"route": "statute", "need_retrieval": True}
    # 2. embedding 相似度：和四个分库的 anchor 比
    domain = embedding_route(query)  # 返回最相似分库 + 置信度
    if domain.confidence > THRESHOLD:
        return {"route": domain.name, "need_retrieval": True}
    # 3. LLM 兜底：判断是闲聊/法律问题/需要联网
    decision = llm_route(query)
    return decision  # {direct_answer | retrieval(库) | web_search}
```

**面试讲法**：
- "为什么三级级联不直接全用 LLM？" → 90% 的查询规则或 embedding 就能判定，LLM 兜底只处理 10% 的疑难，省成本省延迟
- "路由错了怎么办？" → Grader 节点会发现召回文档不相关，触发重新路由
- 指标：路由准确率（人工标注测试集），目标 90%+

### 3.3 检索层：自适应混合检索 + RRF

```python
def retriever_node(state):
    query = state["query"]
    route = state["route"]
    # 在指定分库内混合检索
    bm25_results = bm25_search(query, collection=route, top_k=20)
    vector_results = vector_search(query, collection=route, top_k=20)
    # RRF 融合（不是 max，不是线性加权）
    fused = rrf_fusion(bm25_results, vector_results, k=60)
    # Rerank 精排
    reranked = reranker.rerank(query, fused, top_k=5)
    return {"docs": reranked}
```

**RRF 公式**：`score(d) = Σ 1/(k + rank_i(d))`，k=60

**面试核心对比**（必背）：
| 融合方式 | Top-1 命中率 | 问题 |
|---------|------------|------|
| 仅向量 | XX% | 法条编号查询命中差 |
| 仅 BM25 | XX% | 口语化查询命中差 |
| max() 融合 | XX% | 偏向单路强势结果 |
| **RRF 融合** | **XX%** | 对分数尺度鲁棒，综合最优 |
| RRF + Rerank | **XX%** | 精排再提升 |

> 这张表是你项目的"镇店之宝"，每个数字都要是你真跑出来的。

### 3.4 评估层：Grader（文档评分）— Agentic RAG 的灵魂

这是和普通 RAG 最大的区别。检索完不直接生成，先让 LLM 判断"这些文档够不够回答问题"：

```python
def grader_node(state):
    docs = state["docs"]
    query = state["query"]
    # LLM 逐个评分文档相关性
    grades = [grade_relevance(query, doc) for doc in docs]
    relevant_docs = [d for d, g in zip(docs, grades) if g.score > 0.7]

    if len(relevant_docs) == 0:
        # 一篇都不相关 → 改写 query 重新检索
        if state["iterations"] < MAX_ITER:
            new_query = rewrite_query(query)
            return {"query": new_query, "action": "retry", 
                    "iterations": state["iterations"] + 1}
        else:
            # 达到最大迭代 → 降级
            return {"action": "fallback"}  # 联网 / 转人工 / 拒答
    return {"docs": relevant_docs, "action": "generate"}
```

**面试核心认知**（来自2026面试真题）：
- **终止条件由"上下文充分性"决定，不是固定检索次数**。简单问题1次够，复杂问题可能要3次
- "Grader 阈值怎么定？" → 测试集上画 precision-recall 曲线，选 F1 最高点
- "Grader 用 LLM 会不会太慢？" → 可以批量评分；高价值场景值得；也可以先用轻量 NLI 模型初筛

### 3.5 生成层：Generator（受约束生成）+ 引用注入

```python
def generator_node(state):
    docs = state["docs"]
    query = state["query"]
    # Prompt 约束：只基于证据，标注引用，不确定就说不确定
    prompt = build_prompt(query, docs, 
        constraints=["仅依据提供的法律条文回答",
                     "每个论点标注来源 [1][2]",
                     "证据不足时明确告知用户"])
    answer = llm.generate(prompt, stream=True)  # SSE 流式
    citations = extract_citations(answer, docs)
    return {"answer": answer, "citations": citations}
```

### 3.6 验证层：Hallucination Checker（幻觉检测）+ 自纠正

```python
def hallucination_node(state):
    answer = state["answer"]
    docs = state["docs"]
    # 检查回答的每个论断是否有文档支撑
    unsupported = check_grounding(answer, docs)  # NLI / LLM 判断
    if unsupported:
        if state["iterations"] < MAX_ITER:
            # 带反馈重新生成（告诉 LLM 哪些论断没依据）
            return {"action": "regenerate", 
                    "feedback": unsupported,
                    "iterations": state["iterations"] + 1}
        else:
            return {"action": "return_with_warning"}  # 标记"以下内容请核实"
    return {"action": "done"}
```

**引用溯源升级**（从练手项目的字符串重叠升级）：
- 练手项目：字符串滑窗重叠匹配（0层深度）
- 升级方案：法条级/章节级溯源 + NLI 语义蕴含判断（回答是否被原文蕴含）
- 指标：幻觉率从 XX% 降到 XX%

### 3.7 三层保护（防止 Agent 失控）

| 保护 | 触发条件 | 动作 |
|------|---------|------|
| 最大迭代 | iterations >= 3 | 用已有结果生成 + 标记不确定 |
| 循环检测 | 连续两次相同工具+参数 | 跳出循环，降级 |
| 异常回退 | 工具/LLM 抛异常 | 降级为直接回答，记录失败原因到 trace |

---

## 4. 端到端数据流（一次完整请求）

```
用户问："喝酒后第二天开车算酒驾吗？出了事故怎么赔？"
    ↓
[API网关] 注入 trace_id，鉴权，限流通过
    ↓
[缓存] L1精确未命中 → L2语义缓存相似度0.83未达阈值 → 继续
    ↓
[Router] 规则未命中编号 → embedding 判定为"多意图"（酒驾认定 + 事故赔偿）
         → LLM 判定需要分解为两个子问题，路由到 statute + case
    ↓
[Retriever-1] statute库检索"酒驾认定标准" → BM25+Vector+RRF+Rerank → 5篇
[Retriever-2] case库检索"酒后事故赔偿" → 5篇
    ↓
[Grader] statute 5篇中3篇相关，case 5篇中2篇相关 → 充分，进入生成
    ↓
[Generator] 基于5篇相关文档流式生成 + 标注引用 [1]道交法第91条 [2]...
    ↓
[Hallucination] 检测到"赔偿金额"论断无文档支撑 → 带反馈重新生成（去掉无依据部分）
    ↓
[返回] 流式推送答案 + 引用卡片；写入会话记忆；记录 trace 和指标
```

---

## 5. 评估体系（让项目"系统化"的关键）

### 5.1 评估数据集
- 80-150 条标注测试集，覆盖：单库查询、跨库查询、多意图、口语化、精确编号、无答案（应拒答）
- 每条标注：`{query, expected_docs, expected_answer_points, should_refuse}`

### 5.2 五层指标
| 层 | 指标 | 目标 |
|----|------|------|
| 路由 | 分库路由准确率 | ≥ 90% |
| 检索 | Top-1 / Top-5 命中率、MRR、nDCG | Top-5 ≥ 85% |
| 评分 | Grader 准确率（与人工标注一致率） | ≥ 85% |
| 生成 | 回答准确率、引用准确率、幻觉率 | 幻觉率 ≤ 5% |
| 端到端 | 任务成功率、P99 延迟、平均 token 成本、缓存命中率 | P99 ≤ 3s |

### 5.3 坏例归因（5类）
1. 文档不存在（知识库未收录）
2. 分块切碎（答案跨块）
3. 语义鸿沟（口语 vs 术语）
4. 路由错误（路由到错误分库）
5. 排序错误（召回了但排名太低被截断）

> 每次优化后跑回归，对比前后指标，记录到决策档案。这就是"有基线有结果"。

---

## 6. 分阶段里程碑（约 120-150 小时）

| 阶段 | 内容 | 产出 | 工时 |
|------|------|------|------|
| 阶段0 | 数据流水线 + 四分库 + 评估集 + 跑基线 | 第一批指标数字 | 25h |
| 阶段1 | 混合检索 + RRF + Rerank + 分库路由 | 检索层 AB 数据 | 25h |
| 阶段2 | LangGraph 改造为 Agentic 闭环（Router→Grader→Halluc） | Agentic RAG 雏形 | 30h |
| 阶段3 | 幻觉检测 + 引用溯源升级 + 自纠正循环 | 幻觉率数据 | 20h |
| 阶段4 | 三级缓存 + 可观测（Langfuse+Prometheus） | 性能看板 | 15h |
| 阶段5 | SSE 流式 + React 前端 + Docker 部署 | 可演示系统 | 20h |
| 阶段6 | 全量评估 + 决策档案 + 面试稿 | 完整文档 | 15h |

---

## 7. 面试讲法（STAR-L）

**S（情境）**：法律知识检索中，口语化表述与专业术语语义鸿沟严重，且法律问答对幻觉零容忍，普通"检索→生成"流水线在多步推理问题上准确率不足。

**T（任务）**：设计并实现一个以 LLM 为决策中心的 Agentic RAG 法律问答系统。

**A（行动）**：
- 构建四分库（法条/解释/案例/问答）知识库 + 全流程数据处理（含增量索引）
- 混合检索 BM25+Vector，RRF 融合替代 max()，Top-1 提升 XX pp
- 三级级联分库路由，准确率 XX%
- 用 LangGraph 实现 Router→Retriever→Grader→Generator→Hallucination 闭环，终止条件基于上下文充分性
- 幻觉检测 + 自纠正循环，引用溯源升级到法条级，幻觉率从 XX% 降到 XX%
- 三级缓存 + Langfuse 全链路追踪 + Prometheus 监控

**R（结果）**：Top-5 命中率 XX%，幻觉率 ≤ 5%，P99 延迟 XX ms，缓存命中率 XX%。

**L（亮点/反思）**：
- 分库路由比换 Embedding 模型性价比高得多
- Agentic 闭环在多跳问题上比固定流水线准确率提升显著
- 如果重做，会更早引入评估集（先有标尺再优化）

### 必背追问
1. "这和普通 RAG 区别？" → 普通 RAG 是固定流水线，我的是 LLM 决策的闭环，能自适应检索和自纠正
2. "Grader 怎么避免误判？" → 阈值用 PR 曲线标定 + 人工标注一致率验证
3. "自纠正会不会死循环？" → 三层保护：最大迭代/循环检测/异常降级
4. "成本怎么控制？" → 快路径规则路由省 LLM 调用 + 三级缓存 + 小模型处理简单问题
5. "怎么扩展到 10 万文档？" → Qdrant 分布式 + 载荷过滤 + 量化压缩(PQ)
