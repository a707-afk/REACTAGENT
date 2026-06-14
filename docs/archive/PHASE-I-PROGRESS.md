# 阶段 I：句级溯源 / 幻觉检测 — 进度说明

## 目标

在 RAG 回答与工单 Agent 草稿生成后，用**可复现的句级 grounding** 判断「每句话是否有证据支撑」，替代阶段 H 的 `node_hallucination` 桩逻辑；并与 `POST /chat` 共用 `app/citation_verify.py`。

## 已落地

| 模块 | 说明 |
|------|------|
| `app/citation_verify.py` | `GroundingReport`、`SentenceGrounding`、`sentence_level_grounding`（n-gram 默认；可选 embedding 回退） |
| `app/routes_rag.py` | 生成答案后写 `grounding` 字段到 `ChatResponse` |
| `app/agent_graph/nodes.py` | `node_hallucination` 调用 `sentence_level_grounding(..., prefer_embedding=False)` |
| `scripts/run_eval_hallucination.py` | 金标 `data/eval_hallucination.jsonl`（8 条） |
| `tests/test_citation_verify.py` | 单元测试 + `node_hallucination` 集成断言 |

## 行为说明

### `sentence_level_grounding`

1. 将答案按中英文句号/换行切句。
2. 每句在证据 chunk 上取最佳支持分（n-gram Jaccard + 子串 boost；或 embedding 余弦）。
3. 低于阈值（n-gram 默认 0.28）标 `unsupported`。
4. `unsupported_sentence_rate > 0.35` 则 `passed=False`。

### `node_hallucination`

- 跳过：`policy_skip_rag` 或 `grader_passed` 为假。
- 草稿为空 → 不通过 + `human_review_required`。
- grounding 不通过 → 不通过 + 人工复核备注。
- 异常 → 降级放行 + `human_review_required`（与阶段 H 一致）。

### API

- **`POST /chat`**：`grounding` 字典（`passed` / `sentences` / `unsupported_sentence_rate` 等）。
- **`POST /agent/ticket`**：schema 未变；`audit_trace` 的 `hallucination` 步骤含 `method`、`overlap_ratio`、`unsupported_sentence_rate`。

## 测试

```bash
pytest tests/test_citation_verify.py tests/test_agent_graph_routes.py -q
python scripts/run_eval_hallucination.py
python scripts/run_eval_agent_ticket.py
```

**验收（2026-06-04）**：`pytest` 通过；`run_eval_hallucination` 8/8；`run_eval_agent_ticket` 15/15。

## 与阶段 H 的关系

阶段 H 引入 grader 回环与 hallucination **占位**；阶段 I 将 hallucination 节点接到真实 grounding，金标 Agent 路径仍只校验 `final_action` / `human_review_required` / 必需 audit 子集，故 15 条兼容。

## 下一步（未做）

1. Agent 路径可选 `prefer_embedding=True`（与线上一致，需加载 embedding 模型）。
2. 阈值按业务集校准（`support_threshold` / `max_unsupported_rate` 进 `Settings`）。
3. grounding 失败时回环 `draft` 再生（需 LangGraph 边扩展）。
4. 可选 NLI / LLM judge 作为第三路（成本高，见 D-I1）。

## 面试讲法（30 秒）

> 我们在答案生成后做**句级 grounding**：把回复切成句子，每句在检索 chunk 上算 n-gram 支持分，标 unsupported 比例；超过 35% 就拒答或转人工。工单 Agent 的 `node_hallucination` 和 `/chat` 共用同一套 `citation_verify`，评测用 8 条 grounding 金标 + 原有 15 条 Agent 金标，都能脚本化跑通。
