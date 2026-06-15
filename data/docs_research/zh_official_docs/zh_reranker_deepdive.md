<!-- source: AI辅助整理 | category: rag/reranker | language: zh-CN -->

# Reranker 深度选型：Cross-Encoder vs LLM Reranker

## Reranker 做什么

检索阶段返回 top-K 候选（粗排），Reranker 对这 K 个候选做精细重排（精排）。它不是替代检索，而是优化检索结果。

## 两大技术路线

### Cross-Encoder Reranker（bge-reranker-v2-m3）
- **原理**：把 (query, doc) 对输入编码器，直接输出相关性分数。编码器同时看到 query 和 doc——这比分开编码再算余弦相似度更精确。
- **优点**：轻量（~1GB VRAM）、快速、默认性能好
- **缺点**：不擅长结构化推理（"文档 A 比文档 B 更适合"需要看两者的相对差异）

### LLM-based Reranker（Qwen3-Reranker）
- **原理**：用 CausalLM 的 yes/no logit 分数做重排。给模型 prompt："Document: xxx\nQuery: yyy\nIs this relevant? Yes/No"
- **优点**：可以利用 LLM 的语义理解能力，对复杂推理 questions 更好
- **缺点**：VRAM 更大（0.6B ~2GB, 4B ~10GB），推理更慢，对指令敏感（指令差则性能低于 Cross-Encoder）

## 选型决策

默认用 bge-reranker-v2-m3（轻量、稳定）。在评测集上做 A/B 对比——如果特定类别问题 bge 效果差，再考虑 Qwen3-Reranker。

## Reranker 不是银弹

如果 Embedding 召回就很差，Reranker 只是从烂结果里挑"不那么烂的"。先确保召回质量，再上 Reranker。
