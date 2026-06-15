# 研究文档库

本目录是 Deep Research Agent 的本地知识源，包含开源技术项目的官方 README，
用于支撑"技术选型调研"类研究问题。

## 目录结构

```
docs_research/
├── vector_dbs/ # 向量数据库对比
│ ├── qdrant_readme.md
│ ├── milvus_readme.md
│ ├── pgvector_readme.md
│ ├── chroma_readme.md
│ └── weaviate_readme.md
├── agent_frameworks/ # Agent 框架对比
│ ├── langgraph_readme.md
│ ├── crewai_readme.md
│ ├── autogen_readme.md
│ ├── llamaindex_readme.md
│ └── langchain_readme.md
└── embeddings/ # Embedding 模型对比
 ├── bge-m3_readme.md
 ├── sentence-transformers_readme.md
 └── qwen3-embedding_readme.md
```

## 数据来源

所有文档均为公开开源项目的官方 README，直接从 GitHub 抓取。
更新方式：`python scripts/build_research_kb.py`（阶段 3 实现）。

## 适用研究问题示例

- "对比 Qdrant、Milvus、pgvector 的核心特性"
- "LangGraph 和 CrewAI 各自适合什么场景"
- "BGE-M3 和 Qwen3-Embedding 的区别"
- "向量数据库选型：什么时候用 pgvector 就够了"