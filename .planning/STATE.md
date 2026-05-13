# 状态

**里程碑**: enterprise-rag-kb 路线图落地（2026-05）

**已完成**:

- 状态汇总：`docs/CURRENT-STATUS.md`（功能清单、评估产物与笔记对齐、已知问题、下一阶段命令）。
- 配置漂移：文档与 `.env.example` 统一为 **`QUERY_REWRITE_MODE`**（`off` / `on` / `auto`），与 `app/config.py` 一致；旧名 **`QUERY_REWRITE_ENABLED`** 无对应字段，Settings 为 `extra="ignore"` 时会被忽略。
- 策略护栏：`app/behavior_guard.py`，`/chat` 与 `/retrieve` 在加载索引前短路；响应字段 `behavior`、`refusal_reason_code`。
- 企业 eval 双基线重跑摘要：`docs/EVAL-RERUN-NOTES.md`（需 conda `rags` 及企业索引环境变量；本次跑使用了 `RERANK_ENABLED=false` 以缩短 CPU 耗时，见该文说明）。

**阻塞**:

- 无。默认 `python` 若无 LlamaIndex/Chroma 依赖则评估脚本无法运行，请使用已安装依赖的解释器（如 README 中的 `rags` 环境）。

**未纳入本阶段（只记录，未实现）**:

- 全量 **Embedding 路由器**
- **Qdrant** 迁移与 payload 过滤
- **LangGraph** 工单编排

**下一步建议**: Qdrant 迁移（依赖与 `langchain-chroma` 版本统一后再做）、多端评测含 `user_context` 权限用例、生产环境将 `RERANK_ENABLED` 打开后重跑 eval 对照。
