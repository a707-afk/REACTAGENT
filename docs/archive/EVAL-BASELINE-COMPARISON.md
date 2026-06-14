# 企业检索四组合基线（模板）

> **用途**：在 `DOCS_DIR` / `CHROMA_COLLECTION_NAME` / `BM25_CORPUS_PATH` 与企业索引对齐的前提下，记录 **Router 关/开 × Rerank 关/开** 四组 `run_eval_retrieve.py` 结果。  
> 全矩阵可 **手工分批** 运行（总耗时较长）；有结果后再填表。

**说明**：与 `docs/CURRENT-STATUS.md`、`docs/EVAL-RERUN-NOTES.md` 中「仅 rerank 关下 A/B 双基线」的已文档化数字可并存；本表用于补齐 rerank 维度后的完整对照。

---

**路由语义（代码落地后）**

- `**EVAL_SKIP_DOMAIN_ROUTER=true`（r0）**：不调用路由推断，等价「Router 关」，响应/eval 行无 `router_trace`。
- `**EVAL_SKIP_DOMAIN_ROUTER=false`（r1）**：调用推断并写入 `router_trace`；表中 **2026-05-15** 数字对应 **同时** `DOMAIN_ROUTER_HARD_FILTER=true`（硬性按域收窄候选，历史行为）。生产默认 `**DOMAIN_ROUTER_HARD_FILTER=false`**（仅 trace，不淘汰候选）。一键编排见 `scripts/run_eval_four_baselines.py`。

---

## 建议输出文件命名


| 跳过推断 (`EVAL_SKIP_DOMAIN_ROUTER`) | Hard filter (`DOMAIN_ROUTER_HARD_FILTER`) | Rerank (`RERANK_ENABLED`) | 建议 `EVAL_OUTPUT_PATH`             |
| -------------------------------- | ----------------------------------------- | ------------------------- | --------------------------------- |
| `true`（r0）                       | `false`（默认，r0 时不影响）                       | `false`（关）                | `docs/eval_enterprise_r0_k0.json` |
| `true`                           | `false`                                   | `true`（开）                 | `docs/eval_enterprise_r0_k1.json` |
| `false`（r1）                      | `**true`（回归必须与表一致）**                      | `false`                   | `docs/eval_enterprise_r1_k0.json` |
| `false`                          | `**true`**                                | `true`                    | `docs/eval_enterprise_r1_k1.json` |


（约定：`r0`=跳过推断，`r1`=启用推断 + **回归时** hard filter on；`k0`=rerank off，`k1`=rerank on。）

---

## 运行前公共环境（与 `CURRENT-STATUS` 企业块一致）

在 `rag-kb-project` 根目录 PowerShell 中先设定（路径可按本机解释器调整）：

```powershell
cd c:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project
$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
$env:EVAL_QUESTIONS_PATH="data/eval_enterprise_questions.jsonl"
# $env:QUERY_REWRITE_MODE="auto"
```

---

## 四组合一行一抄（含 `DOMAIN_ROUTER_HARD_FILTER`）

### 1. 跳过推断 × Rerank 关 → `docs/eval_enterprise_r0_k0.json`

```powershell
$env:EVAL_SKIP_DOMAIN_ROUTER="true"
$env:DOMAIN_ROUTER_HARD_FILTER="false"
$env:RERANK_ENABLED="false"
$env:EVAL_OUTPUT_PATH="docs/eval_enterprise_r0_k0.json"
python scripts/run_eval_retrieve.py
```

### 2. 跳过推断 × Rerank 开 → `docs/eval_enterprise_r0_k1.json`

```powershell
$env:EVAL_SKIP_DOMAIN_ROUTER="true"
$env:DOMAIN_ROUTER_HARD_FILTER="false"
$env:RERANK_ENABLED="true"
$env:EVAL_OUTPUT_PATH="docs/eval_enterprise_r0_k1.json"
python scripts/run_eval_retrieve.py
```

### 3. 推断开 + Hard filter 开 × Rerank 关 → `docs/eval_enterprise_r1_k0.json`（与表内 r1 语义一致）

```powershell
$env:EVAL_SKIP_DOMAIN_ROUTER="false"
$env:DOMAIN_ROUTER_HARD_FILTER="true"
$env:RERANK_ENABLED="false"
$env:EVAL_OUTPUT_PATH="docs/eval_enterprise_r1_k0.json"
python scripts/run_eval_retrieve.py
```

### 4. 推断开 + Hard filter 开 × Rerank 开 → `docs/eval_enterprise_r1_k1.json`

```powershell
$env:EVAL_SKIP_DOMAIN_ROUTER="false"
$env:DOMAIN_ROUTER_HARD_FILTER="true"
$env:RERANK_ENABLED="true"
$env:EVAL_OUTPUT_PATH="docs/eval_enterprise_r1_k1.json"
python scripts/run_eval_retrieve.py
```

---

## 结果汇总表（有 JSON 后从 `summary` 摘录）

企业索引对齐、`EVAL_QUESTIONS_PATH=data/eval_enterprise_questions.jsonl`，跑批 UTC **2026-05-15**（单机 CPU rerank，约 50min）；**r1** 行对应 `**DOMAIN_ROUTER_HARD_FILTER=true`**（见 `summary.domain_router_hard_filter`）。明细见 `docs/eval_four_baselines_summary.json`。


| 组合    | 产物文件                         | expect_top1  | expect_top5  | domain top1  | 备注                                     |
| ----- | ---------------------------- | ------------ | ------------ | ------------ | -------------------------------------- |
| r0 k0 | `eval_enterprise_r0_k0.json` | 37/50 (0.74) | 41/50 (0.82) | 40/50 (0.80) | 跳过推断 / Rerank 关                        |
| r0 k1 | `eval_enterprise_r0_k1.json` | 42/50 (0.84) | 48/50 (0.96) | 42/50 (0.84) | 跳过推断 / Rerank 开                        |
| r1 k0 | `eval_enterprise_r1_k0.json` | 28/50 (0.56) | 30/50 (0.60) | 31/50 (0.62) | **推断 + hard filter ON** / Rerank 关（回归） |
| r1 k1 | `eval_enterprise_r1_k1.json` | 29/50 (0.58) | 31/50 (0.62) | 31/50 (0.62) | **推断 + hard filter ON** / Rerank 开（回归） |


---

## 交叉引用

- 历史双基线（rerank 关）：`docs/EVAL-RERUN-NOTES.md`（2026-05-11）。  
- 索引对齐与脚本校验：`scripts/run_eval_retrieve.py`（`EVAL_STRICT_ENTERPRISE` 等）。  
- 状态总览：`docs/CURRENT-STATUS.md`。

### 矩阵与提交策略（与交接 §6-A 对齐）

全 **4×50 条检索**耗时与 GPU 环境相关，**不因缺全矩阵阻断提交**。若 `.venv`/conda 企业索引就绪，建议 CI 之外 **至少跑一次** 烟测（例如上表组合 1：`r0_k0`，router_off + rerank_off），再回填 `EVAL-BASELINE-COMPARISON.md` 表格；其余三格仍可手工长跑补全。