# 当前项目深入收尾方案（做到底）

> 对象：现有 `rag-kb-project`（企业 AI-Ops 领域 RAG），不是从零，而是把已有的"功能齐全雏形"推到"能讲清楚、有完整数据、生产级"的终态。
> 已核实现状基于实际代码（`app/agent_graph/nodes.py`、`multi_graph.py`、`retrieval_pipeline.py`、`citation_verify.py` 等）+ 真实基线（企业集 50 题：Top-1 0.64 / Top-5 0.80 / 域 Top-1 0.72）。
> 配套：领域认知看 `RAG-AGENT-KNOWLEDGE-MAP.md`，决策记录写 `DECISION-LOG.md`。

---

## 一、当前项目体检（基于真实代码）

### 已经做得不错的（这些是你的资产，面试可讲）
| 能力 | 现状 | 面试价值 |
|------|------|---------|
| 混合检索 BM25+Vector+Rerank | 已落地 `retrieval_pipeline.py` | 中，但融合是 max 不是 RRF |
| 域路由（规则+embedding+LLM 三层） | 已落地，有 `router_trace` | 高，三级级联架构是亮点 |
| **权限前置过滤**（tenant/audience/密级） | 已落地 `access_prefilter.py` | **高，企业级特性，很多 demo 没有** |
| 策略引擎（规则+向量+LLM 分层 + 审计） | 雏形可升级 `app/policy/` | 高，安全护栏是企业刚需 |
| 行为护栏 + 拦截评测 | 已落地，有 intercept 数据 | 高，有量化（边界 recall 1.0） |
| 真实评估体系 | 50 题企业集 + 四组合矩阵 | **高，有基线有数据就赢一半** |
| 权限评测 | Forbidden 4/4、Expect 88.5% | 高，量化扎实 |
| Qdrant 后端门面 | 代码就绪，默认 Chroma | 中，体现抽象设计 |

> 结论：这个项目**不是玩具**，它已经有企业级 RAG 的骨架（权限+策略+评估），这是很多候选人没有的。问题在于"最后一公里"——Agent 是假的、检索可以更强、引用太弱、没有自纠正、没缓存、没前端、可观测没接。

### 致命短板（必须收尾的）
| 短板 | 真实现状（已核实代码） | 严重度 |
|------|---------------------|--------|
| **Agent 是直线流不是 Agent** | `nodes.py` 条件边只向前短路到 finalize，gate 失败直接结束，**从不回环重试/改写/自纠正**；`multi_graph` supervisor 只路由到线性流或 escalation 桩 | **P0 致命** |
| 融合用 max() 非 RRF | `retrieval_pipeline.py` 分数归一化后合并 | **P0** |
| 引用是字符串重叠 | `citation_verify.py` 只算 overlap_ratio | **P0** |
| 无幻觉检测/自纠正 | 完全没有 | **P0** |
| 无缓存 | 完全没有 | P1 |
| 可观测只设计未接 | `observability.py` 有结构化日志，但未接 Langfuse/Prometheus | P1 |
| 无像样前端 | 只有 Gradio | P1 |
| Query Rewrite 无 AB 数据 | 有 `auto` 启发式，但没量化开/关召回差 | P1 |

---

## 二、收尾总目标与路线（接续路线图 E/F，定义 G-K）

你现在在 E（Agent MVP）/ F（可观测设计）。收尾定义新阶段 **G→K**：

```
G. 检索层补强：RRF 融合 + Query Rewrite AB 量化         （吃透检索，拿数据）
H. Agent 真改造：直线流 → Agentic 闭环（评分+重试+自纠正） （消灭最大短板）
I. 可信层：引用语义级溯源 + 幻觉检测                      （差异化卖点）
J. 工程化：三级缓存 + 可观测接入(Langfuse+Prometheus)     （生产级信号）
K. 交付：SSE 流式 + React 前端 + Docker 部署 + 决策档案    （可演示+能讲）
```

每个阶段都"先有基线 → 改造 → 重跑评估 → 记录前后数据 → 写决策档案"。

---

## 三、阶段 G：检索层补强（约 20h）

### G1. 融合策略 max() → RRF（保留旧法做 AB）

**现状**：`retrieval_pipeline.py` 把 BM25 和向量分数归一化后取合并（偏 max 语义）。

**改造**：
- 新增 `hybrid_fusion` 配置项：`max`（旧）| `rrf`（新），默认保留 max 以便 AB
- 实现 RRF：`score(d) = Σ 1/(k + rank_i(d))`，k 默认 60，做成配置
- 写网格搜索脚本：k=20/40/60/80，在企业集 50 题上跑 Top-1/Top-5

**预期产出**：
| 配置 | Top-1 | Top-5 | 备注 |
|------|-------|-------|------|
| max（现状基线） | 0.64 | 0.80 | 已有 |
| RRF k=60 | ? | ? | 待测 |
| RRF + 调优 k | ? | ? | 待测 |

> ⚠️ 关键：先复跑一次现状基线确认 0.64/0.80 能复现，再改 RRF。否则你不知道是 RRF 的功劳还是环境差异。

**决策档案 D-G1**：max vs 线性 vs RRF 的对比 + 你的选择 + k 值调优数据。

### G2. Query Rewrite AB 量化

**现状**：`query_rewrite.py` 有 `auto` 启发式门控，但**没有开/关的召回率对比数据**。

**改造**：
- 跑两次评估：`QUERY_REWRITE_MODE=off` vs `on`，对比 Top-5 命中率
- 分析哪类问题改写有用（口语化）、哪类反而有害（精确术语）

**决策档案 D-G2**：Query Rewrite 的真实收益数据 + auto 启发式为什么是合理默认。

---

## 四、阶段 H：Agent 真改造（约 35h，重中之重）

### 这是整个收尾最值钱的部分。把假 Agent 变成真 Agent。

**现状（已核实）**：
```
policy → retrieve → gate → draft → finalize
            ↑          │
            │          ↓ 失败时
            └──(无)── 直接 finalize（不回环、不重试、不改写、不自纠正）
```
这是 Pipeline。面试官看 `nodes.py` 的条件边就知道。

**目标（Agentic 闭环）**：
```
policy → retrieve → grade(新) ─不够─→ rewrite&retry(新,回环) ─┐
            ↑                                                  │
            └──────────────────────────────────────────────────┘
         grade ─够─→ draft → hallucination_check(新) ─有幻觉─→ regenerate(回环)
                                      │
                                   ─通过─→ finalize
         三层保护：max_iter / 循环检测 / 异常降级
```

### H1. 新增 Grader 节点（文档充分性评分）
- 在 `gate` 之后或替代部分 gate 逻辑，新增 `node_grader`
- LLM 判断检索到的 chunk 是否足够回答问题（不只是相似度阈值）
- 不够 → 触发改写重检索（回环），而不是直接 finalize
- 阈值用 PR 曲线标定（不能拍脑袋）

### H2. 新增重检索回环（自适应检索）
- 在 LangGraph 里加条件边：grade 不通过 + iterations < max → 回到 retrieve（带改写后的 query）
- 这是和现状最大的区别：**现在失败就结束，改造后失败会自我修正**

### H3. 新增 Hallucination Check 节点
- `draft` 之后新增 `node_hallucination`
- 检查草稿的论断是否被检索证据支撑（NLI 或 LLM 自检）
- 有幻觉 → 带反馈回到 draft 重新生成（回环）

### H4. 三层保护
- `state` 增加 `iterations` 字段（`state.py` 已有 state 结构，扩展它）
- max_iter=3、连续相同 query+工具检测、异常降级（复用现有 `audit_trace` 记录失败）

### H5. multi_graph 升级为真多 Agent（可选加分）
- 现状 supervisor 只路由线性流或桩。可升级为：检索 Agent / 审查 Agent 分工
- 这是项目二的方向，当前项目可做轻量版作为加分

**预期产出**：
| 指标 | 直线流（现状） | Agentic 闭环 |
|------|--------------|-------------|
| 多跳/复杂问题准确率 | ? | ? |
| gate 失败后的挽回率 | 0%（直接结束） | ?% |
| 幻觉率 | 未测 | ?% |

**决策档案 D-H1~H4**：为什么这些点让 LLM 决策、终止条件设计、Grader 阈值、三层保护。

> ⚠️ 亲手做：构造一个"第一次检索不够、改写后命中"的 case，亲眼看到闭环工作。这是面试讲"自纠正"的底气。

---

## 五、阶段 I：可信层升级（约 18h）

### I1. 引用溯源：字符串重叠 → 语义级

**现状**：`citation_verify.py` 的 `citation_overlap_ratio` 只算字符串滑窗重叠（0层深度）。

**改造**：
- 升级为句子级溯源：把回答拆句，每句找最支撑它的 chunk（embedding 相似度或 NLI）
- 标注每个论断的来源 chunk + 支撑强度
- 无足够支撑的句子标记出来（连接到幻觉检测）

### I2. 幻觉率统计与治理
- 在评估集上人工标注幻觉基线
- 接入 H3 的幻觉检测后，统计治理效果

**决策档案 D-I1**：引用溯源升级方案 + 幻觉率从 XX% 到 XX%。

---

## 六、阶段 J：工程化补强（约 18h）

### J1. 三级缓存
- L1 精确匹配（query hash）→ Redis
- L2 语义缓存（embedding 相似度 > 阈值）→ 阈值用 PR 曲线标定
- L3（可选）会话级
- ⚠️ 缓存一致性：reindex 后失效相关缓存

### J2. 可观测性接入（把设计落地）
- **现状**：`observability.py` 有结构化日志 + `OBSERVABILITY-DESIGN.md` 设计稿，但未接后端
- 接 Langfuse：追踪 Agent 决策树（policy→grade→retry→draft→halluc 全链路）
- 接 Prometheus + Grafana：QPS、延迟分布、各节点耗时、缓存命中率

**预期产出**：性能看板 + 一次真实的瓶颈定位案例（面试讲"我怎么排查问题"）。

**决策档案 D-J1/J2**：缓存阈值标定 + 可观测方案。

---

## 七、阶段 K：交付层（约 22h）

### K1. SSE 流式
- `routes_agent.py` / `routes_rag.py` 增加流式端点
- 流式推送 Agent 的每步决策（policy/grade/retry/draft）到前端

### K2. React + TypeScript 前端
- 替代 Gradio，做一个能展示"检索结果 + 引用卡片 + Agent 决策过程"的界面
- 体现全栈能力

### K3. Docker 部署
- `docker-compose.yml` 已有 Qdrant，补全 app + Redis + 前端
- 在租的服务器上跑通，录演示视频

### K4. 决策档案 + 面试稿
- 汇总 G-K 所有前后对比数据成一张总表
- 决策档案补齐到 15+ 条
- STAR-L 简历描述 + 录音模拟面试

---

## 八、收尾后的完整指标看板（目标）

| 层 | 指标 | 现状 | 目标 |
|----|------|------|------|
| 检索 | Top-1 / Top-5（企业集50题） | 0.64 / 0.80 | RRF 后提升 |
| 检索 | Query Rewrite 收益 | 无数据 | +X pp（有AB） |
| 路由 | 域 Top-1 | 0.72 | 维持/提升 |
| 权限 | Forbidden / Expect | 4/4 / 88.5% | 维持 |
| 护栏 | 边界 recall | 1.0 | 维持 |
| Agent | gate 失败挽回率 | 0% | >0（自纠正） |
| Agent | 复杂问题准确率 | 未测 | 建立基线+提升 |
| 可信 | 幻觉率 | 未测 | 建立基线+降低 |
| 工程 | P99 延迟 / 缓存命中率 | 未测 | 建立看板 |

---

## 九、为什么这条路对你最划算

1. **不浪费已有资产**：权限过滤、策略引擎、评估体系、50题基线都是真东西，扔了可惜。在它基础上收尾，性价比远高于重做。
2. **企业域 + 完整工程链路**正好对标上海那批"企业级知识库构建"的 JD（安续、金仕达那种）。
3. **现状到生产级的差距是清晰可量化的**：每补一个短板都有前后数据，这就是"系统化"的证据。

### 和两个新项目（PROJECT-1/2）的关系
- **本方案 = 把当前企业项目做到底**，作为你的"主力项目/第一项目"，因为它最成熟、资产最多
- **PROJECT-1（法律 Agentic RAG）**：如果时间充裕，可作为第二个 RAG 项目，或者干脆把本项目的 Agentic 改造经验直接用法律域重做一遍（换数据不换架构，省力）
- **PROJECT-2（多 Agent）**：作为 Agent 方向的进阶项目

> 建议：**先把当前项目按 G→K 做到底**（约 130h），它能独立支撑面试。行有余力再考虑第二项目。一个讲透的项目 > 三个半成品。

---

## 十、执行提醒（针对你）

- 每个阶段**先复跑现状基线**再改造，否则分不清是改造的功劳还是环境差异
- RRF、Query Rewrite AB、Agentic 改造前后、幻觉率——这四组数据是面试核武器，必须真跑
- 每完成一个阶段，对照能不能脱稿讲"为什么这么做、试过什么、数据多少"
- 改 Agent（阶段H）时亲手画 LangGraph 状态图，理解回环条件，别让 AI 黑盒生成
- 可以做到阶段 H 就开始投简历，用面试反馈定 I/J/K 的优先级
