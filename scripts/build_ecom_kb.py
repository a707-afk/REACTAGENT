"""Build e-commerce knowledge base for EcomAgent."""
import os


FAQ_ENTRIES = [
    # ── Return Policy ──
    {"topic": "return_policy", "q": "7天无理由退货条件是什么？", "a": "自签收之日起7日内，商品完好、配件齐全、不影响二次销售，可申请7天无理由退货。定制商品、生鲜、虚拟商品、已激活数码产品除外。退货运费由平台承担（首次退货）。"},
    {"topic": "return_policy", "q": "超过7天还能退货吗？", "a": "超过7天但在30天内，商品出现质量问题可申请换货或部分退款。超过30天一般不可退换，但平台会根据具体情况与商家协商。已拆封影响二次销售的，扣除10%-15%折旧费后部分退款。"},
    {"topic": "return_policy", "q": "哪些商品不支持退换？", "a": "内衣裤袜、定制商品、生鲜食品、虚拟商品（充值卡/游戏点卡）、已激活的数码产品（手机/平板/电脑）、个人护理用品（拆封后）不支持7天无理由退换。"},
    {"topic": "return_policy", "q": "退货需要自己付运费吗？", "a": "质量问题退货/换货运费由商家承担。7天无理由退货首次退货平台承担运费（补贴上限15元），超出部分由用户承担。"},

    # ── Exchange ──
    {"topic": "exchange", "q": "换货流程是怎样的？", "a": "申请换货→平台审核（24小时内）→预约上门取件→商家收到退货→仓库发新货。全程3-5个工作日。换货支持同款不同尺码/颜色，差价多退少补。"},
    {"topic": "exchange", "q": "换货可以换不同商品吗？", "a": "换货仅支持同款不同规格（尺码/颜色）的更换。如需更换不同商品，请先退款后重新购买。如果目标商品价格高于原商品，需补差价；低于原商品，退还差价。"},
    {"topic": "exchange", "q": "换货需要多久？", "a": "审核1个工作日内完成，上门取件后商家1-3个工作日收到退货，新商品发货后按地区1-5天送达。全程约3-7个工作日。"},

    # ── Refund ──
    {"topic": "refund", "q": "退款多久到账？", "a": "商家收到退货后1-3个工作日内审核，审核通过后原路退回。微信/支付宝1-3个工作日到账，银行卡1-7个工作日到账，信用卡3-15个工作日到账。"},
    {"topic": "refund", "q": "部分退款怎么计算？", "a": "已拆封影响二次销售的商品，根据商品状态扣除10%-15%折旧费后退还剩余金额。外包装损坏扣5-10元包装费。配件缺失按配件原价扣除。"},
    {"topic": "refund", "q": "退款时优惠券能退回吗？", "a": "全额退款时未过期优惠券退回账户，已过期不退。部分退款时优惠券按比例退回。平台红包过期不补。满减优惠按实际支付金额比例分摊计算。"},
    {"topic": "refund", "q": "拒收商品后怎么退款？", "a": "直接拒收包裹，物流会自动退回商家。商家收到退回商品后系统自动发起退款，无需手动申请。从拒收到退款到账通常需要5-10个工作日。"},

    # ── Complaint ──
    {"topic": "complaint", "q": "如何投诉商家？", "a": "进入订单详情→点击「投诉商家」→选择投诉类型（商品问题/服务态度/虚假宣传/延迟发货等）→填写投诉描述（建议附截图证据）→提交。平台会在24小时内介入处理。"},
    {"topic": "complaint", "q": "投诉后多久回复？", "a": "一般投诉24小时内回复处理结果。涉及金额较大（>500元）的投诉升级为优先处理，2小时内响应。投诉成立后根据问题严重程度赔付：延迟发货赔订单金额5%，虚假宣传赔订单金额30%最高500元。"},
    {"topic": "complaint", "q": "对处理结果不满意怎么办？", "a": "可在投诉详情页点击「申请平台介入」，由平台客服复审。涉及金额较大或严重违规的投诉会自动升级为P0级别，24小时内专人处理。也可拨打12315消费者投诉热线。"},

    # ── Shipping ──
    {"topic": "shipping", "q": "如何查询物流？", "a": "进入订单详情→点击「查看物流」可实时追踪包裹位置。显示预计送达时间和物流公司信息。支持顺丰、中通、圆通、韵达、邮政等主流快递公司。"},
    {"topic": "shipping", "q": "物流超时怎么办？", "a": "物流超过承诺时效可申请赔付。标准快递超时赔付订单金额的5%（上限50元），生鲜冷链超时赔付订单金额的10%（上限100元）。在订单详情页点击「物流投诉」申请。"},
    {"topic": "shipping", "q": "包裹丢失了怎么办？", "a": "物流超过7天未更新视为疑似丢件。联系客服提供订单号→平台核实→全额退款+赔付（赔付订单金额的10%，上限100元）。3个工作日内处理完成。"},
    {"topic": "shipping", "q": "上门取件什么时候来？", "a": "提交退换货申请后，系统自动预约次日上门取件（9:00-18:00）。取件前快递员会电话联系确认。如当天无人联系，可取消重新预约或联系客服加急处理。"},

    # ── Extra FAQ pairs ──
    {"topic": "return_policy", "q": "拆了包装还能退吗？", "a": "外包装拆除但商品完好、不影响二次销售的，可以退货。如果商品本身已使用、清洗、损坏等影响二次销售的，不支持退货，可按部分退款处理。"},
    {"topic": "refund", "q": "退款金额和支付的不一样怎么办？", "a": "可能的原因：1)使用了优惠券，退款按实际支付金额计算；2)部分退款扣除了折旧费；3)运费扣除。如对金额有疑问，联系客服提供退款明细。"},
    {"topic": "exchange", "q": "换的货也想要退货可以吗？", "a": "换货商品同样享受7天无理由退货权益，从收到换货商品之日起重新计算7天。但同一订单最多支持一次换货，换货后再退货只能走退款流程。"},
    {"topic": "complaint", "q": "商家威胁我怎么办？", "a": "立即联系平台客服并提供聊天截图证据。威胁恐吓行为属于严重违规，平台会立即冻结商家账户，并协助报警处理。这类投诉标记为P0级别，2小时内响应。"},
    {"topic": "shipping", "q": "可以改收货地址吗？", "a": "未发货订单可直接修改地址。已发货订单无法修改，建议联系快递公司转寄或拒收后重新下单。跨境电商订单一旦出库无法修改地址。"},
    {"topic": "refund", "q": "退款成功但没收到钱？", "a": "请确认退款路径：1)微信/支付宝查看账单记录；2)银行卡查看交易明细。如超过7个工作日仍未到账，提供退款截图联系客服人工核查。"},
]


def build_faq_markdown(output_dir: str):
    """Write FAQ entries as markdown files for indexing."""
    os.makedirs(output_dir, exist_ok=True)

    by_topic: dict[str, list[dict]] = {}
    for entry in FAQ_ENTRIES:
        by_topic.setdefault(entry["topic"], []).append(entry)

    for topic, entries in by_topic.items():
        topic_display = {
            "return_policy": "退货政策",
            "exchange": "换货指南",
            "refund": "退款流程",
            "complaint": "投诉维权",
            "shipping": "物流配送",
        }.get(topic, topic)

        path = os.path.join(output_dir, f"faq_{topic}.md")
        lines = [f"# 电商售后知识库 — {topic_display}\n"]
        for e in entries:
            lines.append(f"## Q: {e['q']}")
            lines.append(f"A: {e['a']}\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Wrote {len(entries)} entries to {path}")

    # Also create a combined property version
    combined_path = os.path.join(output_dir, "faq_all.md")
    lines = ["# 电商售后知识库（完整版）\n"]
    for entry in FAQ_ENTRIES:
        lines.append(f"## Q: {entry['q']}")
        lines.append(f"A: {entry['a']}\n")
    with open(combined_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote combined {len(FAQ_ENTRIES)} entries to {combined_path}")


if __name__ == "__main__":
    build_faq_markdown("data/docs_ecom")
