# 路线图 §6（A–G）与本仓库对齐

> 来源：`docs/PROJECT-STRATEGY-HANDOFF.md` 「6. 中长期路线图」。本文用 ** checkbox + 仓库现状 + 下一阶段首个可执行条目**（**本 Pass 不包含** OPA、完整 LangGraph、Qdrant 默认化、管理员 UI）。

---

## A. 评估闭环稳定

目标：检索 / 路由 / 护栏 / 权限均能用 **数据证明** 是否有效；有可信 baseline comparison。

- [ ] **检索四组合矩阵**：`router on/off × rerank on/off` 全填满（耗时高，模板见 [`docs/EVAL-BASELINE-COMPARISON.md`](EVAL-BASELINE-COMPARISON.md)，**不阻断日常提交**）。  
      **首个任务**：单机企业索引就绪后跑一次 `EVAL_SKIP_DOMAIN_ROUTER=true`、`RERANK_ENABLED=false` 烟测并落盘 `docs/eval_enterprise_r0_k0.json`。
- [x] **Behavior / policy intercept eval**：[`scripts/run_eval_behavior_guard.py`](../scripts/run_eval_behavior_guard.py)，产物 [`eval_behavior_guard.json`](eval_behavior_guard.json)、[`BEHAVIOR-GUARD-EVAL.md`](BEHAVIOR-GUARD-EVAL.md)。**Phase 2（仅规则层）**：边界子集 recall **1.0**（详见 [`POLICY-MILESTONE-ACCEPTANCE.md`](POLICY-MILESTONE-ACCEPTANCE.md)）；向量/LLM 护栏开启后的「不误杀」抽检仍为 TODO。
- [ ] **权限评测独立跑批**：`user_context` 变参仍缺专用脚本 — **首个文件**：可从 `scripts/run_eval_behavior_guard.py` 抽公共 JSONL 读取，另建 `scripts/run_eval_access_control.py`。

---

## B. Embedding Router

- [ ] 规则路由 + embedding router + LLM fallback。  
      **下一阶段首个落地**：[`data/router_examples.jsonl`](../data/docs/enterprise_ai_ops/11-router-examples/) 已有示例文档；需新增 **`app/embedding_router.py`** 与对齐的 eval 导出。

---

## C. 权限过滤强化

- [ ] 检索 **前** 过滤（向量库/Qdrant payload filter），配套权限 eval。  
      **现状**：[`app/access_control.py`](../app/access_control.py) 为检索后过滤。首个任务：**设计 payload schema + 单次 PoC API 参数**，再改 `retrieval_pipeline.py` 钩子。

---

## D. Qdrant 迁移

- [ ] `VECTOR_BACKEND=chroma|qdrant`、`app/qdrant_index_store.py`、enterprise eval 回归。  
      **下一阶段首个落地**：读 [`docs/QDRANT-NEXT.md`](QDRANT-NEXT.md)，建最小 `docker-compose` 对齐层（仍可选；**本 Pass 未实现**）。

---

## E. LangGraph 工单 Agent

- [ ] `app/agent_graph/`（状态机 + HITL + 工单备注）。  
      **知识库**：`data/docs/enterprise_ai_ops/08-agent-design/langgraph-ticket-agent-design.md`。**代码仍为 0** — 下一阶段从 `state.py` + hello graph 起步。

---

## F. 可观测性 / LLMOps

- [x] **`trace_id` + JSON 结构化日志**（`/retrieve`、`/chat` 事件行）。  
- [x] **策略审计**：[`app/policy/audit_log.py`](../app/policy/audit_log.py)，`event=policy_eval` JSON 一行（租户/角色脱敏摘要）。  
- [ ] **Langfuse / OpenTelemetry、`docs/OBSERVABILITY-DESIGN.md`**。首个任务：**写设计文档占位 + 选一个 trace 后端 SDK**。

---

## G（交接原文 §6）：微调小实验

- [ ] Domain Router 小样本微调。**非主线** — 记在 backlog；本仓库未立项。

---

## 本 Pass 已实现（与企业策略 MVP 对齐，非整阶段「完成」）

| 条目 | 说明 |
|------|------|
| 可升级护栏 | **`app/policy/`**：规则优先级冲突解析、可选向量相似层、可选智谱 JSON 分类、默认 JSON + mtime 热读 |
| API 语义 | **`intercept` 短路**；`warn` 仍检索并返回 `policy_warnings`；`/health/config` 暴露策略相关开关 |
