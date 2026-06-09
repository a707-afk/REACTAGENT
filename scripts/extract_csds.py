"""从 CSDS 数据集提取 FAQ 对并构建中文知识库。

CSDS 数据格式：
  - Dialogue: 完整对话（turn 数组）
  - QA: [{QueSumm, AnsSummShort, AnsSummLong, intent, ...}, ...]
  - 每个 QA segment 是一个话题单元

提取策略：
  1. 遍历所有 QA segment，过滤 JD 平台专属内容
  2. 提取 QueSumm + AnsSummLong 作为 FAQ 对
  3. 文本 hash 去重 + 长度质量过滤
  4. 用 LLM 对每个 FAQ 分类到 14 个客服域
  5. 输出 faq_cn.jsonl

用法：
  python scripts/extract_csds.py --input data/cn_raw/csds --output data/docs_cn
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# JD 平台专属黑名单词 — 含这些词的 QA 片段直接丢弃
# 目标：只保留全行业通用售后知识，剥离京东电商平台绑定内容
# ═══════════════════════════════════════════════════════════════
JD_BLACKLIST = {
    "京东", "京豆", "白条", "自营", "京东快递", "京喜", "店铺券",
    "plus会员", "PLUS会员", "Plus会员", "京东卡", "E卡", "e卡",
    "京准达", "京东白条", "京东金融", "京东支付", "京东钱包",
    "京东商城", "京东自营", "京东物流", "京东到家", "京东超市",
    "京享值", "京豆抵扣", "京贴", "京东优惠", "京东价保",
    "京东e卡", "京东E卡", "京东PLUS", "京东Plus",
}

# JD 专属意图标签 — 这些 intent 直接整段丢弃
JD_INTENT_BLACKLIST = {
    "价保申请流程", "价保条件",  # 京东价保体系
    "近期活动咨询",  # 平台活动
    "京豆相关问题",  # 京豆体系
    "白条相关", "白条支付",  # 白条体系
}

# 最小长度阈值
MIN_Q_LEN = 5   # 问题至少 5 个字符
MIN_A_LEN = 8   # 回答至少 8 个字符


def _contains_jd(text: str) -> bool:
    """检查文本是否包含 JD 平台专属关键词。"""
    for word in JD_BLACKLIST:
        if word in text:
            return True
    return False


def _is_valid_faq(q: str, a: str, intent: str) -> bool:
    """质量过滤：JD 黑词 + 长度 + 纯语气词。"""
    # 1. JD 平台黑名单
    combined = q + a
    if _contains_jd(combined):
        return False
    # 2. JD 专属意图
    if intent in JD_INTENT_BLACKLIST:
        return False
    # 3. 长度过滤
    if len(q) < MIN_Q_LEN or len(a) < MIN_A_LEN:
        return False
    # 4. 纯语气词 / 无实质内容
    garbage_patterns = [
        r"^[嗯啊哦好是对行可]+[，。！？]*$",
        r"^谢谢[！。]*$",
        r"^好的[，。！]*$",
        r"^不客气[！。]*$",
    ]
    for pat in garbage_patterns:
        if re.match(pat, q):
            return False
    return True


# ═══════════════════════════════════════════════════════════════
# 14 域中文 → 英文映射
# ═══════════════════════════════════════════════════════════════
DOMAIN_CN_MAP = {
    "售后退款": "returns",
    "退货退款": "returns",
    "物流配送": "delivery",
    "快递物流": "delivery",
    "账户登录": "account",
    "账号密码": "account",
    "发票账单": "billing",
    "支付扣费": "billing",
    "订单查询": "order",
    "下单购买": "order",
    "商品破损": "tech_support",
    "技术故障": "tech_support",
    "投诉建议": "feedback",
    "意见反馈": "feedback",
    "售前咨询": "sales",
    "价格咨询": "sales",
    "人事HR": "hr",
    "员工福利": "hr",
    "IT支持": "it_support",
    "办公设备": "it_support",
    "产品使用": "product_support",
    "功能说明": "product_support",
    "服务中断": "outages",
    "系统故障": "outages",
    "客服咨询": "customer_service",
    "人工服务": "customer_service",
    "其他": "general",
}


def extract_faqs(input_dir: str, output_dir: str) -> int:
    """从 CSDS JSON 提取 FAQ 对，含 JD 过滤。"""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    faqs: list[dict] = []
    seen_texts: set[str] = set()
    total_qa = 0
    filtered_jd = 0
    filtered_len = 0

    for json_file in sorted(input_path.glob("*.json")):
        logger.info("Processing %s...", json_file.name)
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            logger.warning("%s is not a list, skipping", json_file.name)
            continue

        for item in data:
            qa_segments = item.get("QA", [])

            for seg in qa_segments:
                total_qa += 1
                q = seg.get("QueSumm", "").strip()
                a_long = seg.get("AnsSummLong", "").strip()
                a_short = seg.get("AnsSummShort", "").strip()
                intent = seg.get("intent", "")

                # Prefer longer answer
                a = a_long if len(a_long) > len(a_short) else a_short

                # 质量过滤
                if not _is_valid_faq(q, a, intent):
                    if _contains_jd(q + a) or intent in JD_INTENT_BLACKLIST:
                        filtered_jd += 1
                    else:
                        filtered_len += 1
                    continue

                # Dedup by text hash (q + first 200 chars of answer)
                text_hash = hashlib.md5((q + a[:200]).encode()).hexdigest()
                if text_hash in seen_texts:
                    continue
                seen_texts.add(text_hash)

                faqs.append({
                    "q": q,
                    "a": a,
                    "intent": intent,
                    "dialogue_id": item.get("DialogueID"),
                    "source": "csds",
                })

    # Save raw extraction
    raw_file = output_path / "csds_faq_raw.jsonl"
    with open(raw_file, "w", encoding="utf-8") as f:
        for faq in faqs:
            f.write(json.dumps(faq, ensure_ascii=False) + "\n")

    logger.info("Total QA segments: %d", total_qa)
    logger.info("  Filtered - JD content: %d", filtered_jd)
    logger.info("  Filtered - length/quality: %d", filtered_len)
    logger.info("  Kept (deduped): %d → %s", len(faqs), raw_file)
    return len(faqs)


def classify_domains(input_dir: str, output_dir: str, batch_size: int = 20) -> int:
    """用 SenseNova DeepSeek-V4 批量分类 FAQ 领域。"""
    input_path = Path(input_dir) / "csds_faq_raw.jsonl"
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        logger.error("Raw FAQ file not found: %s", input_path)
        return 0

    # Load FAQs
    faqs = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                faqs.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    logger.info("Classifying %d FAQs into 14 domains...", len(faqs))

    from openai import OpenAI

    SENSENOVA_KEYS = [
        "REDACTED_KEY",
        "REDACTED_KEY",
    ]
    key_idx = 0

    def _get_client():
        nonlocal key_idx
        key = SENSENOVA_KEYS[key_idx]
        key_idx = (key_idx + 1) % len(SENSENOVA_KEYS)
        return OpenAI(api_key=key, base_url="https://token.sensenova.cn/v1")

    classified = 0
    errors = 0

    domain_list_cn = [
        "售后退款", "物流配送", "账户登录", "发票账单", "订单查询",
        "技术故障", "投诉建议", "售前咨询", "人事HR", "IT支持",
        "产品使用", "服务中断", "客服咨询", "其他",
    ]
    domain_list_display = "\n".join(f"- {d}" for d in domain_list_cn)

    for i in range(0, len(faqs), batch_size):
        batch = faqs[i : i + batch_size]

        # Build prompt
        faq_lines = []
        for j, faq in enumerate(batch):
            faq_lines.append(f"[{j}] Q: {faq['q']}\n   A: {faq['a'][:100]}")

        prompt = f"""请为以下 {len(batch)} 条客服FAQ分类到最合适的领域。领域选项：
{domain_list_display}

每条FAQ输出一行JSON：{{"idx": 编号, "domain": "领域名"}}
只输出JSON行，不要任何解释。

FAQ列表：
{chr(10).join(faq_lines)}"""

        for attempt in range(3):
            try:
                client = _get_client()
                resp = client.chat.completions.create(
                    model="deepseek-v4-flash",
                    messages=[
                        {"role": "system", "content": "你是客服领域分类专家。只输出JSON，不要解释。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=2048,
                    timeout=120,
                )
                content = resp.choices[0].message.content or ""

                # Parse each line as JSON
                for line in content.strip().split("\n"):
                    line = line.strip()
                    if not line or not line.startswith("{"):
                        continue
                    try:
                        result = json.loads(line)
                        idx = result.get("idx")
                        domain_cn = result.get("domain", "其他")
                        if idx is not None and 0 <= idx < len(batch):
                            domain_en = DOMAIN_CN_MAP.get(domain_cn, "general")
                            batch[idx]["domain"] = domain_en
                            classified += 1
                    except json.JSONDecodeError:
                        continue
                break
            except Exception as e:
                if attempt == 2:
                    logger.error("Batch %d failed: %s", i, e)
                    errors += len(batch)
                else:
                    time.sleep(2)
        time.sleep(0.3)

        if (i + batch_size) % 500 == 0:
            logger.info("  Progress: %d/%d classified", classified, len(faqs))

    # Assign default domain to unclassified
    for faq in faqs:
        if "domain" not in faq:
            faq["domain"] = "general"

    # Save classified FAQs
    out_file = output_path / "faq_cn.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for faq in faqs:
            f.write(json.dumps(faq, ensure_ascii=False) + "\n")

    logger.info("Classified: %d classified, %d errors → %s", classified, errors, out_file)

    # Stats
    domain_counts: dict[str, int] = {}
    for faq in faqs:
        dom = faq.get("domain", "general")
        domain_counts[dom] = domain_counts.get(dom, 0) + 1

    for dom, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
        logger.info("  %s: %d", dom, count)

    return len(faqs)


def main():
    parser = argparse.ArgumentParser(description="Extract CSDS FAQ pairs for Chinese KB")
    parser.add_argument("--input", default="data/cn_raw/csds", help="CSDS JSON directory")
    parser.add_argument("--output", default="data/docs_cn", help="Output directory")
    parser.add_argument("--skip-classify", action="store_true", help="Skip LLM domain classification")
    args = parser.parse_args()

    t0 = time.perf_counter()

    # Step 1: Extract FAQ pairs with JD filtering
    logger.info("=" * 50)
    logger.info("  STEP 1: Extract + Filter FAQ pairs from CSDS")
    logger.info("=" * 50)
    count = extract_faqs(args.input, args.output)

    # Step 2: Classify domains via LLM
    if not args.skip_classify:
        logger.info("=" * 50)
        logger.info("  STEP 2: Classify FAQ domains via SenseNova LLM")
        logger.info("=" * 50)
        classify_domains(args.output, args.output)

    elapsed = time.perf_counter() - t0
    logger.info("Pipeline complete in %.1f seconds (%.0f min)", elapsed, elapsed / 60)


if __name__ == "__main__":
    main()
