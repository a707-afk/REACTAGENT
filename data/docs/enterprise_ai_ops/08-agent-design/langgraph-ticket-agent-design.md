---
domain: agent_design
subdomain: langgraph_ticket_agent
source_type: architecture
audience: ai_engineer,product_manager,support
security_level: internal
tenant_id: corp-default
owner: ai_platform_team
workflow: agent_design
version: v1.0
status: active
---

# LangGraph 工单助手设计方案

## 设计目标

工单助手用于辅助客服处理复杂问题。它不是完全自主的多 Agent 系统，而是一个由 LangGraph 管理状态和流程的可控工作流。LLM 负责理解、总结、分类和生成建议，流程状态、权限、工具调用和人工审核由代码控制。

## 状态字段

建议 State 包含：

- `ticket_id`
- `user_query`
- `customer_id`
- `customer_tier`
- `intent`
- `risk_level`
- `routed_domains`
- `retrieved_chunks`
- `draft_reply`
- `required_fields`
- `human_review_required`
- `final_action`
- `audit_trace`

## 节点设计

工作流节点：

1. `classify_intent`：识别账号、账单、产品、工单、安全或退款。
2. `detect_risk`：识别退款、数据删除、安全事件、生产事故等高风险。
3. `route_kb`：根据领域检索知识库。
4. `check_sufficiency`：判断证据是否足够。
5. `ask_clarification`：缺少关键信息时追问用户。
6. `draft_reply`：生成客服回复草稿。
7. `verify_citation`：检查回答是否有引用依据。
8. `human_review`：高风险或低置信场景中断等待人工。
9. `create_ticket_note`：写入工单备注。

## 条件边

典型条件：

- 检索无依据 → 拒答或追问。
- 信息不完整 → 追问用户。
- 风险等级高 → 人工审核。
- 引用校验失败 → 重新生成或转人工。
- 工具失败 → 重试或降级。

## 工具列表

只读工具：

- `search_kb`
- `get_ticket`
- `get_customer_profile`

低风险写工具：

- `create_ticket_note`
- `create_draft_reply`
- `add_internal_tag`

高风险工具：

- `approve_refund`
- `delete_customer_data`
- `change_user_role`
- `close_security_incident`

高风险工具默认不开放给 Agent 直接调用。

## 面试表达

这个设计体现了企业 Agent 的核心思想：LLM 不是流程主人，LangGraph 才是流程主人。LLM 负责不确定的语言理解和建议生成，确定性的权限、状态、审批和工具执行由工程系统控制。

