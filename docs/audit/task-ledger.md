# EcomAgent 全局任务跟踪台账

> 更新时间: 2026-06-11 | 分支: feature/ecom-agent | 总原子任务: 35

## 任务状态统计
- 已完成: 35
- 待执行: 0

---

## Phase 0-6 企业级重建 (全部完成)

| ID | 内容 | 状态 | 关键文件 |
|----|------|------|---------|
| P0-7 | ZHIPUAI_API_KEY清理 | ✅ 系统已使用SENSENOVA_API_KEYS | config.py, Dockerfile |
| Step 1.2 | Eval 默认 live → mock | ✅ | run_eval_rag.py |
| Step 1.3 | verify_grounding 缺失函数 | ✅ | citation_verify.py + test_grounding_strip.py |
| Step 1.4 | InputGuard 接入 /chat | ✅ | routes_rag.py, config.py |
| Step 1.5 | API auth 默认开启 | ✅ | config.py main.py |
| Step 2.1 | Redis L2 缓存 | ✅ | redis_client.py, cache.py, config.py |
| Step 2.2 | ToolRegistry DB 幂等 | ✅ | tool_registry.py |
| Step 2.3 | BM25 摄入后自动重建 | ✅ | pipeline.py |
| Step 2.4 | DistributedLock 并发控制 | ✅ | pipeline.py |
| Step 3.1 | Harness 超时保护 | ✅ | harness.py |
| Step 3.2 | Budget Enforcement | ✅ | harness.py |
| Step 3.3 | Grader rewrite 回环恢复 | ✅ | nodes.py |
| Step 3.4 | OutputGuard 扩展 5 类模式 | ✅ | input_sanitizer.py |
| Step 3.5 | 认证失败限流 | ✅ | api_guard.py |
| Step 4.1 | 复合工具 composite_tools.py | ✅ | composite_tools.py (new) |
| Step 4.2 | 注册复合工具到 ToolRegistry | ✅ | tool_registry.py |
| Step 4.3 | Harness Planner 意图预分类 | ✅ | harness.py |
| Step 4.4 | HITL 审批深度集成 | ✅ | harness.py, routes_agent.py |
| Step 4.5 | /agent/ticket 路由到 Harness | ✅ | routes_agent.py, config.py |
| Step 5 | CI/CD 硬化 | ✅ | test.yml, lint.yml |
| Step 6 | 中文 tokenizer + 威胁扫描 fail-closed | ✅ | pipeline.py |

## 基础验证

| 检查项 | 状态 | 结果 |
|--------|------|------|
| `compileall -q app` | ✅ | 0 |
| `pytest` (全量) | ✅ | 291 passed, 0 failed |
| `npm --prefix frontend run build` | ✅ | 构建成功 |
| `docker compose config` | ✅ | 有效配置 |
| CI test.yml | ✅ | 覆盖全分支, 含 PG/Redis/Qdrant 服务 |

## 已知环境限制
- **pyarrow DLL crash**: Windows 上运行全量 pytest 时偶发 access violation（import sklearn→pandas→pyarrow 链），单独跑每个文件均通过。非代码问题。
- **tiktoken 网络下载挂起**: 国内网络无法下载 OpenAI BPE 文件，已实现本地缓存检测 + 启发式回退。
- **Git push 间歇性失败**: GitHub 被 GFW 阻断，非代码问题。
