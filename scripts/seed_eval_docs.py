"""Generate seed FAQ, table, and policy documents for the RAG eval knowledge base.

Output: data/docs_cn/faq/, data/docs_cn/tables/, data/docs_cn/policy/
"""
from pathlib import Path

BASE = Path("data/docs_cn")
for d in ["faq", "tables", "policy"]:
    (BASE / d).mkdir(parents=True, exist_ok=True)


def write(path, content):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")


# ── FAQ Documents (30) ────────────────────────────────────────────
faq_docs = {
    "doc_faq_001.md": """---
domain: shipping
tenant_id: t_demo
status: published
---
# 退货申请指南

## 如何申请退货

退货需在收货后7天内提出申请。请按以下步骤操作：

1. 登录账号，进入"我的订单"
2. 找到需要退货的订单，点击"申请退货"
3. 选择退货原因并上传相关凭证
4. 提交后等待商家审核

需保持商品完好，不影响二次销售。退货时需提供订单号。

## 不支持退货的情况

- 已拆封的个人护理商品
- 定制类商品
- 生鲜食品
""",
    "doc_faq_002.md": """---
domain: shipping
tenant_id: t_demo
status: published
---
# 退货时效与退款周期

## 退款到账时间

退款到账时间为1-7个工作日，不同支付方式到账时间不同：
- 微信支付：1-3个工作日
- 支付宝：1-3个工作日
- 银行卡：3-7个工作日

## 注意事项

退款金额将原路退回至支付账户。
""",
    "doc_faq_003.md": """---
domain: shipping
tenant_id: t_demo
status: published
---
# 商品损坏处理

## 收到破损商品怎么办

收到破损商品需在24小时内联系客服。需提供：
- 开箱视频或照片
- 订单号
- 损坏部位特写

## 联系方式

可通过以下方式联系客服：
- 客服热线：400-xxx-xxxx
- 在线客服：App内消息
""",
    "doc_faq_004.md": """---
domain: shipping
tenant_id: t_demo
status: published
---
# 物流查询指南

## 查询物流状态

在订单详情页查询物流，输入运单号即可追踪。支持以下快递公司：
- 顺丰速运
- 圆通快递
- 中通快递
- 韵达快递
""",
    "doc_faq_005.md": """---
domain: shipping
tenant_id: t_demo
status: published
---
# 发货时效说明

## 发货时间

一般下单后48小时内发货。大促期间可能延迟至72小时。特殊商品如定制类可能需要更长时间。

预售商品会在商品页面标注预计发货时间。
""",
    "doc_faq_006.md": """---
domain: payment
tenant_id: t_demo
status: published
---
# 支付方式说明

## 支持的支付方式

- 微信支付
- 支付宝
- 银行卡（借记卡和信用卡）
- 部分商品支持货到付款

手续费说明：微信支付和支付宝收取0.1%手续费，银行卡收取0.3%手续费。
""",
    "doc_faq_007.md": """---
domain: payment
tenant_id: t_demo
status: published
---
# 优惠券使用规则

## 如何使用优惠券

在结算页面选择可用优惠券。注意：
- 优惠券有使用门槛（如满100减10）
- 优惠券有有效期，过期自动失效
- 部分优惠券不可与其他优惠叠加
""",
    "doc_faq_008.md": """---
domain: shipping
tenant_id: t_demo
status: published
---
# 地址修改指南

## 如何修改收货地址

未发货订单可在订单详情页中修改收货地址。已发货订单需联系客服协助修改。

## 注意事项

修改地址可能导致配送延迟1-2天。
""",
    "doc_faq_009.md": """---
domain: account
tenant_id: t_demo
status: published
---
# 会员权益体系

## 各级会员权益

- 银卡会员享9.5折
- 金卡会员享9折和专属客服
- 钻石会员享8.5折和优先发货

积分获取：每消费1元获得1积分，100积分=1元。
""",
    "doc_faq_010.md": """---
domain: shipping
tenant_id: t_demo
status: published
---
# 订单取消与退款

## 取消订单后退款

订单取消后退款1-3个工作日到账。需要注意：
- 未发货订单立即退款
- 已发货订单需先退回商品再退款
""",
}

for name, content in faq_docs.items():
    write(BASE / "faq" / name, content)


# ── Table Documents (20) ──────────────────────────────────────────
table_docs = {
    "doc_tbl_001.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 各类商品退货政策对比

| 商品类别 | 退货期限 | 条件 | 备注 |
| --- | --- | --- | --- |
| 服装类 | 7天 | 未剪标、未洗涤 | 支持无理由退货 |
| 电子产品 | 7天 | 未激活、包装完整 | 需检测确认 |
| 食品类 | 不支持 | N/A | 不支持无理由退货 |
| 个人护理 | 不支持 | 未拆封可退 | 已拆封不支持 |
""",
    "doc_tbl_002.md": """---
domain: account
tenant_id: t_demo
status: published
---
# 会员折扣表

| 等级 | 折扣 | 积分系数 | 升级条件 |
| --- | --- | --- | --- |
| 普通 | 无 | 1x | 注册即享 |
| 银卡 | 9.5折 | 1.2x | 年消费5000元 |
| 金卡 | 9折 | 1.5x | 年消费20000元 |
| 钻石 | 8.5折 | 2x | 年消费50000元 |
""",
    "doc_tbl_003.md": """---
domain: shipping
tenant_id: t_demo
status: published
---
# 物流时效对比表

| 快递公司 | 华东地区 | 华北地区 | 华南地区 | 西部偏远 |
| --- | --- | --- | --- | --- |
| 顺丰 | 1天 | 1-2天 | 1-2天 | 2-3天 |
| 圆通 | 2-3天 | 3-4天 | 2-3天 | 5-7天 |
| 中通 | 2-3天 | 3-4天 | 2-4天 | 5-8天 |
| 韵达 | 3-4天 | 4-5天 | 3-5天 | 6-10天 |
""",
    "doc_tbl_004.md": """---
domain: payment
tenant_id: t_demo
status: published
---
# 支付渠道手续费

| 支付方式 | 手续费 | 到账时间 | 限额 |
| --- | --- | --- | --- |
| 微信支付 | 0.1% | 实时 | 50000/笔 |
| 支付宝 | 0.1% | 实时 | 50000/笔 |
| 银行卡借记卡 | 0.3% | T+1 | 20000/笔 |
| 银行卡信用卡 | 0.5% | T+1 | 20000/笔 |
""",
    "doc_tbl_005.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 各品类退货率统计

| 品类 | 退货率 | 主要退货原因 |
| --- | --- | --- |
| 服装类 | 15% | 尺码不合适 |
| 电子类 | 3% | 产品质量问题 |
| 食品类 | 0.5% | 包装破损 |
| 家居类 | 8% | 与图片不符 |
""",
    "doc_tbl_006.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 区域销售额对比 (万元)

| 区域 | Q1销售额 | Q2销售额 | 增长率 |
| --- | --- | --- | --- |
| 华东区 | 500 | 620 | +24% |
| 华南区 | 380 | 410 | +7.9% |
| 华北区 | 280 | 310 | +10.7% |
| 西南区 | 150 | 170 | +13.3% |
""",
    "doc_tbl_007.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 客服团队服务指标

| 团队 | 满意度 | 平均响应时间 | 解决率 |
| --- | --- | --- | --- |
| A团队 | 98% | 28秒 | 95% |
| B团队 | 96% | 32秒 | 93% |
| C团队 | 94% | 35秒 | 90% |
""",
    "doc_tbl_008.md": """---
domain: shipping
tenant_id: t_demo
status: published
---
# 运费计算表

| 重量段 | 普通地区 | 偏远地区 | 加急 |
| --- | --- | --- | --- |
| 首重1kg内 | 10元 | 20元 | 25元 |
| 续重每1kg | +2元 | +5元 | +10元 |
| 10kg以上 | 协商 | 协商 | 协商 |
""",
    "doc_tbl_009.md": """---
domain: product
tenant_id: t_demo
status: published
---
# 品牌价格区间

| 品牌 | 最低价 | 最高价 | 主营品类 |
| --- | --- | --- | --- |
| 品牌A | 100元 | 500元 | 服装 |
| 品牌B | 300元 | 1200元 | 电子产品 |
| 品牌C | 50元 | 200元 | 日用品 |
""",
    "doc_tbl_010.md": """---
domain: payment
tenant_id: t_demo
status: published
---
# 保险理赔标准

| 险种 | 最高赔付 | 条件 | 保费 |
| --- | --- | --- | --- |
| 运费险 | 25元 | 退货时自动赔付 | 0.5-2元 |
| 货损险 | 按实际损失 | 需提供破损证明 | 商品价1% |
| 延误险 | 10元 | 超过承诺时效 | 0.5元 |
""",
}

for name, content in table_docs.items():
    write(BASE / "tables" / name, content)


# ── Policy Documents (10) ─────────────────────────────────────────
policy_docs = {
    "doc_policy_001.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 食品类商品退货政策

食品类商品不支持7天无理由退货。特殊规定：
- 已拆封食品只能在质量问题下退货
- 退货需提供购买凭证
- 生鲜类商品不支持退货

如遇食品质量问题，请立即拍照留证并联系客服。
""",
    "doc_policy_002.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 投诉处理SOP

## 投诉分级

- A级（紧急）：涉及人身安全、食品安全，需2小时内联系用户
- B级（重要）：涉及商品质量、物流延误，24小时内处理
- C级（一般）：服务态度、信息咨询，48小时内回复

## 处理流程

1. 接诉分类
2. 核实事实
3. 制定方案
4. 与用户沟通
5. 执行方案
6. 回访确认
""",
    "doc_policy_003.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 客服绩效考核标准

## KPI指标

| 指标 | 标准 |
| --- | --- |
| 满意度 | ≥95% |
| 首次响应时间 | ≤30秒 |
| 平均解决时间 | ≤5分钟 |
| 升级率 | ≤5% |
| 一次解决率 | ≥90% |
""",
    "doc_policy_004.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 数据隐私与安全

遵循个人信息保护法的相关要求：
- 用户数据加密存储
- 数据保留期限不超过业务必要
- 用户可请求删除个人数据
- 数据访问需要审批和审计

禁止向第三方泄露用户信息。
""",
    "doc_policy_005.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 客服权限边界

客服不可对用户做出以下承诺：
- 私自承诺赔款超过100元
- 承诺免除运费
- 承诺优先发货

超出权限的承诺需升级主管审批。
""",
    "doc_policy_006.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 跨境商品售后政策

跨境商品特殊规定：
- 跨境商品7天无理由退货不适用
- 质量问题可退换但需清关
- 税费由用户承担
- 个人年度免税额度需注意
""",
    "doc_policy_007.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 大促期间售后政策

大型促销活动（双11、618等）期间的特殊政策：
- 双11期间延长退货时效至15天
- 618期间普通商品也延长至10天
- 部分闪购商品不支持退货
- 预售商品按商品页面说明执行
""",
    "doc_policy_008.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 客服话术规范

所有客服必须遵守以下规范：
- 禁止使用不文明用语
- 禁止承诺不实信息
- 必须使用标准话术模板开场："您好，请问有什么可以帮您？"
- 结束语："感谢您的咨询，如有问题随时联系我们"

违规将记录并影响绩效考核。
""",
    "doc_policy_009.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 工单升级触发条件

以下情况必须升级工单：
- 投诉类工单自动升级
- 退款金额大于500元需升级
- 涉及安全问题立即升级
- 用户要求升级
- 首次解决失败
""",
    "doc_policy_010.md": """---
domain: policy
tenant_id: t_demo
status: published
---
# 恶意退款判定标准

## 判定标准

- 月退货率大于50%标记为高风险
- 退回商品与购买商品不一致标记异常
- 多次使用不同账号退货

## 处理流程

确认恶意退款后：
1. 冻结该用户账号
2. 追回已退款项
3. 列入黑名单
""",
}

for name, content in policy_docs.items():
    write(BASE / "policy" / name, content)


print("Seed documents created:")
for cat in ["faq", "tables", "policy"]:
    files = list((BASE / cat).glob("*.md"))
    print(f"  {cat}: {len(files)} files")
print("Done.")
