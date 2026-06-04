---
domain: internal_policy
subdomain: knowledge_base_governance
source_type: policy
audience: knowledge_owner,ai_engineer,ops_manager,support
security_level: internal
tenant_id: corp-default
owner: knowledge_operations_team
workflow: kb_lifecycle
version: v1.0
status: active
---

# 企业知识库治理规范

## 目标

企业知识库用于支撑内部问答、客户服务、工单自动化和运营分析。知识库质量直接影响 RAG 系统的回答质量，因此必须建立从文档创建、审核、发布、更新、下线到评估的完整治理流程。

## 角色分工

知识库治理涉及以下角色：

- 知识负责人：对某一领域文档的准确性负责。
- 内容编辑：负责整理文档、FAQ、案例和操作步骤。
- 审核人：负责确认制度、产品、合规或技术内容是否可发布。
- AI 平台管理员：负责索引、向量库、权限和评估集维护。
- 客服运营：负责收集用户问题、bad case 和高频缺口。

## 文档分类

知识库文档分为以下类型：

- 制度类：内部政策、流程、管理要求。
- 产品类：功能说明、计费规则、接口文档、限制条件。
- 客服类：FAQ、话术、处理边界、升级规则。
- 工单类：分类标准、SLA、优先级、派单规则。
- 安全类：敏感信息、权限、攻击防护、事故响应。
- 案例类：真实或模拟处理案例、复盘、经验总结。

## 发布流程

新文档发布必须经过以下步骤：

1. 内容编辑提交初稿。
2. 知识负责人检查事实准确性。
3. 涉及客户承诺、价格、合同或合规的内容必须由对应部门复核。
4. AI 平台管理员补充 metadata。
5. 文档进入测试知识库。
6. 通过至少 5 条测试问题验证可检索性。
7. 发布到正式知识库。

## metadata 要求

每篇文档必须包含以下 metadata：

- `domain`：一级领域。
- `subdomain`：二级领域。
- `source_type`：制度、FAQ、案例、流程或手册。
- `audience`：适用角色。
- `security_level`：公开、内部、受限或高敏。
- `owner`：文档负责人。
- `version`：版本号。
- `status`：active、draft、deprecated。

缺少关键 metadata 的文档不得进入正式索引。

## 更新和下线

制度、价格、SLA、接口限制、权限边界和合规要求发生变化时，知识负责人必须在 2 个工作日内更新文档。过期内容应标记为 `deprecated`，不得直接删除。删除会影响历史引用和审计，应通过状态字段控制检索可见性。

## 质量评估

知识库每周至少运行一次评估集，指标包括：

- Top-1 命中率。
- Top-5 命中率。
- 引用有效率。
- 拒答准确率。
- 高风险问题转人工准确率。
- 客服采纳率。

当某一领域连续两周命中率低于 80%，应由知识负责人和 AI 平台管理员共同排查。

