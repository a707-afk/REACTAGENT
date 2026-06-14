# 阶段 G：检索层补强 — 评测结果

> **日期**：2026-06-04  
> **问题集**：`data/eval_enterprise_questions.jsonl`（50 条）  
> **解释器**：`D:\conda\envs\rags\python.exe`  
> **脚本**：`scripts/run_eval_retrieve.py`

## 统一口径（除下表「变量列」外均相同）

| 项 | 值 |
|---|---|
| `DOCS_DIR` | `data/docs/enterprise_ai_ops` |
| `CHROMA_COLLECTION_NAME` | `enterprise_ai_ops` |
| `BM25_CORPUS_PATH` | `data/bm25_enterprise_corpus.jsonl` |
| `EVAL_SKIP_DOMAIN_ROUTER` | `true` |
| `RERANK_ENABLED` | `false` |
| `HYBRID_BM25_ENABLED` | `true`（默认） |
| `bm25_candidate_top_k` | 20 |

---

## 1. 混合融合：max vs RRF（k 网格）

| 配置 | Top-1 | Top-5 | Domain Top-1 | 产物 |
|---|---:|---:|---:|---|
| **max**（基线） | 35/50 (70%) | 45/50 (90%) | 32/50 (64%) | `eval_phase_g_baseline_max_rerank_off.json` |
| **RRF k=20** | 39/50 (78%) | 46/50 (92%) | 36/50 (72%) | `eval_phase_g_rrf20_rerank_off.json` |
| **RRF k=40** | 39/50 (78%) | 46/50 (92%) | 36/50 (72%) | `eval_phase_g_rrf40_rerank_off.json` |
| **RRF k=60** | 39/50 (78%) | 46/50 (92%) | 36/50 (72%) | `eval_phase_g_rrf60_rerank_off.json` |
| **RRF k=80** | 39/50 (78%) | 46/50 (92%) | 36/50 (72%) | `eval_phase_g_rrf80_rerank_off.json` |

RRF 网格使用 `QUERY_REWRITE_MODE=auto`（与基线 max 一致）。

**相对 max**：Top-1 **+4**，Top-5 **+1**，Domain Top-1 **+4**。  
**k 敏感性**：在本 50 题上 **k∈{20,40,60,80} 指标完全相同**（排序未变）。

---

## 2. Query Rewrite：off vs on

固定 `HYBRID_FUSION=rrf`、`HYBRID_RRF_K=60`，仅改改写模式：

| `QUERY_REWRITE_MODE` | Top-1 | Top-5 | Domain Top-1 | 产物 |
|---|---:|---:|---:|---|
| **off** | 38/50 (76%) | 47/50 (94%) | 35/50 (70%) | `eval_phase_g_rewrite_off.json` |
| **on** | 39/50 (78%) | 46/50 (92%) | 36/50 (72%) | `eval_phase_g_rewrite_on.json` |

**对比**：**on** 比 **off** Top-1 **+1**、Domain **+1**；Top-5 **−1**（47→46）。  
**auto**（RRF 网格）：Top-1/domain 与 **on** 相同（39/36），Top-5 与 **on** 相同（46），介于 off/on 之间。

---

## 3. 结论与推荐默认

### 混合融合

- **推荐**：`HYBRID_FUSION=rrf`，`HYBRID_RRF_K=60`（k 在本集上不敏感，60 与文献默认及 `app/config.py` 默认一致）。
- **代码默认仍为 `max`**：避免破坏历史四组合矩阵与既有部署；新环境/企业评测应显式设 `rrf`。
- **决策档案**：[DECISION-LOG.md](DECISION-LOG.md) **D-03** 已用上表数据回填。

### Query Rewrite

- **推荐保持 `QUERY_REWRITE_MODE=auto`**（代码默认）：本集 Top-1/domain 与 **on** 持平，且避免对已是规范问句的条目每次都调智谱。
- 若 **只追 Top-1/domain、可接受略降 Top-5 与延迟成本**：可试 `on`。
- **决策档案**：**D-09** 已补充全量 50 题 off/on 数字。

### 与 rerank 的关系

本阶段为 **rerank 关** 口径，便于隔离融合与改写收益。上线默认若 **Rerank 开**，需另跑矩阵（见 `docs/EVAL-BASELINE-COMPARISON.md`）再定生产阈值，勿与本表直接横比。

---

## 4. 单测

```powershell
D:\conda\envs\rags\python.exe -m pytest tests/test_hybrid_merge.py -q
```

**结果**：4 passed（2026-06-04）。

---

## 5. 复现命令示例

```powershell
$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
$env:EVAL_QUESTIONS_PATH="data/eval_enterprise_questions.jsonl"
$env:EVAL_SKIP_DOMAIN_ROUTER="true"
$env:RERANK_ENABLED="false"

# RRF k=60
$env:HYBRID_FUSION="rrf"
$env:HYBRID_RRF_K="60"
$env:QUERY_REWRITE_MODE="auto"
$env:EVAL_OUTPUT_PATH="docs/eval_phase_g_rrf60_rerank_off.json"
D:\conda\envs\rags\python.exe scripts/run_eval_retrieve.py

# Rewrite on（其余同上）
$env:QUERY_REWRITE_MODE="on"
$env:EVAL_OUTPUT_PATH="docs/eval_phase_g_rewrite_on.json"
D:\conda\envs\rags\python.exe scripts/run_eval_retrieve.py
```
