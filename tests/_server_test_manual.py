import urllib.request, json, time

def test(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

t0 = time.time()

# Language detection test
from app.language_router import detect_language
print(f"lang('退货怎么操作'): {detect_language('退货怎么操作')}")
print(f"lang('How do I return?'): {detect_language('How do I return?')}")

# CN retrieval
r = test("http://localhost:8000/retrieve", "POST", {"query": "退货怎么操作", "top_k": 3})
chunks = r.get("chunks", [])
print(f"\nCN retrieve: {len(chunks)} chunks, gate={r.get('gate_passed')}")
if r.get("router_trace"):
    print(f"  domain={r['router_trace'].get('primary_domain')}")
for c in chunks[:3]:
    sc = c.get("score", 0) or 0
    print(f"  {sc:.3f}: {str(c.get('text',''))[:80]}")

# EN retrieval
r = test("http://localhost:8000/retrieve", "POST", {"query": "How do I return my order?", "top_k": 3})
chunks = r.get("chunks", [])
print(f"\nEN retrieve: {len(chunks)} chunks, gate={r.get('gate_passed')}")
for c in chunks[:2]:
    sc = c.get("score", 0) or 0
    print(f"  {sc:.3f}: {str(c.get('text',''))[:80]}")

# Chat
r = test("http://localhost:8000/api/chat", "POST", {"query": "退货怎么操作", "top_k": 3})
ans = r.get("answer", "")
print(f"\nCHAT: refused={r.get('refused')}, chunks_used={r.get('chunks_used')}")
if ans:
    print(f"  answer: {ans[:300]}")
else:
    err = str(r.get("detail", r.get("error_code", "unknown")))[:200]
    print(f"  error: {err}")

print(f"\nTotal: {time.time()-t0:.1f}s")