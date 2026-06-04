# 面试准备：企业 RAG + Agent 项目

> STAR-L 结构：**S**ituation → **T**ask → **A**ction → **R**esult → **L**earning。以下为可背诵逐字稿骨架，数字以 [G-K-METRICS-SUMMARY.md](G-K-METRICS-SUMMARY.md) 为准。

---

## 项目描述（STAR-L，约 2 分钟）

**S — 背景**  
我们团队维护一套面向企业运维/客服场景的内部知识库，文档是 Markdown  front matter + 分块，大约 41 篇企业文档、50 条自标注评测题。业务要求：检索要准、回答要有引用、高风险问题不能硬答，客服工单还要能走 Agent 闭环并留审计链。

**T — 任务**  
我负责把「混合检索 RAG + 策略护栏 + LangGraph 工单 Agent」做成可演示、可评测、可部署的系统：包括检索优化、Agent 回环、句级 grounding、缓存与指标，以及最后的 SSE 前端和 Docker 交付。

**A — 行动**  
1. **检索**：BM25 + 向量双路，合并前 min-max；阶段 G 落地 RRF，企业集 Top-1 从 70% 提到 78%；Query Rewrite 保持 auto 平衡成本。  
2. **权限与策略**：检索前 Pre-filter tenant/密级；策略引擎在 RAG 前 intercept 高风险 query。  
3. **Agent**：LangGraph 加 grader 与 rewrite 回环（最多 3 轮），draft 后句级 grounding 防幻觉。  
4. **工程化**：L1 检索缓存 + `/metrics`；阶段 K 用 SSE 推流式草稿与 audit 步骤，React 三 Tab 前端，Docker 多阶段镜像。

**R — 结果**  
- 检索：RRF 相对 max Top-1 **+4**（35→39/50）；Rewrite on 再 +1 vs off。  
- Agent 金标 **15/15**；grounding 金标 **8/8**。  
- 权限 Forbidden **4/4**；Expect hit **88.5%**。  
- 交付：`POST /chat/stream`、`/agent/ticket/stream` + `/app` UI + compose 一键起服务。

**L — 反思**  
硬 domain filter 曾伤召回，默认改为 trace-only；评估必须对齐 DOCS_DIR/collection，否则 JSON 会误导；SSE 目前 token 是模拟分块，下一步接 LLM 真流式。

---

## 必背追问 1：为什么用 RRF 而不是分数加权？

**逐字稿**  
BM25 和向量分数量纲不同，即使用 min-max，加权和还要调 α，而且 α 会随 query 类型漂移。RRF 只看排名，公式是各路上 `1/(k+rank)` 求和，被两路同时召回的文档自然更高。我们在 50 题企业集上，RRF 比原来的 max 融合 Top-1 高了 4 个点，k 从 20 扫到 80 结果一样，所以生产推荐 k=60，和文献默认一致。代价是丢失绝对分置信度，所以门控仍然看 rerank 后的分数，不直接看 RRF 分。

---

## 必背追问 2：Agent 回环怎么避免死循环？

**逐字稿**  
三层保护。第一层，`max_iterations=3`，grader 不过最多 rewrite 再 retrieve 三轮。第二层，每次 rewrite 会把 query 签名写进 `rewrite_history`，如果出现相同的 rewrite 签名就设 `loop_detected`，直接 finalize，不再 draft。第三层，grader 和 hallucination 节点 try/except，异常时要么标记不通过进 finalize，要么降级放行但 `human_review_required=true`。这样 API schema 不用改，audit_trace 里能看到每一步，金标评测仍 15 条全过。

---

## 必背追问 3：幻觉检测为什么不用 LLM-NLI？

**逐字稿**  
我们选的是可复现、零额外 LLM 成本的句级 grounding：把答案按句切开，每句在检索 chunk 上算 n-gram Jaccard 加子串 boost，低于阈值标 unsupported，unsupported 比例超过 35% 就 fail。工单 Agent 的 hallucination 节点和 `/chat` 共用 `citation_verify.py`，评测有 8 条金标。Trade-off 是语义改写可能误判，所以 Agent 异常时会降级放行并转人工；后续可以加 embedding 回退或 LLM judge，但成本和延迟会上去，我们在 D-I1 里写清楚了。

---

## 必背追问 4：缓存会不会返回过期检索结果？

**逐字稿**  
L1 的 key 是 query 加上会影响召回的配置指纹，还有 tenant/roles 这些访问上下文，避免串租户。任何 `reindex` 或向量重建会调用 `cache_clear()` 全量失效，避免索引更新后脏读。L2 语义缓存默认关，因为 threshold 还要用 PR 曲线标定。当前是进程内 LRU，多副本不共享，所以 Docker 水平扩展前要上 Redis，这在阶段 J 文档里标了 backlog。

---

## 必背追问 5：SSE 和 WebSocket 怎么选？为什么保留旧 REST？

**逐字稿**  
问答和工单流都是服务端往浏览器推进度和草稿，不需要客户端高频上行，SSE 用 HTTP 就行，FastAPI 的 StreamingResponse 直接 `text/event-stream`，和现有中间件、trace_id 共用。协议上四种 event：token、step、done、error；Agent 的 step 来自 LangGraph stream 的 audit_trace 增量。LLM 暂时没有接 token 级 API，所以 token 是对完整 answer 分块模拟，协议不变以后可以换真流式。旧的 `POST /chat` 和 `/agent/ticket` 完全保留，方便脚本和评测，流式是增量体验不是 breaking change。

---

## 快速数字卡片

| 指标 | 数字 |
|------|------|
| 企业文档 | 41 篇 |
| 企业 eval | 50 题 |
| RRF vs max Top-1 | 39 vs 35（+4） |
| Rewrite on vs off Top-1 | 39 vs 38 |
| Agent eval | 15/15 |
| Grounding eval | 8/8 |
| 权限 Expect | 88.5% |
