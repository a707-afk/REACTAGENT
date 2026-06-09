"""快速意图分类：CSDS intent -> 14 domain。支持 --no-llm 跳过 LLM。"""
import argparse, json, sys, time, logging
from collections import Counter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("data/docs_cn/classify.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

INTENT_TO_DOMAIN = {
    "保修返修及退换货政策": "returns", "正常退款周期": "returns", "返回方式": "returns",
    "拒收": "returns", "少商品与少配件": "returns", "返修退换货处理周期": "returns",
    "申请退款": "returns", "退款到哪儿": "returns", "售后运费": "returns",
    "返修退换货拆包装": "returns", "返修退换货发票": "returns", "补发": "returns",
    "保修期保质期": "returns", "关闭服务单": "returns", "延保服务": "returns",
    "配送周期": "delivery", "什么时间出库": "delivery", "联系配送": "delivery",
    "物流全程跟踪": "delivery", "订单签收异常": "delivery", "配送方式": "delivery",
    "补货时间": "delivery", "预约配送时间": "delivery", "能否自提": "delivery",
    "物流损": "delivery", "出库地址": "delivery", "返回地址": "delivery",
    "能否配送": "delivery", "物流信息不正确": "delivery", "是否送货上门": "delivery",
    "代收": "delivery", "包装清单": "delivery", "外包装": "delivery",
    "修改订单": "order", "如何取消订单": "order", "订单状态解释": "order",
    "查询取消是否成功": "order", "恢复订单": "order", "库存状态": "order",
    "货到付款": "order", "拆分订单": "order", "订单合并": "order",
    "订单无故取消": "order", "取消订单受理时间": "order", "购物流程": "order",
    "删除修改评价晒单": "order", "预约抢购": "order",
    "发票退换修改": "billing", "是否提供发票": "billing", "查看发票": "billing",
    "增票相关": "billing", "电子发票": "billing", "填写发票信息": "billing",
    "补发票": "billing", "支付方式": "billing", "支付密码": "billing",
    "余额提现": "billing", "充值未到账充值到账时间": "billing", "公司转账": "billing",
    "运费险咨询": "billing",
    "家电安装": "tech_support", "手机邮件相关问题": "tech_support", "安装收费": "tech_support",
    "手机回收流程": "tech_support", "生产日期": "tech_support",
    "售前运费多少": "sales", "商品价格咨询": "sales", "商品检索": "sales",
    "正品保障": "sales", "能否优惠": "sales", "商品比较": "sales",
    "商家入驻条件": "sales", "商家入驻费用": "sales", "促销形式": "sales",
    "使用咨询": "product_support", "属性咨询": "product_support",
    "联系客户": "customer_service", "服务单查询": "customer_service",
    "联系客服": "customer_service", "服务单修改": "customer_service",
    "审核时效": "customer_service", "联系商家": "customer_service",
    "联系售后": "customer_service", "纠纷单申请": "customer_service",
    "企业用户": "hr",
    "": "general", "找回密码": "account", "手机绑定": "account",
    "账号注销": "account", "纠纷单解释": "customer_service",
    "无法申请价保": "general", "解绑和绑定微信": "account",
    "代客户充值": "billing", "无法购买提交": "order",
    "退款异常": "returns", "账户安全": "account",
    "免密支付": "billing", "账户注册": "account",
    "优惠券有效期": "general", "商家入驻联系方式": "sales",
    "发错货": "returns", "账户注销": "account",
    "开箱验货": "delivery", "自营与第三方区别": "general",
    "发货检查": "delivery", "订单改价": "order",
    "商家发货时效": "delivery", "密码找回": "account",
    "申请售后": "returns", "客户投诉": "feedback",
    "投诉举报": "feedback",
    "PLUS会员": "general", "下单后无记录": "order", "下单地址填写": "order",
    "下单备注": "order", "为什么显示无货": "order", "京东ID": "general",
    "京东特色配送": "general", "京东钱包绑定": "general", "京豆积分有效期": "general",
    "京豆积分查看": "general", "京豆积分比值": "general", "京豆积分获得方式": "general",
    "京豆积分解释": "general", "京豆积分退回": "general", "价保记录查询": "general",
    "优惠券使用": "general", "优惠券查看": "general", "优惠券获得方式": "general",
    "优惠券退回": "general", "会员俱乐部": "general", "余额查询": "billing",
    "余额退款": "returns", "修改账户信息": "account", "催促处理纠纷单": "customer_service",
    "充值到账异常": "billing", "充值号码咨询": "billing", "充值号码错误": "billing",
    "分期付款": "general", "取消订单白条处理": "general", "取消退款": "returns",
    "退款失败": "returns", "退款进度": "returns", "发票问题": "billing",
    "发票金额": "billing", "发票类型": "billing", "发票抬头": "billing",
    "发票内容": "billing", "发票邮寄": "billing", "批量下单": "order",
    "商品评价": "feedback", "商品质量": "returns", "商品尺寸": "product_support",
    "商品颜色": "product_support", "商品材质": "product_support",
    "商品库存": "order", "商品缺货": "order", "商品下架": "order",
    "商品推荐": "sales", "商品对比": "sales", "商品试用": "sales",
    "换货申请": "returns", "换货进度": "returns", "换货条件": "returns",
    "维修申请": "tech_support", "维修进度": "tech_support", "维修费用": "tech_support",
    "投诉渠道": "feedback", "投诉进度": "feedback", "投诉结果": "feedback",
    "物流查询": "delivery", "物流延迟": "delivery", "物流投诉": "delivery",
    "运费争议": "delivery", "运费计算": "delivery", "运费减免": "delivery",
    "签收问题": "delivery", "验货问题": "delivery", "保价问题": "general",
    "会员权益": "general", "积分问题": "general", "活动咨询": "general",
    "客服态度": "feedback", "客服效率": "feedback", "客服专业性": "feedback",
    "数据安全": "general", "隐私政策": "general", "账号安全": "account",
    "实名认证": "account", "绑定手机": "account", "绑定邮箱": "account",
    "通知设置": "account", "消息推送": "account",
    "如何评价晒单": "feedback", "是否回收": "returns", "支付到账时间": "billing",
    "回收款项": "returns", "检测单咨询": "tech_support", "在线支付": "billing",
    "赠品领取更换": "returns", "怎么确认收货": "delivery",
    "评价晒单返券和赠品": "general", "解锁锁定": "account",
    "节能补贴": "general", "实名认证与解除": "account",
    "白条分期手续费": "general", "白条使用流程": "general", "订单回收站": "order",
    "提前配送": "delivery", "我的小金库": "general", "填写返件运单号": "returns",
    "在哪里查询退款": "returns", "自提时间": "delivery",
    "取消订单白条处理": "general", "白条还款方式": "general",
    "部分商品退款": "returns", "京东特色配送": "general", "商品介绍": "sales",
    "无法使用优惠券": "general", "订单历史记录查询": "order",
    "查看评价晒单": "feedback", "购物清单": "order",
    "快递单号不正确": "delivery", "登录问题": "account",
    "消费记录": "billing", "配送工作时间": "delivery",
    "商家入驻类目": "sales", "回收时间": "returns",
    "礼品卡退回": "general", "纠纷单处理时效": "customer_service",
    "回收订单取消": "order", "忘记账户名": "account",
    "返修退换货审核不通过": "returns", "有什么颜色": "product_support",
    "优惠券查看": "general", "退款说明": "returns", "退款方式": "returns",
    "退款金额": "returns", "退款时间": "returns", "退款状态查询": "returns",
    "货到付款拒收": "returns", "换货流程": "returns", "维修周期": "tech_support",
    "上门维修": "tech_support", "寄修服务": "tech_support",
    "配件购买": "product_support", "包装破损": "delivery",
    "商品漏发": "returns", "商品错发": "returns", "商品瑕疵": "returns",
    "功能咨询": "product_support", "操作指南": "product_support",
    "版本更新": "tech_support", "兼容性咨询": "tech_support",
    "保修查询": "returns", "延保购买": "sales",
    "会员注册": "account", "会员登录": "account", "会员注销": "account",
    "积分查询": "general", "积分兑换": "general", "积分过期": "general",
    "优惠券领取": "general", "优惠券规则": "general",
    "发票重开": "billing", "发票作废": "billing", "电子发票下载": "billing",
    "发票税号": "billing", "发票邮寄地址": "billing",
    "物流时效": "delivery", "运费标准": "delivery",
    "配送范围": "delivery", "配送时间": "delivery",
    "订单修改地址": "order", "订单加急": "order", "订单备注": "order",
    "订单拆分规则": "order", "合并支付": "order",
}

DOMAIN_CN_MAP = {
    "售后退款": "returns", "退货退款": "returns", "物流配送": "delivery",
    "快递物流": "delivery", "账户登录": "account", "账号密码": "account",
    "发票账单": "billing", "支付扣费": "billing", "订单查询": "order",
    "下单购买": "order", "商品破损": "tech_support", "技术故障": "tech_support",
    "投诉建议": "feedback", "意见反馈": "feedback", "售前咨询": "sales",
    "价格咨询": "sales", "人事HR": "hr", "员工福利": "hr", "IT支持": "it_support",
    "办公设备": "it_support", "产品使用": "product_support", "功能说明": "product_support",
    "服务中断": "outages", "系统故障": "outages", "客服咨询": "customer_service",
    "人工服务": "customer_service", "其他": "general",
}

SENSENOVA_KEYS = [
    "REDACTED_KEY",
    "REDACTED_KEY",
    "REDACTED_KEY",
]
_key_idx = 0


def _get_client():
    global _key_idx
    from openai import OpenAI
    key = SENSENOVA_KEYS[_key_idx]
    _key_idx = (_key_idx + 1) % len(SENSENOVA_KEYS)
    return OpenAI(api_key=key, base_url="https://token.sensenova.cn/v1")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="data/docs_cn/csds_faq_raw.jsonl")
    parser.add_argument("--output", default="data/docs_cn/faq_cn.jsonl")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM classification")
    parser.add_argument("--resume", type=int, default=0, help="Resume from batch index")
    args = parser.parse_args()

    raw_file = args.raw
    out_file = args.output
    skip_llm = args.no_llm

    faqs = []
    with open(raw_file, encoding="utf-8") as f:
        for line in f:
            try:
                faqs.append(json.loads(line))
            except Exception:
                continue

    logger.info("Loaded %d FAQs", len(faqs))

    # Step 1: Intent mapping
    intent_ok = 0
    unmatched = set()
    for faq in faqs:
        intent = faq.get("intent", "")
        if intent in INTENT_TO_DOMAIN:
            faq["domain"] = INTENT_TO_DOMAIN[intent]
            intent_ok += 1
        elif skip_llm:
            faq["domain"] = "general"
            unmatched.add(intent)
        else:
            unmatched.add(intent)

    remaining = [faq for faq in faqs if "domain" not in faq]
    logger.info("Intent match: %d/%d (%.1f%%), remaining: %d",
                intent_ok, len(faqs), 100.0 * intent_ok / max(len(faqs), 1), len(remaining))
    if not skip_llm and unmatched:
        logger.info("Unmatched intents (%d): %s", len(unmatched), sorted(unmatched)[:30])

    # Step 2: LLM for remaining (unless --no-llm)
    if remaining and not skip_llm:
        domain_list_cn = [
            "售后退款", "物流配送", "账户登录", "发票账单", "订单查询",
            "技术故障", "投诉建议", "售前咨询", "人事HR", "IT支持",
            "产品使用", "服务中断", "客服咨询", "其他",
        ]
        domain_display = "\n".join(f"- {d}" for d in domain_list_cn)

        llm_ok = 0
        llm_err = 0
        for i in range(args.resume, len(remaining), 20):
            time.sleep(1.5)
            batch = remaining[i:i + 20]
            lines = []
            for j, faq in enumerate(batch):
                lines.append(f"[{j}] Q: {faq['q']}\n   A: {faq['a'][:100]}")
            prompt = (f"请为以下{len(batch)}条客服FAQ分类到最合适的领域。\n{domain_display}\n\n"
                      f"每条输出一行JSON：{{\"idx\":编号,\"domain\":\"领域名\"}}\n只输出JSON。\n\n"
                      + "\n".join(lines))

            for attempt in range(4):
                try:
                    client = _get_client()
                    resp = client.chat.completions.create(
                        model="deepseek-v4-flash",
                        messages=[
                            {"role": "system", "content": "你是客服领域分类专家。只输出JSON。"},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.1, max_tokens=2048, timeout=120,
                    )
                    content = resp.choices[0].message.content or ""
                    for line in content.strip().split("\n"):
                        line = line.strip()
                        if not line.startswith("{"):
                            continue
                        try:
                            r = json.loads(line)
                            idx = r.get("idx")
                            dom_cn = r.get("domain", "其他")
                            if idx is not None and 0 <= idx < len(batch):
                                batch[idx]["domain"] = DOMAIN_CN_MAP.get(dom_cn, "general")
                                llm_ok += 1
                        except Exception:
                            continue
                    break
                except Exception as e:
                    err = str(e)
                    if "429" in err or "rpm" in err.lower() or "quota" in err.lower():
                        wait = 20 * (attempt + 1)
                        logger.warning("Rate limited, waiting %ds", wait)
                        time.sleep(wait)
                    elif attempt == 3:
                        logger.error("Batch %d failed: %s", i, e)
                        llm_err += len(batch)
                    else:
                        time.sleep(2)

            if (i + 20) % 500 == 0:
                logger.info("LLM: %d/%d", llm_ok, len(remaining))

        logger.info("LLM: %d ok, %d errors", llm_ok, llm_err)

    # Assign default
    for faq in faqs:
        if "domain" not in faq:
            faq["domain"] = "general"

    # Save
    with open(out_file, "w", encoding="utf-8") as f:
        for faq in faqs:
            f.write(json.dumps(faq, ensure_ascii=False) + "\n")

    # Stats
    counts = Counter(f["domain"] for f in faqs)
    logger.info("=== Domain Distribution ===")
    for dom, cnt in counts.most_common():
        logger.info("  %s: %d", dom, cnt)
    logger.info("Done! %d FAQs -> %s", len(faqs), out_file)


if __name__ == "__main__":
    main()
