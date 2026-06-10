# EcomAgent 全局任务跟踪台账

> 更新时间: 2026-06-11 00:02 | 分支: feature/ecom-agent | 总原子任务: 27

## 任务状态统计
- 已完成: 19
- 已推迟(P2低优): 6
- 待执行: 2
- 遇卡点: 0

---

## P0 — 阻塞级 (7/7 完成)

| ID | 内容 | 状态 | 修改文件 |
|----|------|------|---------|
| P0-1 | exchange_parallel 缺 grader_passed | ✅ | nodes.py +1行 |
| P0-2 | exchange_parallel 硬编码默认值 | ✅ 已为state.get回退 | 无需改 |
| P0-3 | LLM fallback 无超时 | ✅ | domain_router.py +ThreadPoolExecutor |
| P0-4 | return_reason 未使用 | ✅ | tools.py 3处return添加return_reason |
| P0-5 | state.py 缺16字段 | ✅ | state.py +20行 |
| P0-6 | README 多处不一致 | ✅ | README.md 全量重写 |
| P0-7 | ZHIPUAI_API_KEY缺失 | ✅ 误报 | 系统用SENSENOVA_API_KEYS |

## P1 — 高优 (8/9 完成, 1推迟)

| ID | 内容 | 状态 |
|----|------|------|
| P1-1 | asyncio.gather 假并行 | ✅ asyncio.to_thread |
| P1-2 | node_draft 直接改state | ✅ 用返回值替代 |
| P1-3 | lifespan 缺BM25预热 | ✅ main.py +8行 |
| P1-4 | DOCS_DIR_CN重复 | ✅ 添加注释说明 |
| P1-5 | return_policy映射 | ⏸ 保留refund(功能正确) |
| P1-6 | 退款误标angry | ✅ 从angry关键词移除 |
| P1-7 | ticket_id碰撞 | ✅ 改用uuid |
| P1-8 | README URL | ✅ P0-6已修复 |
| P1-9 | presetQuery空串 | ✅ trim+默认文案 |

## P2 — 改善 (4/11 完成, 7推迟)

| ID | 内容 | 状态 |
|----|------|------|
| P2-1 | supervisor降级路径 | ⏸ 不可达路径,低优 |
| P2-2 | _append_audit一致性 | ✅ 统一使用 |
| P2-3 | grader LLM能力 | ⏸ 需LLM集成测试 |
| P2-4 | rewrite回环恢复 | ⏸ 需更多测试 |
| P2-5 | trace_span作用域 | ✅ 修复with块 |
| P2-6 | days_since_purchase时钟 | ⏸ 仅注释问题 |
| P2-7 | agent_graph_mode冲突 | ⏸ 低风险 |
| P2-8 | 前端缺return_policy | ✅ 新增场景按钮 |
| P2-9 | Demo不绑ticket_id | ⏸ 需后端配合 |
| P2-10 | draft_reply双重设置 | ⏸ 需SSE流测试 |
| P2-11 | color参数忽略 | ⏸ 低影响 |
