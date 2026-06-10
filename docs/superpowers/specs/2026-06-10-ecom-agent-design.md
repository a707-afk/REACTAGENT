# EcomAgent — 电商智能售后多Agent系统 设计方案

> **版本**: v1.0 | **日期**: 2026-06-10 | **状态**: 已确认
>
> 从 REACTAGENT（通用客服Agent）改造为面向电商售后场景的多Agent系统。

---

## 一、项目定位

### 1.1 核心判断

当前 REACTAGENT 的技术底子很好（LangGraph 10节点、混合检索+Rerank、句级幻觉检测、LLM熔断器、评估体系），但定位为"通用客服"导致面试时无法回答四个致命问题：

- "上线给谁用？" — 无真实场景
- "为什么不用Dify？" — 无差异化
- "产生什么价值？" — 无业务指标
- "为什么付钱？" — 无付费逻辑

改造为电商售后Agent后，以上四个问题均有明确回答。目标公司：上海中型电商/企业服务公司，目标薪资：25K-35K。

### 1.2 差异化策略（vs Dify）

| 能力 | Dify能做吗 | 我们的实现 |
|------|-----------|-----------|
| 知识库RAG | ✅ | ✅ 保留现有混合检索管道 |
| Agent工作流 | ✅ 基础编排 | ✅ Supervisor-Worker多Agent并行 |
| 句级引用溯源+幻觉剥离 | ❌ | ✅ citation_verify.py |
| LLM熔断器+降级 | ❌ | ✅ fault_tolerance.py |
| 情绪检测+分级路由 | ❌ | ✅ 内联Supervisor |
| 补偿金额动态推荐 | ❌ | ✅ 多工具调用+业务逻辑 |
| 与企业系统API深度集成 | ❌ | ✅ Mock API展示集成潜力 |

---

## 二、改造范围

### 2.1 保留不动

| 模块 | 说明 |
|------|------|
| LangGraph 10节点工作流 | policy → reason → tools → retrieve → gate → grader → rewrite → draft → hallucination → finalize |
| 混合检索管道 | Qdrant向量 + BM25 + Qwen3 Reranker |
| 句级幻觉检测 | citation_verify.py + hallucination节点 |
| LLM熔断器+降级 | fault_tolerance.py |
| 策略引擎+行为护栏 | policy/ + behavior_guard.py |
| 工单状态机 | services/ticket_sm.py |
| 评估体系 | tests/ + scripts/ 评测脚本 |
| 前端框架 | React 18 + TypeScript + Vite |
| Docker部署 | docker-compose.yml |
| CI/CD | GitHub Actions |

### 2.2 需要改造

| 模块 | 改动内容 | 预计工作量 |
|------|---------|-----------|
| 知识库 | 换为京东售后政策 + LLM构造FAQ | 2-3天 |
| Agent工具 | 6个工具重定义（+2新 +4改） | 2天 |
| Agent编排 | Supervisor意图路由 + 三Worker并行 | 3天 |
| 前端 | 增加订单面板、工单时间线 | 2天 |
| Mock数据层 | 订单/库存/物流 Mock API | 1天 |
| README+文档 | 重写为电商场景 | 1天 |

### 2.3 新增

| 模块 | 说明 |
|------|------|
| Supervisor意图路由 | 从 node_reason 改造，输出 intent + emotion + order_hint |
| 三Worker并行引擎 | LangGraph parallel node，政策/库存/物流同时执行 |
| 情绪检测 | 内联 Supervisor prompt，输出 angry/neutral |
| 补偿推荐引擎 | 根据订单金额动态推荐补偿金额 |
| 设备自动检测 | config里检测CUDA可用性，自动切换CPU/GPU/API |

---

## 三、架构设计

### 3.1 Intent Flow（意图路由）

```
用户输入 → Supervisor Agent（意图识别+情绪检测）
  ├── intent=exchange → 换货流程（三Worker并行）
  │     ├── Policy Worker  : policy_check(order_id, reason)
  │     ├── Inventory Worker : inventory_query(sku, size, color)
  │     └── Logistics Worker : create_pickup(order_id, address)
  │
  ├── intent=refund → 退款流程（串行）
  │     Policy Worker → 计算退款金额 → create_after_sale_ticket
  │
  ├── intent=complaint → 投诉流程（情绪分级）
  │     emotion=angry  → P0工单 + SLA倒计时 + 升级人工
  │     emotion=neutral → 标准回复 + 补偿推荐
  │
  └── intent=tracking → 物流查询（直通）
        order_lookup → track_shipment → 返回物流状态
```

### 3.2 Supervisor 输出结构

```python
{
    "intent": "exchange",       # exchange / refund / complaint / tracking
    "emotion": null,            # null / angry / neutral (仅complaint时有效)
    "order_hint": "T恤",        # 从用户输入提取的商品关键词
    "confidence": 0.92,
    "reason": "用户提到换L码"
}
```

---

## 四、Agent工具定义（共6个）

| # | 工具名 | 输入 | 来源 | 用于意图 |
|---|--------|------|------|---------|
| 1 | **order_lookup** | user_id, keyword, limit=3 | customer_lookup 改 | 全部 |
| 2 | **policy_check** | order_id, return_reason | escalate 改 | 换货/退款 |
| 3 | **inventory_query** | sku, size, color | 新增 | 换货 |
| 4 | **create_pickup** | order_id, address | 新增 | 换货 |
| 5 | **track_shipment** | order_id | 新增 | 物流查询 |
| 6 | **create_after_sale_ticket** | type, priority, order_id, detail | create_ticket 改 | 全部收尾 |

### 4.1 工具输入输出详情

**order_lookup**
```python
# 输入
{"user_id": "u001", "keyword": "T恤", "limit": 3}
# 输出
{
    "orders": [
        {"order_id": "ORD-001", "product": "XX品牌白色T恤 M码", "date": "2026-06-05", "amount": 129.00},
        {"order_id": "ORD-002", "product": "YY品牌黑色T恤 L码", "date": "2026-06-01", "amount": 89.00}
    ]
}
```

**policy_check**
```python
# 输入
{"order_id": "ORD-001", "return_reason": "尺码不合适"}
# 输出
{
    "eligible": true,
    "policy": "7天无理由退换",
    "refund_type": "full",       # full / partial / denied
    "reason": "购买3天，未拆封，符合全额退款条件",
    "deduction_rate": 0          # 0 / 0.10 / 0.15
}
```

**inventory_query**
```python
# 输入
{"sku": "TEE-WHITE", "size": "L", "color": "白色"}
# 输出
{
    "available": true,
    "stock": 23,
    "warehouse": "上海仓",
    "estimated_delivery": "1-2天"
}
```

**create_pickup**
```python
# 输入
{"order_id": "ORD-001", "address": "上海市XX区XX路XX号"}
# 输出
{
    "pickup_id": "PU20240610",
    "scheduled": "2026-06-11 9:00-18:00",
    "carrier": "顺丰"
}
```

**track_shipment**
```python
# 输入
{"order_id": "ORD-001"}
# 输出
{
    "status": "运输中",
    "carrier": "中通",
    "last_update": "2026-06-10 14:32 已到达上海转运中心",
    "estimated_delivery": "2026-06-11"
}
```

**create_after_sale_ticket**
```python
# 输入
{"type": "exchange", "priority": "p2_medium", "order_id": "ORD-001", "detail": "M码换L码"}
# 输出
{
    "ticket_id": "AS20240610-001",
    "status": "NEW",
    "sla_deadline": "2026-06-11T17:00:00Z"
}
```

---

## 五、Mock数据层设计

### 5.1 订单Mock（3条，覆盖三种policy状态）

| order_id | 商品 | 购买日期 | 状态 | 金额 | 对应 policy_check 结果 |
|----------|------|---------|------|------|---------------------|
| ORD-001 | XX品牌白色T恤 M码 | 2026-06-05 | 未拆封 | 129元 | full — 符合7天无理由，全额退款 |
| ORD-002 | YY品牌黑色T恤 L码 | 2026-05-25 | 已拆封-影响二次销售 | 89元 | partial — 超过7天但30天内，部分退款(扣10%) |
| ORD-003 | ZZ品牌卫衣 XL码 | 2026-04-01 | 已穿洗过 | 299元 | denied — 超过30天，不可退换 |

### 5.2 库存Mock

| SKU | 尺码 | 库存 | 仓库 |
|-----|------|------|------|
| TEE-WHITE | M | 0 | 上海仓 |
| TEE-WHITE | L | 23 | 上海仓 |
| TEE-BLACK | L | 5 | 北京仓 |

### 5.3 物流Mock

| order_id | 状态 | 预计送达 |
|----------|------|---------|
| ORD-001 | 已签收 | — |
| ORD-004 | 运输中 | 2026-06-11 |
| ORD-005 | 已揽收 | 2026-06-12 |

---

## 六、知识库内容

### 6.1 来源（只爬京东一个平台）

- **退换货政策**：京东开放平台售后条款（爬取日期 2026-06）
- **售后FAQ**：基于真实场景由LLM构造，约200-300条
- **物流政策**：京东物流时效和赔付规则

### 6.2 爬取策略

- 单一平台（京东）避免政策矛盾
- 只爬取公开页面，不逆向API
- README诚实标注来源和日期

### 6.3 索引管道

复用现有 chunking.py + reindex_cs.py，参数调整：
- chunk_size: 512 tokens（客服FAQ保持）
- chunk_overlap: 64 tokens
- 领域路由改为电商场景分类：return_policy / shipping / payment / complaint

---

## 七、设备策略

### 7.1 三层架构

| 层级 | 设备 | 用途 |
|------|------|------|
| Tier 1 | CPU / Intel Arc | 日常开发、调试、小规模测试、API模式调LLM |
| Tier 2 | RTX 5070 eGPU | 本地Embedding+Reranker推理、构建索引、检索评测 |
| Tier 3 | V100 远程服务器 | 大规模压测、全量评测（收尾阶段可选） |

### 7.2 代码同步

- GitHub 为单一代码源
- 本机开发 → git push → V100 git pull
- `.env` 分环境配置：`.env.local` / `.env.v100`

### 7.3 设备自动检测

```python
# config.py 新增
if torch.cuda.is_available():
    INFERENCE_BACKEND = "gpu"
    EMBEDDING_DEVICE = "cuda"
else:
    INFERENCE_BACKEND = "api"
    EMBEDDING_DEVICE = "cpu"
```

---

## 八、Git分支策略

- `main` — 当前稳定版本（REACTAGENT v1.x）
- `feature/ecom-agent` — 电商改造开发分支
- 改造完成后合并回 main，打 tag `v2.0-ecom`
- GitHub 历史记录保留，面试时展示从客服到电商的演进

---

## 九、面试准备要点

### 9.1 四个核心问题的回答

**Q: 上线给谁用？**
> 面向电商售后客服团队。每天处理大量退换货/投诉请求，重复性高。我的Agent自动完成订单确认、政策核查、库存查询、取件单生成，把售后流程从5-8步人工操作压缩到3步确认。

**Q: 为什么不用Dify？**
> Dify做不了三件事：第一，Supervisor-Worker多Agent并行协作——三个Worker同时跑政策/库存/物流，最慢的决定总响应时间；第二，句级引用溯源+幻觉剥离——电商售后政策回答必须可靠，Dify没有这个能力；第三，深度业务逻辑——情绪分级、补偿金额动态推荐、工单SLA倒计时。

**Q: 产生什么价值？**
> 离线评估：Recall@5=0.87，幻觉无引用率<3%。性能压测：Locust 1000并发下P50延迟<3秒。换货场景用户交互从5-8步降到2-3步确认。

**Q: 为什么付钱？**
> 电商售后客服人力成本高、流动性大。一套年费8-15万的AI售后系统，如果替代2-3个初级客服的人力（月薪6-8K/人），6个月回本。

### 9.2 可以深讲的技术点

1. 三Worker并行的LangGraph实现（最慢Worker决定总响应时间）
2. 句级引用溯源的无引用率控制
3. LLM熔断器的设计（连续失败3次→降级→恢复）
4. 情绪检测内联Supervisor的路由设计
5. 混合检索在电商政策场景的调优

---

## 十、完整对话示例（换货场景）

```
用户：买了件M码T恤，太小了想换L码

Agent：[调用 order_lookup(user_id="u001", keyword="T恤")]
      找到您2天前的订单——XX品牌白色T恤 M码 ¥129，
      帮您换L码是吗？

用户：对

Agent：[三Worker并行]
      ✓ Policy Worker  : 符合7天无理由换货，可全额换
      ✓ Inventory Worker : L码白色有货，上海仓库存23件
      ✓ Logistics Worker : 已生成上门取件申请
      
      取件地址是：上海市XX区XX路XX号，明天 9:00-18:00
      地址没问题的话我帮您提交？

用户：可以

Agent：换货申请已提交，工单号 #AS20240610-001
      取件后3-5天收到新衣服。

全程用户只回答了"对"和"可以"——不是表单填写，是Agent应该有的体验。
```

---

## 十一、改造清单总览

| 阶段 | 内容 | 预估时间 |
|------|------|---------|
| 0 | 现有代码跑通验证 | 0.5天 |
| 1 | 创建feature/ecom-agent分支 | 0.1天 |
| 2 | 知识库替换（爬取+构造+索引） | 2-3天 |
| 3 | Agent工具重定义（6个工具） | 2天 |
| 4 | Supervisor意图路由+Worker编排 | 3天 |
| 5 | Mock数据层 | 1天 |
| 6 | 前端改造（订单面板+时间线） | 2天 |
| 7 | 设备自动检测 | 0.5天 |
| 8 | Locust压测+性能报告 | 1天 |
| 9 | README+演示视频+博客 | 2天 |
| **总计** | | **14-16天** |

---

> **下一步**: 生成详细的实现计划（writing-plans），分解为可执行的 subagent 任务。
