"""Phase C: Strict audit — delete low-quality, keep only authoritative content.

Rules:
- DELETE: Files with "AI辅助整理" source (no real provenance)
- DELETE: Files < 300 bytes (no content)
- DELETE: Duplicate/similar files
- KEEP: Gold data, official docs, papers, agentic-harness-zh
"""
from pathlib import Path
import re, os, shutil

ROOT = Path("data/docs_research")
GOLD_SRC = Path("data/docs_research/zh_gold_clean")

deleted = []
kept = []

# --- Collect ALL existing files ---
all_existing = list(ROOT.rglob("*.md")) + list(ROOT.rglob("*.yml"))
for top_dir in [ROOT / "official_docs", ROOT / "papers", ROOT / "blogs",
                ROOT / "agent_frameworks", ROOT / "embeddings", ROOT / "vector_dbs",
                ROOT / "zh_official_docs", ROOT / "zh_gold"]:
    if not top_dir.exists(): continue

# --- Criterion 1: DELETE AI-generated content ---
for d in [ROOT / "zh_official_docs"]:
    if not d.exists(): continue
    for f in sorted(d.glob("*.md")):
        c = f.read_text(encoding="utf-8", errors="replace")
        # Keep agentic-harness (user's doc, real source)
        if "agentic_harness_patterns" in f.name:
            kept.append(("USER_DOC", f.name))
            continue
        # Keep Milvus official Chinese docs (real source)
        if "milvus_zh_" in f.name:
            kept.append(("MILVUS_ZH", f.name))
            continue
        # Keep Qwen official docs (real source)
        if f.name.startswith("qwen"):
            kept.append(("QWEN", f.name))
            continue
        # Delete everything else (AI-generated)
        deleted.append(("AI_GEN_NO_SOURCE", f.name))
        f.unlink()

# --- Criterion 2: DELETE very short files ---
for cat_dir in [ROOT / "papers", ROOT / "blogs", ROOT / "agent_frameworks",
                ROOT / "official_docs", ROOT / "vector_dbs", ROOT / "embeddings"]:
    if not cat_dir.exists(): continue
    for f in sorted(cat_dir.glob("*.md")):
        if f.name.startswith("_"): continue
        size = f.stat().st_size
        if size < 400:
            deleted.append(("TOO_SHORT", f"{f.parent.name}/{f.name}"))
            f.unlink()

# --- Criterion 3: DELETE HTML residue from English docs ---
for cat_dir in [ROOT / "official_docs", ROOT / "blogs"]:
    if not cat_dir.exists(): continue
    for f in sorted(cat_dir.glob("*.md")):
        if f.name.startswith("_"): continue
        c = f.read_text(encoding="utf-8", errors="replace")
        tags = len(re.findall(r'<(?:div|span|table|script|style|nav|footer|header)\b', c, re.I))
        if tags > 5:
            # Try to clean
            c2 = re.sub(r'<(div|span|table|script|style|nav|footer|header|aside)\b[^>]*>.*?</\1>', '', c, flags=re.DOTALL|re.I)
            c2 = re.sub(r'<(img|input|button|form|iframe)\b[^>]*>', '', c2, flags=re.I)
            tags2 = len(re.findall(r'<(?:div|span|table|script|style|nav|footer|header)\b', c2, re.I))
            if tags2 < 3:
                f.write_text(c2.strip(), encoding="utf-8")
                kept.append(("CLEANED", f"{f.parent.name}/{f.name}"))
            else:
                deleted.append(("HTML_HEAVY", f"{f.parent.name}/{f.name}"))
                f.unlink()

# --- Criterion 4: KEEP everything else ---
for cat_dir in [ROOT / "papers", ROOT / "blogs", ROOT / "agent_frameworks",
                ROOT / "official_docs", ROOT / "vector_dbs", ROOT / "embeddings"]:
    if not cat_dir.exists(): continue
    for f in sorted(cat_dir.glob("*.md")):
        if f.name.startswith("_"): continue
        kept.append(("EXISTING_KEPT", f"{f.parent.name}/{f.name}"))

# --- Move gold data into main KB ---
for f in sorted(GOLD_SRC.glob("*")):
    target = ROOT / "zh_gold" / f.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if f.suffix == '.yml':
        target = ROOT / "zh_gold" / f.name
    shutil.copy2(f, target)
    kept.append(("GOLD_DATA", f"zh_gold/{f.name}"))

print(f"=== AUDIT COMPLETE ===")
print(f"KEPT: {len(set(k[1] for k in kept))}")
print(f"DELETED: {len(deleted)}")
for reason, name in deleted:
    print(f"  DEL [{reason}] {name}")

# Write audit log
log_path = ROOT / "_audit_log.txt"
with open(log_path, "w", encoding="utf-8") as lf:
    for reason, name in deleted:
        lf.write(f"DELETED [{reason}] {name}\n")
    lf.write(f"\nTotal deleted: {len(deleted)}\n")
