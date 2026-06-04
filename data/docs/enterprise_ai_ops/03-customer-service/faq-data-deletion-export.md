---
domain: customer_service
subdomain: data_deletion_export
source_type: faq
audience: support,customer_success
security_level: public
tenant_id: corp-default
owner: support_operations
workflow: customer_support
version: v2.0
status: active
---

# 数据删除与导出请求 FAQ（一线客服）

> **域边界**：客户侧流程与话术。技术删库步骤见产品手册；审批与 SLA 见工单流程文档。

## 客户要求删除全量知识库

**客服不得直接操作删除。** 须：

1. 确认请求人是否为企业**管理员**或授权签署人。
2. 创建「数据删除 / 合规」工单，标记高风险。
3. 收集：租户 ID、删除范围、法律依据或合同条款、期望完成时间。
4. 转合规与客户成功审批；执行由平台运维在变更窗口完成。

AI 回答「可以在后台一键删除」属于 **RAG bad case**，应引用本文而非仅引用产品 UI 文档。复盘见 `07-cases/case-rag-wrong-citation.md`。

## 导出全量数据

同样需管理员授权与工单审批；导出内容可能含 restricted 字段，须走安全审查。

## 推荐话术

删除或导出全量数据涉及合规与审计，我们需要验证您的管理员身份并通过内部审批流程，无法由在线客服直接执行。请提供企业名称、管理员邮箱与删除范围，我们将创建正式工单跟进。
