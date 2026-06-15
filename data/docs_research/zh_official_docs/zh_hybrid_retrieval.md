<!-- source: AI辅助整理 | category: rag/hybrid-retrieval | language: zh-CN -->

# 混合检索详解：BM25 + Dense + RRF 融合

## 为什么单路检索不够

纯向量（Dense）检索擅长语义匹配，但对精确关键词不敏感——"Qdrant payload filter" 和 "Qdrant 负载过滤" 语义接近但词完全不同。纯 BM25 擅长关键词匹配，但"换货"和"尺码不合适想换"词法差异大。混合检索取两者之长。

## 三阶段流水线

### 阶段 1：并行检索
BM25（词法）：jieba 分词 → BM25Okapi 打分 与 Dense（语义）：BGE-M3 encode → Qdrant HNSW 检索，并行执行。

### 阶段 2：RRF 融合
score = 1 / (k + rank)，k=60。为什么用 RRF 而非 Min-Max 归一化？BM25 和 Cosine 的分数尺度不同——BM25 可能是 0-100，Cosine 是 0-1。Min-Max 强行映射会扭曲分布，RRF 只关心排名不关心绝对分数，更稳健。

### 阶段 3：Rerank 精排
融合后的 top-K 候选 → Cross-encoder 精排 → 取 top-N 最终结果。门控阈值：最优 rerank 分 < 阈值 → 拒答。

## BGE-M3 特殊优势
BGE-M3 自带 sparse 模式，可以完全替代独立 BM25——减少一个组件，架构更简洁。
