# 阶段 E 收口（LangGraph 工单 Agent）

> 更新：2026-06-03。设计：`data/docs/enterprise_ai_ops/08-agent-design/langgraph-ticket-agent-design.md`。

---

## 交付物

| 项 | 路径 | 说明 |
|----|------|------|
| E1–E3 MVP | `app/agent_graph/`、`POST /agent/ticket` | policy → retrieve → gate → draft → finalize |
| E4 路径金标 | `data/eval_agent_ticket.jsonl` | **15** 条，覆盖 5 类 `final_action` |
| E4 评测脚本 | `scripts/run_eval_agent_ticket.py` | mock policy/retrieve/LLM，不加载向量索引 |
| E4 产物 | `docs/eval_agent_ticket.json`、`docs/AGENT-TICKET-EVAL.md` | 最近一次 **15/15 pass（100%）** |
| 单测 | `tests/test_agent_graph_compile.py` | 编译 + 策略短路 + 低风险 mock 路径 |

---

## E4 评测摘要（2026-06-03）

| 指标 | 值 |
|------|-----|
| 用例总数 | 15 |
| 通过 | 15 |
| 通过率 | 100% |

### 按 `final_action` 分布

| final_action | 条数 | 验证要点 |
|--------------|------|----------|
| `policy_intercept` | 4 | audit 含 policy/finalize，**不含** retrieve |
| `no_evidence` | 3 | gate 失败 NO_RESULTS，跳过 draft |
| `gate_fail` | 3 | 低 rerank 分 &lt; 阈值，跳过 draft |
| `draft_ready` | 3 | 完整路径含 draft，人工审核=false |
| `await_human_review` | 2 | gate 通过但 policy 要求人工或 risk=high |

运行：

```powershell
cd rag-kb-project
python scripts/run_eval_agent_ticket.py
pytest tests/test_agent_graph_compile.py -q
```

---

## 明确未做（归 backlog）

- 真实工单系统写回、多 Agent 编排、OPA 外置策略
- Agent 路径与真实向量索引联调 eval（当前 E4 为 mock，与单测一致）
- `ARCHITECTURE.md` Agent 专节已在本次文档同步中补充

---

## 与阶段 D / F 关系

- **D（Qdrant）**：Agent `node_retrieve` 经 `get_vector_index()` 门面，默认仍 Chroma；见 `docs/QDRANT-MIGRATION-EVAL.md`。
- **F（可观测性）**：Agent 侧 `event=agent_ticket` JSON 行 + `audit_trace` 步骤；设计见 `docs/OBSERVABILITY-DESIGN.md`。
