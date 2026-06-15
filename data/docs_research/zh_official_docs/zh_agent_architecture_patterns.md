<!-- source: AI辅助整理 | category: agent-engineering | language: zh-CN -->

# Agent 架构模式全景对比：ReAct、Plan-Execute、Reflection、Loop Engineering

## 为什么选模式比选框架重要

LangGraph、CrewAI、AutoGen 都只是"实现工具"。真正的架构决策是**选什么循环模式**。选错模式，框架再好也救不了。

## 四种核心模式对比

| 模式 | 核心思想 | 适合场景 | 关键缺陷 |
|---|---|---|---|
| ReAct | Think→Act→Observe 单步循环 | 简单工具调用 | LLM 自评不可靠，没有全局规划 |
| Plan-Execute | 先 LLM 生成完整计划，再逐步执行 | 需要分解的复杂任务 | 计划是静态的，不能动态调整 |
| Reflection | ReAct + 每步后 LLM 自评修正 | 需要多次迭代的任务 | 增加了步数，延时翻倍 |
| Loop Engineering | Trigger + Verifiable Goal + Agent + Verification + Guardrails | 生产级 Agent | 复杂度最高，需要外部验证器 |

## ReAct 为什么不够

ReAct 的致命缺陷在基准测试中不明显，但在真实场景中暴露：Agent 在某一轮检索到 3 个相关文档后说"信息足够了"，但实际漏掉了另一个来源的矛盾数据。LLM 无法客观判断"够了"。

## Loop Engineering 的优势

它把决策权从 LLM 交给外部验证器：
1. LLM 负责"做什么"（规划和执行）
2. 验证器负责"做够了吗"（faithfulness + coverage）
3. 护栏负责"别跑飞"（步数上限、成本上限、超时）

## 面试回答要点

被问"你用了什么 Agent 模式"，回答："Loop Engineering——和 ReAct 的区别是验证权不在 LLM 手里，在外部验证器手里。"
