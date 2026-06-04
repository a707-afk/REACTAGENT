"""LlamaIndex + 本地 HuggingFace/Sentence-Transformers 布局的 Embedding 模型。"""
from __future__ import annotations

from functools import lru_cache

from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from app.config import get_settings
from app.inference_device import log_device_context, resolve_inference_device


@lru_cache(maxsize=1)
def get_embedding_model() -> HuggingFaceEmbedding:
    """单例懒加载；仅在首次入库/检索时调用，避免 import app.main 即加载 torch。"""
    settings = get_settings()
    device = resolve_inference_device(settings)
    log_device_context("Qwen Embedding", device)
    return HuggingFaceEmbedding(
        model_name=settings.qwen_embedding_model_path,
        trust_remote_code=True,
        device=device,
    )
