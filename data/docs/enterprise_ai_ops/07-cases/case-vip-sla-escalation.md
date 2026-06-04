---
domain: case
subdomain: sla_escalation
source_type: incident_narrative
audience: support,ops_manager,customer_success
security_level: internal
tenant_id: corp-default
owner: support_operations
workflow: sla_management
version: v2.0
status: active
---

# 案例：VIP 客户工单 SLA 即将超时

> **案例域说明**：历史叙事与根因；**P0/P2 首次响应分钟数、升级表**见《SLA 与升级规则》，本文不重复 SLA 表格。

## 背景

VIP 客户反馈「知识库导入后搜索不到新文档」。工单初判 **P2**（非 P0），首次响应已完成。

## 时间线

- T+0h：客户建单，客服完成首次响应。
- T+20h：内部处理停滞，SLA 监控显示剩余处理时间 **不足 20%**。
- 系统向客服负责人与 AI 平台值班发送**超时预警**（规则见 SLA 文档「自动提醒节点」）。
- 工程师发现导入文档缺少 `status: active`，权限过滤排除该文档。
- 修正 metadata 并触发 reindex 后，客户可检索。

## 根因

非 embedding 故障，而是 **metadata 不完整 + 索引未包含 active 文档**。

## 改进项

1. 导入流程增加 metadata 校验 gate。
2. 客服收集问题时应问：文档名、上传时间、可见范围、用户角色。
3. VIP 标签未改变本案 P2 定级；若客户声明生产中断，应按《工单分类与优先级》重新定级。

## 相关文档

- SLA 权威数值：`04-ticket-workflow/sla-and-escalation.md`
- 分类规则：`04-ticket-workflow/ticket-classification-priority.md`
