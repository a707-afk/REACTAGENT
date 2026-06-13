#!/usr/bin/env python3
"""Annotate gold_chunk_ids for all RAG eval JSONL files.

For FAQ-style markdown knowledge base, each Q&A pair is a natural chunk.
Chunk ID format: {file_name}#Q{n} (1-indexed).

This script:
1. Parses each FAQ markdown file to build a query→chunk_id mapping
2. For each eval case, matches answer_facts against FAQ entries
3. Fills gold_chunk_ids with matching chunk IDs
4. Overwrites the JSONL files in-place

Usage:
    python scripts/annotate_gold_chunks.py          # annotate all
    python scripts/annotate_gold_chunks.py --dry-run # preview only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "data" / "eval" / "rag"
DOCS_DIR = ROOT / "data" / "docs_ecom"

# Files that should have gold_chunk_ids annotated
ANNOTATABLE_FILES = ["faq.jsonl", "permission.jsonl", "policy.jsonl", "multi_turn.jsonl"]
# no_answer.jsonl: gold_chunk_ids should remain [] (no answer expected)
# pdf_table.jsonl: corrupted encoding, skip
# complex_reasoning.jsonl: references non-existent docs, skip


def parse_faq_chunks(md_path: Path) -> list[dict]:
    """Parse a FAQ markdown file into chunks with IDs.

    Returns list of {"chunk_id": str, "question": str, "answer": str}.
    """
    text = md_path.read_text(encoding="utf-8")
    file_name = md_path.name

    # Split by FAQ Q&A pattern: ## Q: ... A: ...
    # Each chunk starts with ## Q:
    chunks = []
    # Pattern: ## Q: <question>\nA: <answer>
    parts = re.split(r'(?=^## Q:)', text, flags=re.MULTILINE)

    q_index = 0
    for part in parts:
        part = part.strip()
        if not part or not part.startswith("## Q:"):
            continue
        q_index += 1

        # Extract question text
        q_match = re.match(r'^## Q:\s*(.+?)(?:\n|$)', part)
        question = q_match.group(1).strip() if q_match else ""

        # Extract answer text
        a_match = re.search(r'^A:\s*(.+?)(?=\n## Q:|\Z)', part, re.DOTALL | re.MULTILINE)
        answer = a_match.group(1).strip() if a_match else ""

        chunk_id = f"{file_name}#Q{q_index}"
        chunks.append({
            "chunk_id": chunk_id,
            "question": question,
            "answer": answer,
            "answer_lower": answer.lower(),
            "question_lower": question.lower(),
        })

    return chunks


def build_faq_index(docs_dir: Path) -> dict[str, list[dict]]:
    """Build file_name → list of chunks mapping."""
    index = {}
    for md_path in sorted(docs_dir.glob("*.md")):
        chunks = parse_faq_chunks(md_path)
        index[md_path.name] = chunks
    return index


def match_chunk_ids(case: dict, faq_index: dict[str, list[dict]]) -> list[str]:
    """Find matching chunk IDs for a case based on gold_document_ids and answer_facts.

    Strategy:
    1. For each answer_fact, find the best-matching chunk via keyword overlap.
    2. If no facts match well, fallback to query-keyword matching (lower threshold).
    3. Deduplicate and limit to max 4 chunks total.
    """
    gold_docs = case.get("gold_document_ids", [])
    answer_facts = case.get("answer_facts", [])
    MAX_CHUNKS_PER_FACT = 2
    MIN_SCORE_FACT = 0.5
    MIN_SCORE_QUERY = 0.4
    MAX_TOTAL_CHUNKS = 4

    if not gold_docs:
        return []

    query = case.get("query", "").lower()
    query_keywords = [w for w in re.split(r'[，。、：；！？\s,.;!?]+', query) if len(w) >= 2]

    scored: dict[str, float] = {}

    for doc_id in gold_docs:
        chunks = faq_index.get(doc_id, [])
        if not chunks:
            continue

        for chunk in chunks:
            best_score = 0.0

            # Strategy 1: answer_facts keyword matching
            if answer_facts:
                for fact in answer_facts:
                    fact_lower = fact.lower()
                    fact_keywords = [w for w in re.split(r'[，。、：；！？\s,.;!?]+', fact_lower) if len(w) >= 2]
                    if fact_keywords:
                        keyword_hits = sum(1 for kw in fact_keywords if kw in chunk["answer_lower"])
                        keyword_score = keyword_hits / len(fact_keywords)
                        # For short facts (<=2 keywords), require at least 1 hit with lower threshold
                        if len(fact_keywords) <= 2 and keyword_hits >= 1:
                            keyword_score = max(keyword_score, 0.5)
                        best_score = max(best_score, keyword_score)

            # Strategy 2: query keyword matching (fallback when facts are short/missing)
            if query_keywords:
                q_hits = sum(1 for kw in query_keywords if kw in chunk["question_lower"] or kw in chunk["answer_lower"])
                q_score = q_hits / len(query_keywords)
                # Query match: use lower threshold since it's less precise
                if q_score >= MIN_SCORE_QUERY:
                    best_score = max(best_score, q_score * 0.85)

            # Apply threshold based on which strategy dominated
            threshold = MIN_SCORE_FACT if answer_facts else MIN_SCORE_QUERY
            if best_score >= threshold:
                cid = chunk["chunk_id"]
                if cid not in scored or best_score > scored[cid]:
                    scored[cid] = best_score

    # Return sorted by score descending, capped at MAX_TOTAL_CHUNKS
    return [cid for cid, _ in sorted(scored.items(), key=lambda x: -x[1])][:MAX_TOTAL_CHUNKS]


def annotate_file(jsonl_path: Path, faq_index: dict[str, list[dict]], dry_run: bool = False) -> int:
    """Annotate gold_chunk_ids for a single JSONL file. Returns count of annotated cases."""
    cases = []
    annotated = 0

    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    for case in cases:
        new_ids = match_chunk_ids(case, faq_index)
        # Always overwrite: re-annotate with stricter matching
        case["gold_chunk_ids"] = new_ids
        if new_ids:
            annotated += 1

    if not dry_run:
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for case in cases:
                f.write(json.dumps(case, ensure_ascii=False) + "\n")

    return annotated


def main():
    parser = argparse.ArgumentParser(description="Annotate gold_chunk_ids for RAG eval datasets")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    print("Building FAQ chunk index from", DOCS_DIR)
    faq_index = build_faq_index(DOCS_DIR)

    total_chunks = sum(len(chunks) for chunks in faq_index.values())
    print(f"Indexed {total_chunks} chunks across {len(faq_index)} files:")
    for fname, chunks in faq_index.items():
        print(f"  {fname}: {len(chunks)} chunks")

    print()
    total_annotated = 0
    for fname in ANNOTATABLE_FILES:
        path = EVAL_DIR / fname
        if not path.exists():
            print(f"  SKIP {fname} (not found)")
            continue
        count = annotate_file(path, faq_index, dry_run=args.dry_run)
        total_annotated += count
        status = "DRY-RUN" if args.dry_run else "WRITTEN"
        print(f"  {fname}: {count} cases annotated [{status}]")

    print(f"\nTotal annotated: {total_annotated} cases")

    # Validate: show some examples
    print("\n--- Sample annotations ---")
    for fname in ANNOTATABLE_FILES:
        path = EVAL_DIR / fname
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 3:
                    break
                case = json.loads(line.strip())
                if case.get("gold_chunk_ids"):
                    print(f"  {case['id']}: gold_chunk_ids = {case['gold_chunk_ids']}")
                    break


if __name__ == "__main__":
    main()
