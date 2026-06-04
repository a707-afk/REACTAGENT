---
domain: ai_governance
subdomain: rag_evaluation
source_type: standard
audience: ai_engineer,qa,ops_manager
security_level: internal
tenant_id: corp-default
owner: ai_platform_team
workflow: rag_evaluation
version: v1.0
status: active
---

# RAG 质量评估规范

## 评估目标

RAG 系统不能只用“感觉回答不错”来验收。评估必须覆盖检索、重排、生成、引用、拒答和权限。上线前应建立基础评估集，上线后持续用真实 bad case 扩充。

## 评估集结构

每条评估样本应包含：

- `id`
- `question`
- `expected_domain`
- `expected_doc`
- `expected_answer_points`
- `should_refuse`
- `required_permission`
- `risk_level`
- `notes`

如果是跨领域问题，应标注主领域和辅助领域。

## 问题类型

评估集应覆盖：

- 简单事实问题。
- 多条件问题。
- 口语化问题。
- 跨领域问题。
- 权限不足问题。
- 知识库无答案问题。
- 高风险自动化问题。
- 文档版本冲突问题。
- 同义词问题。
- 错误诱导问题。

只评估简单事实问题会高估系统能力。

## 核心指标

检索侧指标：

- Top-1 命中率。
- Top-5 命中率。
- MRR。
- 领域路由准确率。
- 权限过滤准确率。

生成侧指标：

- 答案正确性。
- 忠实度。
- 引用有效率。
- 拒答准确率。
- 高风险转人工准确率。

工程侧指标：

- 平均延迟。
- P95 延迟。
- Token 成本。
- 工具调用失败率。
- 超时率。

## bad case 分析

每个 bad case 至少记录：

- 原始问题。
- 检索 query。
- top-k 文档。
- rerank 分数。
- 生成答案。
- 错误类型。
- 修复动作。

错误类型包括：文档缺失、切片不合理、召回失败、重排错误、Prompt 约束弱、权限过滤错误、模型幻觉和评估标签错误。

## 验收标准

企业内部试运行建议达到：

- Top-5 命中率不低于 85%。
- 引用有效率不低于 90%。
- 应拒答问题拒答准确率不低于 90%。
- 高风险问题转人工准确率不低于 95%。

这些指标不是通用行业标准，而是当前项目的内部验收线。不同业务应根据风险调整。

