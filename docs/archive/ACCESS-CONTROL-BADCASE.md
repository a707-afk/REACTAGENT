# 权限评测 Bad Case 分析（Pre-filter 后）

> **历史基线**（仅 Post-filter + 无归一化）：Expect 11/26（42%），Domain 9/24（37.5%）。  
> **当前**（Pre-filter + audience 映射 + domain 修正 + 混合归一化 + Rerank + reindex）：**Expect 23/26（88.5%）**，**Domain 22/24（91.7%）**，Forbidden 4/4。见 `docs/ACCESS-CONTROL-EVAL.md`。

---

## 1. 指标口径


| 指标          | 分子/分母 | 含义                                                   |
| ----------- | ----- | ---------------------------------------------------- |
| Expect top1 | 11/26 | 有 `expect_top1_file_contains` 的题，Top1 路径是否含期望子串      |
| Domain top1 | 9/24  | 有 `expected_domain` 的题，Top1 的 `metadata.domain` 是否一致 |
| Forbidden   | 4/4   | 低密级用户 Top5 不得出现 `forbidden_doc_substrings`           |


未计入 Expect：AC01/03/17/19（仅 forbidden 或空结果）。  
未计入 Domain：AC18/20（无 `expected_domain`）、AC01/03/17/19 等。

用户口述「domain 10/24」与 JSON **9/24** 差 1 条，以 JSON 为准（可能手工统计含 AC29 等边界样例）。

---

## 2. 十五类根因（对应 15 条 Expect 未命中）

### A. BM25 词面劫持（向量弱、BM25 分极高）— 8 条

混合召回合并时，BM25 原始分（可达 10+）压过向量相似度（0.4–0.7），Top1 被「含 metadata / 日志 / 限流」等泛词的无关 chunk 顶掉。


| ID   | 期望                               | 实际 Top1                                             | 说明                              |
| ---- | -------------------------------- | --------------------------------------------------- | ------------------------------- |
| AC09 | `knowledge-base-governance`      | `sensitive-data-redaction` (BM25≈12.9)              | 问「metadata 必填」；脱敏文含「metadata」字样 |
| AC10 | `data-classification-and-access` | `ticket-classification-priority` (BM25≈5.3)         | 「召回」「权限」与工单分类词面相近               |
| AC11 | `vector-index-rebuild`           | `faq-account-login` (BM25≈17.9)                     | 「downtime」/login FAQ 词面碰撞       |
| AC14 | `ai-app-launch-review`           | `customer-complaint-escalation-workflow` (BM25≈6.7) | 「评审」「门禁」与投诉升级流程混淆               |
| AC15 | `agent-boundary-and-hitl`        | `case-prompt-injection-ticket` (BM25≈9.0)           | 「Agent」「人工」命中案例而非治理文            |
| AC16 | `langgraph-ticket-agent`         | `case-vip-sla-escalation` (BM25≈14.4)               | 「langgraph」「状态机」与 VIP 案例共现技术词   |
| AC21 | `it-onboarding-ai-tool-access`   | `platform-overview` (BM25≈19.7)                     | 「IT」「开通」落在产品总览                  |
| AC22 | `ticket-automation-canary`       | `platform-overview` (BM25≈6.3)                      | 「灰度」「熔断」未对齐运维 canary 文          |


**改进方向**：Rerank（企业检索基线 Top1≈0.86）、BM25/向量分归一化后再 merge、或按 `source_type`/`domain` 加权。

---

### B. Case vs Playbook / Workflow 语义纠缠 — 2 条

同一业务（退款、注入）在 **07-cases** 与 **04-ticket-workflow / 06-security** 并存，问法偏「案例/playbook」时向量更贴案例 chunk。


| ID   | 期望                          | 实际 Top1                                                    |
| ---- | --------------------------- | ---------------------------------------------------------- |
| AC02 | `case-refund-human-review`  | `refund-review-workflow`（workflow 排第 1，case 在 Top2–5）      |
| AC07 | `prompt-injection-response` | `case-prompt-injection-ticket`（case 0.61 vs playbook 0.60） |


**改进方向**：题库注明要 case 还是 SOP；或 `source_type` 硬优先 / Router soft boost `security`/`ticket_workflow`。

---

### C. 金标子串 / 文件名与语料不一致 — 1 条


| ID   | 期望子串                 | 语料实际                                      | 实际 Top1                                     |
| ---- | -------------------- | ----------------------------------------- | ------------------------------------------- |
| AC23 | `ai-cost-rate-limit` | `ai-cost-rate-limit-management-policy.md` | `api-call-failure-troubleshooting-handbook` |


子串其实能匹配真文件名，但 Top1 仍是 API 排障文 → 属 **排序**；另：该政策 `audience` 为 `platform_owner,finance_liaison,product`，**不含 `support`**，严格 Pre-filter 下 support 用户 **不应** 看到此文（金标与 RBAC 矛盾）。

---

### D. Audience 角色名与题库 `support` 不对齐 — 多条（检索层「看不见」真答案）

评测统一 `roles: ["support"]`，语料常用 `support_agent`、`csm`、`knowledge_owner` 等，`**can_access_chunk_metadata` 做集合交集**，导致即使 BM25/向量命中，正确答案也不在允许集合内（或永远进不了 Top1 竞争）。

典型文档（support 无法访问）：

- `knowledge-base-governance` → `knowledge_owner,ai_engineer,ops_manager`（AC09）
- `ai-cost-rate-limit-management-policy` → `platform_owner,finance_liaison,product`（AC23）
- `customer-service-reply-scripts-standard` → `support_agent,team_lead`（AC28）
- `customer-success-renewal-risk-detection` → `csm,account_manager,rev_ops`（AC27）
- `knowledge-base-expired-document-process` → `kb_owner,content_admin,legal_liaison`（AC26）

这类题在 **严格 Pre-filter** 下属于 **评测标定问题**，不是「Post-filter 没滤干净」。

**改进方向**：语料 `audience` 增加 `support` 别名；或题库改用 `support_agent`；或映射表 `support` → `support_agent`。

---

### E. Metadata `domain` 与目录 / 金标不一致 — 1 条（Expect 命中但 Domain 失败）


| ID   | 期望 domain    | Top1 文件                                        | Top1 domain        |
| ---- | ------------ | ---------------------------------------------- | ------------------ |
| AC29 | `operations` | `customer-complaint-escalation-workflow`（路径命中） | `customer_service` |


文件在 `09-operations/` 但 front matter 标 `customer_service` → **Domain 9/24 未过的典型**。

---

### F. 跨域泛词 + 无专属高相关 chunk — 4 条


| ID   | 期望                                | 实际 Top1                     | 归类          |
| ---- | --------------------------------- | --------------------------- | ----------- |
| AC25 | `audit-logging-standard`          | `faq-data-deletion-export`  | 「审计」「租户」词面散 |
| AC26 | `knowledge-base-expired-document` | `case-rag-wrong-citation`   | 见 D + BM25  |
| AC27 | `customer-success-renewal`        | `prompt-injection-response` | 见 D         |
| AC28 | `customer-service-reply-scripts`  | `faq-data-deletion-export`  | 见 D         |


---

### G. 权限设计预期（非 Bad Case）— 2 条


| ID         | 现象                            | 结论                                               |
| ---------- | ----------------------------- | ------------------------------------------------ |
| AC01/03/17 | clearance=0，Top1 为 public FAQ | **符合设计**（restricted 不应出现）                        |
| AC19       | `roles: []`，TopK 空            | **符合设计**（`permission-filter-test-cases` 仅 qa 可读） |


---

## 3. 为何 Domain top1 只有 9/24（37.5%）？

在 **24 条带 `expected_domain` 的题** 中，15 条 Top1 的 `domain` 与金标不一致。原因可叠加上面分类：

1. **与 Expect 同步失败（12 条）**
  Top1 文件错了，`domain` 必然错（AC02/07/09–11/14–16/21/22/25–28 等）。
2. **文件对、domain 标错（1 条）**
  AC29：路径含 `customer-complaint-escalation`，金标 `operations`，metadata `customer_service`。
3. **金标 domain 与语料不一致（需人工核对）**
  - `ai-cost-rate-limit-management-policy` 在 `09-operations/`，metadata 为 `**internal_policy`**，题库 AC23 写 `operations`。  
  - `knowledge-base-expired-document-process` 在 `09-operations/`，metadata `**internal_policy`**，AC26 金标 `operations`。
4. **未评 domain 但文件命中**
  AC18 Top1 为 `case-prompt-injection-ticket`（case），题库未写 `expected_domain`。
5. **Router 未参与本评测**
  `skip_domain_router=True`，无 soft boost；开 Router 对 domain 题帮助有限，**Rerank 才是主杠杆**。

---

## 4. Pre-filter 改造说明（已完成）


| 组件                                  | 行为                                                                          |
| ----------------------------------- | --------------------------------------------------------------------------- |
| `resolve_allowed_node_ids`          | 扫 BM25 语料 metadata，与 `can_access_chunk_metadata` 一致                         |
| `vector_retrieve_access_filtered`   | Chroma `query(..., ids=allowed_list)`                                       |
| `bm25_search(..., allowed_ids=...)` | 仅在允许 ID 上排序                                                                 |
| `retrieval_pipeline`                | 有 `user_context` 时不再默认 Post-filter；`ACCESS_POST_FILTER_SAFETY_NET=true` 可兜底 |


**效果**：Forbidden 仍 100%；Expect/Domain **不变**（符合预期：未改排序与语料）。

---

## 5. 建议优先级

1. **P0**：统一 `audience` 与题库 `roles`（`support` ↔ `support_agent` 映射）。
2. **P0**：修正 AC29、`ai-cost` 等 **domain 与目录** 不一致的 front matter。
3. **P1**：企业评测默认开 **Rerank** 或 BM25 分数归一化。
4. **P1**：AC23 等金标改为 `ai-cost-rate-limit-management-policy` 或调整 audience。
5. **P2**：case/workflow 问法拆分或 `source_type` 路由。

---

## 6. 纯检索 Bad Case 清单（Expect top1=false，共 15）

`AC02, AC07, AC09, AC10, AC11, AC14, AC15, AC16, AC21, AC22, AC23, AC25, AC26, AC27, AC28`

## 7. 剩余 3 条 Expect 未命中（2026-06-03 重跑后）


| ID   | 期望                               | 实际 Top1                                      | 根因                                                                 |
| ---- | -------------------------------- | -------------------------------------------- | ------------------------------------------------------------------ |
| AC02 | `case-refund-human-review`       | `refund-review-workflow`                     | 同一退款场景 case/workflow 语义纠缠；Rerank 后 workflow 仍第 1（case 在 Top2）      |
| AC07 | `prompt-injection-response`      | `case-prompt-injection-ticket`               | 案例 chunk 与 security playbook 极近；需 `source_type` 优先或题库区分「案例 vs SOP」 |
| AC28 | `customer-service-reply-scripts` | `customer-service-quality-spot-check-policy` | 问法含「质检抽检」，与 spot-check 政策更贴；金标可改为 spot-check 或合并入口文档               |


## 8. 暂缓决策（2026-06-03，阶段 C 收口）

**决定**：本迭代 **不再修改** 代码、语料 front matter 或 `eval_access_control_questions.jsonl` 以追求 AC02 / AC07 / AC28 的 Top1 命中。


| ID   | 暂缓原因                              | 若将来处理                                             |
| ---- | --------------------------------- | ------------------------------------------------- |
| AC02 | case / workflow 语义近邻，属检索排序与题库意图边界 | `source_type=case` 优先或拆分问法                        |
| AC07 | 案例与 security SOP 争 Top1           | 题库标明要 SOP；或对 `security` domain boost              |
| AC28 | 问法偏「质检抽检」，Top1 spot-check 政策更合理   | 金标改为 `customer-service-quality-spot-check` 或接受双文档 |


**指标接受线**（阶段 C 出口）：Expect ≥ 85%、Domain ≥ 90%、Forbidden 100% — **已满足**（23/26、22/24、4/4）。  
阶段切换说明：`docs/PHASE-C-CLOSURE.md`；下一阶段：`docs/PHASE-E-NEXT.md`。

重跑评测：

```powershell
$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
python scripts/run_eval_access_control.py
```