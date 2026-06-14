# Agent ticket path eval

- **Run date (UTC)**: 2026-06-04T03:25:52Z
- **Command**: `python scripts/run_eval_agent_ticket.py`（repo root）
- **Golden**: `data\eval_agent_ticket.jsonl`
- **Mode**: mock `evaluate_policy` / `retrieve_scored_nodes` / LLM（不加载 Chroma/Qdrant）

## Metrics

| Metric | Value |
|--------|-------|
| Total cases | 15 |
| Passed | 15 |
| Failed | 0 |
| Pass rate | 100.00% |

### By `final_action`

| final_action | count |
|--------------|-------|
| await_human_review | 2 |
| draft_ready | 3 |
| gate_fail | 3 |
| no_evidence | 3 |
| policy_intercept | 4 |

### Coverage

- `policy_intercept`：策略短路，audit 不含 retrieve
- `no_evidence` / `gate_fail`：检索或门控失败，跳过 draft
- `draft_ready` / `await_human_review`：完整路径至 finalize

### Failed cases

(none)

Full JSON: `docs\eval_agent_ticket.json`.
