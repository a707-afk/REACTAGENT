---
domain: product
subdomain: api_integration
source_type: technical_manual
audience: ai_engineer,backend_engineer,customer_engineer
security_level: internal
tenant_id: corp-default
owner: platform_engineering
workflow: integration
version: v1.4
status: active
---

# API 接入与系统集成说明

## 接入目标

平台 API 用于将知识库问答、工单创建、工单查询、客户上下文查询和审计日志能力接入客户现有系统。常见集成对象包括 CRM、客服系统、企业 IM、门户网站、内部审批系统和 BI 平台。

## 基础接口

### 知识库检索接口

检索接口用于返回相关知识片段，不直接生成最终回答。适合调试召回质量、构建自定义问答链路或做引用校验。

请求字段：

- `query`：用户问题。
- `top_k`：返回片段数量。
- `domain`：可选，指定领域。
- `filters`：可选，按权限、客户、部门或文档状态过滤。

### 问答接口

问答接口会执行检索、重排、门控、生成和引用返回。无有效依据时返回拒答。

响应字段：

- `answer`：生成回答。
- `citations`：引用片段。
- `refused`：是否拒答。
- `error_code`：拒答或异常原因。
- `trace_id`：链路追踪 ID。

### 工单创建接口

工单创建接口用于将用户问题转为待处理工单。高风险场景下，AI 只能生成建议字段，最终创建动作需要业务系统确认。

请求字段：

- `title`
- `description`
- `customer_id`
- `category`
- `priority`
- `attachments`
- `source_channel`

## 鉴权要求

所有 API 调用必须携带访问凭证。生产环境不得使用固定测试 Key。推荐方案：

- 内部系统使用服务账号。
- 外部客户使用 OAuth 或签名 Key。
- 高风险接口启用 IP 白名单。
- 敏感操作必须带操作人身份。

## 幂等性要求

创建工单、发送通知、变更状态等接口必须支持幂等。客户端应传入 `idempotency_key`，服务端在一定时间内保证同一 Key 不重复创建资源。

如果 Agent 调用工具失败后重试，缺少幂等机制会导致重复工单、重复通知或重复扣费。

## 错误处理

常见错误码：

- `AUTH_FAILED`：鉴权失败。
- `PERMISSION_DENIED`：权限不足。
- `NO_RETRIEVAL_EVIDENCE`：无有效检索依据。
- `RATE_LIMITED`：请求频率过高。
- `TOOL_TIMEOUT`：外部工具超时。
- `HUMAN_REVIEW_REQUIRED`：需要人工审核。

AI 应用应把错误码转为清晰提示，而不是让模型自行解释底层异常。

## 集成验收

客户系统接入完成后，必须通过以下验收：

1. 正常问答返回引用。
2. 无依据问题能够拒答。
3. 无权限问题不会泄露内容。
4. 工单创建接口具备幂等。
5. trace_id 能串联问答、检索、工具调用和审计日志。
6. 高风险问题不会自动执行不可逆操作。

