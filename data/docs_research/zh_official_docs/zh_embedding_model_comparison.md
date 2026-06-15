<!-- source: AI辅助整理 | category: embedding-models | language: zh-CN -->

# Embedding 模型深度对比：BGE-M3 vs Qwen3 vs Cohere vs OpenAI

## 为什么 Embedding 选型是 RAG 的第一道坎

Embedding 质量直接决定召回上限。Reranker 可以精排，但不能"无中生有"——如果 Embedding 根本没召回相关文档，Reranker 也无能为力。

## 四大路线

### BGE-M3（BAAI）
- 568M 参数，1024 维（dense + sparse + ColBERT 三路）
- 100+ 语言，中英德强
- VRAM：~2GB FP16 / ~0.3GB Q4
- nDCG@10(MIRACLE zh)：0.674
- **唯一同时支持 dense+sparse+多向量的模型**——可以替代 BM25

### Qwen3-Embedding-0.6B（阿里）
- 600M 参数，1024 维（纯 dense）
- 32K 上下文窗口（大幅领先 BGE-M3 的 8K）
- VRAM：~2GB FP16
- nDCG@10(MIRACLE zh)：0.656（略低于 BGE-M3）
- **适合超长文档**（论文全文、合同）

### Cohere Embed v3 / OpenAI text-embedding-3-large
- API 模式，无需 GPU
- 英文强，中文中等
- **成本**：Cohere $0.10/1M tokens、OpenAI $0.13/1M tokens
- **数据隐私风险**：文本离开你的服务器

### 选型决策树
```
需要多语言 + 自定义检索模式 → BGE-M3
需要超长文本（>8K tokens） → Qwen3-Embedding
没有 GPU 资源 → Cohere/OpenAI API
需要纯英文最高精度 → OpenAI text-embedding-3-large
需要中文最高精度 → BGE-M3（MIRACLE zh 第一）
```

## 面试回答要点

被问"为什么选 BGE-M3 不用 Qwen3"，回答：
"BGE-M3 的 dense+sparse 组合让我淘汰了独立的 BM25 组件，架构简化；Qwen3 的 32K 上下文是优势但在我的场景用不上（chunk 512 tokens）。我是基于 MIRACLE benchmark 数据做的决策不是拍脑袋。"
