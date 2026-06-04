# 阶段 E 进度（LangGraph 工单 Agent）

> 更新：2026-06-03。设计文档：`data/docs/enterprise_ai_ops/08-agent-design/langgraph-ticket-agent-design.md`。收口：**`docs/PHASE-E-CLOSURE.md`**。

---

## 已完成

| 项 | 路径 |
|----|------|
| E1 状态与图 | `app/agent_graph/state.py`、`graph.py`、`nodes.py` |
| E2 真实节点 | policy → retrieve → gate → draft → finalize；复用 `evaluate_policy`、`retrieve_scored_nodes`、`evaluate_similarity_gate`、`chat_completion`（失败占位） |
| E3 API | `POST /agent/ticket` — `app/routes_agent.py`；`TicketAgentRequest/Response` — `app/schemas.py`；`app/main.py` 注册 + `/health/config` 暴露 `vector_backend` |
| **E4 路径评测** | `data/eval_agent_ticket.jsonl`（15 条）、`scripts/run_eval_agent_ticket.py` → `docs/eval_agent_ticket.json`、`docs/AGENT-TICKET-EVAL.md`（**15/15 pass**） |
| 单测 | `tests/test_agent_graph_compile.py`（编译 + 策略短路 + 低风险 mock 路径） |
| 依赖 | `langgraph`、`qdrant-client`、`llama-index-vector-stores-qdrant` — `requirements.txt` |
| 架构文档 | `docs/ARCHITECTURE.md` Agent + Qdrant 门面一节 |

---

## 阶段 D（并行，代码就绪）

- `VECTOR_BACKEND=chroma|qdrant`、`app/qdrant_index_store.py`、`app/vector_index.py`
- 操作说明：`docs/QDRANT-NEXT.md`
- `docker-compose.yml` 含 Qdrant 服务

**2026-06-03**：本地 `QDRANT_PATH=data/qdrant_local` 已 reindex（302 节点）+ 权限 eval；报告见 `docs/QDRANT-MIGRATION-EVAL.md`。Docker 可选。

---

## 未做（backlog）

- 真实工单系统写回、多 Agent、OPA
- Agent 与真实向量索引的端到端 eval（E4 当前为 mock 路径金标）

---

## 验收自检

```powershell
cd rag-kb-project
pytest tests/test_agent_graph_compile.py -q
python scripts/run_eval_agent_ticket.py
uvicorn app.main:app --reload
# POST /agent/ticket  body: ticket_id, user_query, user_context
```

期望：`audit_trace` 含 policy/retrieve/gate/draft/finalize 子集；策略命中时 `final_action=policy_intercept` 且不调用检索。
