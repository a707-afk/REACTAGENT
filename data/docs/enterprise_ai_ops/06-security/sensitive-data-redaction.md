---
domain: security
subdomain: data_redaction
source_type: runbook
audience: support,ai_engineer,security
security_level: internal
tenant_id: corp-default
owner: security_team
workflow: data_sanitization
version: v1.0
status: active
---

# 敏感信息脱敏规范

## 脱敏目标

在将客户材料、日志、工单、聊天记录或合同摘要用于 AI 分析前，必须删除或替换敏感信息。脱敏目标是减少泄露风险，同时保留足够上下文用于问题定位。

## 必须脱敏的内容

以下内容必须脱敏：

- 身份证号。
- 银行卡号。
- 手机号。
- 邮箱。
- 客户密钥。
- API Token。
- Cookie。
- 私钥。
- 数据库连接串。
- 生产服务器 IP。
- 合同原文。
- 员工薪酬和绩效。

## 脱敏规则

推荐规则：

- 手机号：`138****1234`
- 邮箱：`u***@example.com`
- 身份证号：只保留最后四位。
- 银行卡号：只保留最后四位。
- API Key：完全替换为 `[REDACTED_API_KEY]`
- Token：完全替换为 `[REDACTED_TOKEN]`
- 客户名称：替换为客户编号。

密钥、Token 和私钥不得保留任何真实片段。

## RAG 入库要求

进入知识库前必须完成脱敏。不得把脱敏责任交给生成模型。脱敏后文档仍应保留必要 metadata，例如客户行业、问题类型、影响范围和处理结论。

## 日志要求

系统日志不得记录完整用户输入中的敏感字段。日志应记录：

- trace_id。
- 用户 ID。
- 文档 ID。
- 命中规则。
- 是否脱敏成功。
- 错误码。

不应记录原始密钥、完整身份证号和完整合同。

## 异常处理

如果发现敏感信息已经进入知识库，应立即：

1. 暂停相关文档检索。
2. 删除或重建索引。
3. 检查缓存和 BM25 语料。
4. 通知安全团队。
5. 复盘导入流程。

仅删除源 Markdown 不足以完成清理，因为向量库、BM25 文件和缓存中可能仍有残留。

