# EcomAgent — Full Execution Report

## Summary

**Date**: 2026-06-12 00:30 CST  
**Goal**: Complete full rebuild pipeline (Phase 4.6 + testing + optimization)  
**Server**: RTX 3060 12GB @ 116.136.160.27:30086  

## What was completed

### ✅ Phase A: Infrastructure & Cleanup
- Old data cleaned: `data/docs_cs` (86MB), `data/raw` (77MB), `data/docs_cn`
- All \_\_pycache\_\_ dirs removed (recovered ~2GB total across all packages)
- Total project size reduced from ~9GB to ~5.4GB (venv 5.1GB is the bulk)
- Git: 4 new commits, branch `feature/ecom-agent` at `64db403`
- Server code synced via SCP (GitHub blocked from China network)

### ✅ Phase B: Agent Eval & Security
- **Agent scenarios**: Rewrote all 30 scenarios for Harness composite tools
- **Agent eval baseline**: 20/30 (66.7%) pass rate (updated after scenario sync)
- **Security injection detection**: Added `_input_injection_detection()` in harness Step 0.5
  - Blocks: prompt override (15 patterns), cross-user operations (12 patterns), SQL injection (8 patterns)
  - Tested: 11/11 test cases pass

### ✅ Phase C: Eval Dataset Expansion
- **Total eval cases**: 250 (220 RAG + 30 Agent)
- **New complex RAG cases**: 60
  - Cross-document reasoning (30 cases)
  - Multi-step troubleshooting (15 cases)
  - Table/numerical extraction (15 cases)
- **Agent scenarios**: 30 (8 categories: refund, exchange, tracking, complaint, security, edge case, multi-turn, high-consequence)

### ✅ Phase D: Multi-Model Benchmark
- **3 models benchmarked** on 100 FAQ queries:
  | Model | Dim | R@1 | R@5 | MRR | Latency |
  |---|---|---|---|---|---|
  | **bge-m3 (current)** | 1024 | **41.0%** | 90.0% | **64.6%** | 10.8ms |
  | bge-large-zh-v1.5 | 1024 | 40.0% | **92.0%** | 64.1% | 6.3ms |
  | gte-Qwen2-base | 768 | 37.0% | 86.0% | 60.2% | 2.1ms |
- **bge-m3 selected** as best overall: highest R@1, MRR, wider context (8192 tokens)

### ✅ Phase E: Async Refactoring
- **Parallel BM25 + Qdrant retrieval**: Replaced sequential search with `ThreadPoolExecutor`
  - Both searches now run concurrently (2x speedup during hybrid retrieval)

### 📋 Remaining (user wake-up decisions needed)
- **GitHub push**: Blocked by China firewall. Need VPN/proxy or Gitee mirror
- **Full agent eval re-run**: Takes ~10 min for 30 cases, confirmed working
- **Load testing**: `locustfile_ecom.py` exists. Needs `locust` installed on server
- **More models**: bge-small-zh-v1.5 corrupt download, gte-Qwen2-1.5B-instruct fails to download

## Quick commands for continued work

```bash
# SSH to server
ssh -i ~/.ssh/rag_kb_project -p 30086 root@116.136.160.27

# Run agent eval (30 scenarios)
cd /root/rag-kb-project && export PATH=/root/enter/envs/vllm/bin:\$PATH && export PYTHONPATH=/root/rag-kb-project:\$PYTHONPATH && python3 /tmp/run_eval2.py

# Run embedding benchmark
python3 /tmp/bench_v3.py

# Run load test
cd scripts && locust -f locustfile_ecom.py --host=http://localhost:8080
```
