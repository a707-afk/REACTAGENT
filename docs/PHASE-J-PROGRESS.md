# 阶段 J：工程化补强 — 进度说明

> 更新：2026-06-04。检索缓存（L1 精确 + 可选 L2 语义）+ Prometheus 风格 `/metrics` + HTTP/检索延迟埋点。

## 目标

1. **J1**：在 `retrieve_scored_nodes` 接入进程内三级缓存中的 **L1（必做）** 与 **L2 语义（可选）**；索引重建后失效。
2. **J2**：暴露 `GET /metrics`；HTTP 中间件记录延迟；检索路径记录 `rag_retrieve_duration_seconds` 与 `rag_cache_hits_total`。

## 已实现文件

| 模块 | 路径 | 说明 |
|------|------|------|
| 缓存 | `app/cache.py` | L1 LRU（query+settings+访问上下文 哈希）；L2 embedding 余弦（`CACHE_SEMANTIC_ENABLED`） |
| 指标 | `app/metrics.py` | `prometheus_client` 可选；未安装时用内存 stub，保证 `/metrics` 可 scrape |
| 配置 | `app/config.py` | `cache_*` 环境变量 |
| 集成 | `app/retrieval_pipeline.py` | `cache_get_retrieval` / `cache_put_retrieval` + `observe_retrieve` |
| 入口 | `app/main.py` | `GET /metrics` + `metrics_latency_middleware` |
| 失效 | `app/vector_index.py`、`scripts/reindex.py` | `rebuild_index` 与 reindex 脚本调用 `cache_clear()` |

## 配置一览

| 变量 | 默认 | 含义 |
|------|------|------|
| `CACHE_ENABLED` | `true` | 总开关 |
| `CACHE_MAX_ENTRIES` | `256` | L1 LRU 容量 |
| `CACHE_SEMANTIC_ENABLED` | `false` | L2（需 embedding，评测/生产再开） |
| `CACHE_SEMANTIC_THRESHOLD` | `0.92` | L2 余弦阈值（应用 PR 曲线标定，见 D-J1） |
| `CACHE_SEMANTIC_MAX_ENTRIES` | `128` | L2 条目上限 |

## 验证

```bash
cd c:\Users\Lenovo\Desktop\传统文件项目\rag-kb-project
pytest tests/test_cache.py tests/test_metrics_endpoint.py -q
pytest tests/ -q
```

启动服务后：

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/metrics | findstr rag_
```

## 未做（留待 J+ / K）

- L1 接 **Redis**（多进程/多副本共享）
- L3 会话级缓存
- Grafana 仪表盘与告警规则
- L2 阈值在企业集上的 PR 曲线产物归档（`【待回填】`）

## 面试讲法（30 秒）

> 检索链路加了 **L1 精确键**（query + 影响召回的配置指纹 + 租户/角色）和可选 **L2 语义缓存**；`reindex` 会 `cache_clear` 避免脏读。可观测上挂了 **`/metrics`**，没装 `prometheus_client` 也有 stub 文本，HTTP 与 `retrieve_scored_nodes` 分别记延迟和 cache hit 层级，和原有 JSON 结构化日志、OTel span 并存。
