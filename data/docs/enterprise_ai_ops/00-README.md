---
domain: overview
subdomain: dataset_guide
source_type: internal_manual
audience: ai_engineer,customer_success,ops_manager
security_level: internal
tenant_id: corp-default
version: v1
status: active
---

# 企业智能客服与工单自动化知识库说明

本目录是一套用于企业级 RAG、Agent、流程自动化项目的模拟企业知识库。它不是单纯的客服 FAQ，而是覆盖内部制度、产品知识、客户支持、工单流转、AI 应用治理、安全合规和事故复盘的综合文档池。

## 业务背景

假设公司提供一套面向 B 端客户的智能知识库和工单平台，客户包括教育、制造、零售、SaaS 企业和内部共享服务中心。平台支持以下能力：

- 企业知识库问答。
- 客户问题自助解答。
- 客服辅助回复。
- 工单自动分类、优先级识别和派单。
- 高风险问题转人工。
- AI 应用上线审批和审计。
- 数据权限隔离和敏感信息处理。
- 运营质量分析与改进。

## RAG 使用方式

这套文档适合用来验证以下 RAG 能力：

- 多领域路由：产品、客服、工单、权限、安全、合规、运营。
- metadata 过滤：按部门、角色、密级、客户等级、流程阶段过滤。
- 混合检索：制度名、接口名、错误码适合 BM25；口语问题适合向量检索。
- Reranker：从多个相似制度中精排最相关片段。
- Query Rewrite：把口语问题改写成标准检索句。
- 引用校验：回答必须能对应到具体制度、流程或 FAQ。
- 拒答策略：权限不足、知识库无依据、高风险自动化场景必须拒答或转人工。

## Agent 使用方式

后续可以把 RAG 扩展成 LangGraph 工作流：

1. 识别用户意图。
2. 路由到产品、客服、工单、合规或安全领域。
3. 检索相关制度和案例。
4. 判断是否需要追问用户。
5. 生成客服建议或工单处理建议。
6. 高风险时创建人工复核任务。
7. 记录审计日志。

## 文档约定

每篇文档顶部使用 front matter 描述 metadata。重要字段包括：

- `domain`：一级领域。
- `subdomain`：二级主题。
- `source_type`：文档类型。
- `audience`：适用角色。
- `security_level`：公开、内部、受限、高敏。
- `workflow`：相关业务流程。
- `owner`：责任部门。
- `status`：是否生效。

这些字段可用于后续实现权限过滤、领域路由和评估集分组。

