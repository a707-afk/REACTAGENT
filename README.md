# EcomAgent — E-commerce After-Sales Multi-Agent System

> **v2.0** — Rebranded from generic CS Agent to e-commerce after-sales Agent with Supervisor-Worker orchestration.
>
> E-commerce after-sales AI agent: Supervisor intent routing, `asyncio.gather` 3-Worker parallel exchange, hybrid search (BM25 + dense vector), LangGraph workflow, citation verification, and circuit breaker protection. Built with FastAPI, Qdrant, and local Qwen3 models.

![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Architecture

```
Client Request
    │
    ▼
┌──────────────────────────────────────────┐
│             FastAPI Gateway              │
│  /api/chat  /api/tickets  /agent/ticket  │
└──────────────┬───────────────────────────┘
               │
    ┌──────────▼──────────────────────┐
    │     Agent Graph (LangGraph)      │
    │  policy → reason (Supervisor) →  │
    │  exchange_parallel / retrieve →  │
    │  gate → grader → draft →         │
    │  hallucination → finalize        │
    └──────────┬───────────────────────┘
               │
    ┌──────────┼───────────────────────┐
    ▼          ▼                       ▼
┌──────┐ ┌──────────┐ ┌──────────────────┐
│Qdrant│ │ Qwen3    │ │ Mock Data Layer  │
│ 54   │ │ Embedding│ │ Orders/Inventory │
│ nodes│ │ (auto    │ │ /Logistics       │
│+ BM25│ │ GPU/CPU) │ │                  │
└──────┘ └──────────┘ └──────────────────┘
```

## Key Features

### Supervisor-Worker Multi-Agent
- **Intent Routing**: classify into 4 intents (exchange/refund/complaint/tracking) via keyword + LLM fallback
- **Exchange Parallel**: `asyncio.gather` runs Policy/Inventory/Logistics checks concurrently — the differentiator vs Dify
- **Emotion Detection**: inline angry keyword detection, escalates complaint urgency (P0 SLA: 2h)

### Agent Tools (6 e-commerce tools)
- `order_lookup` — fuzzy-match user orders by product keyword
- `policy_check` — evaluate return eligibility (7-day unconditional / 30-day quality / denied)
- `inventory_query` — check SKU stock across multi-warehouse
- `create_pickup` — schedule return pickup (next-day 9:00-18:00)
- `track_shipment` — real-time logistics status
- `create_after_sale_ticket` — priority-tiered SLA ticket (P0=2h, P1=4h, P2=24h, P3=72h)

### Retrieval Pipeline (preserved from v1)
- **Hybrid Search**: BM25 (sparse) + Qdrant Dense Vector → Max fusion
- **Domain Router**: 5 e-commerce domain keywords + Zhipu LLM fallback (10s timeout)
- **Similarity Gate**: post-retrieval quality threshold
- **Citation Verification**: sentence-level grounding

### Quality & Safety
- **Behavior Guard**: keyword-based policy engine
- **Circuit Breaker**: LLM failure auto-degrade (2 retries max)
- **Structured Logging**: JSON event logs with trace IDs

## Quick Start

### Prerequisites
- Python 3.12+
- NVIDIA GPU (optional, CPU fallback supported via `INFERENCE_DEVICE=auto`)
- Qwen3-Embedding-0.6B model (local path configured in .env)

### Install
```bash
git clone https://github.com/a707-afk/REACTAGENT.git
cd REACTAGENT
git checkout feature/ecom-agent
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### Configure
```bash
# Copy and edit .env (see .env.example for all options)
# Key settings: DOCS_DIR, INFERENCE_DEVICE, QDRANT_PATH
```

### Build Index
```bash
python scripts/build_ecom_kb.py           # Generate FAQ markdowns
python scripts/reindex.py                 # Qdrant + BM25 indexing
```

### Run
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
# Frontend: http://127.0.0.1:8000/
# API docs: http://127.0.0.1:8000/docs
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/agent/ticket` | Full agent workflow (intent → workers → draft) |
| POST | `/agent/ticket/stream` | Agent workflow with SSE streaming |
| GET | `/api/tickets` | List tickets |
| POST | `/api/tickets` | Create ticket |
| GET | `/api/tickets/{id}` | Get ticket detail |
| GET | `/health` | Health check |
| GET | `/health/config` | Runtime configuration dump |
| GET | `/docs` | OpenAPI Swagger UI |

## Project Structure

```
├── app/
│   ├── agent/
│   │   └── tools.py          # 6 e-commerce tools (order_lookup, policy_check, etc.)
│   ├── agent_graph/
│   │   ├── graph.py          # LangGraph: 11 nodes (incl. exchange_parallel)
│   │   ├── nodes.py          # Node implementations + routing functions
│   │   └── state.py          # TicketAgentState (55 fields, TypedDict)
│   ├── supervisor/
│   │   └── router.py         # Intent routing + emotion detection
│   ├── mock/
│   │   ├── orders.py         # Order fixtures (3 policy states)
│   │   ├── inventory.py      # Multi-warehouse stock
│   │   └── logistics.py      # Tracking + pickup
│   ├── api/                  # REST API layer
│   ├── db/                   # SQLAlchemy async models
│   ├── services/             # Ticket state machine, session memory
│   ├── policy/               # Safety guardrails
│   ├── retrieval_pipeline.py # Hybrid BM25 + Qdrant retrieval
│   ├── domain_router.py      # 5-domain e-commerce classification
│   └── config.py             # Settings (env-driven, device auto-detect)
├── frontend/src/             # React 18 demo UI (Vite + TypeScript)
├── data/docs_ecom/           # E-commerce FAQ knowledge base (24 Q&A, 54 chunks)
├── scripts/                  # FAQ builder + reindex
├── tests/                    # Locust load test
├── docs/                     # Audit reports, plans, specs
└── docker-compose.yml        # PostgreSQL + optional Qdrant server
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.136 (async) |
| Agent | LangGraph (11-node workflow) |
| Vector DB | Qdrant (embedded, 54 FAQ nodes) |
| Sparse Index | BM25 (rank-bm25) |
| Embedding | Qwen3-Embedding-0.6B (GPU auto-detect) |
| LLM | Zhipu GLM-4-Flash (API) |
| Database | SQLite (dev) / PostgreSQL 16 (prod) |
| Frontend | React 18 + Vite + TypeScript |
| Testing | Python bench (load), Locust (planned), pytest |

## Performance

> Measured on Intel i7 CPU (no GPU), 5 concurrent users, 16 requests.

| Metric | Value |
|--------|-------|
| P50 Latency | 169ms |
| P95 Latency | 5464ms |
| P99 Latency | 5464ms |
| RPS (5 users) | 2.9 req/s |
| Failure rate | 0% |
| FAQ entries | 50 Q&A (106 vectors) |
| Intent accuracy (keyword) | >95% |

> Note: P95/P99 reflects LLM draft generation via SenseNova DeepSeek-V4 API (15-20s RTT per request).
> Exchange flow completes in <200ms (no LLM, mock data). Circuit breaker triggers at 2 consecutive LLM failures and degrades to cached response.

## License

MIT
