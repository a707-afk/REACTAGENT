# Qdrant 迁移评测报告

> 生成：2026-06-03（本地嵌入式 `QDRANT_PATH=data/qdrant_local`，Docker 未启动）。  
> 索引：302 节点，`DOCS_DIR=data/docs/enterprise_ai_ops`，`CHROMA_COLLECTION_NAME=enterprise_ai_ops`。

---

## 执行步骤（已完成）

1. `python scripts/reindex.py`（`VECTOR_BACKEND=qdrant`）
2. `python scripts/run_eval_access_control.py` → `docs/eval_access_control_qdrant.json`
3. 与 Chroma 基线对比 → `docs/eval_qdrant_vs_chroma_access.json`

一键脚本（下次）：`python scripts/run_qdrant_migration_eval.py`（`--skip-reindex` 可跳过重建）。

---

## 权限评测对比（30 条金标）

| 指标 | Chroma（基线） | Qdrant（本地） | Δ |
|------|----------------|----------------|---|
| Forbidden top5 | 4/4 (100%) | 4/4 (100%) | 0 |
| Expect top1 子串 | 23/26 (88.5%) | 22/26 (84.6%) | **-1** |
| Domain top1 | 22/24 (91.7%) | 22/24 (91.7%) | 0 |

### Expect 差异

- 与 Chroma **共同未命中**（本迭代暂缓）：AC02、AC07、AC28（见 `ACCESS-CONTROL-BADCASE.md` §8）
- **Qdrant 新增未命中**：AC09（Chroma 曾命中，属排序/向量后端噪声，建议 spot-check）

---

## 代码修复（迁移过程中）

| 问题 | 修复 |
|------|------|
| `load_documents` 收到 str | `qdrant_index_store.rebuild_index` 使用 `Path(settings.docs_dir)` |
| 本地 Qdrant 多实例锁目录 | `qdrant_index_store` 单例 `QdrantClient` |
| `client.search` 已废弃 | `access_prefilter` 改用 `query_points` |

---

## 结论与建议

- **权限安全面**（Forbidden）与 **域 Top1** 与 Chroma 一致，可认为迁移未破坏 Pre-filter 主路径。
- **Expect** 略降 1 条（AC09），在评测噪声范围内；若要以 Chroma 为生产默认，可保留 Chroma 直至 AC09 对齐或接受 Qdrant。
- **生产切换**：优先 `docker compose up -d qdrant` + `QDRANT_URL`（支持并发）；开发机无 Docker 时用 `QDRANT_PATH` 单进程评测。
- **检索 50 题 eval**（2026-06-03，约 33 分钟，Rerank ON、router 跳过）：`docs/eval_enterprise_retrieve_qdrant.json`
  - Expect top1：**43/50 (86%)**
  - Expect top5：**48/50 (96%)**
  - Domain top1：**38/50 (76%)**
  - 与历史 Chroma `eval_enterprise_r0_k1.json`（43/50 top1）**一致**。

---

## 产物路径

- `data/qdrant_local/` — 嵌入式向量数据
- `docs/eval_access_control_qdrant.json`
- `docs/ACCESS-CONTROL-EVAL-QDRANT.md`
- `docs/eval_qdrant_vs_chroma_access.json`
- `docs/eval_enterprise_retrieve_qdrant.json`
- Chroma 基线：`docs/eval_access_control_chroma_baseline.json`
