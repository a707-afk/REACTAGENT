# Agent ticket live eval

- **Run date (UTC)**: 2026-06-03T11:17:28Z
- **Command**: `python scripts/run_eval_agent_ticket_live.py`
- **Golden subset**: `['AT-001', 'AT-002', 'AT-003']`
- **Mode**: 真实 `run_ticket_agent`（policy + Chroma retrieve + gate；LLM 失败时用占位草稿）

## 前置条件

| 项 | 说明 |
|----|------|
| 索引 | `DOCS_DIR` + `CHROMA_COLLECTION_NAME=enterprise_ai_ops` + `reindex.py` |
| 校验 | 建议 `EVAL_ENTERPRISE_STRICT=1` |
| 智谱 | 可选；无 Key 时 `draft_ready` 路径仍可有占位 `draft_reply` |

## Metrics

| Metric | Value |
|--------|-------|
| Total cases | 3 |
| Passed | 0 |
| Failed | 3 |
| Pass rate | 0.00% |

### Failed cases

- **AT-001**: runtime: InternalError: Error executing plan: Internal error: Error finding id
- **AT-002**: runtime: InternalError: Error executing plan: Internal error: Error finding id
- **AT-003**: runtime: InternalError: Error executing plan: Internal error: Error finding id

Full JSON: `docs\eval_agent_ticket_live.json`.

> 检索分与金标 mock 分不一致时，`gate_fail` / `no_evidence` 可能偏离金标；可对照 `actual.hits` 与日志 `event=retrieve|gate`。
