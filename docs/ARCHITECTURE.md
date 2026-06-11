# EcomAgent Architecture

## System Overview

EcomAgent is an enterprise RAG+Agent customer service platform built with a coordinator-pattern Agent Harness, hybrid retrieval pipeline, and full observability stack.

## Component Architecture

### 1. API Gateway (FastAPI)

```
Request → Auth Middleware → Rate Limiter → Input Sanitizer → Router → Response
```

- Auth: API key hash verification (SHA-256), tenant isolation
- Input Sanitizer: 16 regex patterns covering 5 injection categories
- SSE streaming: Event-driven server-sent events for Agent/Chat/RAG
- Health: /health/live + /health/ready + /health/config

### 2. Agent Harness

```
Policy Pre-check → Plan → Execute (per step):
    Select Tool → Permission Gate → Schema Validate → Idempotency Check → Execute → Audit Log
                    ↓
            Observe → Evaluate → HITL Approval → Finalize
```

- Coordinator pattern (not swarm)
- Tool Registry: 6 registered e-commerce tools
- Permission Gate: 4 risk levels (LOW/MEDIUM/HIGH/CRITICAL)
- Every step written to agent_steps table for audit replay
- HITL approval API for high-risk actions

### 3. Retrieval Pipeline

```
User Query
  → Query Rewrite / Expansion
  → ACL Prefilter (tenant + role)
  → Dense Retrieval (Qdrant)
  → Sparse Retrieval (BM25)
  → Hybrid Fusion (RRF default)
  → Domain/Intent Boosting
  → Rerank (Qwen3-Reranker)
  → Similarity Gate
  → Chunk Packing
```

### 4. Ingestion Pipeline

```
Upload File
  → MIME + Extension Validation
  → File Size Check (50MB limit)
  → SHA-256 Dedup
  → Threat Scan (stub)
  → Parse (PDF/DOCX/Image/Markdown)
  → Text Clean
  → Chunk (token-based + overlap)
  → DB Write (Document + Chunks)
  → Qdrant Write (Vector Index)
  → BM25 Write (Sparse Index)
  → Job Progress Update
```

### 5. Safety & Degradation

```
Input Guard → Document Sanitizer → Tool Permission Gate → Output Guard

Degradation Manager:
  - 8 components tracked (LLM, Embedding, Reranker, Qdrant, Redis, Postgres, Tool, OCR)
  - Auto-degrade on failure, auto-recover
  - Structured logs + metrics counters
  - User-readable degradation reports
```

## Database Schema (13 Tables)

| Table | Purpose |
|---|---|
| customers | Customer records |
| chat_sessions | Chat session history |
| messages | Chat messages |
| tickets | Support tickets |
| ticket_events | Ticket state changes |
| documents | Uploaded documents |
| ingestion_jobs | Async ingestion tasks |
| agent_runs | Agent execution records |
| agent_steps | Per-step audit trail |
| approvals | HITL approval requests |
| eval_runs | Evaluation run records |
| eval_cases | Gold-standard eval cases |
| alembic_version | Migration tracking |

## Key Design Decisions

1. **Coordinator over Swarm**: Predictable, auditable execution plan
2. **Tool Registry over direct dispatch**: Enforced permission gate, no bypass
3. **State-based Tabs over React Router**: Simpler, no routing dependency
4. **Async worker (arq)**: Non-blocking ingestion/eval/agent jobs
5. **SQLite for dev, PostgreSQL for prod**: Alembic migrations handle both

## Deployment

```bash
# Full stack (Docker)
docker compose up -d

# Components:
# - Qdrant (port 6333)
# - PostgreSQL (port 5432)
# - Redis (port 6379)
# - FastAPI App (port 8000)
# - Worker (arq)

# Initialize
python -m alembic upgrade head
python scripts/seed_eval_docs.py
```
