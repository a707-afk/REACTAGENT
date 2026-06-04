# 状态

**里程碑**: enterprise-rag-kb 路线图落地（2026-05 → 2026-06）

**已完成**:

- 状态汇总：`docs/CURRENT-STATUS.md`。
- 策略护栏：`docs/POLICY-MILESTONE-ACCEPTANCE.md`、`docs/BEHAVIOR-GUARD-EVAL.md`。
- Embedding Router：`docs/ROUTER-EVAL.md`（primary_accuracy≈0.80）。
- **阶段 C 权限**：Pre-filter、混合归一化、权限评测 **23/26 / 22/24 / 4/4**；收口 `docs/PHASE-C-CLOSURE.md`。
- **阶段 D Qdrant**：本地 `data/qdrant_local` reindex + 权限 eval（`docs/QDRANT-MIGRATION-EVAL.md`）；默认运行仍 Chroma。
- **阶段 E**：LangGraph MVP + E4 路径评测 **15/15**（`docs/PHASE-E-CLOSURE.md`）。
- **阶段 F**：可观测性设计（`docs/OBSERVABILITY-DESIGN.md`）；router eval 含 `domain_weights` 等字段。
- **下一里程碑（本 Pass）**：F JSON 日志切片、`run_eval_agent_ticket_live.py`、`smoke_agent_ticket.py`、`static/index.html` Agent UI、`docs/NEXT-MILESTONE.md`、Chroma Pre-filter ID 对齐修复。

**当前阶段**: **A–F 之后 Pass 收尾 — 可观测性 + Agent DX + 快速验证**

**暂缓**: 权限 AC02/07/28；OPA；多 Agent；Qdrant 生产默认切换；Langfuse/OTel SDK

**阻塞**: 无。

**Backlog**: 见 `docs/NEXT-MILESTONE.md`（Qdrant 生产默认、OTel、管理 UI、G 微调）
