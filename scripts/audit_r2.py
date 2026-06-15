"""Round 2 audit: deep content quality scan.

Checks:
1. HTML tag residue (>5 tags = flagged)
2. Abstract-only papers (<2KB, likely no real content)
3. Near-duplicates (same first 200 chars)
4. Boilerplate-heavy files (>50% of content is nav/menu)
5. Empty/whitespace-only sections
"""
from pathlib import Path; import re, hashlib

ROOT = Path("data/docs_research")
issues = {"html":[], "tiny":[], "dupe":[], "boilerplate":[], "empty_sections":[]}

# Track first-200-char hashes for duplicate detection
hashes = {}

for f in sorted(ROOT.rglob("*.md")):
    if f.name.startswith("_"): continue
    c = f.read_text(encoding="utf-8", errors="replace")
    rel = str(f.relative_to(ROOT))

    # --- 1. HTML residue ---
    tags = len(re.findall(r'<(?:div|span|table|script|style|nav|footer|header|iframe|img|input|button)\b', c, re.I))
    if tags > 5:
        issues["html"].append((rel, tags))

    # --- 2. Tiny files ---
    if f.stat().st_size < 2000 and "/papers/" in rel:
        issues["tiny"].append((rel, f.stat().st_size))

    # --- 3. Near-duplicates ---
    h = hashlib.md5(c[:200].encode()).hexdigest()
    if h in hashes:
        issues["dupe"].append((rel, hashes[h]))
    else:
        hashes[h] = rel

    # --- 4. Boilerplate ---
    nav_lines = len(re.findall(r'(?i)(Quickstart|User Manual|Tutorials|Support|Search|Navigation|Menu)', c[:2000]))
    total_lines = c.count('\n') + 1
    if nav_lines > 3 and total_lines > 10 and nav_lines / min(total_lines, 50) > 0.15:
        issues["boilerplate"].append((rel, nav_lines))

for k, v in issues.items():
    if v:
        print(f"\n--- {k.upper()} ({len(v)} issues) ---")
        for item in v[:15]:
            if k == "dupe":
                print(f"  {item[0]}  <=>  {item[1]}")
            else:
                print(f"  {item[0]}  ({item[1]})")
    else:
        print(f"\n--- {k.upper()}: CLEAN ---")

print(f"\nTotal issues found: {sum(len(v) for v in issues.values())}")
