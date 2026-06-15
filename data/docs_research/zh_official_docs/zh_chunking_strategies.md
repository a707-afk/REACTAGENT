<!-- source: AI辅助整理 | category: rag/chunking | language: zh-CN -->

# Chunking 策略深度：按格式分发 + 参数调优

## 一刀切是最大的坑

Markdown 文档标题是天然边界，PDF 论文的表格需要特殊处理，HTML 页面有导航栏污染。对所有文档用同一个 chunking 策略 = 对一部分文档是"最佳"，对另一部分是"灾难"。

## 按格式分发

**Markdown**：层次化标题递归切分。按 H2 分大块 → 块内递归切至 512 tokens → 64 token overlap。保留 heading_path 元数据。

**PDF**：先 pymupdf4llm 转 Markdown（保留表格和公式）→ 再用 Markdown 策略切分。不用原生 PDF 切分——会破坏表格结构。

**HTML**：先 html2text 转 Markdown → 再用 Markdown 策略切分。关键前置步骤：去导航栏、去 footer、去 sidebar（这些是 HTML 特产，Markdown 不需要）。

## Chunk Size 比 Chunk Strategy 更重要

据 arXiv 评测（2605.22203），chunk size 的调优效果大于 chunking strategy 的选择。推荐 256-512 tokens + 10-15% overlap。太小（<128）→ 上下文碎片化；太大（>1024）→ 噪音比例上升。

## 关键参数

| 参数 | 推荐值 | 理由 |
|---|---|---|
| chunk_size | 512 tokens | 技术文档最优点（英文 200-300 词、中文 300-500 字） |
| chunk_overlap | 64 tokens | 保证跨 chunk 上下文连续 |
| 最小 chunk 长度 | 50 tokens | 过滤无效短 chunk |

## 面试回答要点
"我用了按格式分发的 chunking——不是一刀切。Markdown 用层次化递归、PDF 先转 Markdown 再切、HTML 先去导航栏。chunk size 512 是实验数据支撑的（不是猜的）。"
