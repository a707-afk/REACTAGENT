"""Pull gold data PART 2: Hacker News, Meta RSS, Uber, ThinkWorks, CNCF"""
from pathlib import Path
from urllib.request import urlopen, Request
import json, time, re

OUT = Path("data/docs_research/zh_gold")

# --- Hacker News: search for comparison/architecture keywords ---
HN_QUERIES = [
    "Qdrant vs Milvus",
    "LangGraph vs CrewAI",
    "RAG architecture production",
    "vector database comparison",
    "LLM agent memory system",
    "why we moved away from PostgreSQL",
    "agentic RAG best practices",
    "embedding model comparison",
]

hn_count = 0
for q in HN_QUERIES:
    url = f"https://hn.algolia.com/api/v1/search?query={q.replace(' ', '+')}&hitsPerPage=5"
    req = Request(url, headers={"User-Agent": "gold-data"})
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            fname = f"hn_{q.replace(' ','_').replace('?','')[:50]}.json"
            (OUT / fname).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            hn_count += 1
            print(f"  HN: {q} -> {data.get('nbHits',0)} hits")
    except Exception as e:
        print(f"  HN FAIL: {q} — {e}")
    time.sleep(1)

# --- Meta Engineering RSS ---
try:
    req = Request("https://engineering.fb.com/feed/", headers={"User-Agent": "gold-data"})
    with urlopen(req, timeout=20) as resp:
        c = resp.read().decode("utf-8", errors="replace")
        (OUT / "meta_engineering_rss.xml").write_text(c, encoding="utf-8")
        print(f"  Meta RSS: {len(c)} chars")
except Exception as e:
    print(f"  Meta RSS FAIL: {e}")

# --- Uber Engineering (scrape article list) ---
try:
    req = Request("https://www.uber.com/blog/engineering/", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as resp:
        c = resp.read().decode("utf-8", errors="replace")
        (OUT / "uber_engineering.html").write_text(c, encoding="utf-8")
        print(f"  Uber Engineering: {len(c)} chars")
except Exception as e:
    print(f"  Uber FAIL: {e}")

# --- ThoughtWorks Radar (scrape index page) ---
try:
    req = Request("https://www.thoughtworks.com/radar", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as resp:
        c = resp.read().decode("utf-8", errors="replace")
        (OUT / "thoughtworks_radar.html").write_text(c, encoding="utf-8")
        print(f"  ThoughtWorks Radar: {len(c)} chars")
except Exception as e:
    print(f"  ThoughtWorks FAIL: {e}")

# --- Martin Fowler Bliki RSS ---
try:
    req = Request("https://martinfowler.com/feed.atom", headers={"User-Agent": "gold-data"})
    with urlopen(req, timeout=20) as resp:
        c = resp.read().decode("utf-8", errors="replace")
        (OUT / "martinfowler_feed.xml").write_text(c, encoding="utf-8")
        print(f"  Martin Fowler: {len(c)} chars — entries: {c.count('<entry>')}")
except Exception as e:
    print(f"  Fowler FAIL: {e}")

print(f"\nPart 2 done. HN queries: {hn_count}/8")
