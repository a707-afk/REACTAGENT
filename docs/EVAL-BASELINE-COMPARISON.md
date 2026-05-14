# 企业检索四组合基线（模板）

> **用途**：在 `DOCS_DIR` / `CHROMA_COLLECTION_NAME` / `BM25_CORPUS_PATH` 与企业索引对齐的前提下，记录 **Router 关/开 × Rerank 关/开** 四组 `run_eval_retrieve.py` 结果。  
> 全矩阵可 **手工分批** 运行（总耗时较长）；有结果后再填表。

**说明**：与 `docs/CURRENT-STATUS.md`、`docs/EVAL-RERUN-NOTES.md` 中「仅 rerank 关下 A/B 双基线」的已文档化数字可并存；本表用于补齐 rerank 维度后的完整对照。

---

## 建议输出文件命名

| Router (`EVAL_SKIP_DOMAIN_ROUTER`) | Rerank (`RERANK_ENABLED`) | 建议 `EVAL_OUTPUT_PATH` |
|-----------------------------------|---------------------------|-------------------------|
| `true`（关） | `false`（关） | `docs/eval_enterprise_r0_k0.json` |
| `true`（关） | `true`（开） | `docs/eval_enterprise_r0_k1.json` |
| `false`（开） | `false`（关） | `docs/eval_enterprise_r1_k0.json` |
| `false`（开） | `true`（开） | `docs/eval_enterprise_r1_k1.json` |

（约定：`r0`=skip router，`r1`=router on；`k0`=rerank off，`k1`=rerank on。）

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

## 四组合一行一抄（改 `EVAL_SKIP_DOMAIN_ROUTER` / `RERANK_ENABLED` / `EVAL_OUTPUT_PATH`）

### 1. Router 关 × Rerank 关 → `docs/eval_enterprise_r0_k0.json`

```powershell
$env:EVAL_SKIP_DOMAIN_ROUTER="true"
$env:RERANK_ENABLED="false"
$env:EVAL_OUTPUT_PATH="docs/eval_enterprise_r0_k0.json"
python scripts/run_eval_retrieve.py
```

### 2. Router 关 × Rerank 开 → `docs/eval_enterprise_r0_k1.json`

```powershell
$env:EVAL_SKIP_DOMAIN_ROUTER="true"
$env:RERANK_ENABLED="true"
$env:EVAL_OUTPUT_PATH="docs/eval_enterprise_r0_k1.json"
python scripts/run_eval_retrieve.py
```

### 3. Router 开 × Rerank 关 → `docs/eval_enterprise_r1_k0.json`

```powershell
$env:EVAL_SKIP_DOMAIN_ROUTER="false"
$env:RERANK_ENABLED="false"
$env:EVAL_OUTPUT_PATH="docs/eval_enterprise_r1_k0.json"
python scripts/run_eval_retrieve.py
```

### 4. Router 开 × Rerank 开 → `docs/eval_enterprise_r1_k1.json`

```powershell
$env:EVAL_SKIP_DOMAIN_ROUTER="false"
$env:RERANK_ENABLED="true"
$env:EVAL_OUTPUT_PATH="docs/eval_enterprise_r1_k1.json"
python scripts/run_eval_retrieve.py
```

---

## 结果汇总表（有 JSON 后从 `summary` 摘录）

| 组合 | 产物文件 | expect_top1 | expect_top5 | domain top1 | 备注 |
|------|-----------|-------------|-------------|---------------|------|
| r0 k0 | `eval_enterprise_r0_k0.json` | | | | |
| r0 k1 | `eval_enterprise_r0_k1.json` | | | | |
| r1 k0 | `eval_enterprise_r1_k0.json` | | | | |
| r1 k1 | `eval_enterprise_r1_k1.json` | | | | |

---

## 交叉引用

- 历史双基线（rerank 关）：`docs/EVAL-RERUN-NOTES.md`（2026-05-11）。  
- 索引对齐与脚本校验：`scripts/run_eval_retrieve.py`（`EVAL_STRICT_ENTERPRISE` 等）。  
- 状态总览：`docs/CURRENT-STATUS.md`。
