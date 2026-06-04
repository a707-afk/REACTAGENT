# 企业策略 / 护栏 — 分阶段验收标准

> 执行原则：**做完一块、验收一块、汇报一块**。超大项目（路线图 A–F）见 `[ROADMAP-PHASES-A-F.md](ROADMAP-PHASES-A-F.md)`，本文只约束 **策略引擎与护栏评测**。

---

## Phase 1 — 规则层 MVP（优先级 + 冲突 + JSON 热读）

**目标**：替换「一刀切正则」，支持分类、`priority`、多规则命中后 **单一胜者**（已实现：`priority` 降序 → `category_order` → `id`）。

**交付物**


| 项     | 路径                                               |
| ----- | ------------------------------------------------ |
| 策略引擎  | `app/policy/engine.py`、`models.py`、`loader.py`   |
| 默认规则包 | `data/behavior_rules.default.json`               |
| 兼容入口  | `app/behavior_guard.py` → `evaluate_policy(...)` |


**验收**

- `python -m compileall app scripts` 无报错  
- 修改 JSON 保存后 **无需重启**：`loader.load_rules_bundle` 按文件 **mtime** 失效缓存  
- `/retrieve`、`/chat` 在加载索引前调用 `evaluate_policy`，拦截时短路 RAG

**通过日期**：以首次合并策略包并经代码评审为准（当前仓库已满足）。

---

## Phase 2 — 模板正则 + 假阴性归零（规则层）

**目标**：对评估集中历史 **FN（应拦未拦）** 增补 `template_patterns` / `pattern`。

**验收**

- `python scripts/run_eval_behavior_guard.py`（默认：`POLICY_EMBEDDING_GUARD=false`、`POLICY_LLM_GUARD=false`）  
- **Recall（boundary 子集）≥ 1.0**，**Recall（high）≥ 1.0**（以脚本打印及 `docs/eval_behavior_guard.json` 为准）

**最近一次**：见 `docs/BEHAVIOR-GUARD-EVAL.md` 中的 UTC 时间与指标摘要。

---

## Phase 3 — 向量相似护栏（可选）

**条件**：本地 Embedding 可用（见 `INFERENCE_DEVICE` / Qwen 路径）。

**开关**：`POLICY_EMBEDDING_GUARD=true`，阈值 `POLICY_EMBEDDING_THRESHOLD`（默认 0.72）。

**验收**

- 启用后跑一次 `run_eval_behavior_guard.py`，summary 中 `policy_embedding_guard_enabled: true`  
- **不出现大量误杀**：抽样 10 条「应答类」eval（`answer_with_citation`）仍为 **不应短路**（脚本 `scripts/run_policy_phase3_answer_sample.py`，笔记 `[PHASE3-EMBEDDING-NOTES.md](PHASE3-EMBEDDING-NOTES.md)`）

---

## Phase 4 — 智谱 JSON 分类护栏（可选）

**条件**：配置 `ZHIPUAI_API_KEY`，`POLICY_LLM_GUARD=true`，`POLICY_LLM_CONFIDENCE`（默认 0.8）。

**验收**

- `run_eval_behavior_guard` summary 中 `policy_llm_guard_enabled: true`（与 Phase 3 同一次跑批：`POLICY_EMBEDDING_GUARD=true` + `POLICY_LLM_GUARD=true`，见 `docs/eval_behavior_guard.json`）  
- 关规则仅用 LLM 烟测 5 条边界句 → 期望 majority 判为 medium/high（`[PHASE4-LLM-GUARD-NOTES.md](PHASE4-LLM-GUARD-NOTES.md)`：4/5 为 medium/high）

---

## Phase 5 — 审计日志

**验收**

- `app/policy/audit_log.py`：`event=policy_eval` JSON 单行，`trace_id`、匹配规则、`embedding_max_sim`、`llm_`*、`user_context` 脱敏字段  
- **运维**：`app/logging_config.py` 支持环境变量 `**POLICY_AUDIT_LOG_PATH`** → 为 `app.policy.audit` 挂载仅消息的 FileHandler（`propagate=False`）；部署侧设置路径即可落盘（说明见 `.env.example`）

---

## Phase 6 — 检索四组合矩阵（与护栏独立）

**来源**：交接文档 §5、`docs/EVAL-BASELINE-COMPARISON.md`。

**验收**

- 在企业索引对齐前提下：四组 JSON **均已生成**并有 `EVAL-BASELINE-COMPARISON.md` 表格摘要（编排：`scripts/run_eval_four_baselines.py`，r1 **显式** `DOMAIN_ROUTER_HARD_FILTER=true` 以保持与历史矩阵可比；汇总 `docs/eval_four_baselines_summary.json`）

---

## 「任务 4」门禁（domain router 默认是否过滤）

**条件**：Phase 6 矩阵完成后，对比 Top-5 **不因 router on 大幅下降**（阈值由项目负责人定）。

**产出**：`[ADR-domain-router-default.md](ADR-domain-router-default.md)`：**默认 `DOMAIN_ROUTER_HARD_FILTER=false`（不按 domain 硬性淘汰候选），保留推断与 `router_trace`**；四组合表中 **r1** 列为回归专用（`EVAL_SKIP_DOMAIN_ROUTER=false` 且 `**DOMAIN_ROUTER_HARD_FILTER=true`**）。

---

## 下一阶段大块（不在本文一次性验收）

按 `[docs/PROJECT-STRATEGY-HANDOFF.md](PROJECT-STRATEGY-HANDOFF.md)` §6 与 `[ROADMAP-PHASES-A-F.md](ROADMAP-PHASES-A-F.md)`：**Embedding Router**、检索前权限、Qdrant、LangGraph、OTel/Langfuse、DB 规则表与管理后台等 — **逐项立项**，每项复制本节结构另写验收表。