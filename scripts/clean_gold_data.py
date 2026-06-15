"""Clean gold data: HTML→markdown, RSS→text, HN JSON→articles.

Phase B: converts all gold raw data into clean markdown files.
Phase C: audits existing data, deletes low-quality content.
"""
from pathlib import Path
import re, json, html as html_mod, time, os
from xml.etree import ElementTree as ET

GOLD = Path("data/docs_research/zh_gold")
OUT_DIR = Path("data/docs_research/zh_gold_clean")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLEANED, DELETED = 0, 0

def _html_to_text(h):
    """Strip HTML tags, preserve structure."""
    h = re.sub(r'<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>', '', h, flags=re.DOTALL|re.I)
    h = re.sub(r'<h[1-6][^>]*>', lambda m: '\n\n'+'#'*int(m.group(0)[2])+' ', h, flags=re.I)
    h = re.sub(r'</h[1-6]>', '\n', h, flags=re.I)
    h = re.sub(r'<li[^>]*>', '\n- ', h, flags=re.I)
    h = re.sub(r'<p[^>]*>', '\n\n', h, flags=re.I)
    h = re.sub(r'<br\s*/?>', '\n', h, flags=re.I)
    h = re.sub(r'<code[^>]*>', '`', h, flags=re.I); h = re.sub(r'</code>', '`', h, flags=re.I)
    h = re.sub(r'<pre[^>]*>', '\n```\n', h, flags=re.I); h = re.sub(r'</pre>', '\n```\n', h, flags=re.I)
    t = re.sub(r'<[^>]+>', '', h)
    t = html_mod.unescape(t)
    t = re.sub(r'\n{4,}', '\n\n\n', t); t = re.sub(r'[ \t]+', ' ', t)
    return t.strip()

# --- Clean Meituan HTMLs ---
for f in sorted(GOLD.glob("meituan_*.html")):
    c = f.read_text(encoding="utf-8", errors="replace")
    # Extract title
    ti = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', c)
    title = ti.group(1) if ti else f.stem
    # Extract article body (Meituan uses a specific class)
    body = re.search(r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>\s*(?:<footer|</body)', c, re.DOTALL)
    text = _html_to_text(body.group(1)) if body else _html_to_text(c)
    if len(text) < 300: continue
    out = OUT_DIR / f"{f.stem.replace('.html','')}.md"
    header = f"<!-- source: 美团技术团队 | gold-data -->\n# {title}\n\n"
    out.write_text(header + text, encoding="utf-8")
    CLEANED += 1; f.unlink()  # Remove raw HTML

# --- Clean ThoughtWorks Radar HTML ---
for f in sorted(GOLD.glob("thoughtworks_radar.*")):
    if f.suffix != '.html': continue
    c = f.read_text(encoding="utf-8", errors="replace")
    # Extract blips from the JavaScript data
    blips = re.findall(r'"blips":\s*\[(.*?)\]', c, re.DOTALL)
    blip_data = []
    for block in blips:
        items = re.findall(r'\{(.*?)\}', block, re.DOTALL)
        for item in items:
            name = re.search(r'"name"\s*:\s*"([^"]+)"', item)
            ring = re.search(r'"ring"\s*:\s*"([^"]+)"', item)
            desc = re.search(r'"description"\s*:\s*"([^"]+)"', item)
            if name:
                blip_data.append(f"- **{name.group(1)}** [{ring.group(1) if ring else 'N/A'}] — {desc.group(1)[:200] if desc else ''}")
    if blip_data:
        text = "# ThoughtWorks Technology Radar (2026)\n\n" + "\n".join(blip_data[:100])
        (OUT_DIR / "thoughtworks_radar_blips.md").write_text(text, encoding="utf-8")
        CLEANED += 1
    f.unlink()

# --- Parse Meta RSS ---
for f in sorted(GOLD.glob("meta_engineering_rss*")):
    c = f.read_text(encoding="utf-8", errors="replace")
    root = ET.fromstring(c)
    entries = []
    for item in root.iter('item'):
        title = (item.find('title').text or '') if item.find('title') is not None else ''
        link = (item.find('link').text or '') if item.find('link') is not None else ''
        desc = (item.find('description').text or '') if item.find('description') is not None else ''
        entries.append(f"## {title}\n\n{_html_to_text(desc)[:500]}\n\n原文: {link}")
    if entries:
        text = "# Meta Engineering Blog\n\n" + "\n\n---\n\n".join(entries[:20])
        (OUT_DIR / "meta_engineering_articles.md").write_text(text, encoding="utf-8")
        CLEANED += 1
    f.unlink()

# --- Parse Martin Fowler RSS ---
for f in sorted(GOLD.glob("martinfowler_feed*")):
    c = f.read_text(encoding="utf-8", errors="replace")
    root = ET.fromstring(c)
    entries = []
    for entry in root.iter('{http://www.w3.org/2005/Atom}entry'):
        title = ''; link = ''; summary = ''
        for child in entry:
            if child.tag.endswith('title'): title = (child.text or '')
            if child.tag.endswith('link'): link = child.get('href', '')
            if child.tag.endswith('summary'): summary = (child.text or '')
        if title:
            entries.append(f"## {title}\n\n{_html_to_text(summary)[:400]}\n\n原文: {link}")
    if entries:
        text = "# Martin Fowler's Bliki\n\n" + "\n\n---\n\n".join(entries)
        (OUT_DIR / "martinfowler_bliki.md").write_text(text, encoding="utf-8")
        CLEANED += 1
    f.unlink()

# --- Parse HN JSON into articles ---
for f in sorted(GOLD.glob("hn_*.json")):
    data = json.loads(f.read_text(encoding="utf-8"))
    hits = data.get('hits', [])[:5]
    query = f.stem.replace('hn_','').replace('_',' ')[:60]
    lines = [f"# Hacker News: {query}", '']
    for h in hits:
        title = h.get('title','') or h.get('story_title','')
        url = h.get('url','') or ''
        points = h.get('points',0)
        comments = h.get('num_comments',0)
        lines.append(f"- **{title}** ({points} 分, {comments} 评论)")
        if url: lines.append(f"  链接: {url}")
    if len(lines) > 2:
        (OUT_DIR / f"{f.stem}.md").write_text('\n'.join(lines), encoding="utf-8")
        CLEANED += 1
    f.unlink()

# --- Copy CNCF landscape ---
cncf = GOLD / "cncf_landscape.yml"
if cncf.exists():
    os.rename(str(cncf), str(OUT_DIR / "cncf_landscape.yml"))
    CLEANED += 1

# --- Copy already-clean gold markdowns (keep originals in GOLD) ---
for f in sorted(GOLD.glob("*.md")):
    if f.name.startswith('_'): continue
    c = f.read_text(encoding="utf-8", errors="replace")
    if len(c.strip()) < 200: continue
    # Strip HTML tags from gold markdowns
    c2 = re.sub(r'<(img|picture|source|svg|input|button|form|iframe)[^>]*>', '', c, flags=re.I)
    c2 = re.sub(r'\n{4,}', '\n\n\n', c2)
    (OUT_DIR / f.name).write_text(c2.strip(), encoding="utf-8")
    CLEANED += 1

print(f"Phase B done. Cleaned {CLEANED} files -> {OUT_DIR}")
