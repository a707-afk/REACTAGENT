"""Preprocess raw customer service datasets into unified document format for RAG ingestion.

Converts Tobi-Bueck tickets + Bitext Q&A + existing enterprise_ai_ops docs into
llama_index Document objects with consistent metadata (domain, subdomain, source, etc.),
then writes them as JSONL suitable for direct ingestion.

Output:
  - data/docs_cs/corpus.jsonl   (unified document corpus, ~90K documents)
  - data/docs_cs/meta.json      (basic stats)
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


# Map Tobi-Bueck queue names to domain slugs
QUEUE_TO_DOMAIN: dict[str, str] = {
    "Technical Support": "tech_support",
    "Customer Service": "customer_service",
    "Billing and Payments": "billing",
    "Product Support": "product_support",
    "IT Support": "it_support",
    "Returns and Exchanges": "returns",
    "Sales and Pre-Sales": "sales",
    "Human Resources": "hr",
    "Service Outages and Maintenance": "outages",
    "General Inquiry": "general",
}

# Map Bitext categories to domain slugs
CATEGORY_TO_DOMAIN: dict[str, str] = {
    "ACCOUNT": "account",
    "CANCELLATION_FEE": "billing",
    "DELIVERY": "delivery",
    "FEEDBACK": "feedback",
    "INVOICE": "billing",
    "NEWSLETTER": "marketing",
    "ORDER": "order",
    "PAYMENT": "billing",
    "REFUND": "billing",
    "SHIPPING_ADDRESS": "delivery",
}

# Priority levels
PRIORITY_MAP = {"low": "low", "medium": "medium", "high": "high", "critical": "critical"}


def _clean_text(text: str) -> str:
    """Basic text cleaning: strip, collapse whitespace, remove control chars."""
    if not text:
        return ""
    text = " ".join(text.split())
    # Remove ASCII control characters except common ones
    return "".join(ch for ch in text if ch.isprintable() or ch in "\n\r\t")


def process_tobi_bueck(input_path: Path) -> list[dict]:
    """Convert Tobi-Bueck tickets into structured documents.

    Each ticket becomes a document with subject+body as text and answer as a separate field.
    """
    docs = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)

            subject = _clean_text(row.get("subject", ""))
            body = _clean_text(row.get("body", ""))
            answer = _clean_text(row.get("answer", ""))
            queue = str(row.get("queue", "") or "")
            ticket_type = str(row.get("type", "") or "")
            priority = str(row.get("priority", "") or "").lower()
            language = str(row.get("language", "") or "").lower()

            # Build document text: subject + body (customer side)
            doc_text = f"# {subject}\n\n{body}" if subject else body
            if not doc_text.strip():
                continue

            domain = QUEUE_TO_DOMAIN.get(queue, "general")
            subdomain = queue.replace(" ", "_").lower()

            doc = {
                "text": doc_text,
                "metadata": {
                    "source": "tobi_bueck",
                    "domain": domain,
                    "subdomain": subdomain,
                    "queue": queue,
                    "ticket_type": ticket_type,
                    "priority": PRIORITY_MAP.get(priority, "medium"),
                    "language": language,
                    "has_answer": bool(answer.strip()),
                    "tenant_id": "cs-agent-default",
                    "security_level": "internal",
                    "audience": "support_agent",
                    "status": "active",
                    "version": str(row.get("version", "1")),
                },
                "answer": answer,
            }
            docs.append(doc)
    return docs


def process_bitext(input_path: Path) -> list[dict]:
    """Convert Bitext Q&A pairs into structured documents.

    Each Q&A becomes a document with instruction as text and response as answer.
    """
    docs = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)

            instruction = _clean_text(row.get("instruction", ""))
            response = _clean_text(row.get("response", ""))
            category = str(row.get("category", "") or "")
            intent = str(row.get("intent", "") or "")
            flags = str(row.get("flags", "") or "")

            if not instruction.strip():
                continue

            domain = CATEGORY_TO_DOMAIN.get(category, "general")
            subdomain = f"{category}_{intent}".lower()

            # Detect language variation from flags
            has_colloquial = "Q" in flags
            has_typos = "Z" in flags
            has_offensive = "W" in flags

            doc = {
                "text": f"# Customer Question ({category}: {intent})\n\n{instruction}",
                "metadata": {
                    "source": "bitext",
                    "domain": domain,
                    "subdomain": subdomain,
                    "category": category,
                    "intent": intent,
                    "flags": flags,
                    "has_colloquial": has_colloquial,
                    "has_typos": has_typos,
                    "has_offensive": has_offensive,
                    "language": "en",
                    "has_answer": bool(response.strip()),
                    "tenant_id": "cs-agent-default",
                    "security_level": "internal",
                    "audience": "support_agent",
                    "status": "active",
                    "version": "1",
                },
                "answer": response,
            }
            docs.append(doc)
    return docs


def process_enterprise_docs(docs_dir: Path) -> list[dict]:
    """Read existing enterprise_ai_ops markdown documents."""
    docs = []
    if not docs_dir.is_dir():
        print(f"  [skip] enterprise docs dir not found: {docs_dir}")
        return docs

    for md_file in docs_dir.rglob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
            text = _clean_text(text)
            if not text.strip():
                continue

            # Determine domain from directory structure
            rel = md_file.relative_to(docs_dir)
            parts = rel.parts
            domain = parts[0] if len(parts) > 1 else "general"
            subdomain = parts[1] if len(parts) > 2 else domain

            doc = {
                "text": f"# {md_file.stem}\n\n{text}",
                "metadata": {
                    "source": "enterprise_ai_ops",
                    "domain": domain,
                    "subdomain": subdomain,
                    "file_name": md_file.name,
                    "file_path": str(rel),
                    "tenant_id": "corp-default",
                    "security_level": "internal",
                    "audience": "all",
                    "status": "active",
                    "version": "1",
                },
                "answer": "",
            }
            docs.append(doc)
        except Exception as e:
            print(f"  [warn] failed to read {md_file}: {e}")

    return docs


def deduplicate(docs: list[dict]) -> list[dict]:
    """Remove near-duplicate documents by text hash."""
    seen = set()
    unique = []
    for doc in docs:
        text_sig = hash(doc["text"][:200])
        if text_sig in seen:
            continue
        seen.add(text_sig)
        unique.append(doc)
    return unique


def main() -> None:
    raw_dir = ROOT / "data" / "raw"
    out_dir = ROOT / "data" / "docs_cs"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_docs: list[dict] = []

    # 1. Tobi-Bueck tickets
    tobi_path = raw_dir / "tobi_bueck_tickets.jsonl"
    if tobi_path.exists():
        print(f"[1/3] Processing Tobi-Bueck tickets from {tobi_path} ...")
        docs = process_tobi_bueck(tobi_path)
        print(f"  -> {len(docs)} documents")
        all_docs.extend(docs)
    else:
        print(f"[1/3] Tobi-Bueck not found at {tobi_path}; skipping")

    # 2. Bitext Q&A
    bitext_path = raw_dir / "bitext_cs_qna.jsonl"
    if bitext_path.exists():
        print(f"\n[2/3] Processing Bitext Q&A from {bitext_path} ...")
        docs = process_bitext(bitext_path)
        print(f"  -> {len(docs)} documents")
        all_docs.extend(docs)
    else:
        print(f"[2/3] Bitext not found at {bitext_path}; skipping")

    # 3. Existing enterprise docs
    enterprise_dir = ROOT / "data" / "docs" / "enterprise_ai_ops"
    print(f"\n[3/3] Processing enterprise docs from {enterprise_dir} ...")
    docs = process_enterprise_docs(enterprise_dir)
    print(f"  -> {len(docs)} documents")
    all_docs.extend(docs)

    # Deduplicate
    print(f"\n[Dedup] Before: {len(all_docs)} docs")
    all_docs = deduplicate(all_docs)
    print(f"[Dedup] After:  {len(all_docs)} docs")

    # Write corpus JSONL
    corpus_path = out_dir / "corpus.jsonl"
    print(f"\nWriting corpus to {corpus_path} ...")
    with open(corpus_path, "w", encoding="utf-8") as f:
        for doc in all_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    # Stats
    domains = {}
    sources = {}
    for doc in all_docs:
        dom = doc["metadata"]["domain"]
        src = doc["metadata"]["source"]
        domains[dom] = domains.get(dom, 0) + 1
        sources[src] = sources.get(src, 0) + 1

    meta = {
        "total_documents": len(all_docs),
        "domains": dict(sorted(domains.items(), key=lambda x: -x[1])),
        "sources": sources,
    }
    meta_path = out_dir / "meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Metadata written to {meta_path}")
    print(f"\n=== Summary ===")
    print(f"Total: {len(all_docs)} documents")
    print(f"Sources: {json.dumps(sources, indent=2)}")
    print(f"Domains: {json.dumps(dict(sorted(domains.items(), key=lambda x: -x[1])), indent=2)}")

    # Also export to standard docs format (directory structure)
    print(f"\nCorpus ready for indexing: {corpus_path}")
    print(f"  File size: {corpus_path.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
