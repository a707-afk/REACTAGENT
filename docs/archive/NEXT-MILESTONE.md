# 下一里程碑 backlog（路线图 A–F 之后）

> 更新：2026-06-03。上一 Pass 已完成 LangGraph 工单 Agent、E4 mock 路径评测、可观测性设计与 F 最小 JSON 日志切片。

## 建议实施顺序

| 优先级 | 项 | 说明 | 依赖 |
|--------|-----|------|------|
| P0 | **可观测性接入后端** | `retrieve` / `gate` / `query_rewrite` 已 stdout JSON；接 Loki/ELK handler | F 切片 |
| P0 | **Agent live eval 常态化** | `scripts/run_eval_agent_ticket_live.py` + CI 可选 job | 企业 Chroma 索引 |
| P1 | **Qdrant 生产默认** | `VECTOR_BACKEND=qdrant` + Docker/`QDRANT_URL`；见 `QDRANT-NEXT.md` | D 评测通过 |
| P1 | **管理 UI / 规则表** | 策略规则 DB + 简易管理页（暂缓 AC02/07/28 评测补齐） | 策略引擎 |
| P2 | **OpenTelemetry** | HTTP span + retrieve/gate/LLM 子 span | 集中式日志 |
| P2 | **Langfuse** | LLM 与 Agent 步骤采样 | OTel 或并行 |
| P2 | **权限 AC02/07/28** | 补齐 `eval_access_control` 金标 | 企业索引 |
| P3 | **OPA / 多 Agent** | 外部策略与编排扩展 | 产品决策 |
| P3 | **阶段 G 微调** | Router/门控阈值、Query Rewrite 评测迭代 | eval 基线 |

## 本 Pass 已交付（下一里程碑起点）

- `app/observability.py`：`event=retrieve|gate|query_rewrite`
- `scripts/run_eval_agent_ticket_live.py`：企业 KB 检索路径金标（默认 AT-005/011/014/015）
- `scripts/smoke_agent_ticket.py`：HTTP 冒烟 `/health` + `/agent/ticket`
- `static/index.html`：工单 Agent 表单 → `POST /agent/ticket`
- `app/access_prefilter.py`：Chroma Pre-filter 仅 query 集合内存在的 ID
- 文档：`AGENT-TICKET-LIVE-EVAL.md`、`README` 快速验证、`.env.example`

## 暂缓（不变）

- git commit（由用户触发）
- OPA、多 Agent 编排
- Langfuse/OTel SDK 依赖引入
