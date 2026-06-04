# 阶段 C 收口：权限过滤与评测（2026-06-03）

> **结论**：路线图 **C（权限过滤强化）** 的 MVP 目标已达成，可进入 **阶段 E（LangGraph 工单 Agent）**。  
> 远期 **Qdrant payload filter（路线图 D）** 与 **可观测性设计（路线图 F）** 可并行立项，但不阻塞 E。

---

## 已交付


| 项          | 说明                                                                             |
| ---------- | ------------------------------------------------------------------------------ |
| Pre-filter | `app/access_prefilter.py`：Chroma `ids` + BM25 可访问子集，检索前收窄                      |
| 规则         | `app/access_control.py`：tenant / 密级 / audience；`support` ↔ `support_agent` 等映射 |
| 混合召回       | `HYBRID_SCORE_NORMALIZE=true`：BM25/向量 min-max 后 merge                          |
| 评测         | `scripts/run_eval_access_control.py`，30 条金标，`docs/ACCESS-CONTROL-EVAL.md`      |
| 语料         | `enterprise_ai_ops` metadata 修正 + reindex（302 节点）                              |


## 评测指标（企业索引，默认 Rerank + 归一化）


| 指标             | 结果               |
| -------------- | ---------------- |
| Forbidden top5 | **4/4**          |
| Expect top1    | **23/26（88.5%）** |
| Domain top1    | **22/24（91.7%）** |


产物：`docs/eval_access_control.json`（UTC 2026-06-03T04:38:50）。

## 进入阶段 E 的前置（已满足）

依据 `docs/ROADMAP-PHASES-A-F.md` §E：

- 企业 RAG 基线（检索四组合 / rerank 矩阵）已有落盘文档。
- Router 生产默认 trace-only（`DOMAIN_ROUTER_HARD_FILTER=false`）。
- 权限 eval **稳定一轮**（上表；Forbidden 全通过）。

---

## 暂缓项（本阶段不再改代码/金标）

以下 3 条记入 backlog，**当前迭代不处理**（详见 `docs/ACCESS-CONTROL-BADCASE.md` §8）：

- **AC02**：case vs refund workflow Top1 纠缠  
- **AC07**：prompt injection 案例 vs security playbook  
- **AC28**：质检话术金标 vs spot-check 政策语义更接近

可选后续（非阻塞 E）：`source_type` 轻量 boost、金标微调、Rerank 阈值实验。

---

## 未纳入本阶段（仍属路线图 D）

- Qdrant 默认向量后端、`VECTOR_BACKEND` 切换  
- Chroma 上原生 `where` 替代 `ids` 全表预筛（当前 Pre-filter 已满足 Tenant Isolation 评测目标）

---

## 下一阶段

→ **[PHASE-E-NEXT.md](PHASE-E-NEXT.md)**（LangGraph 工单 Agent：状态定义 + hello graph + 与现有 `/retrieve`、`evaluate_policy` 对接）