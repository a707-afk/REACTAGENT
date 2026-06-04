---
domain: case
subdomain: rag_bad_case
source_type: quality_narrative
audience: ai_engineer,support,qa
security_level: internal
tenant_id: corp-default
owner: ai_platform_team
workflow: rag_evaluation
version: v2.0
status: active
---

# 案例：AI 回答引用了错误制度（RAG bad case）

> 数据删除**客服流程**见 `03-customer-service/faq-data-deletion-export.md`；本案例为质量复盘叙事。

## 背景

客服问：「客户要求删除全量知识库，可以直接操作吗？」系统回答可在后台删除，引用了产品手册，**未**引用删除/export FAQ。

## 问题

回答混淆「产品能力」与「谁可在何种审批下操作」。客户若照做可能绕过权限与审计。

## 定位（trace 摘要）

- 向量与 BM25 均偏向「删除知识库」产品文档。
- Rerank top1 为操作手册；安全/流程文档排位靠后。
- 未触发 data_deletion 领域路由。

## 修复动作（平台侧）

1. 评估集增加本题（E003 等）。
2. 对删除/导出关键词加强安全与客服流程召回。
3. Prompt 要求高风险操作优先引用流程文档。

## 复盘模版位置

本文件即为 **RAG bad case 复盘模版** 实例；新 bad case 可复制「背景 / 问题 / 定位 / 修复 / 教训」结构，勿在案例内粘贴 SLA 或财务字段表。

## 相关文档

- `03-customer-service/faq-data-deletion-export.md`
- `05-ai-governance/rag-quality-evaluation.md`
