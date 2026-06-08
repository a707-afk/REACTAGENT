"""Download customer service datasets from HuggingFace and save as JSONL.

Data sources:
  - Tobi-Bueck/customer-support-tickets  (61K rows, train split)
  - bitext/Bitext-customer-support-llm-chatbot-training-dataset (27K rows, train split)

Output:
  - data/raw/tobi_bueck_tickets.jsonl    (~53 MB, 61K rows)
  - data/raw/bitext_cs_qna.jsonl         (~19 MB, 27K rows)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def download_tobi_bueck(out_path: Path) -> int:
    """Download Tobi-Bueck/customer-support-tickets (61K tickets)."""
    from datasets import load_dataset

    print("[1/2] Downloading Tobi-Bueck/customer-support-tickets ...")
    ds = load_dataset("Tobi-Bueck/customer-support-tickets", split="train")
    n = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for row in ds:
            obj = {
                "source": "tobi_bueck",
                "queue": str(row.get("queue", "") or ""),
                "priority": str(row.get("priority", "") or ""),
                "language": str(row.get("language", "") or ""),
                "subject": str(row.get("subject", "") or ""),
                "body": str(row.get("body", "") or ""),
                "answer": str(row.get("answer", "") or ""),
                "type": str(row.get("type", "") or ""),
                "version": row.get("version", ""),
            }
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            n += 1
            if n % 10000 == 0:
                print(f"  ... {n} rows")
    print(f"  Done: {n} rows written to {out_path}")
    return n


def download_bitext_cs(out_path: Path) -> int:
    """Download bitext/Bitext-customer-support-llm-chatbot-training-dataset (27K Q&A)."""
    from datasets import load_dataset

    print("\n[2/2] Downloading bitext/Bitext-customer-support-llm-chatbot-training-dataset ...")
    ds = load_dataset(
        "bitext/Bitext-customer-support-llm-chatbot-training-dataset",
        split="train"
    )
    n = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for row in ds:
            obj = {
                "source": "bitext",
                "flags": str(row.get("flags", "") or ""),
                "instruction": str(row.get("instruction", "") or ""),
                "category": str(row.get("category", "") or ""),
                "intent": str(row.get("intent", "") or ""),
                "response": str(row.get("response", "") or ""),
            }
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            n += 1
            if n % 10000 == 0:
                print(f"  ... {n} rows")
    print(f"  Done: {n} rows written to {out_path}")
    return n


def main() -> None:
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    tobi_path = raw_dir / "tobi_bueck_tickets.jsonl"
    bitext_path = raw_dir / "bitext_cs_qna.jsonl"

    if tobi_path.exists():
        print(f"Tobi-Bueck already exists: {tobi_path} ({tobi_path.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        download_tobi_bueck(tobi_path)

    if bitext_path.exists():
        print(f"Bitext already exists: {bitext_path} ({bitext_path.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        download_bitext_cs(bitext_path)

    print(f"\nAll done. Data in {raw_dir}/")


if __name__ == "__main__":
    main()
