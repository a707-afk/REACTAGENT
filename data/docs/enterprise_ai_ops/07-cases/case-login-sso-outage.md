---
domain: case
subdomain: sso_outage
source_type: incident_narrative
audience: support,sre,customer_success
security_level: internal
tenant_id: corp-default
owner: support_operations
workflow: incident_response
version: v2.0
status: active
---

# 案例：企业客户 SSO 登录异常（IdP 证书过期）

> 一线**收集信息清单**见 `03-customer-service/faq-account-login.md`（SAML invalid assertion 专节）；本文为 2025 年一次 IdP 证书过期事件复盘。

## 背景

企业版客户周一上午反馈约 300 人 SSO 失败，错误 **SAML assertion invalid**；密码登录已禁用。

## 经过

1. 客服按 FAQ 收集域名、截图、时间、影响范围。
2. 工单分类「SSO 登录失败」，优先级 **P1**（定级规则见工单分类文档）。
3. 集成支持确认：**客户 IdP 证书前夜过期**，平台服务正常。
4. 客户管理员上传新证书后抽样恢复登录。

## 根因

客户侧证书生命周期管理缺失，非平台 outage。

## 改进

- FAQ 补充 assertion invalid 与证书过期关联说明。
- 路由规则：错误含 SAML/IdP/certificate 时优先集成支持。

## 相关文档

- 客服收集清单：`03-customer-service/faq-account-login.md`
- 事故响应流程：`04-ticket-workflow/incident-response-workflow.md`
