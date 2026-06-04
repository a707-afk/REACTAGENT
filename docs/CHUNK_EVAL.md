# 切片策略对比记录

用于同一批 `data/eval_questions.jsonl` 问题，在不同 `CHUNK_STRATEGY` / `chunk_size` / `overlap` 下记录召回与回答质量（面试素材）。

## 自动化检索与分数校准（推荐先做）

在项目根目录执行（需已 `reindex`、本机可加载 Embedding 与 Chroma）：

```powershell
cd c:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project
& "D:\conda\envs\rags\python.exe" scripts/run_eval_retrieve.py
```

- 输出：`**docs/eval_retrieve_autorun.json**`（每条问题的 `top_hits` 在 **Rerank 开启时 `score` 为重排分**；`ranked_scores_after_gate_metric`；门控是否通过）。
- **阈值 0.6 应对齐 `summary.gate_score_min` / `gate_score_max`（重排分）**，不是 `vector_raw_*`。若量纲不符，调整 `**RETRIEVAL_SIMILARITY_THRESHOLD`** / `**RETRIEVAL_SCORE_HIGHER_IS_BETTER`**，并可临时设置 `**RERANK_ENABLED=false**` 做仅向量对照。

**校准备忘**：CrossEncoder（默认 `BAAI/bge-reranker-base`）输出与 Chroma 向量相似度刻度不同；**务必看本次跑批的 `gate_score_*`** 再定 0.6 是否合理；**K2** 指 **Rerank 之后** 的门控（最优重排分与阈值），不是「向量召回第 2 名」。

## 配置快照（每次实验填写）


| 日期         | chunk_strategy           | chunk_size_tokens | chunk_overlap_tokens | 索引节点数            | eval_autorun 文件名           |
| ---------- | ------------------------ | ----------------- | -------------------- | ---------------- | -------------------------- |
| 2026-05-06 | markdown_heading_overlap | 512               | 64                   | （本地 reindex 后填写） | eval_retrieve_autorun.json |


## 单题记录（人工 E2E：仅检索 / 问答）

在 `http://127.0.0.1:8000/` 上对下列 id 各点一次「仅检索」「问答」，将 **是否命中预期、答案是否胡编** 记入本表；可与上一节 JSON 对照。


| eval_id | 检索是否命中预期文件 | 答案是否可引用 | bad case 简述 |
| ------- | ---------- | ------- | ----------- |
| 1       |            |         |             |
| 2       |            |         |             |
| 3       |            |         |             |
| 4       |            |         |             |
| 5       |            |         |             |
| 6       |            |         |             |
| 7       |            |         |             |
| 8       |            |         |             |
| 9       |            |         |             |
| 10      |            |         |             |
| 11      |            |         |             |
| 12      |            |         |             |
| 13      |            |         |             |
| 14      |            |         |             |
| 15      |            |         |             |


## 策略说明（项目内）

- `markdown_heading_overlap`：Markdown 标题切分 + 过长节按 token 二次切分（P0，默认）。
- `heading_only`：仅标题切分，不二次切分（对照实验）。

切换方式：环境变量或 `.env` 中设置（见 `app/config.py` 字段名，对应大写环境变量如 `**CHUNK_STRATEGY`**、`**CHUNK_SIZE_TOKENS`**、`**CHUNK_OVERLAP_TOKENS**`），然后重新执行 `python scripts/reindex.py`。