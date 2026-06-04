# 企业 RAG 能力路线图（本仓库执行版）

> GSD 完整 autonomous 依赖 `.planning/STATE.md` 与历史 ROADMAP；此处为 **rag-kb-project 技术落地清单**。

## 阶段与状态

| # | 内容 | 状态 |
|---|------|------|
| 1 | `file_path` 元数据相对 `docs_dir` 一致性（basename 回查） | done |
| 2 | `UserContext` + 租户/密级/audience 检索后过滤 | done |
| 3 | 领域路由（规则 + 智谱 LLM fallback）+ **`DOMAIN_ROUTER_HARD_FILTER`（默认 off，显式 on 时 rerank 前收窄）** | done |
| 4 | `run_eval_retrieve`：top5 命中、domain top1、`EVAL_SKIP_DOMAIN_ROUTER` | done |
| 5 | 生成后 `citation_overlap_ratio` + JSON 结构化日志 + `X-Trace-ID` | done |
| 6 | Docker：`docker-compose.yml`（Qdrant）；向量后端仍以 **Chroma** 为主 | done |
| 7 | 配置对齐：`QUERY_REWRITE_MODE`（`off`/`on`/`auto`）与 `app/config.py` | done |
| 8 | 策略引擎 `app/policy/`（默认 `data/behavior_rules.default.json`，可选向量/智谱层），`app/behavior_guard.py` 薄封装 | done |
| 9 | 企业 eval 双基线（`EVAL_SKIP_DOMAIN_ROUTER` on/off），见 `docs/EVAL-RERUN-NOTES.md` | 见 STATE |
| 10 | 迁移 **Qdrant** 向量存储与生产双写 | **后续**（接口已定，避免与本里程碑混做） |

## 环境变量备忘

- `EVAL_SKIP_DOMAIN_ROUTER`：eval 脚本默认 `true`（跳过推断）；`false` + **`DOMAIN_ROUTER_HARD_FILTER=true`** 复现矩阵 r1 / 历史硬过滤；**生产默认 hard filter 关**，见 `ADR-domain-router-default.md`。
- `INFERENCE_DEVICE` / `QUERY_REWRITE_MODE`：见 `.env.example`（已废弃名称 **`QUERY_REWRITE_ENABLED`**，pydantic `extra=ignore` 会忽略旧变量，请以 `QUERY_REWRITE_MODE` 为准）。
- `BEHAVIOR_GUARD_ENABLED` / `BEHAVIOR_GUARD_RULES_PATH`：规则包路径；未配置或文件缺失时用 `data/behavior_rules.default.json`。见 `app/policy/`。
- `POLICY_EMBEDDING_GUARD` / `POLICY_EMBEDDING_THRESHOLD`（默认 0.72）、`POLICY_LLM_GUARD` / `POLICY_LLM_CONFIDENCE`（默认 0.8）：可选第二阶段护栏。
