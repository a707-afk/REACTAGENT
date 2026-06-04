---
domain: case
subdomain: refund_review
source_type: incident_narrative
audience: support,finance,customer_success
security_level: restricted
tenant_id: corp-default
owner: finance_operations
workflow: refund_review
version: v2.0
status: active
---

# 案例：客户要求 AI 自动批准退款

> **案例域说明**：仅记录**时间线、决策与教训**。退款材料字段与审批步骤见《退款申请审核流程》；禁止在本案例重复财务复核字段表。

## 背景（2025-Q3）

客户因上月短时服务异常，要求退还当月 50% 服务费，并坚持「AI 直接确认金额、不要人工」。

## 事件经过

1. 在线客服收到诉求，系统创建退款工单。
2. 客户**拒绝上传**故障日志，仍要求**立即退款**。
3. 一线按 FAQ 解释需财务审批；客户升级至客户成功经理。
4. 财务按《退款申请审核流程》核对合同与付款；SRE 补充故障窗口说明。
5. 业务负责人批准部分退款；**未**由 AI 自动批准。

## 关键决策

- 未因客户施压跳过财务复核。
- AI 仅生成摘要与缺失材料提示。
- 人工复核 playbook：**《退款申请审核流程》** + 本案例教训「拒绝日志仍须走 restricted 工单」。

## 教训

AI 或客服不得承诺退款比例与到账时间。类似问法在权限评测中，低 clearance 用户不应在 top5 看到 restricted 案例全文或完整 workflow 字段表。

## 相关文档（链接，非复制）

- 流程权威版：`04-ticket-workflow/refund-review-workflow.md`
- 客服话术：`03-customer-service/` 计费 FAQ（如有）
