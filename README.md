# CS Agent Backend — Customer Service AI Agent with RAG

Production-grade customer service AI agent backend: hybrid search (BM25 + dense vector), LangGraph agent loop with tool calling, ticket state machine, multi-turn session memory, and policy guardrails. Built with FastAPI, Qdrant, PostgreSQL, and local Qwen3 models.

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
│        │            │           │         │
│   Auth │       Rate Limit   │   SSE      │
└────────┼────────────┼───────┼────────────┘
         │            │       │
    ┌────▼────────────▼───────▼────────┐
    │         Agent Graph (LangGraph)   │
    │  policy → reason → tools →       │
    │  retrieve → gate → grader →      │
    │  rewrite → draft → hallucination │
    └────────────────┬─────────────────┘
                     │
    ┌────────────────┼─────────────────┐
    │                │                  │
    ▼                ▼                  ▼
┌────────┐   ┌────────────┐   ┌──────────────┐
│ Qdrant │   │  Qwen3     │   │ PostgreSQL   │
│ 78K    │   │ Embedding  │   │ Tickets      │
│ vectors│   │ + Reranker │   │ Sessions     │
│ + BM25 │   │ (RTX 5070) │   │ Customers    │
└────────┘   └────────────┘   └──────────────┘
```

## Key Features

### Retrieval Pipeline
- **Hybrid Search**: BM25 (sparse) + Qdrant Dense Vector → RRF/Max fusion → Qwen3 Reranker
- **Domain Router**: Keyword + embedding dual-path fusion + Zhipu LLM fallback + Platt calibration (15 domains)
- **Similarity Gate**: Post-rerank quality threshold with configurable refusal messages
- **Query Rewrite**: Auto-mode heuristic + Zhipu LLM for Chinese query expansion
- **Access Control**: Tenant/role/security-clearance pre-filter on vector + BM25 retrieval

### Agent System
- **LangGraph Workflow**: policy → reason → tool_exec → retrieve → gate → grader → rewrite loop → draft → hallucination → finalize
- **4 Built-in Tools**: `retrieve_kb`, `create_ticket`, `escalate`, `customer_lookup` (OpenAI function-calling schema)
- **Agentic Loop**: Up to 3 rewrite iterations with loop detection
- **Grounding Verification**: Sentence-level citation verification + unsupported sentence stripping

### Business Logic
- **Ticket State Machine**: 6 states with validated transitions (NEW→IN_PROGRESS→WAITING_CUSTOMER→ESCALATED→RESOLVED→CLOSED)
- **SLA Scheduling**: Priority-tiered deadlines (P0=15min, P1=1h, P2=4h, P3=8h) with customer-tier multipliers
- **Session Memory**: Multi-turn conversation context injection (last N messages, 4K char window)

### Safety & Observability
- **Policy Engine**: Behavior guard (keyword + embedding + LLM classifier) + OPA integration
- **OpenTelemetry**: OTEL spans + Langfuse LLM traces + Prometheus metrics endpoint
- **Structured Logging**: JSON event logs with trace IDs

## Quick Start

### Prerequisites
- Python 3.12+
- NVIDIA GPU (optional, CPU fallback supported)
- [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) model (local)
- [Zhipu API key](https://open.bigmodel.cn/) (for LLM features)

### Install
```bash
git clone https://github.com/a707-afk/REACTAGENT.git
cd REACTAGENT
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### Configure
```bash
copy .env.cs-agent .env
# Edit .env: set ZHIPUAI_API_KEY, verify model paths
```

### Build Index (if not pre-built)
```bash
python scripts/download_cs_data.py   # Download datasets (62K + 27K)
python scripts/preprocess_cs_data.py  # Clean & unify
python scripts/reindex_cs.py          # Qdrant + BM25 indexing (GPU)
```

### Run
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Or with Docker:
docker compose up -d
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | RAG-augmented chat (JSON response) |
| POST | `/api/chat/stream` | RAG chat with SSE streaming |
| POST | `/agent/ticket` | Full agent workflow (ticket + retrieval + draft) |
| POST | `/agent/ticket/stream` | Agent workflow with SSE streaming |
| GET  | `/api/tickets` | List tickets (filter by status) |
| POST | `/api/tickets` | Create ticket |
| GET  | `/api/tickets/{id}` | Get ticket detail |
| PATCH | `/api/tickets/{id}/transition` | State machine transition |
| GET  | `/health` | Health check |
| GET  | `/metrics` | Prometheus metrics |
| GET  | `/docs` | OpenAPI Swagger UI |

## Evaluation Results

**Dataset**: 78,023 documents across 15 CS domains (Tobi-Bueck 62K tickets + Bitext 27K Q&A)

| Metric | Value |
|--------|-------|
| **Recall@5** | **0.867** |
| Precision@5 | 0.520 |
| MRR | 0.579 |
| Latency p50 | 2.78s |
| Latency p95 | 47.30s |

```bash
# Run evaluation
python scripts/run_eval_cs_full.py --size full
```

## Project Structure

```
├── app/
│   ├── agent/            # Agent tools (function-calling schemas + implementations)
│   │   └── tools.py      # retrieve_kb, create_ticket, escalate, customer_lookup
│   ├── agent_graph/      # LangGraph workflow
│   │   ├── graph.py      # Graph compilation: 10 nodes
│   │   ├── nodes.py      # Node implementations
│   │   └── state.py      # TicketAgentState TypedDict
│   ├── api/              # REST API layer
│   │   ├── chat.py       # POST /api/chat, /api/chat/stream
│   │   ├── tickets.py    # CRUD + state transitions
│   │   └── deps.py       # Auth, DB session DI
│   ├── db/               # SQLAlchemy async models
│   │   ├── engine.py     # Async engine + session factory
│   │   └── models/       # Ticket, Customer, ChatSession, Message
│   ├── services/         # Business logic
│   │   ├── ticket_sm.py  # Ticket state machine
│   │   └── session_mgr.py # Multi-turn conversation memory
│   ├── policy/           # Safety guardrails
│   ├── retrieval_pipeline.py  # Hybrid retrieval + rerank
│   ├── domain_router.py  # Multi-domain classification
│   └── config.py         # Settings (env-driven)
├── data/                 # CS corpus, Qdrant index, BM25
├── scripts/              # Data pipeline + eval
├── tests/                # 15+ test modules
├── alembic/              # DB migrations
├── docker-compose.yml    # App + PostgreSQL + Qdrant
└── .github/workflows/    # CI: test + lint
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.136 (async) |
| Agent | LangGraph (10-node workflow) |
| Vector DB | Qdrant (embedded, 78K vectors) |
| Sparse Index | BM25 (rank-bm25) |
| Embedding | Qwen3-Embedding-0.6B (GPU) |
| Reranker | Qwen3-Reranker-0.6B (GPU) |
| LLM | Zhipu GLM-4-Flash (API) |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 async |
| Migrations | Alembic |
| Observability | OpenTelemetry + Langfuse + Prometheus |
| Container | Docker + docker-compose |
| CI/CD | GitHub Actions |

## License

MIT
