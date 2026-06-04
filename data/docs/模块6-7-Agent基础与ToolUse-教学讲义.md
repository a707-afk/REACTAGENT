# 模块 6-7：Agent 基础 + Tool Use — 教学讲义（实施稿）

> 对应《RAG学习教学记录与规划》模块 6-7（v2 框架版图）。教学方式：**概念 → 机制 → 实操 → 面试**。  
> 建议顺序：先读 **附录 A（MCP 快速过关）**，再按 **L1→L7** 学习；若已完整学完规划文档中的 MCP 模块，附录 A 可仅作自查清单。

---

## 导读：学完本章你应能回答的问题

- Agent 与「单次 LLM 调用」本质差在哪？ReAct 循环怎么画？
- Function Calling 与 MCP 各自解决什么？如何协同？
- v2 五类框架（LangGraph / CrewAI / OpenAI Agents SDK / Smolagents / Google ADK）各一句话定位 + 场景选型？
- AutoGen、Dify 在新版图里如何表述（不超纲）？

---

# 附录 A：MCP 快速过关（L4 前必达）

> **用途**：若尚未学习规划文档「★ 新增模块：MCP协议」全模块，请在本附录达标后再学 **L4** 及之后涉及「Calling vs MCP」「MCP 暴露检索」的内容。

## A.1 三要素（面试必答）

| 要素 | 含义 | 示例 |
|------|------|------|
| **Tools** | 可执行动作 | 搜索、写库、发消息 |
| **Resources** | 只读上下文 | 读文件、拉取配置 |
| **Prompts** | 可复用模板 | 预设提示词片段 |

## A.2 架构与传输

- **MCP Server**：暴露 Tools / Resources / Prompts。
- **MCP Client**：宿主应用（IDE、Agent 运行时）连接 Server 消费能力。
- **传输**：JSON-RPC over **stdio**（本地）或 **Streamable HTTP**（远程）。

## A.3 行业含义（一句话）

- **N×M → N+M**：多应用、多工具时，用统一协议减少定制集成次数。
- **2025-12**：MCP 捐赠给 **Agentic AI Foundation（AAIF）**，治理上更偏行业标准（面试可加一句）。

## A.4 与 RAG 的结合（预习）

- 可将「向量检索 / 元数据过滤」封装为一个 **MCP Tool**；Agent 侧仍通过 **Function Calling**（或等价机制）决定是否、如何调用该工具。

## A.5 自查清单（全勾再进入 L4）

- [ ] 能口述 Tools / Resources / Prompts 区别各一例  
- [ ] 能区分 MCP Server 与 Client  
- [ ] 能回答：「MCP 解决集成规范问题，不是替代某个 Agent 框架」  

---

# L1：Agent 定义、单次推理 vs 自主行动、ReAct（6.1 Part 1）

## 学习目标

- 记忆公式：**Agent ≈ LLM + 记忆 + 工具 + 规划**（记忆与规划在模块 8、9 深化）。
- 能对比：**单次 prompt-completion** vs **多步行动序列**（谁决定「下一步」）。

## 概念

- **单次推理**：人写好调用顺序，模型只负责生成文本。
- **Agent**：模型（或运行时）参与决策——**调不调工具、调哪个、是否结束**。

## 机制：ReAct

循环：**Thought（推理）→ Action（行动/工具）→ Observation（观察结果）→** 再 Thought …

```
用户问：某公司 2024 年营收政策变更影响？
Thought：需要先检索内部制度与公开新闻。
Action：search_knowledge_base(query="营收 政策 2024")
Observation：[chunk1, chunk2, ...]
Thought：信息够写摘要，不再检索。
Action：finish(answer="...", citations=[...])
```

## 实操（轻量，不写代码）

用**伪代码**写满 3 轮 ReAct（含至少一次「不需要工具直接答」的分支也可）。

## 面试快答

| 问题 | 要点 |
|------|------|
| Agent 和 Chain 的区别？ | Chain 链路由开发者固定；Agent 由模型/运行时**动态**选下一步 |
| ReAct 解决什么？ | 把**推理**与**工具使用**显式交错，便于调试与加审计 |

## 参考延伸

与模块 3「Agentic RAG」关系：Agentic RAG 是上层范式，可内含 Routing / CRAG / Adaptive 等；本章补齐 **工具层与框架层**。

---

# L2：2026 Agent 类型与岗位语境（6.1 Part 2）

## 四类类型（规划文档口径）

| 类型 | 典型任务 | 工具特征 |
|------|----------|----------|
| **Chat Agent** | 对话、轻量查数 | 检索、FAQ、少量 API |
| **Research Agent** | 多源汇总、对标 | 检索、爬取/搜索、摘要链 |
| **Workflow Agent** | 业务流程（审批、工单） | 写库、状态机、**人工审批** |
| **Coding Agent** | 改代码、跑测试 | 读文件、终端、LSP/CI |

## 与模块 3 LangGraph 的 Hook

- 你在 **3.7** 已见 `StateGraph` / `TypedDict` 状态。
- **企业价值重申**（用户纠正）：LangGraph 主卖点之一是 **Human-in-the-loop**（高风险操作前 pause，人工批准再继续），而非「只做 Query Routing」。
- 本节将 **Workflow Agent + 需审计分支** 默认与 **LangGraph** 心智对齐（具体代码在 L5）。

## 实操（讨论）

挑一个你熟悉业务：**更像 Chat 还是 Workflow？** 若加「必须先人工批准再发邮件」，状态机应放在哪一类节点？

## 面试快答

「Agent 类型怎么选？」—— 按 **任务是否多步、是否强合规、工具是否写副作用** 三分法简答即可。

---

# L3：Function Calling 机制与工具设计（6.2 Part 1）

## 机制

1. 模型在支持 **tool schema** 的前提下，输出 **结构化** `tool_calls`（名称 + 参数 JSON）。
2. **运行时**执行对应函数 / RPC / MCP 桥接。
3. 将 **tool 结果** 以 `role=tool`（或厂商等价字段）写回消息历史。
4. 模型进入下一轮，决定继续调用或输出最终答案。

## 伪代码（一次闭环）

```text
messages = [system, user("查知识库：退款策略")]
response = llm.chat(messages, tools=[search_kb])
# response.tool_calls = [{ name: "search_kb", args: { q: "退款" } }]
result = search_kb(**tool_args)
messages += [assistant_tool_calls, tool_message(result)]
final = llm.chat(messages, tools=[search_kb])
```

## 工具设计原则

- **单一职责**：一个工具一件事（检索 vs 写库分离）。
- **描述可检验**：参数含义、单位、空值语义写清，降低模型乱填。
- **错误可解析**：返回结构化错误码 + 简短原因，便于模型自纠或重试。

## 多工具编排（概览）

- **描述差异**：不同工具的 description 要让模型「一眼能选对」。
- **顺序策略**：常见模式 **先检索只读 → 再写**，避免未经验证就写入。
- **冲突**：两工具都可写同一资源时，在系统层设 **互斥锁或权限标签**，不要只靠 prompt。

## 面试快答

「如何避免模型乱调工具？」—— Schema + 描述 + **允许调用的白名单** + 运行时校验参数 + 护栏（模块 12 展开）。

---

# L4：Function Calling vs MCP、与 RAG 结合、面试题（6.2 Part 2）

## 前置

完成 **附录 A MCP 快速过关**。

## 核心对比（v2 必背）

| 维度 | Function Calling | MCP |
|------|------------------|-----|
| 层级 | 模型侧「如何发起一次工具调用」**机制** | 应用间「如何连同一套工具/资源」**协议** |
| 范围 | 常在一应用内闭环 | 跨宿主、跨团队复用 Server |
| 关系 | **不互斥** | Agent 可用 Calling **调用** MCP 暴露的工具 |

**口诀**：Calling 是「打电话的方式」，MCP 是「插线板与插座标准」。

## 与 RAG 的话术示例

- **工具列表**：`search_vector_db`（返回 chunk + doc_id）、`verify_citations`（检查回答中的 `[Doc_N]`）、`create_ticket`（可选）。
- 若检索由独立团队维护：将 `search_vector_db` 做成 **MCP Tool**，主应用只接 MCP。

## 面试题与答题骨架

**Q：为什么有了 Function Calling 还要 MCP？**  
**A：** Calling 不解决「100 个应用 × 100 个工具」的集成爆炸；MCP 把工具以标准 Server 暴露，实现 **N+M** 级复用与治理（版本、鉴权、审计）。

**Q：MCP 会取代 LangGraph 吗？**  
**A：** 不同层——Graph 管 **编排与状态**；MCP 管 **对外能力与上下文接入**。

---

# L5：LangGraph + CrewAI（6.3 Part 1）

## LangGraph

| 项 | 内容 |
|----|------|
| **核心抽象** | State、Node、Edge、Conditional Edge |
| **强项** | 显式状态机、分支、可回放轨迹 |
| **企业关键词** | **Human-in-the-loop**（`interrupt` / checkpoint 等，细节见模块 11） |

**复习钩子（对齐模块 3.7）**：状态用 `TypedDict`；`StateGraph` 上 `add_node` / `add_conditional_edges`；`compile()` 后 `invoke`。

**RAG 挂钩**：检索、重排、生成可拆节点；**低置信 / 高风险** 走「人工审核」边。

## CrewAI

| 项 | 内容 |
|----|------|
| **核心抽象** | Role、Goal、Backstory（声明式「人设 + 分工」） |
| **强项** | 快速搭 **多角色协作** demo |
| **弱项** | 极复杂分支与稽核，常不如显式图清晰 |

## 对比（面试）

「同一多步报告任务，用 LangGraph 还是 CrewAI？」—— 原型/角色戏剧感强：CrewAI；要强审计、多条件路由、人在回路：LangGraph。

## 极简方向标（非完整可运行代码）

**LangGraph 递进实操（环境、阶段 1–5 脚本）**：见项目内 [`LangGraph学习路线.md`](LangGraph学习路线.md)（原《LangGraph与CrewAI-深度学习》已由该路线替代，CrewAI 单列时再补）。

- **LangGraph**：仓库与文档检索关键词 `StateGraph Human-in-the-loop`。
- **CrewAI**：官方 Quickstart `Agent` + `Task` + `Crew`。

---

# L6：OpenAI Agents SDK + Smolagents（6.3 Part 2）

## OpenAI Agents SDK（≈2025-03，替代 Swarm）

| 项 | 内容 |
|----|------|
| **核心** | **handoff** — 显式把对话控制权交给另一 Agent（带上下文） |
| **定义要素** | 指令、模型、tools、**可 handoff 的下游 Agent 列表** |
| **场景** | 已押注 OpenAI API、多专长 Agent 分流 |

**序列图心智**：用户 → Agent A →（handoff）→ Agent B → tools → 回到 B 或再交接。

## Smolagents（Hugging Face）

| 项 | 内容 |
|----|------|
| **核心** | Agent **生成并执行代码**（不仅是 JSON 填工具参数） |
| **场景** | 本地模型、HF 生态、需要「临时 orchestration」算子 |
| **风险一句** | 代码执行必须 **沙箱/权限**（模块 12 安全深化） |

## 面试对比

「SDK handoff vs CrewAI 角色？」—— handoff 是 **控制流 API 级别显式**；CrewAI 偏 **声明式角色协作**。

---

# L7：Google ADK、MCP vs A2A、决策树总复盘、模拟面试（6.3 Part 3）

## Google ADK（Agent Development Kit）

| 项 | 内容 |
|----|------|
| **亮点** | **原生 A2A** 互操作；Gemini 多模态 |
| **场景** | Google Cloud、要与 **异构框架** Agent 对接 |

## A2A 预习（完整在模块 10）

| 协议 | 连接对象 | 记忆 |
|------|----------|------|
| **MCP** | Agent ↔ **工具 / 数据** | 垂直集成 |
| **A2A** | Agent ↔ **Agent** | 水平协作 |

Google 亦采用 MCP：两者 **分工不竞争**；企业系统常 **两个都要**。

## 降级/删除项（面试一句话）

- **AutoGen**：曾流行；**v0.7.5 后长期无更**，生产选型淡化，一提即止。  
- **Dify**：**低代码/可视化编排产品**，不与 LangGraph/CrewAI 等「开发框架」同层竞品表。

## v2 选型决策树（必背）

| 场景 | 推荐 | 一句话理由 |
|------|------|------------|
| 生产、复杂分支、人在回路 | **LangGraph** | 图状态机，审计与回溯强 |
| 快速原型、角色分工明确 | **CrewAI** | 声明式角色，上手快 |
| OpenAI 栈、显式多 Agent 交接 | **OpenAI Agents SDK** | handoff 一阶抽象 |
| 本地 LLM、HF、灵活算子 | **Smolagents** | 代码执行，少绑固定工具 |
| 跨框架 Agent、GCP/Gemini | **Google ADK** | 原生 A2A |

## 模拟面试题（45 min 可用）

1. 为什么说 LangGraph 在企业里常与「审批」绑定？若只有 Query Routing 需求，_graph 是否仍必选？  
2. 检索服务由别的团队维护，你如何切 MCP？Calling 在哪里？  
3. Smolagents 与「普通 Tool Calling Agent」的本质差别？风险点？  
4. MCP 与 A2A 各管什么？为什么不是二选一？  
5. 场景题：售后工单「先检索知识库文档 → 生成回复」且「发送前必须人工批准」—— 框架与节点如何粗粒度设计？

---

# 课后作业（必做 + 选做）

## 作业 1：决策树自测（必做）

复制规划文档 v2 决策表 **5 行**，每格补 **不少于 20 字** 的「为什么」，可举反例（什么情况下**不**选推荐项）。

## 作业 2：双框架 Mini Demo（必做）

**同一任务**：「检索至少 3 段资料 → 生成带 `[Doc_N]` 引用的短答」（检索可 mock 成假数据，重点在 **编排**）。

- **实现 A**：LangGraph（状态含 `documents`、`draft`、`approved` 等字段；至少 2 个 node）。  
- **实现 B**：CrewAI（至少 2 个 Agent 或 2 个 Task）。  

**交付**：`README` 中写 **编排心智负担对比**（各 5 条 bullet）。

## 作业 3：面试卡片（选做）

6 张卡片：**ReAct**、**Calling vs MCP**、**LangGraph / CrewAI / Agents SDK / Smolagents / ADK** 各「定位 + 场景」一行。

---

# 附录 B：教学目标核对表

学完 L1–L7 后自评：

- [ ] 能画 ReAct 并举例  
- [ ] 能说明 Calling 与 MCP 的协同  
- [ ] 能背决策树 5 行  
- [ ] 知 AutoGen / Dify 新定位  
- [ ] 完成最小 Tool 闭环思路 + 任选一框架 Hello Agent 路线  

---

*讲义结束 · 与《RAG学习教学记录与规划》模块 6-7 v2 对齐*
