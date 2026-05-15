# 状态

**里程碑**: enterprise-rag-kb 路线图落地（2026-05）

**已完成**:

- 状态汇总：`docs/CURRENT-STATUS.md`（功能清单、评估产物与笔记对齐、已知问题、下一阶段命令）。
- 配置漂移：文档与 `.env.example` 统一为 **`QUERY_REWRITE_MODE`**（`off` / `on` / `auto`），与 `app/config.py` 一致；旧名 **`QUERY_REWRITE_ENABLED`** 无对应字段，Settings 为 `extra="ignore"` 时会被忽略。
- 策略护栏：`app/policy/`（默认 JSON `data/behavior_rules.default.json`，mtime 热读）、`app/behavior_guard.py` 兼容入口；`/retrieve`、`/chat` 短路拦截；审计 `event=policy_eval`。分阶段验收：`docs/POLICY-MILESTONE-ACCEPTANCE.md`。**Phase 2（规则层）** boundary intercept recall **1.0**（见 `docs/BEHAVIOR-GUARD-EVAL.md`）。
- 企业 eval 双基线重跑摘要：`docs/EVAL-RERUN-NOTES.md`（需 conda `rags` 及企业索引环境变量；本次跑使用了 `RERANK_ENABLED=false` 以缩短 CPU 耗时，见该文说明）。

**阻塞**:

- 无。默认 `python` 若无 LlamaIndex/Chroma 依赖则评估脚本无法运行，请使用已安装依赖的解释器（如 README 中的 `rags` 环境）。

**未纳入本阶段（只记录，未实现）**:

- 全量 **Embedding 路由器**
- **Qdrant** 迁移与 payload 过滤
- **LangGraph** 工单编排

**下一步建议**: 按 `docs/POLICY-MILESTONE-ACCEPTANCE.md` 推进 Phase 3–6（embedding/LLM 护栏抽检、检索四矩阵）；路线图大块见 `docs/ROADMAP-PHASES-A-F.md`。
