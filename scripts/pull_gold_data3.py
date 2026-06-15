"""Pull Meituan tech blog articles (Chinese gold data)"""
from pathlib import Path
from urllib.request import urlopen, Request
import re, time

OUT = Path("data/docs_research/zh_gold")
BASE = "https://tech.meituan.com"

# Fetch the article list page
try:
    req = Request(BASE + "/", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")
        # Extract article links
        articles = re.findall(r'<a[^>]*href="(/20\d{2}/\d{2}/\d{2}/[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
        (OUT / "meituan_article_list.html").write_text(html, encoding="utf-8")
        print(f"Meituan article list: {len(html)} chars")
        print(f"Articles found: {len(articles)}")
        for link, title in articles[:15]:
            clean_title = re.sub(r'<[^>]+>', '', title).strip()[:60]
            print(f"  {link} | {clean_title}")
        
        # Fetch top 10 articles as individual files
        fetched = 0
        for link, title in articles[:10]:
            clean_title = re.sub(r'<[^>]+>', '', title).strip()
            fname = "meituan_" + link.replace("/", "_").strip("_") + ".html"
            try:
                req2 = Request(BASE + link, headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(req2, timeout=20) as resp2:
                    c = resp2.read().decode("utf-8", errors="replace")
                    (OUT / fname).write_text(c, encoding="utf-8")
                    fetched += 1
                    print(f"  FETCHED: {fname} ({len(c)} chars) - {clean_title[:60]}")
            except Exception as e2:
                print(f"  SKIP: {link} - {str(e2)[:50]}")
            time.sleep(1)
        print(f"\nMeituan articles fetched: {fetched}/10")
except Exception as e:
    print(f"Meituan FAIL: {e}")
