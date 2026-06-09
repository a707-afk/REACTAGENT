"""下载中文客服数据集：AliCS + Taobao-Service-Dialogue。

数据源：
  - AliCS: HuggingFace / ModelScope 阿里电商客服对话集（20 万+对话）
  - Taobao-Service-Dialogue: 淘宝轻量化对话集（4.7 万，带意图标注）

用法：
  python scripts/download_cn_datasets.py --data-dir data/cn_raw
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def download_alics(output_dir: Path) -> int:
    """下载 AliCS 数据集。优先从 ModelScope，fallback 到 HuggingFace。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    alics_dir = output_dir / "alics"
    alics_dir.mkdir(exist_ok=True)

    count = 0

    # Try ModelScope first (faster in China)
    try:
        from modelscope.msdatasets import MsDataset
        logger.info("Downloading AliCS from ModelScope...")
        ds = MsDataset.load("iic/AliCS", split="train")
        output_file = alics_dir / "alics.jsonl"
        with open(output_file, "w", encoding="utf-8") as f:
            for item in ds:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                count += 1
        logger.info("AliCS: downloaded %d dialogues from ModelScope", count)
        return count
    except Exception as e:
        logger.warning("ModelScope download failed: %s, trying HuggingFace...", e)

    # Fallback to HuggingFace
    try:
        from datasets import load_dataset
        logger.info("Downloading AliCS from HuggingFace (iic/AliCS)...")
        ds = load_dataset("iic/AliCS", split="train", trust_remote_code=True)
        output_file = alics_dir / "alics.jsonl"
        with open(output_file, "w", encoding="utf-8") as f:
            for item in ds:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                count += 1
        logger.info("AliCS: downloaded %d dialogues from HuggingFace", count)
        return count
    except Exception as e:
        logger.error("AliCS: all sources failed: %s", e)
        return 0


def download_taobao_service(output_dir: Path) -> int:
    """下载 Taobao-Service-Dialogue 数据集。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_dir = output_dir / "taobao_service"
    ts_dir.mkdir(exist_ok=True)

    count = 0
    try:
        from datasets import load_dataset
        logger.info("Downloading Taobao-Service-Dialogue from HuggingFace...")
        # The dataset might be under different names
        for ds_name in [
            "shibing624/nlp_zh",
            "qgyd2021/taobao_service_dialogue",
        ]:
            try:
                ds = load_dataset(ds_name, split="train", trust_remote_code=True)
                output_file = ts_dir / "taobao_service.jsonl"
                with open(output_file, "w", encoding="utf-8") as f:
                    for item in ds:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                        count += 1
                logger.info("Taobao-Service: downloaded %d dialogues from %s", count, ds_name)
                return count
            except Exception:
                continue
        logger.warning("Taobao-Service: standard names not found")
    except Exception as e:
        logger.warning("Taobao-Service: HuggingFace download failed: %s", e)

    # If HuggingFace fails, try downloading a sample directly
    logger.info("Creating sample Taobao-Service dataset for testing...")
    sample_data = [
        {"dialog": "客户：我的快递到哪了？\n客服：请提供您的订单号，我帮您查询物流信息。", "domain": "物流配送", "intent": "物流查询"},
        {"dialog": "客户：收到的东西是坏的，我要退货！\n客服：非常抱歉给您带来不好的体验。请您拍照上传商品破损照片，我会为您申请退货退款。", "domain": "售后退款", "intent": "破损退货"},
        {"dialog": "客户：为什么自动扣了我两次钱？\n客服：我查一下您的账单记录。请稍等...您好，系统确实出现了重复扣款，我会为您申请退款，3-5个工作日到账。", "domain": "售后退款", "intent": "重复扣款"},
    ]
    output_file = ts_dir / "taobao_service_sample.jsonl"
    with open(output_file, "w", encoding="utf-8") as f:
        for item in sample_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    logger.info("Created %d sample dialogues", len(sample_data))
    return len(sample_data)


def main():
    parser = argparse.ArgumentParser(description="Download Chinese CS datasets")
    parser.add_argument("--data-dir", default="data/cn_raw", help="Output directory")
    parser.add_argument("--skip-alics", action="store_true")
    parser.add_argument("--skip-taobao", action="store_true")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    logger.info("Target directory: %s", data_dir.resolve())

    total = 0
    if not args.skip_alics:
        total += download_alics(data_dir)
    if not args.skip_taobao:
        total += download_taobao_service(data_dir)

    logger.info("Total dialogues downloaded: %d", total)
    logger.info("Data saved to %s", data_dir.resolve())


if __name__ == "__main__":
    main()
