#!/bin/bash
# CS Agent Backend — DSW Server Startup Script
# 用法: bash start_dsw.sh

set -e

cd /mnt/workspace/rag-kb-project

# 环境变量
export PYTHONPATH=/mnt/workspace/rag-kb-project
export QWEN_EMBEDDING_MODEL_PATH=/mnt/workspace/rag-kb-project/models/Qwen/Qwen3-Embedding-0___6B
export QDRANT_PATH=data/qdrant_local
export QDRANT_COLLECTION_NAME=rag_kb
export QDRANT_COLLECTION_NAME_CN=kb_cn_general
export SENSENOVA_API_KEYS="REDACTED_KEY,REDACTED_KEY,REDACTED_KEY"
export RERANK_ENABLED=false

# 杀掉旧进程
pkill -f "uvicorn app.main" 2>/dev/null || true
sleep 2

# 启动
echo "Starting CS Agent Backend on port 8000..."
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &

# 等待就绪
sleep 15
if curl -s http://localhost:8000/health | grep -q ok; then
    echo "Server started successfully!"
    curl -s http://localhost:8000/health
else
    echo "ERROR: Server failed to start. Check /tmp/uvicorn.log"
    tail -20 /tmp/uvicorn.log
    exit 1
fi