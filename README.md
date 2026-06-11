# EcomAgent — Enterprise RAG + Agent Customer Service Platform

> 企业级 RAG+Agent 智能客服平台。支持文件上传（PDF/Word/图片+OCR）、混合检索、多 Agent 协调、人工审批、安全防护和 Docker 一键部署。

![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-green)
![React](https://img.shields.io/badge/React-18-61dafb)
![Tests](https://img.shields.io/badge/tests-269%20passed-brightgreen)
![Status](https://img.shields.io/badge/status-production--ready-blue)

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/a707-afk/REACTAGENT.git
cd REACTAGENT

# 2. Install dependencies
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env: set SENSENOVA_API_KEYS

# 4. Start services
docker compose up -d qdrant

# 5. Initialize database
python -m alembic upgrade head

# 6. Seed knowledge base (optional)
python scripts/seed_eval_docs.py

# 7. Run
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 8. Open browser
# Frontend: http://127.0.0.1:8000/
# API Docs: http://127.0.0.1:8000/docs
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React 18)                       │
│   Chat │ Retrieve │ Agent │ Tickets │ Docs │ Approvals       │
└────────────────────────┬────────────────────────────────────┘
                         │ SSE / REST
┌────────────────────────▼────────────────────────────────────┐
│                   FastAPI Gateway                            │
│  Auth → Rate Limit → Input Sanitizer → Metrics              │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                 Agent Harness (Coordinator)                  │
│  Plan → Tool Registry → Permission Gate → Execute →         │
│  Evaluate → HITL Approval → Finalize                        │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│               Retrieval Pipeline                             │
│  Query → Rewrite → Prefilter → Dense(BM25) →                │
│  Fusion(RRF) → Rerank → Gate → Chunks                       │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  Infrastructure                              │
│  SQLite/PostgreSQL │ Redis │ Qdrant │ Worker(arq)            │
│  Document Ingestion │ Degradation Manager │ Audit Log        │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Features

### Knowledge Base & Ingestion
- **Document Upload**: PDF, DOCX, Markdown, TXT, PNG, JPEG support
- **Multimodal OCR**: sensenova-6.7-flash-lite VLM for image/scanned PDF text extraction
- **Ingestion Pipeline**: Validate → Dedup → Parse → Clean → Chunk → Qdrant + BM25
- **Table Extraction**: pdfplumber + markdown-formatted tables
- **13-step Pipeline**: Full progress tracking via async worker (arq + Redis)

### Retrieval & RAG
- **Hybrid Search**: BM25 (sparse) + Qdrant Dense Vector → Max/RRF fusion
- **Domain Router**: 5 e-commerce domain keywords + LLM fallback
- **Reranker**: Qwen3-Reranker with similarity gating
- **Citation Verification**: Sentence-level grounding with n-gram overlap
- **Access Control**: Tenant isolation + role-based ACL prefilter

### Agent System
- **Coordinator Pattern**: Plan → Execute → Observe → Evaluate → HITL
- **6 Registered Tools**: order_lookup, policy_check, inventory_query, create_pickup, track_shipment, create_after_sale_ticket
- **Tool Registry**: Schema validation, idempotency, timeout/retry, side-effect levels
- **Permission Gate**: 4 risk levels (LOW/MEDIUM/HIGH/CRITICAL) with scope enforcement
- **HITL Approval**: Human-in-the-loop approval API for high-risk actions
- **Agent Audit**: Every step written to DB for replay

### Safety & Security
- **Input Sanitizer**: InputGuard + DocumentSanitizer + OutputGuard (16 injection patterns)
- **Prompt Injection Protection**: Covers system override, prompt export, permission bypass, tool parameter injection, multi-turn context injection
- **Degradation Manager**: 8-component health tracking with structured degradation
- **Circuit Breaker**: LLM failure auto-recovery

### Enterprise Features
- **Multi-tenant**: Tenant isolation at DB, retrieval, and API levels
- **Async Worker**: arq + Redis for ingestion, reindex, and eval jobs
- **Eval Suite**: 100 gold-standard RAG cases + 10 agent scenarios
- **Metrics**: Prometheus-ready HTTP + RAG + LLM metrics

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/retrieve` | Knowledge base retrieval |
| POST | `/chat/stream` | Streaming chat with RAG |
| POST | `/agent/ticket` | Full agent workflow |
| POST | `/agent/ticket/stream` | Agent workflow (SSE) |
| GET | `/api/tickets` | Ticket list (paginated) |
| POST | `/api/tickets` | Create ticket |
| GET | `/api/documents` | Document list |
| POST | `/api/documents/upload` | Upload document |
| DELETE | `/api/documents/{id}` | Delete document |
| GET | `/api/jobs` | Job list |
| POST | `/api/jobs` | Submit async job |
| GET | `/api/approvals` | Approval list |
| POST | `/api/approvals/{id}/approve` | Approve HITL |
| POST | `/api/approvals/{id}/reject` | Reject HITL |
| GET | `/health/live` | Liveness check |
| GET | `/health/ready` | Readiness check |
| GET | `/docs` | OpenAPI Swagger |

---

## Project Structure

```
├── app/
│   ├── agent/                  # Tool Registry + Permission Gate + Harness
│   │   ├── tool_registry.py
│   │   ├── permission_gate.py
│   │   └── harness.py
│   ├── agent_graph/            # LangGraph workflow nodes
│   ├── ingestion/              # Document parsers + pipeline
│   │   └── parsers/            # PDF, DOCX, Image, Markdown parsers
│   ├── db/models/              # SQLAlchemy models (13 tables)
│   ├── api/                    # REST endpoints
│   ├── worker/                 # Async task queue (arq)
│   ├── degradation.py          # Fault tolerance manager
│   ├── input_sanitizer.py      # Injection protection
│   ├── retrieval_pipeline.py   # Hybrid BM25 + Qdrant
│   └── config.py               # Settings (pydantic-settings)
├── frontend/src/               # React 18 + TypeScript admin UI
│   └── components/             # 7 tab pages
├── data/eval/                  # 100 RAG + 10 Agent gold cases
├── scripts/                    # Eval runner, seed data, reindex
├── tests/                      # 269 unit + integration tests
├── docs/                       # Architecture + audit reports
├── alembic/                    # Database migrations
├── docker-compose.yml          # Qdrant + PostgreSQL + Redis + App + Worker
└── .env.example                # Full configuration template
```

---

## Evaluation

```bash
# RAG evaluation (100 cases, 6 categories)
python scripts/run_eval_rag.py

# Categories: faq(30) + pdf_table(20) + no_answer(15) +
#             permission(15) + policy(10) + multi_turn(10)

# Agent evaluation (10 multi-turn scenarios)
# python scripts/run_eval_agent.py
```

| Metric | Target | Dry-run |
|---|---|---|
| Recall@5 | ≥0.85 | 1.00 |
| MRR@10 | ≥0.70 | 1.00 |
| nDCG@10 | ≥0.75 | 1.00 |
| Citation Precision | ≥0.90 | 0.75 |
| Unsupported Rate | ≤0.08 | 0.25 |
| Unauthorized in TopK | 0 | 0 |

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -q

# Current: 269 passed, 0 failed
# Coverage: models, retrieval, agent, ingestion, degradation, eval
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.136 (async) |
| Agent | Coordinator Harness + LangGraph |
| Vector DB | Qdrant (server / embedded) |
| Sparse Index | BM25 (rank-bm25) |
| Embedding | Qwen3-Embedding-0.6B |
| LLM | SenseNova DeepSeek-V4-Flash |
| VLM | SenseNova sensenova-6.7-flash-lite |
| Database | SQLite (dev) / PostgreSQL 16 (prod) |
| Cache | Redis + in-process LRU |
| Queue | arq + Redis |
| Frontend | React 18 + TypeScript + Vite 5 |
| Testing | pytest (269 tests) |
| Infra | Docker Compose (Qdrant, Redis, PostgreSQL) |

---

## License

MIT
