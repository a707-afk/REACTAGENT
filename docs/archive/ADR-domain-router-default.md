# ADR：domain router — 硬性过滤默认值与 trace

## 状态

已采纳：**默认关闭 domain hard filter**；保留路由推断与 `router_trace`。四组合回归矩阵见 `docs/EVAL-BASELINE-COMPARISON.md`（r1 单元格需 `DOMAIN_ROUTER_HARD_FILTER=true` 以复现历史「Router 开 + 收窄候选」）。

## 背景（2026-05-15 企业 eval，50 条）

在 **推断 + 硬性按域过滤**（历史实现）下，`router on` 相对 `router off` 显著拉低 Top-5；日志多次出现「过滤后无候选，回退全库」。Rerank 无法恢复未进入候选集的文档。

矩阵数值（**r1 = 推断 + HARD_FILTER ON**，与当时代码一致）：


| 组合    | 推断  | Hard filter | Rerank | expect_top1  | expect_top5  | domain top1  |
| ----- | --- | ----------- | ------ | ------------ | ------------ | ------------ |
| r0_k0 | 关   | -           | 关      | 37/50 (0.74) | 41/50 (0.82) | 40/50 (0.80) |
| r0_k1 | 关   | -           | 开      | 42/50 (0.84) | 48/50 (0.96) | 42/50 (0.84) |
| r1_k0 | 开   | ON          | 关      | 28/50 (0.56) | 30/50 (0.60) | 31/50 (0.62) |
| r1_k1 | 开   | ON          | 开      | 29/50 (0.58) | 31/50 (0.62) | 31/50 (0.62) |


## 代码与配置语义


| 开关                                    | 默认          | 含义                                                                                            |
| ------------------------------------- | ----------- | --------------------------------------------------------------------------------------------- |
| `DOMAIN_ROUTER_ENABLED`               | `true`      | `false` 时不调用 `route_domains`，无 `router_trace`                                                 |
| `**DOMAIN_ROUTER_HARD_FILTER`**       | `**false**` | `**true**` 时在 rerank 前按 `allowed_domains` **淘汰候选**；`false` 时仅推断域并写入 trace，**不参与 elimination** |
| `DOMAIN_ROUTER_STRICT` / `FALLBACK_*` | -           | **仅当** `HARD_FILTER=true` 时在收窄逻辑中生效                                                           |


API：`skip_domain_router=true` → 与「关推断」等价（无 trace），与 hard filter 独立。

占位（~~未实现~~ **已实现，默认关**）：`DOMAIN_ROUTER_SOFT_BOOST_ENABLED` / `DOMAIN_ROUTER_SOFT_BOOST_TOP_CHUNKS` / `DOMAIN_ROUTER_SOFT_BOOST_DELTA`——在 **rerank 前** 仅对 top-k 中与 `allowed_domains` 元数据匹配的候选加小幅分，需显式开启。

## 路由增强（路线图落地，2026）


| 能力                            | 默认                                     | 说明                                                                        |
| ----------------------------- | -------------------------------------- | ------------------------------------------------------------------------- |
| `DOMAIN_ROUTER_ENHANCED`      | `true`                                 | 关键词 + 归一化 Embedding 融合、多域 `allowed_domains`、`routing_trace`               |
| `DOMAIN_ROUTER_USE_EMBEDDING` | `true`                                 | Embedding Router；评测可设 `false` 仅跑规则                                        |
| `domain_router_profiles.json` | `data/...`                             | 域权重乘子与各域原型短语（centroid）                                                    |
| Platt + temperature 校准        | `data/router_calibration.default.json` | `ROUTER_CALIBRATION_PATH`；规则支路 raw=`best_score/total`；LLM 支路 raw=0.75 后校准 |
| 离线拟合                          | `scripts/fit_router_calibration.py`    | 用 golden 或 `run_eval_router` 的 `*_predictions.csv` 写新 JSON                |
| 路由评测                          | `scripts/run_eval_router.py`           | Top-k 重叠率、混淆矩阵、F1 CSV/JSON，与检索管线独立                                        |


## 决策

- **当前版本**：生产等价配置下 `**DOMAIN_ROUTER_HARD_FILTER=false`**；路由作为 **trace / observability、prior / soft routing 信号**，**非**默认 hard gate；软加权（soft boost）**默认关闭**，开启后亦不删除候选。
- **回归**：`scripts/run_eval_four_baselines.py` 对 **r1** 显式设置 `DOMAIN_ROUTER_HARD_FILTER=true`，与已归档 JSON 语义对齐。
- **校准闭环**：评测导出含 `confidence_branch`、`raw_confidence`；`scripts/fit_router_calibration.py` 离线拟合并写 JSON，由 `ROUTER_CALIBRATION_PATH` 指向生效。

## 参考

- `docs/EVAL-BASELINE-COMPARISON.md`
- `docs/eval_four_baselines_summary.json`
- `app/config.py`、`app/retrieval_pipeline.py`