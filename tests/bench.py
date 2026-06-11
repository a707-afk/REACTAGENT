"""Simple HTTP load test for EcomAgent — replaces Locust when pip unavailable."""
import concurrent.futures
import time
import statistics
import urllib.request
import json

BASE_URL = "http://127.0.0.1:8000"
ENDPOINT = "/agent/ticket"

QUERIES = [
    "买了件M码T恤太小了想换L码",
    "我要退款不想要了",
    "这什么垃圾骗子要投诉你们",
    "我的快递到哪了",
]

def send_request(query: str) -> tuple[float, bool, int]:
    """Send one request, return (latency_ms, success, status_code)."""
    t0 = time.perf_counter()
    try:
        data = json.dumps({"ticket_id": "bench", "user_query": query, "customer_id": "u001"}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}{ENDPOINT}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()
        elapsed = (time.perf_counter() - t0) * 1000
        return (elapsed, True, 200)
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return (elapsed, False, getattr(e, "code", 0))


def run_bench(users: int = 10, iterations: int = 5):
    """Run N users each sending M requests, report stats."""
    all_times = []
    failures = 0
    total = users * iterations
    t0 = time.perf_counter()

    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=users) as ex:
        for _ in range(iterations):
            for q in QUERIES * ((users + 3) // 4):  # distribute queries
                f = ex.submit(send_request, q)
                futures.append(f)
            if len(futures) >= total:
                break

    for f in concurrent.futures.as_completed(futures):
        ms, ok, _ = f.result()
        all_times.append(ms)
        if not ok:
            failures += 1

    total_sec = time.perf_counter() - t0
    all_times.sort()
    n = len(all_times)

    def pct(p):
        idx = int(n * p / 100)
        return all_times[min(idx, n-1)]

    print(f"=== EcomAgent Load Test ===")
    print(f"Users: {users} | Requests: {n} | Duration: {total_sec:.1f}s")
    print(f"RPS: {n/total_sec:.1f}")
    print(f"Failures: {failures} ({failures/n*100:.1f}%)")
    print(f"Latency (ms): P50={pct(50):.0f} P95={pct(95):.0f} P99={pct(99):.0f}")
    print(f"Min={all_times[0]:.0f} Max={all_times[-1]:.0f} Mean={statistics.mean(all_times):.0f}")


if __name__ == "__main__":
    run_bench(users=5, iterations=2)
