<!-- source: AI辅助整理 | category: rag/grounding | language: zh-CN -->

# 引用溯源：句级 Grounding 实现原理

## 为什么需要 Grounding

LLM 生成回答时可能编造不存在的事实（幻觉）。Grounding 在生成后验证：每句话是否被检索到的源文档支撑？未被支撑的句子 = 幻觉风险。

## n-gram 字符重叠法

对答案拆句 → 每句对每个 chunk 做 3-gram Jaccard 重叠。阈值 0.28：低于阈值的句子标记为 unsupported。

**子串加成**："Qdrant 支持 HNSW 索引"如果在 chunk 中找到连续至少 4 个字符的匹配（如"HNSW"），即使 n-gram 重叠率不高，也提高分数。

## Embedding 余弦相似法

对答案句和 chunk 各做 Embedding → 计算余弦相似度。阈值 0.42 标记为 supported。

**混合策略**：优先用 Embedding 模式（更准确），Embedding 模型不可用时 fallback 到 n-gram 模式。

## 句子拆分

按中文标点拆分：句号、感叹号、问号、分号、换行符。最小句子长度 2 字符。

## Grounding 报告

返回：每句的 support_score、best_chunk_id、unsupported 标记、unsupported_rate。如果 > 35% 句子 unsupported → grounding failed → 回到检索补充。
