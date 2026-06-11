"""Comprehensive embedding/reranker model benchmark for EcomAgent."""
import time
import json
import sys
import os
import gc

os.environ["HF_HOME"] = "/root/models"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"


def get_gpu_mem():
    try:
        import torch
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            return (total - free) / 1e9
        return 0
    except Exception:
        return 0


results = {}

all_models = {
    "bge-m3": "/root/models/BAAI/bge-m3",
}

reranker_models = {
    "bge-reranker-v2-m3": "/root/models/BAAI/bge-reranker-v2-m3",
}

test_queries = [
    "如何申请退货退款？需要什么条件？",
    "退货流程怎么走？七天无理由退货有什么限制？",
    "退款到账需要多长时间？可以退到信用卡吗？",
    "商品有质量问题，已经过了退货期还能退吗？",
    "换货需要什么条件？可以换不同款式吗？",
    "换货运费谁承担？质量问题换货包邮吗？",
    "快递显示已签收但我没收到货怎么办？",
    "物流信息几天没更新了，能帮我查一下吗？",
    "包裹破损里面的东西坏了，怎么申请赔偿？",
    "发货后可以改地址吗？怎么操作？",
    "国际快递一般多久能到？关税谁承担？",
    "客服态度太差了，我要投诉！",
    "等了半个月还没收到货，太生气了！",
    "你们的东西质量太差了，是假货吧？",
    "海外订单可以退吗？运费怎么办？",
    "跨境商品有没有额外的税费？",
    "我买了一双鞋，但是大小不合适",
    "我想换货。换货大概多久能到？新的什么时候发出来？",
    "会员有优先退款权吗？VIP用户有什么特殊权益？",
    "如何开具发票？可以开公司抬头的吗？",
]

print("=" * 70)
print("EcomAgent Embedding Model Benchmark")
print("=" * 70)

# === 1. Embedding Models ===
for name, path in all_models.items():
    if not os.path.isdir(path):
        print(f"\nSKIP {name}: not found at {path}")
        continue

    print(f"\n{'=' * 70}")
    print(f"Model: {name}")
    print(f"Path: {path}")
    print(f"{'=' * 70}")

    try:
        from sentence_transformers import SentenceTransformer
        import torch

        gc.collect()
        torch.cuda.empty_cache()
        gpu_before = get_gpu_mem()

        start = time.time()
        model = SentenceTransformer(path, device="cuda")
        load_time = time.time() - start
        gpu_after = get_gpu_mem()
        gpu_used = round(gpu_after - gpu_before, 2)
        print(f"  Load time: {load_time:.1f}s, GPU memory: {gpu_used:.1f} GB")

        # Warmup
        _ = model.encode(["warmup query for cache"])
        torch.cuda.synchronize()

        # Test different batch sizes
        batch_tests = {}
        for bs in [1, 4, 8, 16, 32]:
            batch = test_queries[: min(bs, len(test_queries))]
            if len(batch) < 1:
                continue

            # Warmup for this batch size
            _ = model.encode(batch, show_progress_bar=False)
            torch.cuda.synchronize()

            times = []
            for _ in range(10):
                start_t = time.time()
                emb = model.encode(batch, show_progress_bar=False)
                torch.cuda.synchronize()
                times.append(time.time() - start_t)

            avg = sum(times) / len(times)
            texts_per_sec = len(batch) / avg if avg > 0 else 0
            batch_tests[str(bs)] = {
                "avg_time_s": round(avg, 4),
                "texts_per_sec": round(texts_per_sec, 1),
                "dim": emb.shape[1],
            }
            print(
                f"  Batch {bs:2d}: {avg:.4f}s = {texts_per_sec:.0f} texts/s | "
                f"dim={emb.shape[1]}"
            )

        results[name] = {
            "type": "embedding",
            "load_time_s": round(load_time, 1),
            "gpu_mem_gb": gpu_used,
            "batch_tests": batch_tests,
        }

        del model
        gc.collect()
        torch.cuda.empty_cache()

    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {str(e)[:200]}")
        results[name] = {"type": "embedding", "error": str(e)[:200]}
    sys.stdout.flush()

# === 2. Reranker ===
if reranker_models:
    print(f"\n{'=' * 70}")
    print("Reranker Benchmark")
    print(f"{'=' * 70}")

    query = "如何申请退货退款？"
    passages = [
        "本店支持七天无理由退货，退货需保证商品完好、吊牌未拆。",
        "退款将在收到退货商品后1-7个工作日内原路退回。",
        "换货需要先办理退货，再重新下单购买新品。",
        "质量问题请提供开箱视频或照片，客服会为您处理。",
        "物流信息超过48小时未更新，建议联系快递公司查询。",
        "VIP会员享有优先退款权益，退款处理时间缩短至24小时。",
        "国际订单退货需自行承担运费，建议先联系客服确认。",
        "发票可以在订单详情页面申请电子发票，支持公司抬头。",
        "换货时如果商品存在差价，需要补足差额部分。",
        "投诉建议将在24小时内由高级客服专员处理。",
    ]

    for name, path in reranker_models.items():
        try:
            # transformer-based reranker
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch

            start = time.time()
            tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
            model = AutoModelForSequenceClassification.from_pretrained(
                path, trust_remote_code=True
            ).to("cuda")
            model.eval()
            load_time = time.time() - start
            print(f"\n{name}: loaded in {load_time:.1f}s")

            # Benchmark reranking
            pairs = [[query, p] for p in passages]
            inputs = tokenizer(
                pairs, padding=True, truncation=True, return_tensors="pt", max_length=512
            ).to("cuda")

            start = time.time()
            with torch.no_grad():
                outputs = model(**inputs)
            torch.cuda.synchronize()
            elapsed = time.time() - start
            scores = outputs.logits.squeeze(-1).cpu().numpy()
            top_idx = scores.argmax()

            print(f"  Rerank {len(passages)} passages: {elapsed * 1000:.0f}ms")
            print(f'  Top passage: "{passages[top_idx][:50]}..."')

            results[name] = {
                "type": "reranker",
                "load_time_s": round(load_time, 1),
                "rerank_time_ms": round(elapsed * 1000, 1),
            }
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {str(e)[:200]}")
            results[name] = {"type": "reranker", "error": str(e)[:200]}

# === Summary ===
print(f"\n{'=' * 70}")
print("SUMMARY")
print(f"{'=' * 70}")
for name, data in results.items():
    if "error" in data:
        print(f"  {name}: ERROR - {data['error']}")
    elif data["type"] == "embedding":
        bs32 = data.get("batch_tests", {}).get("32", {})
        print(
            f"  {name}: load={data['load_time_s']}s, "
            f"GPU={data['gpu_mem_gb']}GB, "
            f"texts/s={bs32.get('texts_per_sec', 'N/A')}, "
            f"dim={bs32.get('dim', '?')}"
        )
    elif data["type"] == "reranker":
        print(
            f"  {name}: load={data['load_time_s']}s, "
            f"rerank={data['rerank_time_ms']}ms"
        )

# Save results
with open("/root/bench_results.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nResults saved to /root/bench_results.json")
print("ALL DONE")
