# G–K 阶段指标与要点汇总

> 数字均摘自仓库内评测产物与阶段文档，**未编造**。rerank 关 / 开口径勿混读。

---

## 阶段 G：检索层（RRF + Rewrite）

**口径**：企业 50 题 `eval_enterprise_questions.jsonl`，`EVAL_SKIP_DOMAIN_ROUTER=true`，`RERANK_ENABLED=false`，`HYBRID_BM25_ENABLED=true`。

| 配置 | Top-1 | Top-5 | Domain Top-1 |
|------|------:|------:|-------------:|
| **max**（基线） | 35/50 (70%) | 45/50 (90%) | 32/50 (64%) |
| **RRF k=20/40/60/80** | 39/50 (78%) | 46/50 (92%) | 36/50 (72%) |
| Rewrite **off**（RRF k=60） | 38/50 (76%) | 47/50 (94%) | 35/50 (70%) |
| Rewrite **on**（RRF k=60） | 39/50 (78%) | 46/50 (92%) | 36/50 (72%) |

**要点**：

- RRF 相对 max：Top-1 **+4**，Top-5 **+1**，Domain **+4**；k∈{20,40,60,80} 在本集 **同分**。
- Rewrite **on** vs **off**：Top-1 **+1**，Domain **+1**；Top-5 **−1**（47→46）。
- 推荐：新环境显式 `HYBRID_FUSION=rrf`、`HYBRID_RRF_K=60`；改写保持 **`auto`**（与 on 同 Top-1/domain，省调用）。

来源：[PHASE-G-RESULTS.md](PHASE-G-RESULTS.md)、[DECISION-LOG.md](DECISION-LOG.md) D-03 / D-09。

---

## 阶段 H：Agentic 闭环

**架构**：`policy → retrieve → gate → grader ⇄ rewrite_query → draft → hallucination → finalize`。

| 项 | 内容 |
|----|------|
| 回环上限 | `max_iterations=3` |
| 防死循环 | `rewrite_history` 相同签名 → `loop_detected` |
| API | `POST /agent/ticket` schema **未变**；`audit_trace` 新增 grader / rewrite_query / hallucination |
| 评测 | 金标 15/15 pass（`run_eval_agent_ticket.py`） |

来源：[PHASE-H-PROGRESS.md](PHASE-H-PROGRESS.md)。

---

## 阶段 I：句级 grounding

| 项 | 内容 |
|----|------|
| 模块 | `app/citation_verify.py` — n-gram 默认阈值 0.28，`unsupported_sentence_rate > 0.35` → fail |
| `/chat` | 响应新增 `grounding` 字段 |
| Agent | `node_hallucination` 接真实 grounding（非桩） |
| 评测 | grounding 金标 8/8；Agent 金标仍 15/15 |

来源：[PHASE-I-PROGRESS.md](PHASE-I-PROGRESS.md)。

---

## 阶段 J：缓存 + 指标

| 项 | 默认 | 说明 |
|----|------|------|
| L1 精确缓存 | `CACHE_ENABLED=true`，256 条 | query + 配置指纹 + 租户上下文 |
| L2 语义缓存 | `CACHE_SEMANTIC_ENABLED=false` | 可选 embedding 余弦 ≥0.92 |
| `/metrics` | Prometheus 文本 | 无 `prometheus_client` 时 stub |
| 失效 | `reindex` → `cache_clear()` | |

来源：[PHASE-J-PROGRESS.md](PHASE-J-PROGRESS.md)。

---

## 阶段 K：交付层（摘要）

| 项 | 内容 |
|----|------|
| SSE | `/chat/stream`、`/agent/ticket/stream` |
| 前端 | `frontend/` → `static/app/`，挂载 `/app/` |
| Docker | 多阶段 Dockerfile + compose `api` + `qdrant` |

来源：[PHASE-K-PROGRESS.md](PHASE-K-PROGRESS.md)。

---

## 历史基线（勿与 G 表混读）

2026-05-11 双基线（**rerank 关**）：跳过 router Top-1 **0.64**，router+hard filter **0.54** — 见 [EVAL-RERUN-NOTES.md](EVAL-RERUN-NOTES.md)、[CURRENT-STATUS.md](CURRENT-STATUS.md)。

权限评测（2026-06-03）：Forbidden **4/4**，Expect **23/26 (88.5%)**，Domain **22/24 (91.7%)** — [ACCESS-CONTROL-EVAL.md](ACCESS-CONTROL-EVAL.md)。
