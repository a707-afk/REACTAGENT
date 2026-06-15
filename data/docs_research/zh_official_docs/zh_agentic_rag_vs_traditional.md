<!-- source: AI辅助整理 | category: agent/agentic-rag | language: zh-CN -->

# Agentic RAG vs 传统 RAG：什么时候需要 Agent

## 区别不在检索，在决策

传统 RAG：用户问 → 检索 → 生成回答。一次查询，一次回答。

Agentic RAG：用户问 → Agent 推理 → 分解子问题 → 多次检索 → 综合 → 回答。Agent 自主决定"搜什么、搜几次、够了没"。

## 什么时候需要 Agentic RAG

- 问题需要多步推理："对比 Qdrant 和 Milvus"需要先搜 A 特性、再搜 B 特性、再对比
- 问题需要验证："这个说法对吗"需要搜多个源、交叉验证
- 问题需要综合："给我写一份报告"需要搜、分析、组织、写、检查

简单问题（"Qdrant 怎么安装"）用传统 RAG 更高效。

## Agentic RAG 的额外成本

每一步检索消耗 LLM token（决策 token + 检索 token + 综合 token）。Agentic RAG 比传统 RAG 多 3-10x token 消耗。如果问题不需要多步推理，Agentic RAG 是浪费。

## 面试回答要点
"Agentic RAG 不是银弹。简单问题用传统 RAG（快、便宜），复杂问题用 Agentic RAG（需要多步推理和验证）。我的系统按问题复杂度自动分级——这是工程判断，不是新技术。"
