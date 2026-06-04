# syntax=docker/dockerfile:1

# --- 前端构建 ---
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- API 运行 ---
FROM python:3.11-slim AS api
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY static/ ./static/
COPY --from=frontend /static/app ./static/app

EXPOSE 8000

# 示例环境变量（可在 compose 中覆盖）
ENV DOCS_DIR=data/docs/enterprise_ai_ops \
    CHROMA_COLLECTION_NAME=enterprise_ai_ops \
    BM25_CORPUS_PATH=data/bm25_enterprise_corpus.jsonl \
    VECTOR_BACKEND=chroma

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
