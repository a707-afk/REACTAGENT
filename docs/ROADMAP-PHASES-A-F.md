# 路线图 §6（A–G）与本仓库对齐

> 来源：`docs/PROJECT-STRATEGY-HANDOFF.md` 「6. 中长期路线图」。本文用 ** checkbox + 仓库现状 + 下一阶段首个可执行条目**（**本 Pass 不包含** OPA、完整 LangGraph、Qdrant 默认化、管理员 UI）。
>
> 更新口径（2026-05-15）：当前 `domain router` 已升级为 **规则 + Embedding Router + 可选 LLM fallback + 多域 allowed_domains + calibration + router_trace**。生产默认仍然是 **不硬过滤候选**：`DOMAIN_ROUTER_HARD_FILTER=false`。旧四组合矩阵里的 r1 行是“历史 hard filter 回归”，不能再当作生产 router 效果。

---

## A. 评估闭环稳定

目标：检索 / 路由 / 护栏 / 权限均能用 **数据证明** 是否有效；有可信 baseline comparison。

- **检索四组合矩阵**：编排 `[scripts/run_eval_four_baselines.py](../scripts/run_eval_four_baselines.py)`；磁盘汇总 `[eval_four_baselines_summary.json](eval_four_baselines_summary.json)`（末尾若偶有 `_meta`，仅见于 subprocess 异常时）。
- **生产型 Router 评估矩阵**：`[scripts/run_eval_prod_router_matrix.py](../scripts/run_eval_prod_router_matrix.py)`；产物与 Stable CPU 批注见 `**[EVAL-RERUN-NOTES.md](EVAL-RERUN-NOTES.md)`**、`[eval_prod_router_matrix_summary.json](eval_prod_router_matrix_summary.json)`、三份 `eval_enterprise_prod_router_*.json`。
- **Behavior / policy intercept eval**：`[scripts/run_eval_behavior_guard.py](../scripts/run_eval_behavior_guard.py)`，`[eval_behavior_guard.json](eval_behavior_guard.json)`。
- **权限评测首个脚本**：`[scripts/run_eval_access_control.py](../scripts/run_eval_access_control.py)`（含 **EVAL_ENTERPRISE_STRICT** 与企业 BM25 路径校验），`[eval_access_control.json](eval_access_control.json)`，`[ACCESS-CONTROL-EVAL.md](ACCESS-CONTROL-EVAL.md)`；语料三域边界见 `[DATA-CORPUS-REDESIGN.md](DATA-CORPUS-REDESIGN.md)`。payload 前置过滤仍属路线图 **C**。

进入 B/C 的条件：生产型 Router trace-only 评估不低于 router off baseline；soft boost 若下降则继续默认关闭。评估结果必须写入文档，不能只看控制台。

---

## B. Embedding Router

- **P0 代码已落地**：`[app/domain_router.py](../app/domain_router.py)` 已支持规则打分、Embedding Router 融合、可选 LLM fallback、多域 `allowed_domains`、`raw_confidence` / `confidence`、`routing_trace`；`[app/embedding_router.py](../app/embedding_router.py)`、`[app/router_profiles.py](../app/router_profiles.py)`、`[app/router_calibration.py](../app/router_calibration.py)` 已存在。
- **生产默认安全**：`[app/retrieval_pipeline.py](../app/retrieval_pipeline.py)` 默认不按域硬过滤；`DOMAIN_ROUTER_SOFT_BOOST_ENABLED` 已实现但默认关闭。
- **Router 离线金标与评测**：`[data/router_eval_golden.jsonl](../data/router_eval_golden.jsonl)` 约 **80** 条（`[scripts/generate_router_eval_golden.py](../scripts/generate_router_eval_golden.py)` 可重写）；运行 `[scripts/run_eval_router.py](../scripts/run_eval_router.py)` 产出 `**docs/router_eval_metrics_*`**；说明见 `**[ROUTER-EVAL.md](ROUTER-EVAL.md)`**。快照指标（默认配置、`top_k=3`）：`primary_accuracy≈0.80`，`topk_overlap_hit_rate≈0.975`（以本机 `router_eval_metrics_summary.json` 为准）。
- **Router profile 继续加厚（可选）**：`[data/domain_router_profiles.json](../data/domain_router_profiles.json)` 现为 **version 2**、每 domain **5** 条 prototype；路线图原定 **8–15** / domain 可作下一小步增量。
- **Centroid 缓存**：`[app/embedding_router.py](../app/embedding_router.py)` 已对 domain prototype **均值向量**做 LRU（`clear_embedding_router_centroid_cache()` 可清空）。

进入 C 的条件：router trace-only 不伤检索；router eval 有 primary accuracy / top-k overlap；soft boost 是否启用有数据结论。

---

## C. 权限过滤强化 — **阶段性完成（2026-06-03）**

- 检索 **前** Pre-filter：`[app/access_prefilter.py](../app/access_prefilter.py)`（Chroma `ids` + BM25 子集）；规则与角色展开：`[app/access_control.py](../app/access_control.py)`；混合分归一化：`HYBRID_SCORE_NORMALIZE`。
- 评测：`[scripts/run_eval_access_control.py](../scripts/run_eval_access_control.py)`，30 条金标；**Forbidden 4/4**，**Expect 23/26**，**Domain 22/24**（见 `[ACCESS-CONTROL-EVAL.md](ACCESS-CONTROL-EVAL.md)`）。
- 收口与暂缓 3 条 Bad Case：`[PHASE-C-CLOSURE.md](PHASE-C-CLOSURE.md)`、`[ACCESS-CONTROL-BADCASE.md](ACCESS-CONTROL-BADCASE.md)` §8。
- **未做（归路线图 D）**：Qdrant payload 原生 `where` 替代 ids 预筛。

**下一阶段**：→ **[PHASE-E-NEXT.md](PHASE-E-NEXT.md)**（LangGraph）。D / F 可并行 backlog。

---

## D. Qdrant 迁移 — **本地迁移 + 权限评测已完成**

- `VECTOR_BACKEND=chroma|qdrant`、单例客户端、`query_points` Pre-filter；操作 **`[QDRANT-NEXT.md](QDRANT-NEXT.md)`**。
- **2026-06-03**：嵌入式 `QDRANT_PATH=data/qdrant_local`，302 节点 reindex；权限 eval 对比 **`[QDRANT-MIGRATION-EVAL.md](QDRANT-MIGRATION-EVAL.md)`**（Forbidden/Domain 与 Chroma 持平，Expect -1 条 AC09）。
- Docker 服务仍可选（并发 / 生产）；本机未起 Docker 时用 `QDRANT_PATH` 单进程。

默认运行路径仍为 **Chroma**，切 Qdrant 需显式 env + reindex。

---

## E. LangGraph 工单 Agent — **MVP + E4 评测已完成（2026-06-03）**

- **设计**：`data/docs/enterprise_ai_ops/08-agent-design/langgraph-ticket-agent-design.md`。
- **执行清单**：`[PHASE-E-NEXT.md](PHASE-E-NEXT.md)`；进度 **`[PHASE-E-PROGRESS.md](PHASE-E-PROGRESS.md)`**；收口 **`[PHASE-E-CLOSURE.md](PHASE-E-CLOSURE.md)`**。
- **代码**：`app/agent_graph/`（policy → retrieve → gate → draft → finalize）；**`POST /agent/ticket`**。
- **E4 评测**：`data/eval_agent_ticket.jsonl`（15 条）、`scripts/run_eval_agent_ticket.py` → `[AGENT-TICKET-EVAL.md](AGENT-TICKET-EVAL.md)`（**15/15 pass**）。

流程：`输入问题 -> policy guard -> retrieval -> evidence gate -> draft answer -> [high risk] human review -> ticket note`

**Backlog**：真实工单写回、多 Agent、与真实向量索引联调 eval。

---

## F. 可观测性 / LLMOps — **设计完成（2026-06-03）**

- **`trace_id` + JSON 结构化日志**（`/retrieve`、`/chat`、`agent_ticket` 事件行）。  
- **策略审计**：`[app/policy/audit_log.py](../app/policy/audit_log.py)`，`event=policy_eval` JSON 一行（租户/角色脱敏摘要）。  
- **设计文档**：**`[OBSERVABILITY-DESIGN.md](OBSERVABILITY-DESIGN.md)`** — trace 粒度（request、router、rewrite、retrieve、rerank、guard、LLM、citation、access control、agent_ticket）。  
- **Router eval 扩展**：`run_eval_router.py` 输出 `domain_weights`、`raw_confidence`、`routing_trace.confidence_branch`。

**未做**：Langfuse / OpenTelemetry SDK 接入、生产仪表盘。

---

## G（交接原文 §6）：微调小实验

- Domain Router 小样本微调。**非主线** — 记在 backlog；本仓库未立项。

---

## 本 Pass 已实现（与企业策略 MVP 对齐，非整阶段「完成」）


| 条目     | 说明                                                                           |
| ------ | ---------------------------------------------------------------------------- |
| 可升级护栏  | `**app/policy/`**：规则优先级冲突解析、可选向量相似层、可选智谱 JSON 分类、默认 JSON + mtime 热读          |
| API 语义 | `**intercept` 短路**；`warn` 仍检索并返回 `policy_warnings`；`/health/config` 暴露策略相关开关 |
