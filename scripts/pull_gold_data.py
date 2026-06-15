"""Pull gold-data sources for the research knowledge base."""
from pathlib import Path
from urllib.request import urlopen, Request
import time

OUT = Path("data/docs_research/zh_gold")
OUT.mkdir(parents=True, exist_ok=True)

SOURCES = [
    ("SDP_zh.md", "https://raw.githubusercontent.com/donnemartin/system-design-primer/master/README-zh-Hans.md", "System Design Primer 中文版"),
    ("SDP_en.md", "https://raw.githubusercontent.com/donnemartin/system-design-primer/master/README.md", "System Design Primer English"),
    ("deerflow_zh.md", "https://raw.githubusercontent.com/bytedance/deer-flow/main/README_zh.md", "ByteDance DeerFlow 中文"),
    ("deerflow_en.md", "https://raw.githubusercontent.com/bytedance/deer-flow/main/README.md", "ByteDance DeerFlow English"),
    ("uitars_zh.md", "https://raw.githubusercontent.com/bytedance/UI-TARS-desktop/main/README.zh-CN.md", "ByteDance UI-TARS 中文"),
    ("trae_agent.md", "https://raw.githubusercontent.com/bytedance/trae-agent/main/README.md", "ByteDance Trae Agent"),
    ("flowgram.md", "https://raw.githubusercontent.com/bytedance/flowgram.ai/main/README.md", "ByteDance FlowGram"),
    ("zvec.md", "https://raw.githubusercontent.com/alibaba/zvec/main/README.md", "Alibaba zvec 向量数据库"),
    ("page_agent.md", "https://raw.githubusercontent.com/alibaba/page-agent/main/README.md", "Alibaba Page Agent"),
]

ok = 0
for fname, url, label in SOURCES:
    req = Request(url, headers={"User-Agent": "gold-data-harvester"})
    try:
        with urlopen(req, timeout=25) as resp:
            if resp.status == 200:
                c = resp.read().decode("utf-8", errors="replace")
                if len(c) > 500:
                    header = f"<!-- source: {label} | url: {url} -->\n\n"
                    (OUT / fname).write_text(header + c, encoding="utf-8")
                    print(f"  OK: {fname} ({len(c)} chars)")
                    ok += 1
                else:
                    print(f"  SKIP: {fname} too short ({len(c)} chars)")
            else:
                print(f"  HTTP {resp.status}: {fname}")
    except Exception as e:
        print(f"  FAIL: {fname} — {str(e)[:80]}")
    time.sleep(0.5)

print(f"\nGold data fetched: {ok}/{len(SOURCES)}")
