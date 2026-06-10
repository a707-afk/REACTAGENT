# EcomAgent 全局任务跟踪台账

> 创建时间: 2026-06-11 | 分支: feature/ecom-agent | 总原子任务: 27

## 任务状态统计
- 待执行: 27
- 执行中: 0
- 已完成: 0
- 遇卡点: 0

---

## P0 — 阻塞级 (7项)

| ID | 文件 | 内容 | 状态 |
|----|------|------|------|
| P0-1 | nodes.py | exchange_parallel 缺少 grader_passed:True | 待执行 |
| P0-2 | nodes.py | exchange_parallel 硬编码默认值 | 待执行 |
| P0-3 | domain_router.py | LLM fallback 无超时控制 | 待执行 |
| P0-4 | tools.py | return_reason 参数未使用 | 待执行 |
| P0-5 | state.py | 缺失16个运行时字段定义 | 待执行 |
| P0-6 | README.md | 多处文档与代码不一致 | 待执行 |
| P0-7 | .env | ZHIPUAI_API_KEY检查/SENSENOVA配置 | 待执行 |

## P1 — 高优 (9项)

| ID | 文件 | 内容 | 状态 |
|----|------|------|------|
| P1-1 | nodes.py | asyncio.gather 内同步函数未真正并行 | 待执行 |
| P1-2 | nodes.py | node_draft 直接修改 state dict | 待执行 |
| P1-3 | main.py | lifespan 未预热 BM25 | 待执行 |
| P1-4 | .env | DOCS_DIR/DOCS_DIR_CN 重复 | 待执行 |
| P1-5 | router.py | return_policy 映射到 refund 不精准 | 待执行 |
| P1-6 | router.py | detect_emotion 中"退款"误列为angry | 待执行 |
| P1-7 | tools.py | ticket_id 并发碰撞风险 | 待执行 |
| P1-8 | README.md | 仓库URL确认 | 待执行 |
| P1-9 | AgentStreamTab.tsx | presetQuery 空字符串边界 | 待执行 |

## P2 — 改善 (11项)

| ID | 文件 | 内容 | 状态 |
|----|------|------|------|
| P2-1 | graph.py | supervisor 路由缺 finalize 降级 | 待执行 |
| P2-2 | nodes.py | exchange_parallel 不用 _append_audit | 待执行 |
| P2-3 | nodes.py | grader 简化版未用 LLM | 待执行 |
| P2-4 | nodes.py | route_after_grader 未启用 rewrite 回环 | 待执行 |
| P2-5 | nodes.py | node_hallucination trace_span 作用域错误 | 待执行 |
| P2-6 | mock/orders.py | days_since_purchase 依赖系统时钟 | 待执行 |
| P2-7 | config.py | agent_graph_mode 双开关冲突 | 待执行 |
| P2-8 | App.tsx | 前端缺 return_policy 场景 | 待执行 |
| P2-9 | App.tsx | Demo 不绑定 ticket_id | 待执行 |
| P2-10 | AgentStreamTab.tsx | draft_reply 双重设置覆盖 | 待执行 |
| P2-11 | mock/inventory.py | color 参数被忽略 | 待执行 |
