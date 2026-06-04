# 企业知识库升级路线

本项目已从学习文档 RAG 扩展为“企业内部知识 + 客服 + 工单/流程自动化”的业务知识库。当前新增文档位于 `data/docs/enterprise_ai_ops/`，后续可以在此基础上继续做多领域 RAG、权限过滤、LangGraph 工单助手和微调实验。

## 当前文档池

新增文档覆盖：

- 内部制度：AI 平台使用、知识库治理、数据分级与访问控制。
- 产品资料：平台说明、套餐限制、API 接入。
- 客服 FAQ：账号登录、账单发票、回答质量、数据删除与导出。
- 工单流程：分类优先级、SLA、退款审核、生产事故响应。
- AI 治理：上线评审、RAG 评估、Agent 边界和人工审核。
- 安全手册：Prompt Injection、敏感信息脱敏、审计日志。
- 案例复盘：SSO 异常、错误引用、退款人工审核、提示词注入、VIP SLA。
- Agent 设计：LangGraph 工单助手架构。

## 为什么这样设计

这套数据不是简单 FAQ，而是为了支持企业级 AI 应用项目的完整能力：

```text
用户问题
  ↓
领域路由
  ↓
权限过滤
  ↓
混合检索 + Rerank
  ↓
引用校验
  ↓
高风险问题转人工
  ↓
工单/流程自动化
```

## 文档 metadata

新增 Markdown 顶部使用 front matter，例如：

```yaml
---
domain: ticket_workflow
subdomain: refund_review
source_type: workflow
audience: support,finance,customer_success
security_level: restricted
owner: finance_operations
workflow: refund_review
version: v1.0
status: active
---
```

`app/chunking.py` 已支持解析这些字段，索引后的 chunk 会带上 metadata。后续可以基于这些字段做：

- domain 路由。
- security_level 权限过滤。
- source_type 分组评估。
- workflow 自动化编排。
- owner 责任归属。

## 评估集

企业场景评估集位于 `data/eval_enterprise_questions.jsonl`，当前包含 30 条问题，覆盖：

- 普通事实问答。
- 高风险转人工。
- 权限与数据删除。
- Prompt Injection。
- 退款审批。
- SLA。
- Agent 边界。
- RAG bad case。

后续建议把现有 `scripts/run_eval_retrieve.py` 扩展为可指定评估集文件，并增加以下指标：

- `expected_domain` 命中率。
- `expected_doc_contains` 命中率。
- 高风险问题拒答/转人工准确率。
- 权限问题拒答准确率。
- 引用有效率。

## 下一步建议

优先级建议：

1. 运行 `scripts/reindex.py`，确认新增文档可被索引。
2. 用 `/retrieve` 手动测试 10 条企业评估问题。
3. 改造评估脚本，支持 `eval_enterprise_questions.jsonl`。
4. 加领域路由器：规则 + embedding router + LLM fallback。
5. 加 metadata filter：按 `domain`、`security_level`、`status` 过滤。
6. 迁移向量库到 Qdrant。
7. 基于 `08-agent-design` 做 LangGraph 工单助手。

## 面试表达

可以这样讲：

“我最初做的是一个学习文档 RAG demo，后来把它升级成企业智能客服和工单自动化知识库。它不是只回答 FAQ，而是围绕真实企业场景设计了制度、产品、客服、工单、安全、AI 治理和案例文档，并为每篇文档加 metadata。这样后续可以自然扩展出领域路由、权限过滤、RAG 评估、LangGraph 工单流程和高风险人工审核。”

