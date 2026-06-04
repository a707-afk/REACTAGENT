# Router 离线评测（Embedding Router / 规则融合）

本仓库用 **金标 JSONL** 驱动 `domain_router.route_domains`，与检索管线解耦，便于迭代 profile 与校准。

## 金标数据

- 路径：`data/router_eval_golden.jsonl`（每行一个 JSON：`id`、`question`、`expect_primary`、`expect_domains`、`notes` 可选）。
- 重新生成（会覆盖文件）：

```bash
python scripts/generate_router_eval_golden.py
```

当前生成规模约 **80** 条（含单域、跨域、模糊与安全类措辞）。

## 运行评测

在项目根目录：

```bash
python scripts/run_eval_router.py
```

常用环境变量（与 `app.config.Settings` 一致）：

| 变量 | 含义 |
|------|------|
| `ROUTER_EVAL_GOLDEN` | 金标路径，默认 `data/router_eval_golden.jsonl` |
| `ROUTER_EVAL_OUT_PREFIX` | 输出文件前缀，默认 `docs/router_eval_metrics`（**不含**扩展名） |
| `ROUTER_EVAL_TOP_K` | Top-k overlap 截断，默认 `3` |
| `DOMAIN_ROUTER_USE_EMBEDDING` | Enhanced 模式下是否走 Embedding Router，默认 `true`；纯规则对比可设 `false` |
| `DOMAIN_ROUTER_ENHANCED` | 是否多域融合路径，默认 `true` |
| `DOMAIN_ROUTER_PROFILES_PATH` | profile JSON，默认 `data/domain_router_profiles.json` |
| `ROUTER_CALIBRATION_PATH` / `DOMAIN_ROUTER_CALIBRATION_PATH` | 校准 JSON；空则使用 `data/router_calibration.default.json` |
| `QWEN_EMBEDDING_MODEL_PATH` 等 | 与 `app.embeddings` 一致；首次加载会拉取/加载本地权重 |

CLI 等价：`--golden`、`--out-prefix`、`--top-k`。

## 输出产物

默认前缀 `docs/router_eval_metrics` 下生成（UTF-8-sig）：

- `router_eval_metrics_predictions.csv`：逐条预测、`method`、`confidence_branch`、是否 primary 命中、是否 top-k 与金标域有交集。
- `router_eval_metrics_aggregate.csv`：`count`、`topk_overlap_hit_rate`、`primary_accuracy`。
- `router_eval_metrics_confusion.csv`：金标 primary × 预测 primary 计数。
- `router_eval_metrics_f1.csv`：按域 precision/recall 及近似 macro-F1。
- `router_eval_metrics_summary.json`：聚合指标 + 金标路径。

控制台会打印一行摘要，例如：`topk_overlap@3 … primary_accuracy …`。

### 最近一次批注快照（需在本地重跑后以你的机器为准）

在默认配置、金标 **80** 条、`top_k=3` 的一次运行结果为：

| 指标 | 值 |
|------|-----|
| `topk_overlap_hit_rate` | 0.975 |
| `primary_accuracy` | 0.800 |
| `macro_f1_approx` | ≈ 0.800 |

**解读：**

- **primary_accuracy**：预测 `primary_domain` 与金标 `expect_primary` 一致的比例。
- **topk_overlap_hit_rate**：将预测 `allowed_domains` 截取前 **k** 个后，是否与金标 `expect_domains` **至少有一个域相交**——适合标注了多合法域的跨域样本。

## Profile 与缓存行为

- **Profile**：`data/domain_router_profiles.json`（当前 `version: 2`），含各域加权与多条 **prototype**。路线图建议每域最终 **8–15** 条原型句时可继续增补；改版后务必重跑评测与（若使用）`scripts/fit_router_calibration.py`。
- **`load_domain_router_profiles`** 等对路径字符串做了进程内 LRU：同一路径在未重启 Python 的前提下可能仍为旧缓存；**改 profile 文件后请重启评测进程**（或在新进程中跑脚本）。
- **Centroid LRU**：`app/embedding_router.py` 对「每域 prototype 均值向量」做了有序字典 LRU（约 96 项），同一 `(domain, 模型前缀, 规范化 prototype 集合)` 不会重复做整批 prototype embedding。评测或切换 profile/模型后可调用 **`clear_embedding_router_centroid_cache()`**（多见于单测或热切换场景）。

## 相关文档与脚本

- 路线图：**[ROADMAP-PHASES-A-F.md](ROADMAP-PHASES-A-F.md)** §B。
- 校准拟合：`scripts/fit_router_calibration.py`。
- 生产型矩阵评测：`scripts/run_eval_prod_router_matrix.py`（不同于本脚本的本机离线金标）。
