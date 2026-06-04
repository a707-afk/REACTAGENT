# LangGraph 递进学习路线（带你跑通）

> 旧版「LangGraph + CrewAI 并列深度学习」讲义已下线；**当前默认只按下面阶段练 LangGraph**。CrewAI 可日后单独开题。智谱 **API Key 只放在本机 [.env](.env)**（从 [.env.example](.env.example) 复制），勿写入代码仓库。

---

## 环境准备

在项目根目录 `c:\Users\Lenovo\Desktop\传统文件项目`：

```powershell
Copy-Item .env.example .env
# 编辑 .env，填写 ZHIPUAI_API_KEY
pip install -U python-dotenv "langgraph>=0.2" langchain-core langchain-community `
  langgraph-checkpoint-sqlite httpx PyJWT typing_extensions
```

- **阶段一、四、五**不调用大模型也可跑通；**二、三**需要智谱密钥。  
- 持久化示例会在 `examples/` 下生成本地 `*.sqlite`（已在 [.gitignore](.gitignore) 忽略）。

---

## 第一阶段：基础构建（Hello World）

**目标**：手写最简单的两节点流转，熟悉 `StateGraph` 与 `compile()`。

**练习**：Node A 把输入转大写，Node B 打印结果。

**对应脚本**：[`examples/langgraph_phase1_hello.py`](examples/langgraph_phase1_hello.py)

```bash
python examples/langgraph_phase1_hello.py
```

**自查**：能指出 `START` / `END`、`add_node`、`add_edge` 各做什么；`invoke` 的入参与返回的 `state` 是什么关系。

---

## 第二阶段：状态管理与持久化（Memory & Persistence）

**目标**：同一 `thread_id` 在**进程重启**后仍能续聊（断点续跑 + 跨会话记忆落库）。

**核心**：`SqliteSaver`（`langgraph-checkpoint-sqlite`）；`configurable.thread_id`。

**状态**：使用内置 `MessagesState`（内部已用 **`add_messages` reducer** 合并消息列表，避免手写列表拼接）。

**对应脚本**：[`examples/langgraph_phase2_persistence.py`](examples/langgraph_phase2_persistence.py)

```bash
python examples/langgraph_phase2_persistence.py
```

**自查**：删掉 `examples/phase2_chat.sqlite` 后重新运行，记忆会消失——说明记忆来自 **checkpoint 文件 + thread_id**，不是魔法。

---

## 第三阶段：智能决策（The Agentic Loop）

**目标**：`bind_tools` + **条件边**：若有工具调用则进 `ToolNode`，否则结束（与 ReAct 同构）。

**对应脚本**：[`examples/langgraph_phase3_agentic_loop.py`](examples/langgraph_phase3_agentic_loop.py)

```bash
python examples/langgraph_phase3_agentic_loop.py
```

**自查**：能在日志或断点里看到：`AIMessage.tool_calls` 非空时路由到 `tools`，执行后回到 `agent`。

---

## 第四阶段：Human-in-the-loop（人机审批）

**目标**：敏感节点执行前暂停，人工确认后再 `resume`。

**要点**：`compile(..., interrupt_before=["节点名"])`；继续时用 `Command(resume=True)`（或按业务传入结构化 `resume` 负载）。

**对应脚本**：[`examples/langgraph_phase4_hitl.py`](examples/langgraph_phase4_hitl.py)

```bash
python examples/langgraph_phase4_hitl.py
```

生产进阶：用持久化 checkpointer + 唯一 `thread_id`，审批服务在后台调用 `invoke(Command(resume=...), config)`；需要时配合 `update_state` 修正状态（参见 LangGraph 官方 HITL 文档）。

---

## 高阶进阶：多智能体 / 大图（本仓库骨架）

### Supervisor 模式

**对应脚本**：[`examples/langgraph_phase5_supervisor_sketch.py`](examples/langgraph_phase5_supervisor_sketch.py) — 当前为**规则主管**（无 LLM），便于看清条件边；你可把 `supervisor_node` 换成「LLM 输出 next_worker」。

```bash
python examples/langgraph_phase5_supervisor_sketch.py
```

### Hierarchical（层级 / 子图）

**练法建议**：把一个工人节点 `compile()` 成 `CompiledStateGraph`，在外层 `StateGraph` 里当**单节点**嵌入（官方关键词：`subgraph`）。本仓库不展开长代码，避免与你的 LangGraph 版本 API 细节冲突——以你安装的版本文档为准。

### 状态与 reducer（面试常问）

- 用 **`TypedDict` / Pydantic`** 明确字段，避免 state 随意长键名。  
- 消息历史字段用 **`Annotated[list[...], add_messages]`**（或直接继承 **`MessagesState`**）：新输出会 **append**，而不是整表覆盖。  
- 需要「上限截断」时，在写入前对 `messages` 做滑动窗口或摘要（与 RAG 的上下文压缩同理）。

---

## 推荐学习顺序（我带你跑通时的节奏）

1. 跑通 **阶段一**，改 `HelloState` 多一个字段试 `invoke`。  
2. 跑通 **阶段二**，改第二次用户问题，观察是否仍记得上文。  
3. **阶段三** 换一个你自己的 `@tool`，观察多轮工具循环。  
4. **阶段四** 把 `execute_risky` 换成「发邮件」伪动作，练习拒绝 `resume`。  
5. **阶段五** 把规则主管改成「LLM 输出 JSON → `next_worker`」（自练）。

---

## 与 RAG / 企业落地的连接点（备忘）

- 检索 / 重排 / 生成可拆成 **多个节点**；低置信可走 **条件边** 触发二次检索（呼应 Adaptive RAG）。  
- **HITL** 适合「对客回复发出前审核」「写库前审批」。  
- **SqliteSaver / Postgres checkpointer** 是生产持久化的方向，教学用 SQLite 即可。

---

*讲义与 `examples/` 同步维护；模型默认 `glm-4-flash`，见 [`llm_factory.py`](llm_factory.py)。*
