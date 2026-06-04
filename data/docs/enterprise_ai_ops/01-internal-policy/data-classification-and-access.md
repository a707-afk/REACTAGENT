---
domain: internal_policy
subdomain: data_access_control
source_type: policy
audience: employee,security,ai_engineer
security_level: internal
tenant_id: corp-default
owner: security_team
workflow: access_control
version: v1.0
status: active
---

# 数据分级与访问控制规范

## 数据分级

公司数据按敏感程度分为四级：

| 等级 | 名称 | 示例 | 默认访问范围 |
|---|---|---|---|
| L1 | 公开 | 官网资料、公开产品介绍 | 全员可见 |
| L2 | 内部 | 内部流程、通用制度、培训材料 | 公司员工 |
| L3 | 受限 | 客户合同摘要、故障日志、价格策略 | 授权团队 |
| L4 | 高敏 | 密钥、个人敏感信息、财务明细、安全漏洞细节 | 特定审批授权 |

AI 知识库默认只允许索引 L1、L2 和经过脱敏处理的 L3 内容。L4 内容不得进入普通知识库。

## 访问控制原则

RAG 检索必须在召回前执行权限过滤。不得先召回所有 chunk 再让 LLM 判断是否可见。权限过滤至少应考虑：

- 用户所属部门。
- 用户岗位角色。
- 客户归属关系。
- 数据密级。
- 文档状态。
- 是否涉及个人信息或客户商业秘密。

如果用户没有权限，系统应返回权限不足或转人工，而不是生成模糊回答。

## metadata 过滤要求

每个 chunk 必须继承文档 metadata。关键字段包括：

- `security_level`
- `department`
- `customer_tier`
- `owner`
- `status`
- `effective_date`

向量库检索时应带上 metadata filter。例如客服人员查询客户问题时，只能检索公开产品资料、客服 FAQ 和自己团队可见的处理流程，不能检索财务策略或安全漏洞细节。

## 敏感信息处理

进入知识库前必须删除或脱敏以下内容：

- 身份证号、银行卡号、手机号、邮箱。
- API Key、Token、Cookie、私钥。
- 客户合同原文。
- 未公开安全漏洞利用细节。
- 未经授权的客户数据。
- 员工薪酬、绩效和处罚记录。

## 异常处理

当用户问题疑似越权时，系统应执行以下动作：

1. 不返回敏感内容。
2. 记录 trace_id、用户、问题、命中的领域和拒答原因。
3. 提示用户通过正式权限申请流程处理。
4. 对连续异常查询触发安全告警。

## 面试表达要点

企业级 RAG 不是简单把文档放进向量库，而是必须把权限和检索绑定。真正安全的方案是“检索前过滤 + 检索后引用校验 + 访问日志审计”，不能依赖 LLM 自觉保密。

