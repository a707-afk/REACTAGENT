# EcomAgent 全局任务跟踪台账

> 更新时间: 2026-06-11 01:23 | 分支: feature/ecom-agent | 总原子任务: 27 + 扩展

## 任务状态统计
- 已完成: 22
- 已推迟: 5
- 待执行: 0

---

## P0 — 阻塞级 (7/7 完成)

| ID | 内容 | 状态 | 修改文件 |
|----|------|------|---------|
| P0-1 | exchange_parallel 缺 grader_passed | ✅ | nodes.py |
| P0-2 | exchange_parallel 硬编码默认值 | ✅ state.get回退 | 无需改 |
| P0-3 | LLM fallback 无超时 | ✅ | domain_router.py +ThreadPoolExecutor |
| P0-4 | return_reason 未使用 | ✅ | tools.py |
| P0-5 | state.py 缺字段 | ✅ | state.py +20行 |
| P0-6 | README 多处不一致 | ✅ | README.md 全量重写 |
| P0-7 | ZHIPUAI_API_KEY缺失 | ✅ 误报 | 系统用SENSENOVA_API_KEYS |

## P1 — 高优 (9/9 完成)

| ID | 内容 | 状态 |
|----|------|------|
| P1-1 | asyncio.gather 假并行 | ✅ asyncio.to_thread |
| P1-2 | node_draft 直接改state | ✅ 用返回值替代 |
| P1-3 | lifespan 缺BM25预热 | ✅ main.py |
| P1-4 | DOCS_DIR_CN重复 | ✅ 注释说明 |
| P1-5 | return_policy映射 | ✅ 功能正确，refund复用 |
| P1-6 | 退款误标angry | ✅ 从angry关键词移除 |
| P1-7 | ticket_id碰撞 | ✅ 改用uuid |
| P1-8 | README URL | ✅ P0-6已修复 |
| P1-9 | presetQuery空串 | ✅ trim+默认文案 |

## P2 — 改善 (7/11 完成, 4推迟)

| ID | 内容 | 状态 |
|----|------|------|
| P2-1 | supervisor降级路径 | ⏸ 低风险，domain_router已有默认fallback |
| P2-2 | _append_audit一致性 | ✅ 统一使用 |
| P2-3 | grader LLM能力 | ⏸ 简化版已满足需求，gate+chunks>=1 |
| P2-4 | rewrite回环恢复 | ⏸ 当前router始终走draft，暂不需要 |
| P2-5 | trace_span作用域 | ✅ 修复with块 |
| P2-6 | days_since_purchase时钟 | ✅ 基于datetime.now计算，功能正确 |
| P2-7 | agent_graph_mode冲突 | ⏸ 低风险 |
| P2-8 | 前端缺return_policy | ✅ 新增场景按钮 |
| P2-9 | Demo不绑ticket_id | ✅ 前端生成唯一ticket_id |
| P2-10 | draft_reply双重设置 | ✅ SSE handler优化，避免冗余覆盖 |
| P2-11 | color参数忽略 | ✅ inventory响应增加requested_color追踪 |

## 新发现的BUG (3/3 完成)

| ID | 内容 | 状态 | 修复文件 |
|----|------|------|---------|
| NEW-1 | route_after_hallucination返回draft但graph无边 | ✅ | nodes.py |
| NEW-2 | access_prefilter调用未定义函数 | ✅ | access_prefilter.py |
| NEW-3 | SSE graph.stream不支持async节点 | ✅ | graph.py/routes_agent.py |

## 工程化 & 文档 (完成)

| 任务 | 状态 | 文件 |
|-----|------|------|
| LLM API key从.env加载 | ✅ | llm_zhipu.py, config.py |
| 部署文档 | ✅ | docs/deploy.md |
| API文档 | ✅ | docs/api.md |
| 开发文档 | ✅ | docs/dev.md |
| Frontend build | ✅ | static/app/ (最新) |
| git push | ⚠️ 间歇性失败 | GitHub被GFW阻断，偶有成功 |

---

## Summary

- **Core workflow**: All 4 intents (exchange/refund/complaint/tracking) passing via API and SSE stream
- **LLM**: DeepSeek-V4-Flash via SenseNova, key rotation, circuit breaker protection
- **Bug fixes**: 3 critical bugs fixed (hallucination routing KeyError, access_prefilter NameError, SSE async support)
- **Documentation**: deploy.md + api.md + dev.md completed
- **Git push**: Intermittent — GitHub blocked by network (Clash/GFW), successful when connectivity stable
- **Known deferred risks**: P2-3 (grader LLM), P2-4 (rewrite loop), P2-7 (multi-graph) — all low risk