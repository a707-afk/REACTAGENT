---
domain: ticket_workflow
subdomain: classification_priority
source_type: workflow
audience: support,ops_manager
security_level: internal
tenant_id: corp-default
owner: support_operations
workflow: ticket_triage
version: v2.0
status: active
---

# 工单分类与优先级规则

> VIP 身份**不自动**把普通咨询升为 P0。P0 仅用于明确的生产中断或安全事件。SLA 数值见《SLA 与升级规则》。

## 优先级判定原则

| 级别 | 典型场景 |
|---|---|
| P0 | 全租户不可用、数据泄露疑似、核心 API 全失败 |
| P1 | 大比例用户 SSO/登录失败、关键功能不可用 |
| P2 | 单功能异常、VIP 咨询但无生产中断声明 |
| P3 | 一般咨询、配置疑问 |
| P4 | 需求建议、文档反馈 |

## VIP 客户普通咨询

VIP 标签用于**响应资源倾斜与升级关注**，**不能**仅因 VIP 将「产品使用咨询」直接标为 P0。若 VIP 声明生产中断或引用 SLA 违约，按实际影响重新定级并引用《SLA 与升级规则》。

## 分类维度

- 产品功能 / 账号权限 / 计费 / 集成 SSO / 安全 / 数据 / AI 质量。

## 与 SLA 的关系

定级后 SLA 计时规则以 `sla-and-escalation.md` 为准；案例库中的 VIP 超时事件仅作复盘参考。
