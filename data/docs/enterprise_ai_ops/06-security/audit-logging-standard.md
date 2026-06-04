---
domain: security
subdomain: audit_logging
source_type: standard
audience: ai_engineer,security,ops_manager,support
security_level: internal
tenant_id: corp-default
owner: security_team
workflow: observability
version: v1.0
status: active
---

# AI 应用审计日志规范

## 目标

AI 应用的审计日志用于回答三个问题：谁发起了请求、系统基于什么证据做了什么、最终是否执行了业务动作。审计日志不是普通调试日志，必须可追踪、可检索、可留存。

## 必须记录的字段

每次请求应记录：

- trace_id。
- user_id。
- tenant_id。
- request_time。
- original_query。
- rewritten_query。
- routed_domain。
- retrieval_filters。
- top_k_documents。
- rerank_scores。
- gate_result。
- model_name。
- token_usage。
- tool_calls。
- final_answer_hash。
- refused。
- error_code。

高风险流程还必须记录人工审核人和审核结果。

## 不应记录的内容

日志不应记录：

- 完整密钥。
- 完整 Token。
- 完整身份证号。
- 完整银行卡号。
- 未脱敏合同正文。
- 客户高敏数据原文。

必要时可以记录哈希、摘要或脱敏片段。

## OTel 与业务日志

OpenTelemetry 适合记录 trace、span、耗时、模型调用、检索调用和工具调用。业务审计日志适合记录用户、权限、审批、拒答、风险等级和最终动作。两者应通过 trace_id 关联。

## 留存要求

普通问答日志建议保留 180 天。涉及合同、退款、数据删除、安全事件和生产变更的审计日志，至少保留 3 年，具体以公司合规要求为准。

## 查询场景

审计日志应支持以下查询：

- 某个用户最近 30 天的 AI 请求。
- 某个客户的数据导出请求。
- 某个 trace_id 的完整链路。
- 某次高风险工具调用的审批记录。
- 某个文档被引用的次数。
- 某类拒答的趋势。

## 面试表达要点

OTel 能告诉我们系统发生了什么，但不能替代权限和工作流控制。企业级 AI 系统需要“可观测 + 可控制 + 可审计”三件事同时存在。

