# EcomAgent Deployment Guide

> Version 2.0 | E-commerce After-Sales Multi-Agent System

## Local Development

### Prerequisites
- Python 3.12+
- NVIDIA GPU with 8GB+ VRAM (optional, automatic CPU fallback)
- Git

### Step-by-Step

```bash
# 1. Clone and checkout
git clone https://github.com/a707-afk/REACTAGENT.git
cd REACTAGENT
git checkout feature/ecom-agent

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env: set SENSENOVA_API_KEYS (comma-separated), QWEN_EMBEDDING_MODEL_PATH
```

### Build Knowledge Base

```bash
# Generate e-commerce FAQ markdown
python scripts/build_ecom_kb.py

# Build Qdrant vector index + BM25 corpus
python scripts/reindex.py
```

### Start Server

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Frontend UI: http://127.0.0.1:8000/
- API Docs: http://127.0.0.1:8000/docs
- Health Check: http://127.0.0.1:8000/health

## Docker Deployment

### Prerequisites
- Docker Engine 24+
- Docker Compose v2

### Build and Run

```bash
# Start infrastructure services (PostgreSQL + Qdrant)
docker compose up -d qdrant postgres

# Build and run app
docker compose up -d app
```

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SENSENOVA_API_KEYS` | (required) | LLM API keys, comma-separated |
| `QWEN_EMBEDDING_MODEL_PATH` | `/models/qwen3-embedding` | Embedding model path |
| `DATABASE_URL` | `sqlite+aiosqlite:///...` | Database connection string |
| `INFERENCE_DEVICE` | `auto` | `cpu`, `cuda`, or `auto` |
| `QDRANT_PATH` | `data/qdrant_local` | Qdrant local storage |
| `DEBUG` | `false` | Enable debug mode |

## Production Considerations

- Use PostgreSQL instead of SQLite (`DATABASE_URL=postgresql+asyncpg://...`)
- Run Qdrant in server mode (already configured in docker-compose.yml)
- Set `DEBUG=false`, `DOMAIN_ROUTER_ENABLED=true`
- Configure proper `SENSENOVA_API_KEYS` with failover keys
- Set `INFERENCE_DEVICE=cpu` for CPU-only servers
- Frontend static files are served from `static/app/` by the FastAPI app

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Model not found | Ensure QWEN_EMBEDDING_MODEL_PATH points to valid Qwen3-Embedding directory |
| LLM calls fail | Check SENSENOVA_API_KEYS, network connectivity to token.sensenova.cn |
| Qdrant lock error | Only one process can access qdrant_local. Use Qdrant server in production |
| Slow first request | BM25 cold start. Pre-warm is built into server lifespan |
| SSE not streaming | Check browser EventSource support. Fallback to POST /agent/ticket |
