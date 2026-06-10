# EcomAgent Development Guide

> Architecture, Design Decisions, and Extension Points

## Architecture Overview

```
┌──────────────────────────────────────────────────┐
│                 FastAPI App                       │
│  ┌────────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ RAG Routes │  │ API CRUD │  │ Agent Routes  │ │
│  │ /retrieve  │  │ /tickets │  │ /agent/ticket │ │
│  │ /chat      │  │ /sessions│  │ (sync + SSE)  │ │
│  └─────┬──────┘  └──────────┘  └──────┬─────────┘ │
│        │                              │           │
│  ┌─────▼──────────────────────────────▼──────┐    │
│  │         LangGraph Agent Workflow          │    │
│  │  11 nodes: policy → reason → (exchange    │    │
│  │  parallel | retrieve) → gate → grader →   │    │
│  │  draft → hallucination → finalize         │    │
│  └───────────────────┬──────────────────────┘    │
│                      │                           │
│  ┌───────────────────▼──────────────────────┐    │
│  │       Retrieval Pipeline                  │    │
│  │  Domain Router → BM25 + Qdrant → Gate    │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Supervisor-Worker Pattern
Instead of a flat chain of nodes, the supervisor (`app/supervisor/router.py`) classifies intent before routing to dedicated worker flows. Exchange uses 3 parallel workers (Policy/Inventory/Logistics) via `asyncio.gather()` — the key differentiator from linear agent frameworks.

### 2. Exchange Parallel Flow
When the supervisor detects `intent=exchange`, the graph routes to `node_exchange_parallel`. Three async workers run concurrently using `asyncio.to_thread()`:
- Policy check (return eligibility)
- Inventory query (stock availability)
- Pickup scheduling (logistics)

All three must pass for `exchange_ready=True`.

### 3. Simplified Grader (v2)
The evidence grader (`node_grader`) was simplified to check `gate_passed + chunks >= 1`. This avoids the rewrite loop that caused recursion limit issues in earlier versions. The rewrite query node is preserved but not used in the current graph routing.

### 4. LLM Circuit Breaker
After 3 consecutive LLM failures, the circuit breaker (`fault_tolerance.py`) degrades to retrieval-only mode — the draft uses the top chunk content directly without LLM generation.

### 5. Local Vector Search
Qdrant runs in embedded mode (local file storage). The `_qdrant_client` function in `qdrant_index_store.py` uses a global singleton pattern to prevent concurrent file access errors.

## Key Files

| File | Responsibility |
|------|---------------|
| `app/agent_graph/graph.py` | LangGraph state graph compilation (11 nodes) |
| `app/agent_graph/nodes.py` | All node implementations + routing functions |
| `app/agent_graph/state.py` | TicketAgentState TypedDict (55 fields) |
| `app/agent_graph/fault_tolerance.py` | Circuit breaker, timeout decorator, dead-loop detection |
| `app/agent/tools.py` | 6 e-commerce tools + dispatch |
| `app/supervisor/router.py` | Intent routing + emotion detection |
| `app/mock/orders.py` | Order fixtures (full/partial/denied policy states) |
| `app/mock/inventory.py` | Multi-warehouse stock data |
| `app/mock/logistics.py` | Shipment tracking + pickup scheduling |
| `app/domain_router.py` | 5-domain e-commerce keyword + LLM classification |
| `app/llm_zhipu.py` | SenseNova DeepSeek-V4 client with key rotation |
| `app/retrieval_pipeline.py` | BM25 + Qdrant hybrid retrieval |
| `app/config.py` | Pydantic Settings (env-driven, 50+ fields) |

## Adding a New Intent

1. **Domain Router** (`app/domain_router.py`): Add keyword mappings
2. **Supervisor Router** (`app/supervisor/router.py`): Add domain→intent mapping in `route_intent()`
3. **Graph Routing** (`app/agent_graph/graph.py`): Add conditional edge in `route_after_supervisor`
4. **Node Implementation** (`app/agent_graph/nodes.py`): Add worker function
5. **Mock Data** (`app/mock/`): Add fixtures if needed
6. **Knowledge Base** (`data/docs_ecom/`): Add FAQ entries, rebuild with `python scripts/reindex.py`

## Testing

```bash
# Unit tests
pytest tests/ -v

# Graph compilation + routing
pytest tests/test_agent_graph_compile.py tests/test_agent_graph_routes.py -v

# API smoke test
python tests/server_test.py

# Locust load test
locust -f tests/locustfile_ecom.py --host http://localhost:8000
```

## Common Extension Patterns

### Add a New Tool
1. Define schema in `app/agent/tools.py` (OpenAI function-calling format)
2. Add handler function with `_execute_` prefix
3. Register in `TOOL_DISPATCH` dict
4. Wire into the graph if it needs to be called from a specific node

### Switch to PostgreSQL
```bash
# Set DATABASE_URL in .env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/csagent

# Run migrations
alembic upgrade head
```

### Use Qdrant Server (for concurrent access)
```bash
docker compose up -d qdrant
# Set QDRANT_URL=http://localhost:6333 and unset QDRANT_PATH in .env
```

## Performance Notes

- BM25 cold start: ~2s (first request triggers jieba tokenization, pre-warmed in lifespan)
- Qdrant query: <10ms (54 nodes)
- LLM response: 2-5s (DeepSeek-V4-Flash via SenseNova API)
- Exchange parallel: <100ms (all workers finish within one asyncio.gather tick)
- Full refund flow: 5-10s (RAG + LLM generation)
- Memory: ~2GB (Qwen3-Embedding model loaded)
