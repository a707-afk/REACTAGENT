# 决策档案 DECISION-LOG

> 这是本项目的"为什么"总账。面试官不关心你用了什么，关心你**为什么这么选、还考虑过什么、代价是什么**。
>
> **使用方法**：
> 1. 每条决策固定 6 段：背景/约束 → 备选方案 → 选择与理由 → 代价/放弃了什么 → 量化结果 → 会被追问的 3 层 + 逐字答案。
> 2. 量化数字标 `【待回填】` 的，等 `docs/REAL-DATA-BASELINE.md` 真实数据跑出来后回填，**不要编**。编的数字面试官追两句就穿帮。
> 3. 新增任何功能（RRF、自适应检索、缓存……）后，**必须回来加一条**。
> 4. 面试前对着每条的"逐字答案"念出来，录音，回放听哪里卡 —— 卡的地方就是没想清楚的地方。
>
> 编号规则：`D-编号`。当前覆盖：现有已实现部分（D-01 ~ D-12）。后续阶段的新决策从 D-13 起继续追加。

---

## 索引

| 编号 | 决策 | 一句话 |
|---|---|---|
| D-01 | 混合检索（BM25 + 向量）而非纯向量 | 纯向量在精确编号/法条号/缩写上召回差，词法路补这块 |
| D-02 | 合并前各路 min-max 归一化 | BM25 分值域和向量分值域不可比，不归一会让一路压死另一路 |
| D-03 | 混合融合 max \| RRF（阶段 G 已落地） | 企业集 RRF 优于 max（+4 Top-1）；k∈{20,40,60,80} 同分，默认仍 max 便于 AB |
| D-04 | chunk = Markdown 标题切分 + 二次 SentenceSplitter（512/64 overlap） | 尊重文档语义边界，再用 overlap 防关键信息落在切割点 |
| D-05 | 加 Rerank（Cross-Encoder，粗筛 20 → 精排 5） | Bi-Encoder 快但糙，Cross-Encoder 同时看 query+doc，精度高 |
| D-06 | 门控阈值作用在"重排后"分数上 | 门控要看最终质量分，不是向量召回的原始分 |
| D-07 | 权限用检索前 Pre-filter，Post-filter 仅兜底 | 先过滤候选集再检索，避免"检索到了又被踢掉"导致召回不足 |
| D-08 | 领域路由默认软提升 / 仅 trace，不硬过滤 | 硬按域淘汰候选易伤召回；软 boost 信噪比提升但不丢可达性 |
| D-09 | Query Rewrite 用 auto（启发式决定是否改写） | 口语化表达和文档书面语有语义鸿沟，但不是每条都值得多花 200ms |
| D-10 | 向量后端 Chroma/Qdrant 可切换（auto） | 本地起步用 Chroma，要高维/生产换 Qdrant，留切换口 |
| D-11 | 行为护栏 + 策略引擎前置短路 | 高风险/合规问题在检索前拦截转人工，不能让 RAG 直接答 |
| D-12 | 自标注评测集 + 四组合评测矩阵 | 不信排行榜信自己的测试集；指标要可复现、分模块 |
| D-I1 | 句级 n-gram grounding 作幻觉闸（非 LLM-NLI） | 可复现、零额外 LLM 成本；Agent 与 /chat 共用 |
| D-J1 | 检索 L1 精确 + 可选 L2 语义缓存 | 进程内 LRU；reindex 全量失效；L2 阈值待 PR 标定 |
| D-J2 | Prometheus `/metrics` + HTTP/检索延迟 | stub 可 scrape；与 JSON 日志、OTel 并存 |
| D-K1 | SSE（StreamingResponse）而非 WebSocket | 单向推送足够；与 FastAPI 原生兼容；LLM 无真流式时分块模拟 |

---

## D-01 混合检索（BM25 + 向量）而非纯向量

- **背景/约束**：法律问答里大量"精确符号"——法条号（民法典第 1062 条）、案号、专有名词、缩写。纯向量检索算余弦相似度，对这种"字面精确匹配"很弱：搜"第 1062 条"可能召回一堆语义相近但条号不对的内容。
- **备选方案**：(a) 纯向量；(b) 纯 BM25 关键词；(c) 向量 + BM25 混合。
- **选择与理由**：选 (c)。向量负责语义召回（"夫妻共同财产怎么分"能召回不含这几个字的相关条文），BM25 负责精确词法召回（法条号、案号、术语）。两条路互补，覆盖面比任何单路都大。实现见 [app/retrieval_pipeline.py](../app/retrieval_pipeline.py) `_retrieve_scored_nodes_impl` 与 [app/bm25_store.py](../app/bm25_store.py)（jieba 分词 + `rank_bm25` 的 BM25Okapi）。
- **代价/放弃了什么**：多维护一份 BM25 语料（reindex 时落盘 `data/bm25_corpus.jsonl`）；合并逻辑变复杂（分值不可比，要归一化，见 D-02）；多一次检索的延迟（BM25 本身极快，可忽略）。
- **量化结果**：纯向量 vs 混合，Top-1/Top-5 命中率对比 = 【待回填，用 `scripts/run_eval_retrieve.py` 开关 `HYBRID_BM25_ENABLED` 跑两次】。
- **会被追问**：
  - Q1「为什么不用纯向量？」→ 纯向量在精确匹配上有结构性短板。搜一个具体法条号、案号、缩写，它召回的是语义最近的，不是字面最准的。文档里如果有 RFC 7231 这种，纯向量可能给你一篇讲 HTTP 规范的文章而不是 7231 本身。法律场景这种精确符号特别多，所以必须有词法路补。
  - Q2「BM25 和向量分数不在一个量纲，你怎么合并？」→ 见 D-02，合并前各自 min-max 归一化到 [0,1]；当前用取 max，正在升级为 RRF（见 D-03），RRF 用排名不用分值，更稳健。
  - Q3「两路都召回同一个 chunk 怎么办？」→ 按 node_id 去重，合并时取两路归一化后的较优分（max 法）；RRF 下则是两路 reciprocal rank 相加，被两路都召回的天然加权更高。

## D-02 合并前各路 min-max 归一化

- **背景/约束**：BM25 的原始分（基于 TF-IDF/词频）和向量相似度（余弦，0~1 附近）完全不在一个量纲。直接把两个分数放一起排序，分值域大的那一路会系统性压死另一路。
- **备选方案**：(a) 不归一化直接合并；(b) 各路 min-max 归一化到 [0,1]；(c) z-score 标准化；(d) 直接用排名（RRF）。
- **选择与理由**：当前用 (b)，见 [app/retrieval_pipeline.py](../app/retrieval_pipeline.py) `_normalize_scores_minmax`。简单、可解释，把每一路自己的最强/最弱拉到 [0,1] 再比较。配置开关 `HYBRID_SCORE_NORMALIZE`（默认开）。
- **代价/放弃了什么**：min-max 对单路内的离群值敏感（一个超高分会把其他分压扁）；而且它只解决"量纲"，没解决"两路重要性谁更高"——这正是 RRF（d）更优的地方。
- **量化结果**：开/关归一化的 Top-1 对比 = 【待回填】。
- **会被追问**：
  - Q1「为什么不用 z-score？」→ z-score 假设分布近似正态，BM25 分布长尾严重，标准化后负值和量纲含义不直观；min-max 更简单且够用。但两者都没绕开"单路离群值"问题，所以最终我转向 RRF（用排名，天生免疫量纲和离群值）。
  - Q2「归一化在 rerank 之前还是之后？」→ 之前。归一化只是为了让两路候选能公平地进入同一个候选池，最终精排还是交给 Rerank（D-05）。
  - Q3「min-max 的边界情况？」→ 当一路只有一个候选或全部同分时 hi<=lo，代码里退化为全 1 或全 0，避免除零。

## D-03 混合融合 max | RRF（阶段 G 已落地）

- **背景/约束**：两路归一化后，被同一个 node 命中时怎么合一个分。历史上 `_merge_hybrid_by_node_id` 取两路的 max；max 不体现「两路共同召回」的叠加信号。
- **备选方案**：(a) max；(b) 加权和 `α·vec + (1-α)·bm25`；(c) RRF（Reciprocal Rank Fusion，按排名 `Σ 1/(k+rank)`）。
- **选择与理由**：阶段 G 已实现 (c)，见 [app/retrieval_pipeline.py](../app/retrieval_pipeline.py) `_merge_hybrid_rrf` 与 `HYBRID_FUSION` / `HYBRID_RRF_K`（[app/config.py](../app/config.py)）。**代码默认仍为 `max`**，便于与历史基线 AB；**推荐生产/企业评测口径**为 `rrf` + `k=60`。RRF 用排名不用分值，免疫量纲与离群值，被多路共同召回的文档自然加权更高。保留 `max` 作对照开关。
- **代价/放弃了什么**：RRF 丢弃绝对分值置信度，只保留名次；实现上多一个融合分支与单测（`tests/test_hybrid_merge.py`）。max 仍可作为回退。
- **量化结果**（企业 50 题，`eval_enterprise_questions.jsonl`，`EVAL_SKIP_DOMAIN_ROUTER=true`，`RERANK_ENABLED=false`，`QUERY_REWRITE_MODE=auto`，2026-06-04，产物见 [PHASE-G-RESULTS.md](PHASE-G-RESULTS.md)）：
  - **max**：Top-1 **35/50 (70%)**，Top-5 **45/50 (90%)**，domain Top-1 **32/50 (64%)** — `docs/eval_phase_g_baseline_max_rerank_off.json`
  - **RRF**（k=20/40/60/80 四档 **同分**）：Top-1 **39/50 (78%)**，Top-5 **46/50 (92%)**，domain Top-1 **36/50 (72%)** — 例：`docs/eval_phase_g_rrf60_rerank_off.json`
  - **相对 max**：Top-1 **+4**，Top-5 **+1**，domain Top-1 **+4**；k 在 20–80 间对本集不敏感。
- **会被追问**：
  - Q1「RRF 公式？k 取多少？」→ `score(d) = Σ_r 1/(k + rank_r(d))`，rank 从 1 起；默认配置 `HYBRID_RRF_K=60`。本企业集扫 k=20/40/60/80 指标相同，故推荐 **60**（文献常用、与默认一致）。
  - Q2「RRF 比加权和好在哪？」→ 加权和要调 α，最优 α 随 query 漂移；RRF 不需 α，对两路分值不可比免疫。
  - Q3「RRF 有什么缺点？为什么代码默认还是 max？」→ 损失绝对分置信度；默认 max 是为不破坏既有部署与四组合矩阵可比性，新环境显式设 `HYBRID_FUSION=rrf` 即可。

## D-04 chunk = Markdown 标题切分 + 二次 SentenceSplitter（512 / overlap 64）

- **背景/约束**：法律文档结构性强（编/章/节/条）。如果按固定字数一刀切，会把"第 X 条的后半句"和"第 X+1 条的前半句"切进同一块，或把一条切成两块，导致检索回来的是断章取义的碎片。
- **备选方案**：(a) 固定字数切；(b) 纯按 Markdown 标题切（heading_only）；(c) 标题切分 + 过长段落二次按 token overlap 切（markdown_heading_overlap）。
- **选择与理由**：默认 (c)，见 [app/chunking.py](../app/chunking.py) `build_nodes`。先用 `MarkdownNodeParser` 按标题层级切（保留 `header_path`，如"民法典 > 婚姻家庭编 > 第 1062 条"），再对过长块用 `SentenceSplitter`（chunk_size=512 token、overlap=64）二次切，overlap 防止关键信息正好落在切割点。`heading_only`（b）保留做对照。
- **代价/放弃了什么**：依赖文档本身是规范 Markdown（front matter + 标题）；非结构化 PDF 需要先转 Markdown 才能吃到这套切分的好处。overlap 带来约 12% 的存储冗余。
- **量化结果**：512 vs 256 vs heading_only 的 Top-5 对比 = 【待回填】。
- **会被追问**：
  - Q1「chunk_size 为什么 512 不是别的？」→ 512 token 是"够装下一条法律条文 + 上下文"和"不稀释相似度"的平衡点。切太大相关内容被无关内容稀释、余弦分被拉低；切太小上下文断裂。具体值我会用测试集在 256/512/768 之间扫一遍定，不是拍脑袋。
  - Q2「overlap 设多少？为什么要 overlap？」→ 64 token（约 12%）。防止一个完整语义单元正好被切割点劈开，相邻块各拿半句。生产常用 10%~20%。
  - Q3「标题路径 header_path 有什么用？」→ 两个用：一是检索回来的 chunk 带"出处面包屑"，LLM 更容易理解上下文；二是溯源时能标到"某法 > 某编 > 第 X 条"（见 D-05 引用溯源升级）。

## D-05 加 Rerank（Cross-Encoder，粗筛 20 → 精排 5）

- **背景/约束**：第一阶段混合召回是 Bi-Encoder 思路（query 和 doc 分别编码再算相似度），快但粗，只能算"大概相关"。法律问答对精度要求高，召回前几条经常有语义接近但不对题的。
- **备选方案**：(a) 不 rerank，直接取召回 Top-5；(b) 加 Cross-Encoder rerank。
- **选择与理由**：选 (b)，见 [app/config.py](../app/config.py) `rerank_*` 与 `app/rerank.py`。先混合召回 20 个候选（`rerank_candidate_top_k`），再用 Qwen3-Reranker（Cross-Encoder，把 query 和 doc 拼一起送进模型，同时看两边）精排取 Top-5。`rerank_backend=auto` 兼容 Qwen3-causal 与 BGE cross_encoder。
- **代价/放弃了什么**：Cross-Encoder 慢（每个候选都要过一次模型），所以不能对全库做，只能粗筛后精排；多一次模型加载和显存占用。
- **量化结果**：rerank 开/关的 Top-5 命中率 = 【待回填】（文档基准值 71%→89%，以自己测试集为准）。
- **会被追问**：
  - Q1「为什么 rerank 比向量检索准？」→ 编码方式不同。向量检索是 Bi-Encoder，query 和 doc 分开编码，模型看不到对方，只能算粗略语义距离；Rerank 是 Cross-Encoder，把 query+doc 拼起来一起进模型，注意力能交叉，判精度高很多。代价是慢，所以只能粗筛后精排。
  - Q2「粗筛取 20、精排取 5 怎么定的？」→ 粗筛要 recall（候选里得包含正确答案，宁多勿漏），精排要 precision。20→5 是延迟和召回的平衡，我会用测试集看"正确答案落在召回前 20 的比例"来定粗筛数。
  - Q3「门控阈值是作用在向量分还是 rerank 分？」→ rerank 分（见 D-06），因为门控判断的是"最终质量"，rerank 分才是最终排序依据。

## D-06 门控阈值作用在"重排后"的分数上

- **背景/约束**：需要一个"拒答闸门"——召回质量太差时宁可说"知识库无相关内容"也不让 LLM 硬答（防幻觉第一道闸）。问题是这个阈值该卡哪套分数。
- **备选方案**：(a) 卡向量召回原始分；(b) 卡重排后分数。
- **选择与理由**：选 (b)，见 [app/retrieval_gates.py](../app/retrieval_gates.py) `evaluate_similarity_gate`。取重排后第一名的分与 `retrieval_similarity_threshold`（默认 0.6）比，低于则返回 `SIMILARITY_GATE_FAIL` 拒答。理由：rerank 分才是系统对"最相关那条到底有多相关"的最终判断，向量原始分会被归一化、混合、boost 改写过，不能代表最终质量。
- **代价/放弃了什么**：阈值是个魔法数字，定高了误杀（该答的拒了），定低了漏放（不相关的也答）；需要用测试集校准，且 rerank backend 换了阈值要重标。
- **量化结果**：阈值 0.5/0.6/0.7 下的误杀率/漏放率 = 【待回填】。
- **会被追问**：
  - Q1「这个 0.6 怎么来的？」→ 不是拍的，是用标注评测集扫阈值，看误杀（该答拒了）和漏放（不该答答了）的交叉点定的；换 rerank 模型要重标，因为不同模型分布不同。
  - Q2「分数越大越相关还是越小？」→ 有个 `retrieval_score_higher_is_better` 开关。Qwen reranker 是越大越相关；若换成距离类模型，内部取反后再比，阈值统一按"越大越好"语义校准。
  - Q3「门控拒答了，用户体验怎么办？」→ 返回明确的"知识库中无相关内容"而不是瞎编，并带 error_code 供前端区分；这是刻意的——法律场景宁可不答也不能编。

## D-07 权限用检索前 Pre-filter，Post-filter 仅兜底

- **背景/约束**：多租户/分级权限场景，用户只能看其权限内的文档。问题是"过滤"放在检索前还是检索后。
- **备选方案**：(a) 检索后过滤（Post-filter，先全库检索再踢掉无权限的）；(b) 检索前预筛候选 ID（Pre-filter）；(c) 两者都做。
- **选择与理由**：默认 (b) Pre-filter，见 `retrieve_scored_nodes` 里 `resolve_allowed_node_ids` + `vector_retrieve_access_filtered`，BM25 也传 `allowed_ids`。理由：Post-filter 会"检索到了又被踢掉"，导致最终候选数不足、召回受损（你取 Top-20 结果 15 个无权限，只剩 5 个）。Pre-filter 先把候选集限定在可访问范围内再检索，保证召回数。Post-filter 仅作为 `access_post_filter_safety_net`（默认关）兜底。
- **代价/放弃了什么**：Pre-filter 需要能按元数据预先算出"可访问 node_id 集合"，实现更复杂；权限规则变化时要保证预筛逻辑同步。
- **量化结果**：Pre vs Post 的有效召回数对比 = 【待回填，见 `scripts/compare_access_eval_backends.py`】。
- **会被追问**：
  - Q1「为什么不直接检索后过滤？」→ Post-filter 会伤召回：你取 Top-20，如果其中大半无权限被踢，最终可能不足 5 条。Pre-filter 先限定候选集再检索，召回数有保证。
  - Q2「Pre-filter 怎么实现的？」→ 按 roles/tenant_id/security_clearance 在元数据层预解析出 allowed node_id 集合，向量检索和 BM25 都只在这个子集上排序。
  - Q3「那为什么还留 Post-filter？」→ 兜底（safety net），防止 Pre-filter 逻辑有漏洞时无权限内容泄漏到结果里，纵深防御。默认关，可开。

## D-08 领域路由默认软提升 / 仅 trace，不硬过滤

- **背景/约束**：法律库混了多种文档（法条/司法解释/案例/FAQ）。文档里电力案例的经验是"分库召回比换模型管用"。但"按域收窄候选"如果做成硬过滤，路由判错就直接把正确答案过滤掉了。
- **备选方案**：(a) 硬过滤（hard filter，rerank 前按 allowed_domains 淘汰候选）；(b) 软提升（soft boost，对匹配域的候选小幅加分，不淘汰）；(c) 仅推断写 trace，不参与排序。
- **选择与理由**：默认 (c)/(b)，见 [app/retrieval_pipeline.py](../app/retrieval_pipeline.py) `_domain_soft_boost_nodes` 与 `domain_router_hard_filter`（默认 False）。路由结果默认只作为 trace/prior；可选开 soft boost 给匹配域的前 3 个候选加 `delta=0.07`。硬过滤保留为开关但默认关。理由：路由必然有错判率，硬过滤把"召回"的命运交给"路由准确率"，一旦路由错，召回直接归零且不可恢复；软提升只改变排序倾向，不丢可达性。
- **代价/放弃了什么**：软提升对信噪比的提升不如硬过滤激进（硬过滤能彻底排除跨域噪声）；delta 是魔法数字要调。
- **量化结果**：hard filter vs soft boost vs trace-only 三组的 domain-top1 / 整体 top1 = 【待回填，见 `scripts/run_eval_prod_router_matrix.py`】。
- **会被追问**：
  - Q1「分库召回为什么管用？」→ 同一个库里文档都是同领域，上下文一致，搜"财产分割"不会混进刑事条文，信噪比天然高。这比换 embedding 模型便宜得多、效果更稳。
  - Q2「那你为什么不硬按域过滤？」→ 因为路由有错判率。硬过滤等于把召回成败押在路由准确率上，路由一错召回归零且不可恢复。我用软提升：路由对就加分排前面，路由错也只是没加分，正确答案还在候选里，rerank 还能救回来。可达性不丢。
  - Q3「soft boost 的 delta 0.07 怎么定？会不会盖过 rerank？」→ delta 作用在 rerank 之前的归一化分（[0,1]）上，且只给前 3 个匹配域候选加，量级可控；最终排序仍由 rerank 决定，boost 只影响"谁进 rerank 的前排"。值用测试集调。

## D-09 Query Rewrite 用 auto（启发式决定是否改写）

- **背景/约束**：用户口语化提问（"离婚财产咋分"）和法律文档书面语（"夫妻共同财产的分割"）有语义鸿沟，字面不匹配会让余弦相似度排不进前列。但不是每条 query 都值得多花一次 LLM 调用（+200ms、+成本）。
- **备选方案**：(a) off 永不改写；(b) on 每次必改写；(c) auto 启发式判断是否需要改写。
- **选择与理由**：默认 (c) auto，见 [app/config.py](../app/config.py) `query_rewrite_mode` 与 `app/query_rewrite.py`。改写不是同义词替换，是把口语扩写成含专业术语的检索句。auto 用启发式（如长度、是否已含术语）决定调不调，省掉"本来就规范的 query"的无谓开销。
- **代价/放弃了什么**：改写引入 LLM 依赖和延迟，且改写本身可能引入噪声（扩写跑偏）；auto 的启发式判断有误判（该改的没改）。
- **量化结果**（企业 50 题全量，与阶段 G 检索口径一致：`HYBRID_FUSION=rrf`、`HYBRID_RRF_K=60`、`RERANK_ENABLED=false`、`EVAL_SKIP_DOMAIN_ROUTER=true`，2026-06-04）：
  - **off**：Top-1 **38/50 (76%)**，Top-5 **47/50 (94%)**，domain **35/50 (70%)** — `docs/eval_phase_g_rewrite_off.json`
  - **on**：Top-1 **39/50 (78%)**，Top-5 **46/50 (92%)**，domain **36/50 (72%)** — `docs/eval_phase_g_rewrite_on.json`
  - **auto**（RRF 网格同配置）：Top-1 **39/50**，Top-5 **46/50**，domain **36/50** — 与 **on** 的 Top-1/domain 一致，Top-5 略低于 **off**（47 vs 46）
  - **结论**：本集 **on/auto 略利于 Top-1/domain**，**off 略利于 Top-5**；默认 **auto** 在成本与 Top-1 之间折中。历史文档「40%→75%」为口语子集叙事，勿与本 50 题全量混读。
- **会被追问**：
  - Q1「改写具体改什么？」→ 不是同义词替换，是把口语扩写成包含专业术语的描述。比如"离婚财产咋分"扩写成"夫妻共同财产分割 + 离婚财产分配原则 + 婚姻法财产条款"，再拿扩写后的去检索。
  - Q2「为什么 auto 不全开？」→ 全开每条都 +200ms +成本，但很多本来就规范的 query 不需要改。auto 用启发式只对口语化/短句改写，把钱花在刀刃上。这是个成本/收益权衡。
  - Q3「改写会不会改跑偏？」→ 会，所以改写句只用于"检索"，最终答案生成仍基于检索回的原文；而且 retrieval_query 会在响应里透出，可观测、可回归。

## D-10 向量后端 Chroma / Qdrant 可切换（auto）

- **背景/约束**：个人机起步要轻量、零运维；但生产/高维向量要更强的后端。不想锁死一个。
- **备选方案**：(a) 只用 Chroma；(b) 只用 Qdrant；(c) auto，有 Qdrant 数据用 Qdrant，否则 Chroma。
- **选择与理由**：(c)，见 [app/config.py](../app/config.py) `vector_backend`。本地开发用 Chroma（嵌入式、零依赖），需要时切 Qdrant（原生支持高维、生产可扩展）。留显式开关强制指定。
- **代价/放弃了什么**：要维护两套后端的适配层；两边行为细节（过滤语法、距离度量）需对齐测试。
- **量化结果**：迁移一致性见 `scripts/run_qdrant_migration_eval.py`。
- **会被追问**：
  - Q1「为什么不直接上 Milvus/Qdrant？」→ 个人机起步阶段 Chroma 嵌入式零运维，能让我先把检索策略和评测跑通；文档也说"先跑基线再优化"。等维度/规模上来（比如 Qwen 2560 维，pgvector 顶不住）再切 Qdrant，留了 auto 切换口。
  - Q2「向量量化能省显存，为什么不量化？」→ 不能量化 embedding 输出。余弦相似度在高维上误差累积，每维丢一点精度，几百维下来方向就偏了，文档实测掉 5~8 个点，比换模型的提升还大。正确做法是换支持高维的库（Qdrant）或用 Matryoshka 指定低维输出。
  - Q3「Chroma 和 Qdrant 距离度量一致吗？」→ 要对齐（都用 cosine），迁移后用 `run_qdrant_migration_eval.py` 跑一致性回归，确认 Top-K 没漂移。

## D-11 行为护栏 + 策略引擎前置短路

- **背景/约束**：法律场景有高风险/合规红线（如"帮我钻法律空子""教唆"类）。这类问题不能让 RAG 直接答，要拦截转人工。
- **备选方案**：(a) 不拦，全交 RAG；(b) 仅关键词规则拦截；(c) 规则 + 向量相似度 + LLM 分类的多层护栏，命中则短路 RAG 转人工。
- **选择与理由**：(c)，见 [app/routes_rag.py](../app/routes_rag.py) `evaluate_policy` 前置、`app/behavior_guard.py`、`app/policy/engine.py`、以及 OPA 外部策略（默认 fail-open）。命中高风险/合规短语直接 `should_skip_rag` 返回 `human_review`，不进检索。
- **代价/放弃了什么**：误杀（正常问题被拦）；多层护栏增加延迟和维护成本；规则包要持续更新。
- **量化结果**：护栏拦截率 / 误杀率 = 【待回填，见 `scripts/run_eval_behavior_guard.py`】。
- **会被追问**：
  - Q1「护栏是硬编码 1.0 那种吗？」→ 不是。文档点名的"五穿帮"第一条就是硬编码护栏。我这里是真在跑的：规则 + 可选向量相似度 + 可选 LLM 分类三层，命中输出原因码和风险档，有拦截率/误杀率指标，不是写死的 mock。
  - Q2「OPA 为什么 fail-open？」→ 外部策略服务（OPA）不可用时默认放行（fail-open），保证核心问答可用性；高风险判断仍由本地护栏兜底。这是可用性 vs 安全的权衡，可按场景改 fail-close。
  - Q3「拦截后怎么处理？」→ 返回 `human_review` 行为 + 原因码，转人工复核流程，并落审计日志（trace_id 串起来）。

## D-12 自标注评测集 + 四组合评测矩阵

- **背景/约束**：MTEB 等公开排行榜测的是通用场景，越垂直越不准（文档电力案例 BGE-M3 榜上分高，真实数据前 5 只 1 条相关）。需要自己的、可复现的、分模块的评测。
- **备选方案**：(a) 看排行榜选型；(b) 自标注测试集 + 脚本化评测。
- **选择与理由**：(b)。见 [scripts/run_eval_retrieve.py](../scripts/run_eval_retrieve.py)（Top-1/Top-5/domain-top1 命中率 + 分数分布）、`run_eval_prod_router_matrix.py`（路由四组合矩阵）、`run_eval_behavior_guard.py`、`run_eval_access_control.py`、`run_eval_agent_ticket.py`。评测题含 `expected_doc_contains`/`expected_domain`/`expected_behavior`，可机器判命中。
- **代价/放弃了什么**：标注要人力（目标 200~300 条）；测试集本身要防污染（脚本里有 enterprise 索引对齐校验，防止跑错库）。
- **量化结果**：见 `docs/REAL-DATA-BASELINE.md`。
- **会被追问**：
  - Q1「为什么不信 MTEB 排行榜？」→ 排行榜测通用语料（新闻/百科/对话），业务越垂直越专业越靠不住。文档里 BGE-M3 榜上分不低，放电力知识库一测前 5 只 1 条相关。所以我用自己标注的法律测试集做选型依据。
  - Q2「你的评测覆盖哪些模块？」→ 不只 RAG。检索（Top-1/Top-5/domain-top1）、领域路由（四组合矩阵）、行为护栏（拦截率/误杀率）、权限、Agent 工单路径都有独立评测脚本。文档"五穿帮"第五条就是"只有 RAG 有指标"，我刻意全模块都埋了。
  - Q3「评测集怎么防污染/防过拟合？」→ 脚本里有 enterprise 索引对齐校验（DOCS_DIR/collection 名不对就 WARNING 甚至退出码 2），防止误跑默认库把指标刷漂亮；标注集和（未来）微调集严格不重叠。

---

## D-I1 句级 n-gram grounding 作幻觉闸（非 LLM-NLI）

- **背景/约束**：阶段 H 的 `node_hallucination` 仅为「非空 + 简单子串」桩；`/chat` 需要可观测的溯源报告。法律/工单场景要求**可复现、可回归**，且不能把每条草稿都再调一次 LLM NLI（成本 + 非确定性）。
- **备选方案**：(a) 继续桩；(b) LLM / NLI 判 unsupported；(c) 字符 overlap 仅文档级；(d) 句级 n-gram（+ 可选 embedding）对齐 chunk。
- **选择与理由**：选 (d)，见 [app/citation_verify.py](../app/citation_verify.py) `sentence_level_grounding`。[routes_rag.py](../app/routes_rag.py) 与 [nodes.py](../app/agent_graph/nodes.py) `node_hallucination` 共用。默认 **n-gram**（`prefer_embedding=False` 于 Agent 评测路径），embedding 作增强回退。unsupported 句比例超 `DEFAULT_MAX_UNSUPPORTED_RATE=0.35` 则 `passed=False`。
- **代价/放弃了什么**：对「改述但语义正确」的句子可能误杀（字面重合低）；n-gram 阈值需用金标调；未实现 grounding 失败 → 自动重写草稿回环。
- **量化结果**（2026-06-04，mock/离线）：
  - `python scripts/run_eval_hallucination.py`：**8/8** — `data/eval_hallucination.jsonl`
  - `python scripts/run_eval_agent_ticket.py`：**15/15**（draft_ready 金标 mock 草稿与 chunk 对齐）
  - `pytest tests/test_citation_verify.py`：通过
- **会被追问**：
  - Q1「为什么不用 NLI？」→ NLI/LLM 准但慢、结果难复现，且评测要零额外 API。n-gram 在「草稿应贴近检索片段」的工单场景够用，先把闸接上并有金标；NLI 可作为后续增强路。
  - Q2「35% unsupported 怎么来的？」→ 默认常量 + 金标 HG-02/HG-07 负例校准起点；上线前应在真实草稿集上扫 `max_unsupported_rate` 与 `support_threshold`。
  - Q3「和 citation_overlap_ratio 区别？」→ overlap 是**文档级**「引用片段是否出现在答案」；grounding 是**句级**「每句话最佳 chunk 是否过阈值」，更细、可指出哪句 unsupported。

---

## D-J1 检索 L1 精确 + 可选 L2 语义缓存（进程内）

- **背景/约束**：同一检索参数下重复 query（客服高峰、评测重跑）会重复走向量/BM25/rerank，延迟与 GPU 成本高。知识库更新后必须避免返回过期候选。
- **备选方案**：(a) 不缓存；(b) 仅 L1 精确键；(c) L1 + L2 语义近似；(d) 直接上 Redis 三级。
- **选择与理由**：本阶段选 **(b) 默认 + (c) 可选**，见 [app/cache.py](../app/cache.py)、[app/retrieval_pipeline.py](../app/retrieval_pipeline.py)。L1 键含 query、top_k、rewrite 开关、访问上下文（tenant/roles/clearance）及影响召回的 settings 指纹（混合/ rerank/ 路由/ 向量后端等）。L2 默认关（`CACHE_SEMANTIC_ENABLED=false`），避免无 embedding 环境误加载模型。索引重建在 [app/vector_index.py](../app/vector_index.py) `rebuild_index` 与 [scripts/reindex.py](../scripts/reindex.py) 调用 `cache_clear()`。
- **代价/放弃了什么**：进程内缓存不跨 worker/多机；未做 Redis L3 会话级；L2 阈值 0.92 为占位，需 PR 曲线标定（见下）。
- **量化结果**：L1 命中 P99 延迟降幅、L2 命中率与误命中率 = 【待回填】。
- **会被追问**：
  - Q1「为什么不用一上来就 Redis？」→ 先把键设计与失效语义跑通（键里含 settings 指纹 + reindex 清空），单机演示和单测不引入运维依赖；多副本再上 Redis 是同一键空间的延伸。
  - Q2「L2 阈值怎么定？」→ 在标注集上对「同义不同字面」query 画 precision-recall，选 F1 或业务可接受误命中率下的阈值；默认 0.92 偏保守，生产前必须重标。
  - Q3「缓存一致性？」→ 语料/索引变更 → `cache_clear()`；键含 rerank/混合/路由配置，改配置自然 miss，不会静默用旧策略下的结果。

## D-J2 Prometheus 指标 + HTTP/检索延迟

- **背景/约束**：仅有 stdout JSON 难以做 P99、QPS、缓存命中率聚合；设计稿（阶段 F）写了指标项但未暴露 scrape 端点。
- **备选方案**：(a) 仅日志；(b) Prometheus pull + 可选 `prometheus_client`；(c) 只接商业 APM。
- **选择与理由**：选 **(b)**，见 [app/metrics.py](../app/metrics.py)、[app/main.py](../app/main.py) `GET /metrics` 与 `metrics_latency_middleware`。未安装 `prometheus_client` 时用内存 stub 输出同名指标文本，CI 与本地 `curl` 不依赖额外服务。检索路径 `observe_retrieve` 记 `rag_retrieve_duration_seconds`；缓存命中记 `rag_cache_hits_total{level=l1|l2}`。与既有 `log_structured_event`、`trace_span` **并存**。
- **代价/放弃了什么**：stub 模式无 histogram bucket 精度；尚未接 Grafana 与业务 counter（gate_fail、final_action）；endpoint 标签用路由 path，高基数路径需后续规范化。
- **量化结果**：【待回填】一次真实瓶颈案例（如 rerank 占比）写入 `PHASE-J-PROGRESS.md`。
- **会被追问**：
  - Q1「和 OTel/Langfuse 重复吗？」→ 不重复：OTel/Langfuse 偏 trace 与 LLM 审计；Prometheus 偏聚合 SLO。同一请求可同时有 trace_id 日志 + `/metrics` 计数。
  - Q2「为什么 metrics 不强制装 prometheus_client？」→ 降低开发机/CI 依赖；stub 保证端点契约稳定，生产镜像装 observability 额外依赖即可。
  - Q3「检索延迟包含缓存命中吗？」→ 包含。命中时耗时接近序列化开销，histogram 会分出快路径，便于看命中率收益。

## D-K1 SSE（StreamingResponse）而非 WebSocket

- **背景/约束**：阶段 K 需要前端展示问答草稿增量与 Agent `audit_trace` 步骤；部署形态仍是 FastAPI 单体 + 静态页，无长连接网关。
- **备选方案**：(a) 保持 JSON 轮询；(b) **SSE** `text/event-stream`；(c) WebSocket 双向通道。
- **选择与理由**：选 **(b)**。问答与工单流均为 **服务端→客户端单向** 推送；FastAPI `StreamingResponse` 零额外依赖，与现有 `POST /chat`、`POST /agent/ticket` **并存**（向后兼容）。Agent 侧用 LangGraph `stream(stream_mode="updates")` 按节点 yield `step`；LLM 暂无 token 级 API 时对 `answer`/`draft_reply` **分块模拟** `token` 事件。
- **代价/放弃了什么**：SSE 单向，不能客户端中途 cancel 帧（需断开连接）；模拟 token 非真流式延迟；WebSocket 生态（房间、双向工具调用）留待后续。
- **量化结果**：验收以 `curl -N` 可见 `event: token|step|done|error`；pytest `tests/test_sse_routes.py` 校验 `Content-Type`。
- **会被追问**：
  - Q1「为什么不用 WebSocket？」→ 当前只需服务端推送进度与草稿，HTTP/2 下 SSE 足够；实现与 nginx 反代更简单，且与 REST 共用同一端口与鉴权中间件。
  - Q2「真流式 LLM 怎么接？」→ 在 `chat_completion` 增加 stream 回调，把 chunk 映射为 `token` 事件即可，协议不变。
  - Q3「Agent step 事件从哪来？」→ 每个 LangGraph 节点更新时读 `audit_trace` 增量，映射为 `event: step`，最后 `done` 带完整 `TicketAgentResponse` 字段。

---

## 待补（随阶段推进追加，每个功能完成后回来写）

- D-13 RRF 融合（替换 max）— 阶段 1 ✅ 见 D-03
- D-14 问题类型预分类 + 自适应检索 — 阶段 1
- D-15 embedding 选型对比（法律分库测试集）— 阶段 1
- D-16 法条级/章节级溯源 + 幻觉率下降 — 阶段 I 部分由 D-I1 覆盖；NLI/回环待补
- D-17 三级缓存 + 成本/延迟看板 — 阶段 J 部分落地（L1/L2 进程内 + `/metrics`）；Redis/Grafana 【待补】
- D-18 工具路由 / 真 ReAct + 三层异常 — 阶段 2
- D-19 四级分层记忆 / 上下文压缩 + 消融 — 阶段 2
- D-20 SSE 为什么不用 WebSocket — 阶段 3
