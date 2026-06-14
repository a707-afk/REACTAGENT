# 企业语料域边界重设计（2026-06）

## 变更摘要

1. **三域边界**（检索与 router 的主战场）  
   - `customer_service`（`03-customer-service/`）：终端用户 FAQ、一线收集信息与话术；**不含** SLA 数值表、财务复核字段表。  
   - `ticket_workflow`（`04-ticket-workflow/`）：SLA、升级、退款审批、定级等**内部流程权威版**。  
   - `case`（`07-cases/`）：历史事件**叙事与教训**；通过标题/路径引用 workflow，**不复制** SLA 表或财务字段表。

2. **Front matter 规范**  
   全部 41 篇企业 Markdown 已补全 `tenant_id: corp-default`，并与 `domain/subdomain/security_level/audience/owner/status/version` 对齐。

3. **索引元数据**  
   `app/chunking.py` 在 load 阶段解析 front matter，并在 **Markdown 分块后** 用 `_inherit_doc_metadata` 把 `domain` / `security_level` / `audience` 等回填到每个 chunk（否则 LlamaIndex 切分后只剩 `file_path`）。缺省 `tenant_id: corp-default`。

4. **评测隔离**  
   `scripts/run_eval_access_control.py` 增加与 `run_eval_retrieve.py` 一致的 **enterprise strict** 校验（`DOCS_DIR` / `CHROMA_COLLECTION_NAME` / `BM25_CORPUS_PATH`）；`EVAL_STRICT_ENTERPRISE=1` 未对齐时退出码 2。

5. **Router 策略**  
   未改动默认值：`DOMAIN_ROUTER_HARD_FILTER=false`（仅 trace + 可选 soft boost）。

## 重建企业索引

PowerShell（仓库根目录 `rag-kb-project`）：

```powershell
$env:DOCS_DIR = "data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME = "enterprise_ai_ops"
$env:BM25_CORPUS_PATH = "data/bm25_enterprise_corpus.jsonl"
python scripts/reindex.py
python scripts/verify_enterprise_chunk_metadata.py
```

## 权限评测（企业 index）

```powershell
$env:DOCS_DIR = "data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME = "enterprise_ai_ops"
$env:BM25_CORPUS_PATH = "data/bm25_enterprise_corpus.jsonl"
$env:RERANK_ENABLED = "false"
$env:EVAL_ENTERPRISE_STRICT = "1"
python scripts/run_eval_access_control.py
```

产物：`docs/eval_access_control.json`、`docs/ACCESS-CONTROL-EVAL.md`。

## 企业检索评测（可选）

```powershell
$env:EVAL_QUESTIONS_PATH = "data/eval_enterprise_questions.jsonl"
$env:EVAL_OUTPUT_PATH = "docs/eval_enterprise_retrieve.json"
$env:EVAL_ENTERPRISE_STRICT = "1"
python scripts/run_eval_retrieve.py
```

## 域边界设计原则（3 域）

| 域 | 回答什么 | 禁止什么 |
|---|---|---|
| customer_service | 客户怎么说、客服收集什么、何时转二线 | 复制 P0 15 分钟等 SLA 表、财务复核字段表 |
| ticket_workflow | SLA/升级/退款审批/定级规则 | 长篇事故故事、重复 FAQ 话术 |
| case | 一次事件的经过、决策、教训 | 复制 workflow 表格；应用链接指向 workflow 文件名 |

## 相关文件

- 语料：`data/docs/enterprise_ai_ops/`
- 权限题库：`data/eval_access_control_questions.jsonl`
- 检索题库：`data/eval_enterprise_questions.jsonl`
- 校验脚本：`scripts/verify_enterprise_chunk_metadata.py`
