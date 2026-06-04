---
domain: customer_service
subdomain: answer_quality
source_type: faq
audience: support,ai_engineer,customer_success
security_level: internal
tenant_id: corp-default
owner: ai_platform_team
workflow: answer_quality_support
version: v1.0
status: active
---

# AI 回答质量问题处理 FAQ

## 问题范围

AI 回答质量问题包括答非所问、引用错误、无依据强答、回答过长、回答过短、口吻不符合客服规范、重复回答、拒答过多和检索不到应有文档。

## 初步定位

客服或 AI 平台工程师应按以下顺序定位：

1. 用户问题是否清晰。
2. 知识库是否存在答案。
3. 文档是否已索引。
4. 检索结果是否命中正确 chunk。
5. Reranker 是否把正确 chunk 排到前面。
6. 门控阈值是否过高或过低。
7. Prompt 是否要求只基于引用回答。
8. 模型是否忽略了系统约束。

不要一开始就判断为模型能力问题。大多数 RAG 质量问题来自文档、切片、检索、重排或提示词约束。

## 答非所问

答非所问常见原因：

- 查询太口语化，向量检索召回偏离。
- 多个领域存在相似词，例如“额度”可能指 API 额度、发票额度或权限额度。
- chunk 太短，缺少上下文。
- chunk 太长，噪声过多。
- Reranker 候选不足。

处理建议：

- 开启 Query Rewrite。
- 增加领域路由。
- 调整 chunk size 和 overlap。
- 增加评估问题。
- 检查 top-k 候选和重排分布。

## 引用错误

引用错误分两类：

- 检索引用本身不相关。
- 检索相关，但生成答案引用编号不准确。

第一类应优化检索和重排；第二类应增加引用校验或要求模型逐条引用证据。高风险场景下，应在生成后做自动校验，无法校验时转人工。

## 拒答过多

拒答过多可能是门控阈值过高、Reranker 分数刻度不匹配、评估集覆盖不足或文档缺失。处理时应查看：

- `gate_score_min`
- `gate_score_max`
- 被拒答问题的 top-k 文档。
- 是否有正确答案但分数低。

不要为了减少拒答直接把阈值调得很低，否则会增加幻觉。

## 客服回复边界

客服可以向客户解释系统需要基于已授权知识库回答。若客户反馈答案错误，应收集问题原文、答案、引用、时间和 trace_id，提交“回答质量问题”工单。

## 推荐回复模板

您好，我们已记录该问题。为了定位是知识库内容、检索召回、重排还是生成环节导致，请您提供问题原文、系统回答、引用来源和发生时间。我们会根据 trace_id 排查链路，并在确认后更新知识库或调整检索策略。

