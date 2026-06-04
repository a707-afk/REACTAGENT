# 阶段 H：Agent 真改造 — 进度说明

## 目标

将 `POST /agent/ticket` 背后的 LangGraph 从**直线 Pipeline**升级为**最小可演示的 Agentic 闭环**：检索质量不够时自动改写 query 重试，草稿生成后做幻觉检测桩，并保留三层保护。

## 架构变化

### 改造前（直线）

```
policy → retrieve → gate ──fail──→ finalize
                      └──pass──→ draft → finalize
```

- `gate` 失败直接 `finalize`，无回环
- `multi_graph` 的 supervisor 仅路由 escalation 桩

### 改造后（Agentic 闭环）

```
policy → retrieve → gate → grader ──pass──→ draft → hallucination → finalize
                              │
                              └──fail & iter<3──→ rewrite_query ──┐
                              └──fail & iter≥3 / loop──→ finalize  │
                                                                    │
                              └─────────────────────────────────────┘
                                         (回到 retrieve)
```

### 新增状态字段（`TicketAgentState`）

| 字段 | 用途 |
|------|------|
| `iterations` / `max_iterations` | 检索-评分回环计数（默认 max=3） |
| `grader_passed` / `grader_feedback` | 证据是否足够支撑草稿 |
| `hallucination_passed` / `hallucination_feedback` | 草稿句级 grounding（阶段 I 已接 `citation_verify`） |
| `citations` | 引用占位，便于后续接 `citation_verify` |
| `rewrite_history` / `loop_detected` | 相同改写动作循环检测 |

### 新增节点

1. **`node_grader`**：启发式评分（门控通过 + chunk≥1 + 最优分≥阈值×0.9）。TODO：可换 LLM grader。
2. **`node_rewrite_query`**：按轮次追加「详细说明 / 相关政策流程 / …」后缀改写 query。
3. **`node_hallucination`**：阶段 I 已接 `sentence_level_grounding`（见 [PHASE-I-PROGRESS.md](PHASE-I-PROGRESS.md)）。

### 三层保护

1. **`max_iterations=3`**：`route_after_grader` 超限则 `finalize`，保留 gate 阶段写入的 `final_action`（如 `gate_fail` / `no_evidence`）。
2. **相同 action 循环检测**：`rewrite_history` 中出现相同 `rewrite:{query}` 签名则 `loop_detected=True`，立即 `finalize`。
3. **异常降级**：`grader` / `hallucination` 捕获异常 — 前者标记不通过，后者降级放行并 `human_review_required=True`。

## API 兼容性

- **`POST /agent/ticket`** 请求/响应 schema 未变；`audit_trace` 会多出 `grader` / `rewrite_query` / `hallucination` 步骤。
- 金标评测仍校验**必需步骤子集**与 **forbidden_steps**，不强制完整路径一致。

## 测试

```bash
pytest tests/test_agent_graph_compile.py tests/test_agent_graph_routes.py -q
python scripts/run_eval_agent_ticket.py
```

## 面试讲法（30 秒版）

> 我们把工单 Agent 从「一次性 RAG 管道」改成了 **LangGraph 条件回环**：gate 之后加 **grader** 判断证据够不够；不够就 **rewrite query** 再 retrieve，最多 3 轮，并用 rewrite 签名防死循环。证据够了才 **draft**，之后走 **hallucination 桩** 和 citations 占位。失败路径仍落到原来的 `gate_fail` / `no_evidence`，成功路径仍是 `draft_ready`，所以线上 API 和金标 15 条评测都兼容。下一步可以把 grader / hallucination 换成 LLM 或现有的 `citation_verify`。

## 下一步建议

1. grader 换 LLM structured output（pass/fail + 改写建议）
2. hallucination 接 `app/citation_verify.py`
3. multi_graph supervisor 扩展：按 grader 失败次数路由 escalation
4. 在 `TicketAgentResponse` 中可选暴露 `grader_feedback` / `citations` 供前端展示
