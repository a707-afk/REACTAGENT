"""三层清洗管线：规则粗筛 → LLM 批量提炼 → 向量聚类去重。

流水线：
  1. 第一层：规则极速粗筛（纯 Python，CPU 分钟级）
  2. 第二层：智谱 API 批量提炼 FAQ（~30 分钟，约 20 元）
  3. 第三层：FAISS 向量聚类去重（GPU 分钟级）

输入：data/cn_raw/alics/*.jsonl + data/cn_raw/taobao_service/*.jsonl
输出：data/docs_cn/faq_cn.jsonl（6-8 万高质量 FAQ）

用法：
  python scripts/clean_cn_pipeline.py --input data/cn_raw --output data/docs_cn --stage all
  python scripts/clean_cn_pipeline.py --stage 1   # 仅粗筛
  python scripts/clean_cn_pipeline.py --stage 2   # 仅 LLM 提炼
  python scripts/clean_cn_pipeline.py --stage 3   # 仅去重
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
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── 第一层：规则粗筛 ──

# 平台黑名单（AliCS 重点是阿里系平台专属词）
PLATFORM_BLACKLIST = {
    "阿里妈妈", "直通车", "淘金币", "聚划算", "88VIP", "88会员",
    "淘宝客", "钻展", "品销宝", "超级推荐", "引力魔方",
    "天猫积分", "店铺券", "平台券", "双十一", "双11", "618",
    "淘工厂", "淘特", "闲鱼", "菜鸟", "菜鸟裹裹",
    "花呗", "借呗", "网商银行", "余额宝",
    # 广义平台词（跨平台通用但无售后价值）
    "用户协议", "隐私政策", "违法违规", "禁售",
}

# 无知识价值的短回复模式
SHORT_REPLY_PATTERNS = [
    re.compile(r"^(好[的的呢]?|嗯+[呢]?|哦+[了]?|额+|谢谢|感谢|行|对|是的|OK|ok|好的呢|收到|明白|了解|知道了)[\.。!！?？,，]*$"),
    re.compile(r"^(欢迎|welcome).*[!！]*$", re.IGNORECASE),
    re.compile(r"^(请问有什么|有什么可以|请问需要).*[?？]$"),
]

# 广告/促销话术特征词
AD_PATTERNS = [
    re.compile(r"(限时|秒杀|抢购|超低价|大促|清仓|爆款|热卖|包邮|满减|赠品|立减|直降)"),
    re.compile(r"(点击|关注|收藏|加购|下单|立即|马上|赶紧|手慢|错过).*(购买|抢|下单)"),
]


def _contains_platform_words(text: str) -> bool:
    for word in PLATFORM_BLACKLIST:
        if word in text:
            return True
    return False


def _is_short_noise(text: str) -> bool:
    if len(text) < 3:
        return True
    for pattern in SHORT_REPLY_PATTERNS:
        if pattern.match(text.strip()):
            return True
    return False


def _is_advertisement(text: str) -> bool:
    for pattern in AD_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _extract_qa_pairs(dialog_text: str) -> list[dict[str, str]]:
    """从单段对话中提取 user→agent QA 对。"""
    pairs: list[dict[str, str]] = []
    lines = dialog_text.strip().split("\n")
    current_user: str | None = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 识别角色
        if line.startswith(("客户：", "用户：", "买家：", "顾客：", "客户:", "用户:", "买家:", "客户", "用户", "买家")):
            current_user = re.sub(r"^(客户|用户|买家|顾客)[：:]", "", line).strip()
        elif line.startswith(("客服：", "商家：", "卖家：", "小蜜：", "客服:", "商家:", "客服", "商家")):
            agent_reply = re.sub(r"^(客服|商家|卖家|小蜜)[：:]", "", line).strip()
            if current_user and len(current_user) >= 3 and len(agent_reply) >= 5:
                pairs.append({"q": current_user, "a": agent_reply})
            current_user = None

    return pairs


def stage1_rule_filter(input_dir: str, output_dir: str) -> dict[str, int]:
    """第一层：规则极速粗筛。返回统计信息。"""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stats = {"total_dialogs": 0, "kept": 0, "filtered_platform": 0, "filtered_noise": 0, "filtered_ad": 0, "kept_pairs": 0}
    out_file = output_path / "stage1_filtered.jsonl"

    with open(out_file, "w", encoding="utf-8") as outf:
        for jsonl_file in input_path.rglob("*.jsonl"):
            logger.info("Processing %s...", jsonl_file.name)
            with open(jsonl_file, "r", encoding="utf-8") as inf:
                for line in inf:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    stats["total_dialogs"] += 1

                    # Extract dialog text
                    dialog = item.get("dialog") or item.get("text") or item.get("content") or ""
                    if not dialog:
                        continue

                    # Platform filter
                    if _contains_platform_words(dialog):
                        stats["filtered_platform"] += 1
                        continue

                    # Ad filter
                    if _is_advertisement(dialog):
                        stats["filtered_ad"] += 1
                        continue

                    # Noise filter
                    if _is_short_noise(dialog):
                        stats["filtered_noise"] += 1
                        continue

                    # Extract QA pairs
                    pairs = _extract_qa_pairs(dialog)
                    if not pairs:
                        continue

                    stats["kept"] += 1
                    stats["kept_pairs"] += len(pairs)

                    # Preserve domain/intent metadata if available
                    domain = item.get("domain") or item.get("intent") or ""
                    item_out = {
                        "dialog": dialog,
                        "pairs": pairs,
                        "domain": domain,
                        "source": item.get("source", jsonl_file.stem),
                    }
                    outf.write(json.dumps(item_out, ensure_ascii=False) + "\n")

    logger.info("Stage 1 results: %s", json.dumps(stats, indent=2, ensure_ascii=False))

    # Save stats
    with open(output_path / "stage1_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    return stats


# ── 第二层：智谱 API 批量提炼 ──

_EXTRACT_SYS_PROMPT = """你是售后FAQ提炼专家。根据下面一段客服对话，提炼标准和通用的售后知识。

任务：
1. 提炼客户最核心要解决的1个问题（精简成标准FAQ问句）
2. 提炼客服给出的完整、可复用的标准解决方案（剔除安抚语气词如"非常抱歉"、"感谢您的理解"，只留实操步骤和关键信息）
3. 分类领域：从以下14个选项中选择最匹配的一个：
   售后退款(returns)、物流配送(delivery)、账户登录(account)、发票账单(billing)、
   商品破损(tech_support)、保修投诉(feedback)、订单查询(order)、
   技术故障(tech_support)、投诉建议(feedback)、售前咨询(sales)、
   人事HR(hr)、IT支持(it_support)、产品使用(product_support)、其他(general)

约束：
- 不要任何电商平台专属内容（如京东、淘宝、优惠券、积分、会员等）
- 只保留全行业通用的售后知识
- 如果对话内容完全是平台专属或无法提炼通用知识，返回 {"skip": true, "reason": "平台专属"}

输出严格JSON格式：
{"q": "标准FAQ问句", "a": "完整标准解决方案", "domain": "英文domain名"}
或
{"skip": true, "reason": "跳过原因"}"""


def _call_zhipu_extract(dialogs: list[str], api_key: str, model: str = "glm-4-flash") -> list[dict]:
    """批量调用智谱 API 提炼 FAQ（每批 5-8 段对话）。"""
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
    )

    results: list[dict] = []
    batch_size = 5

    for i in range(0, len(dialogs), batch_size):
        batch = dialogs[i : i + batch_size]
        batch_text = "\n\n---\n\n".join(f"[对话 {j+1}]\n{d}" for j, d in enumerate(batch))

        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": _EXTRACT_SYS_PROMPT},
                        {"role": "user", "content": f"请逐条提炼以下{len(batch)}段对话，每段返回一个JSON对象，用换行分隔：\n\n{batch_text}"},
                    ],
                    temperature=0.1,
                    max_tokens=4096,
                    timeout=60,
                )
                content = resp.choices[0].message.content or ""

                # Parse each JSON line
                for line in content.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if obj.get("skip"):
                            results.append({"skip": True, "reason": obj.get("reason", "")})
                        elif obj.get("q") and obj.get("a"):
                            obj["domain"] = obj.get("domain", "general")
                            results.append(obj)
                        else:
                            results.append({"skip": True, "reason": "empty q/a"})
                    except json.JSONDecodeError:
                        results.append({"skip": True, "reason": "json parse error"})

                break
            except Exception as e:
                if attempt == 2:
                    logger.error("API call failed after 3 attempts: %s", e)
                    results.extend([{"skip": True, "reason": str(e)}] * len(batch))
                else:
                    time.sleep(2 ** attempt)

        time.sleep(0.1)  # Rate limit buffer

    return results


def stage2_llm_extract(input_dir: str, output_dir: str) -> dict[str, int]:
    """第二层：智谱 API 批量提炼。"""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("ZHIPUAI_API_KEY") or os.environ.get("ZHIPU_API_KEY")
    if not api_key:
        logger.error("ZHIPUAI_API_KEY not set. Stage 2 requires API key.")
        return {"error": "no_api_key"}

    stats = {"total_faqs": 0, "extracted": 0, "skipped": 0}
    out_file = output_path / "stage2_faq_raw.jsonl"

    stage1_file = input_path / "stage1_filtered.jsonl"
    if not stage1_file.exists():
        logger.error("Stage 1 output not found: %s", stage1_file)
        return {"error": "stage1_not_found"}

    all_dialogs: list[str] = []
    with open(stage1_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
                dialog = item.get("dialog", "")
                if dialog:
                    all_dialogs.append(dialog)
            except json.JSONDecodeError:
                continue

    logger.info("Stage 2: processing %d filtered dialogs via ZhiPu API", len(all_dialogs))
    results = _call_zhipu_extract(all_dialogs, api_key)

    with open(out_file, "w", encoding="utf-8") as f:
        for r in results:
            if not r.get("skip"):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                stats["extracted"] += 1
            else:
                stats["skipped"] += 1
            stats["total_faqs"] += 1

    logger.info("Stage 2 results: %s", json.dumps(stats, indent=2, ensure_ascii=False))
    return stats


# ── 第三层：向量聚类去重 ──

def stage3_dedup(input_dir: str, output_dir: str, sim_threshold: float = 0.88) -> dict[str, int]:
    """第三层：FAISS 向量聚类去重。"""
    import numpy as np

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stage2_file = input_path / "stage2_faq_raw.jsonl"
    if not stage2_file.exists():
        logger.error("Stage 2 output not found: %s", stage2_file)
        return {"error": "stage2_not_found"}

    # Load all FAQs
    faqs: list[dict] = []
    with open(stage2_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                faqs.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    logger.info("Stage 3: loading %d FAQs for dedup", len(faqs))

    if len(faqs) < 2:
        out_file = output_path / "faq_cn.jsonl"
        with open(out_file, "w", encoding="utf-8") as f:
            for faq in faqs:
                f.write(json.dumps(faq, ensure_ascii=False) + "\n")
        return {"total": len(faqs), "kept": len(faqs), "removed": 0}

    # Embed all questions
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    except Exception:
        logger.warning("bge-small-zh not available, using paraphrase-multilingual")
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    questions = [faq.get("q", "") for faq in faqs]
    logger.info("Embedding %d questions...", len(questions))

    batch_size = 256
    embeddings = model.encode(questions, batch_size=batch_size, show_progress_bar=True, device="cuda")

    # FAISS IVF clustering
    import faiss
    dim = embeddings.shape[1]
    nlist = min(4096, max(4, int(np.sqrt(len(questions)))))
    quantizer = faiss.IndexFlatIP(dim)
    index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)

    # Normalize for cosine similarity
    faiss.normalize_L2(embeddings)

    if len(questions) < nlist:
        # Too few for IVF, use flat index
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
    else:
        index.train(embeddings)
        index.add(embeddings)

    # Find near-duplicates
    k = min(50, len(questions))
    distances, indices = index.search(embeddings, k)

    # Greedy clustering
    kept: set[int] = set()
    removed: set[int] = set()
    processed: set[int] = set()

    for i in range(len(questions)):
        if i in processed:
            continue
        kept.add(i)
        processed.add(i)

        # Find all similar items
        for j_idx in range(1, k):
            j = int(indices[i][j_idx])
            if j < 0 or j >= len(questions):
                continue
            if j in processed:
                continue
            sim = float(distances[i][j_idx])
            if sim > sim_threshold:
                removed.add(j)
                processed.add(j)

    kept_faqs = [faqs[i] for i in sorted(kept)]
    logger.info("Stage 3: kept %d / %d (removed %d duplicates)", len(kept_faqs), len(faqs), len(removed))

    # Write output
    out_file = output_path / "faq_cn.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for faq in kept_faqs:
            f.write(json.dumps(faq, ensure_ascii=False) + "\n")

    # Write stats
    stats = {"total": len(faqs), "kept": len(kept_faqs), "removed": len(removed), "dedup_ratio": round(len(removed) / max(len(faqs), 1), 3)}
    with open(output_path / "stage3_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    logger.info("Stage 3 complete: %s", json.dumps(stats, indent=2, ensure_ascii=False))
    return stats


# ── 入口 ──

def main():
    parser = argparse.ArgumentParser(description="3-layer Chinese CS data cleaning pipeline")
    parser.add_argument("--input", default="data/cn_raw", help="Raw data directory")
    parser.add_argument("--output", default="data/docs_cn", help="Output directory")
    parser.add_argument("--stage", default="all", choices=["1", "2", "3", "all"])
    parser.add_argument("--sim-threshold", type=float, default=0.88, help="Dedup similarity threshold")
    args = parser.parse_args()

    t0 = time.perf_counter()

    if args.stage in ("1", "all"):
        logger.info("=" * 50)
        logger.info("  STAGE 1: Rule-based filtering")
        logger.info("=" * 50)
        stage1_rule_filter(args.input, args.output)

    if args.stage in ("2", "all"):
        logger.info("=" * 50)
        logger.info("  STAGE 2: LLM-based FAQ extraction")
        logger.info("=" * 50)
        stage2_llm_extract(args.output, args.output)

    if args.stage in ("3", "all"):
        logger.info("=" * 50)
        logger.info("  STAGE 3: Vector clustering dedup")
        logger.info("=" * 50)
        stage3_dedup(args.output, args.output, sim_threshold=args.sim_threshold)

    elapsed = time.perf_counter() - t0
    logger.info("Pipeline complete in %.1f seconds", elapsed)


if __name__ == "__main__":
    main()
