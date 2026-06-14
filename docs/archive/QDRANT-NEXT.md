# Qdrant 迁移操作指南（阶段 D）

> **状态**：代码已落地（`app/qdrant_index_store.py`、`app/vector_index.py`、`app/vector_backend.py`、Pre-filter `HasIdCondition`）。默认 **`VECTOR_BACKEND=auto`**：本地/远程 Qdrant 有数据则用 Qdrant，否则 Chroma。

---

## 何时切换

- 权限 metadata schema 已稳定（阶段 C 已完成 Pre-filter）。
- 需要 payload 级过滤或与外部 Qdrant 集群对齐时再切；**不要在未 reindex 前只改 `VECTOR_BACKEND`**。

---

## 本地启动 Qdrant

### 方式 A：Docker（推荐生产 / 并发评测）

```powershell
cd rag-kb-project
docker compose up -d qdrant
# 健康检查：Invoke-WebRequest http://localhost:6333/collections
```

`docker-compose.yml` 已包含 `qdrant/qdrant:v1.12.5`，数据卷 `qdrant_storage`。设置 `QDRANT_URL=http://localhost:6333`，**不要**设 `QDRANT_PATH`。

### 方式 B：嵌入式本地目录（无 Docker）

```powershell
$env:VECTOR_BACKEND="qdrant"
$env:QDRANT_PATH="data/qdrant_local"
# 同一进程内复用单例 QdrantClient（app/qdrant_index_store.py）
```

Windows 上评测请**单进程**跑完（勿多开 API + eval 同时写同一 `QDRANT_PATH`）。

---

## 环境变量（企业语料示例）

```powershell
# 默认 auto；显式 qdrant 亦可
$env:VECTOR_BACKEND="auto"
# 或 $env:VECTOR_BACKEND="qdrant"
$env:QDRANT_URL="http://localhost:6333"
# 本地嵌入式：$env:QDRANT_PATH="data/qdrant_local"

$env:DOCS_DIR="data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME="enterprise_ai_ops"
$env:BM25_CORPUS_PATH="data/bm25_enterprise_corpus.jsonl"
```

**auto 行为**：`resolve_vector_backend()` 检测 `QDRANT_PATH` 目录或 `QDRANT_URL` 上 `CHROMA_COLLECTION_NAME` 是否有点；有则 Qdrant，否则 Chroma。未设 `QDRANT_PATH` 时默认尝试 `data/qdrant_local`。

集合名仍用 `CHROMA_COLLECTION_NAME`（与 Chroma 配置共用，避免双份命名）。

---

## 重建索引

```powershell
python scripts/reindex.py
```

流程与 Chroma 一致：先 embed 全部节点，再写入 Qdrant collection。BM25 语料同步到 `BM25_CORPUS_PATH`。

---

## 应用与评测

- API：`/health/config` 返回 `vector_backend`、`qdrant_url`。
- 检索 / 权限评测脚本已走 `app.vector_index` 门面，无需改调用方。

```powershell
python scripts/run_eval_access_control.py
python scripts/run_eval_retrieve.py
```

---

## Pre-filter 差异

| 后端 | 向量预筛 |
|------|----------|
| Chroma | `collection.get(where=...)` 取 `ids` |
| Qdrant | `HasIdCondition` + 允许的 node id 列表 |

BM25 子集逻辑两端相同（`allowed_ids`）。

---

## 回退 Chroma

```powershell
$env:VECTOR_BACKEND="chroma"
# 或 Remove-Item Env:VECTOR_BACKEND
```

重启 API 前可 `clear_index_memory_cache()`（reindex 脚本内已处理）。Chroma 持久化目录未删除，无需重新 embed 若索引仍在。

---

## 依赖

`requirements.txt`：

- `qdrant-client>=1.9.0`
- `llama-index-vector-stores-qdrant`

安装：`pip install -r requirements.txt`（在 conda `rags` 环境中）。

---

## 已知限制

- 未实现 Qdrant payload `where` 替代全量 id 列表（路线图后续优化）。
- Windows 上 Rerank 偶发崩溃时，评测可设 `ACCESS_EVAL_USE_RERANK=false`。
- 首次 Qdrant reindex 耗时与 Chroma 同级（取决于节点数与 GPU）。
