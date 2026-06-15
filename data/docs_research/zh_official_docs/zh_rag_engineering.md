<!-- source: AI辅助整理 - 基于多个工程实践来源、生产级RAG陷阱总结 -->
<!-- category: rag/engineering -->
<!-- language: zh-CN -->

# RAG 工程实践：从 Demo 到生产级的关键跃升

## 最常见的 5 个工程陷阱

### 1. 评测造假（Dry-run 陷阱）
用 gold chunks 直接模拟检索结果，算出 Recall@5=1.0。这不是评测，是循环证明。真实评测必须：① 真实检索 ② 独立 golden set ③ 报告级指标（不只是 chunk 级）

### 2. 上下文窗口滥用
把所有检索结果无差别塞进 prompt。"top_k=20 检索，768-dim embedding"看起来不错——但你塞了 20 个 × 500 token = 10000 token 的上下文，其中 70% 是噪音。正确做法：Rerank 后取 top 5-7，每个 chunk 截断到 300 token。

### 3. Chunking 一刀切
所有文档用同一种切分策略。Markdown 按标题切的效果好，但 PDF 论文里表格会被拆碎、HTML 页面里导航栏会被当正文。正确做法：按文档格式分发——Markdown 用层次化递归、PDF 先转 Markdown 再切、HTML 先去导航栏再切。

### 4. 嵌入模型选错
选"排行榜最高的"模型，但它不支持你的语言/领域。"MTEB 排行第一"通常是英文通用场景。如果你做中文技术问答，需要看 MIRACL 中文子集的评测结果。BGE-M3 在中文场景的 nDCG@10=0.674。

### 5. 缓存不分租户
"我们加了缓存，QPS 翻倍"——但缓存键里没有 tenant_id。用户 A 检索了敏感文档，结果被缓存；用户 B 搜索同样关键词时，看到了 A 的私有文档。

## 生产级的 RAG 流水线

```
用户查询
  → Query Rewrite（LLM 改写为更精确的检索词）
  → 并行检索（BM25 词法 + Dense 向量 → RRF 融合）
  → Rerank（Cross-encoder 精排，取 top 5-7）
  → Similarity Gate（最优分 < 阈值 → 拒答）
  → LLM 生成（带引用标注 [1][2]）
  → 句级 Grounding（验证每句话是否被源支撑）
  → 输出（不通过则回到 Query Rewrite 重新检索）
```

## Reranker 不是银弹

如果嵌入模型的召回就很差（chunking 不当、嵌入模型选错），Reranker 只能从烂结果里挑"不那么烂的"。**先修召回，再上 Reranker**。

## 面试回答要点

被问"RAG 怎么从 Demo 做到生产级"：
- 评测体系（不是 dry-run，是真实指标）
- 上下文预算（不是越多越好，是精排后取少量精华）
- 按格式分发 chunking（不是一刀切）
- 缓存要按租户隔离（安全漏洞案例）
