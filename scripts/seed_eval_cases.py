"""Generate gold-standard RAG evaluation cases — 100 total.

Output: data/eval/rag/*.jsonl
"""
import json
from pathlib import Path

OUTPUT = Path("data/eval/rag")
OUTPUT.mkdir(parents=True, exist_ok=True)

all_cases = []


def add(cat, qid, query, chunks, facts, docs=None, roles=None, forbidden=None):
    all_cases.append({
        "id": f"{cat.upper()}-{qid:03d}",
        "query": query,
        "tenant_id": "t_demo",
        "roles": roles or ["support_agent"],
        "gold_document_ids": docs or [],
        "gold_chunk_ids": chunks,
        "answer_facts": facts,
        "forbidden_document_ids": forbidden or [],
        "category": cat,
    })


# ── FAQ (30) ──────────────────────────────────────────────────────
faqs = [
    ("如何申请退货？", ["chunk_faq_return_01","chunk_faq_return_02"], ["退货需在7天内申请","需保持商品完好","需提供订单号"]),
    ("退货需要多长时间？", ["chunk_faq_return_time_01"], ["退款到账1-7个工作日","不同支付方式到账时间不同"]),
    ("商品收到后发现有损坏怎么办？", ["chunk_faq_damage_01","chunk_faq_contact_01"], ["需24小时内联系客服","需提供开箱视频或照片"]),
    ("如何查询物流状态？", ["chunk_faq_logistics_01"], ["在订单详情页查询","输入运单号追踪"]),
    ("发货时间一般多久？", ["chunk_faq_delivery_01"], ["下单后48小时内发货","大促期间可能72小时"]),
    ("支持哪些支付方式？", ["chunk_faq_payment_01","chunk_faq_payment_02"], ["微信支付、支付宝、银行卡","部分商品货到付款"]),
    ("优惠券怎么使用？", ["chunk_faq_coupon_01"], ["结算页面选择优惠券","有使用门槛和有效期"]),
    ("如何修改收货地址？", ["chunk_faq_address_01"], ["未发货订单可修改","已发货订单需联系客服"]),
    ("会员等级有什么权益？", ["chunk_faq_member_01"], ["银卡9.5折","金卡9折和专属客服","钻石8.5折和优先发货"]),
    ("订单取消后多久退款？", ["chunk_faq_cancel_01","chunk_faq_return_time_01"], ["取消后退款1-3个工作日","已发货需先退回"]),
    ("商品颜色和图片不符怎么办？", ["chunk_faq_color_01"], ["提供实际商品照片","可换货或退货退款"]),
    ("发票如何索取？", ["chunk_faq_invoice_01"], ["订单详情页申请发票","电子发票1-3个工作日发送"]),
    ("换货流程是什么？", ["chunk_faq_exchange_01","chunk_faq_exchange_02"], ["订单详情页申请","7天内提出","运费由商家承担"]),
    ("能修改订单信息吗？", ["chunk_faq_modify_order_01"], ["未发货可修改规格和收货信息","已发货仅可修改收货信息"]),
    ("快递丢件了怎么办？", ["chunk_faq_lost_package_01"], ["联系快递公司确认","确认丢件后重新发货或退款"]),
    ("尺码不合适能换吗？", ["chunk_faq_exchange_01"], ["支持7天无理由换货","保持商品完好","部分特殊商品不支持"]),
    ("怎么联系人工客服？", ["chunk_faq_contact_01","chunk_faq_contact_02"], ["热线400-xxx-xxxx","在线客服9:00-21:00","App内在线客服"]),
    ("可以用他人的账号下单吗？", ["chunk_faq_account_01"], ["可以使用他人账号","收货人需与实名信息一致"]),
    ("商品缺货什么时候补货？", ["chunk_faq_restock_01"], ["热门商品1-2周补货","可设置到货提醒"]),
    ("赠品出现问题可以退换吗？", ["chunk_faq_gift_01"], ["赠品不参与单独退换","主商品退货时一并退回"]),
    ("跨境商品有什么特殊政策？", ["chunk_faq_cross_border_01","chunk_faq_cross_border_02"], ["不支持7天无理由","注意税费和个人额度","按保税区政策执行"]),
    ("怎么修改绑定的手机号？", ["chunk_faq_phone_01"], ["个人中心安全设置中修改","需验证原手机号和实名信息"]),
    ("积分如何使用？", ["chunk_faq_points_01"], ["结算时抵扣现金","100积分=1元","有效期1年"]),
    ("怎么查看历史订单？", ["chunk_faq_history_01"], ["个人中心我的订单","支持按时间、状态筛选"]),
    ("订单状态一直不更新怎么办？", ["chunk_faq_order_status_01"], ["物流信息可能延迟","超过48小时联系客服"]),
    ("如何注销账号？", ["chunk_faq_account_02"], ["设置中选择注销","需无未完成订单","注销后数据不可恢复"]),
    ("商品包装破损可以拒收吗？", ["chunk_faq_damage_02"], ["外包装破损可以拒收","拒收后联系客服退款或重发"]),
    ("怎么给商品写评价？", ["chunk_faq_review_01"], ["完成交易可评价","含星级评分和文字描述"]),
    ("活动规则看不懂怎么办？", ["chunk_faq_activity_01"], ["活动页查看详细说明","咨询在线客服"]),
    ("为什么有些地区不支持配送？", ["chunk_faq_delivery_area_01"], ["偏远地区需额外运费和时间","特殊商品有区域限制"]),
]
for i, (q, c, f) in enumerate(faqs, 1):
    add("faq", i, q, c, f, docs=[f"doc_faq_{i:03d}"])

# ── PDF Table (20) ────────────────────────────────────────────────
tables = [
    ("退货政策按商品类别有什么不同？", ["chunk_tbl_return_matrix_01","chunk_tbl_return_matrix_02"], ["服装类7天无理由","食品类不支持","电子产品需检测"]),
    ("各级会员的折扣分别是多少？", ["chunk_tbl_member_discount_01"], ["银卡9.5折","金卡9折","钻石8.5折"]),
    ("各物流公司的配送时效对比？", ["chunk_tbl_logistics_compare_01"], ["顺丰1-2天","圆通2-3天","中通2-4天","韵达3-5天"]),
    ("不同支付渠道的手续费是多少？", ["chunk_tbl_payment_fee_01"], ["微信支付0.1%","支付宝0.1%","银行卡0.3%"]),
    ("各品类退货率统计是多少？", ["chunk_tbl_category_return_rate_01"], ["服装类退货率最高约15%","电子类约3%"]),
    ("Q1和Q2各区域销售额对比？", ["chunk_tbl_sales_region_q1q2_01"], ["华东Q1 500万Q2 620万","华南Q1 380万Q2 410万"]),
    ("各客服团队的服务指标对比？", ["chunk_tbl_cs_kpi_01"], ["A团队满意度98%","B团队满意度96%","平均响应30秒"]),
    ("运费怎么根据地区和重量计算？", ["chunk_tbl_shipping_cost_01"], ["首重1kg内10元","续重每kg加2-5元","偏远地区加倍"]),
    ("各品牌商品的价格区间对比？", ["chunk_tbl_brand_price_range_01"], ["品牌A 100-500元","品牌B 300-1200元","品牌C 50-200元"]),
    ("不同险种的理赔额度和条件？", ["chunk_tbl_insurance_matrix_01"], ["运费险最高赔付25元","货损险按实际损失"]),
    ("各仓库的库存和配送范围对比？", ["chunk_tbl_warehouse_compare_01"], ["华东仓覆盖江浙沪皖","华南仓覆盖粤闽赣湘"]),
    ("退货运费的承担规则？", ["chunk_tbl_return_shipping_01"], ["质量问题卖家承担","非质量问题买家承担"]),
    ("积分兑换商品有哪些选择？", ["chunk_tbl_points_exchange_01"], ["1000积分换10元券","5000积分换50元礼品卡"]),
    ("各月份促销活动日历？", ["chunk_tbl_promo_calendar_01"], ["1月年货节","6月618","11月双11","12月双12"]),
    ("不同客服等级的处理权限？", ["chunk_tbl_agent_permissions_01"], ["初级客服只能查询","高级客服可退≤200元","主管可全额退"]),
    ("投诉类型和处理时效对比？", ["chunk_tbl_complaint_sla_01"], ["普通投诉24小时","紧急投诉4小时","涉及安全2小时"]),
    ("各快递公司的丢件赔付标准？", ["chunk_tbl_courier_compensation_01"], ["顺丰保价赔全额","圆通按运费5倍","中通按运费3倍"]),
    ("不同等级用户的售后优先级？", ["chunk_tbl_vip_priority_01"], ["钻石用户优先处理","投诉类全员优先"]),
    ("退款金额的审批权限表？", ["chunk_tbl_refund_approval_01"], ["≤100元自动审批","100-500元主管",">500元经理"]),
    ("各渠道客户满意度对比？", ["chunk_tbl_channel_satisfaction_01"], ["App渠道94%","小程序91%","电话88%"]),
]
for i, (q, c, f) in enumerate(tables, 1):
    add("pdf_table", i, q, c, f, docs=[f"doc_tbl_{i:03d}"])

# ── No Answer (15) ────────────────────────────────────────────────
noans = [
    ("如何申请企业账号？", [], []),
    ("可以用比特币付款吗？", [], []),
    ("商品如何进行抵押贷款？", [], []),
    ("如何在你们平台开网店？", [], []),
    ("有线下实体店吗？", [], []),
    ("怎么购买公司股票？", [], []),
    ("支持拼多多支付吗？", [], []),
    ("请问今天的天气怎么样？", [], []),
    ("帮我写一首关于购物的诗", [], []),
    ("能否提供政治相关咨询？", [], []),
    ("我可以购买你们公司的股份吗？", [], []),
    ("有外语版本的服务吗？", [], []),
    ("可以请你们的CEO给我回电话吗？", [], []),
    ("商品可以用在太空站吗？", [], []),
    ("你们支持F-1学生签证吗？", [], []),
]
for i, (q, c, f) in enumerate(noans, 1):
    add("no_answer", i, q, c, f)

# ── Permission (15) ──────────────────────────────────────────────
perms = [
    ("查看退款审批的决策记录", ["chunk_perm_audit_01"], ["审批记录仅对主管和审计开放"],
     ["agent_supervisor"], []),
    ("获取用户支付密码", [], ["支付密码不可获取"],
     ["support_agent"], ["doc_forbidden_01"]),
    ("查看VIP用户的信息详情", ["chunk_perm_vip_data_01"], ["VIP用户完整信息仅限高级客服"],
     ["agent_supervisor"], []),
    ("导出所有用户数据", [], ["全量数据导出需总监审批"],
     ["support_agent"], ["doc_forbidden_02"]),
    ("查看其他部门的客服工单", [], ["跨部门工单需协调权限"],
     ["support_agent_l1"], ["doc_other_dept_01"]),
    ("修改商品的销售价格", [], ["价格修改仅限运营角色"],
     ["support_agent"], ["doc_pricing_01"]),
    ("查看投诉人实名信息", [], ["投诉人实名信息仅限法务和安全"],
     ["support_agent"], ["doc_personal_01"]),
    ("删除用户的差评", [], ["差评删除仅限内容管理团队"],
     ["support_agent"], ["doc_review_admin_01"]),
    ("查看退款失败日志", ["chunk_perm_refund_log_01"], ["退款日志仅对技术和风控开放"],
     ["tech_support"], []),
    ("获取客服通话录音", [], ["录音获取需用户本人同意"],
     ["support_agent"], ["doc_recording_01"]),
    ("修改用户积分余额", [], ["积分修改需风控审批"],
     ["support_agent"], ["doc_points_01"]),
    ("查看平台签约商家的合同", [], ["合同查看仅限商务拓展和法务"],
     ["support_agent"], ["doc_contract_01"]),
    ("批量关闭用户账号", [], ["批量关闭需安全部门审批"],
     ["support_agent"], ["doc_batch_close_01"]),
    ("查看实时销售数据看板", ["chunk_perm_sales_dashboard_01"], ["销售看板对经理级以上开放"],
     ["manager"], []),
    ("修改客服排班表", ["chunk_perm_schedule_01"], ["排班修改仅限团队组长"],
     ["team_leader"], []),
]
for i, (q, c, f, roles, forbidden) in enumerate(perms, 1):
    add("permission", i, q, c, f, roles=roles, forbidden=forbidden)

# ── Policy (10) ──────────────────────────────────────────────────
policies = [
    ("退款政策中关于食品类商品的规定", ["chunk_policy_food_return_01"], ["食品类不支持7天无理由","已拆封食品只能质量问题退货","退货需购买凭证"]),
    ("投诉处理的SOP流程", ["chunk_policy_complaint_sop_01","chunk_policy_complaint_sop_02"], ["投诉分A/B/C三级","A级2小时内联系","B级24小时","C级48小时"]),
    ("服务质量考核的KPI标准", ["chunk_policy_kpi_01"], ["满意度≥95%","首次响应≤30秒","平均解决≤5分钟"]),
    ("数据隐私保护的合规要求", ["chunk_policy_privacy_01"], ["遵循个人信息保护法","数据加密存储","用户可请求删除数据"]),
    ("客服对用户承诺的权限边界", ["chunk_policy_commitment_01"], ["不可私自承诺赔款超100元","不可承诺免运费","不可承诺优先发货"]),
    ("跨境商品的售后服务政策", ["chunk_policy_cross_border_01"], ["跨境商品7天无理由不适用","质量问题可退换但需清关","税费由用户承担"]),
    ("大促期间的退换货特殊政策", ["chunk_policy_promo_return_01"], ["双11期间延长退货至15天","部分闪购商品不支持退货"]),
    ("客服话术规范要求", ["chunk_policy_script_01"], ["禁止使用不文明用语","禁止承诺不实信息","必须使用标准话术模板"]),
    ("工单升级的触发条件", ["chunk_policy_escalation_01"], ["投诉类工单自动升级","退款>500元需升级","涉及安全问题立即升级"]),
    ("恶意退款的判定标准和处理流程", ["chunk_policy_fraud_refund_01","chunk_policy_fraud_refund_02"], ["月退货率>50%标记高风险","退回商品与购买不一致标记异常","确认恶意冻结账号"]),
]
for i, (q, c, f) in enumerate(policies, 1):
    add("policy", i, q, c, f, docs=[f"doc_policy_{i:03d}"])

# ── Multi-Turn (10) ──────────────────────────────────────────────
mt = [
    ("我上周买了一件T恤现在想退。之前咨询过T恤尺码问题。", ["chunk_mt_return_01","chunk_mt_return_02"], ["确认是否在7天内","T恤属于服装类支持7天无理由"]),
    ("之前说的那个包裹怎么还没到？快递单号SF1234567890。之前投诉过物流延误。", ["chunk_mt_logistics_01","chunk_mt_tracking_01"], ["SF1234567890在XX中转站","预计明天送达","因天气延误"]),
    ("上次那个破了的商品给我换一个新的吧。之前反馈过商品破损。", ["chunk_mt_exchange_damage_01"], ["确认已提供破损照片","安排换货","新品2-3天送达"]),
    ("上次客服答应给我补发的赠品什么时候到？", ["chunk_mt_gift_ship_01"], ["核实客服承诺记录","赠品已发出"]),
    ("上次退款的50元怎么还没到账？我用的支付宝。", ["chunk_mt_refund_status_01"], ["退款单号RF20260601001","支付宝退款1-3个工作日"]),
    ("我之前问了换货现在改主意了直接退了吧。之前咨询过换货流程。", ["chunk_mt_return_swap_01"], ["从换货转为退货流程","先取消换货申请","重新提交退货"]),
    ("你说让我重新下单但我发现之前那个优惠券过期了。上次客服建议我重新下单。", ["chunk_mt_coupon_expired_01"], ["确认优惠券有效期","过期通常不可恢复","特殊情况可申请补偿券"]),
    ("我上次反馈的快递暴力运输问题你们调查结果出来了吗？", ["chunk_mt_investigation_01"], ["调查已完成","快递公司承认暴力运输","用户可得50元补偿"]),
    ("你上次说帮我查的商品库存现在有货了吗？之前查询过热门商品库存。", ["chunk_mt_restock_check_01"], ["确认SKU","查询实时库存","有货尽快告知"]),
    ("我上次投诉快递员态度不好有处理结果吗？之前投诉过快递服务。", ["chunk_mt_complaint_result_01"], ["工单号C20260520001","已发整改通知","补偿20元优惠券"]),
]
for i, (q, c, f) in enumerate(mt, 1):
    add("multi_turn", i, q, c, f, docs=[f"doc_mt_{i:03d}"])

# ── Write JSONL files ─────────────────────────────────────────────
cats = {}
for case in all_cases:
    cats.setdefault(case["category"], []).append(case)

for cat, cases in sorted(cats.items()):
    path = OUTPUT / f"{cat}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"  {cat}: {len(cases)} cases")

print(f"\nTotal: {len(all_cases)} cases across {len(cats)} categories")
