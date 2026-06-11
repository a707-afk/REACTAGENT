"""?? Embedding ?????

?? sentence-transformers?????? bge ????
llama-index HuggingFaceEmbedding????????????? async?
"""
from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any, List, Optional

from app.config import get_settings
from app.inference_device import log_device_context, resolve_inference_device

logger = logging.getLogger(__name__)

_KNOWN_ST_MODELS = frozenset({
    "BAAI/bge-m3",
    "BAAI/bge-large-zh-v1.5",
    "BAAI/bge-small-zh-v1.5",
    "BAAI/bge-base-zh-v1.5",
    "intfloat/multilingual-e5-large",
    "intfloat/multilingual-e5-base",
    "intfloat/e5-mistral-7b-instruct",
    "maidalun1020/bce-embedding-base_v1",
})


def _is_sentence_transformers_model(name: str) -> bool:
    """?????????? sentence-transformers ???"""
    lower = name.lower()
    if any(known.lower() in lower for known in _KNOWN_ST_MODELS):
        return True
    if "/bge-" in lower or "bge-" in lower:
        return True
    if "bce-embedding" in lower:
        return True
    if "multilingual-e5" in lower:
        return True
    return False


@lru_cache(maxsize=2)
def _load_st_model(model_path: str, device: str):
    """?? sentence-transformers ?????????????"""
    from sentence_transformers import SentenceTransformer
    log_device_context(f"ST: {model_path}", device)
    return SentenceTransformer(model_path, device=device)


@lru_cache(maxsize=2)
def _load_hf_model(model_name: str, device: str):
    """?? llama-index HuggingFaceEmbedding ?????"""
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    log_device_context(f"HF: {model_name}", device)
    return HuggingFaceEmbedding(
        model_name=model_name,
        trust_remote_code=True,
        device=device,
    )


class EmbeddingModel:
    """??? Embedding ?????

    - ???? sentence-transformers ? HuggingFace ??
    - ?? async / sync ?? encode ??
    - ???? encode
    - LRU ????????
    """

    def __init__(
        self,
        model_name: str,
        model_path: Optional[str] = None,
        device: str = "cpu",
    ) -> None:
        self._model_name = model_name
        self._model_path = model_path or model_name
        self._device = device
        self._resolved_path: Optional[str] = None

        import os
        if _is_sentence_transformers_model(model_name):
            local_path = model_path or ""
            if local_path and os.path.isdir(local_path):
                self._resolved_path = local_path
            elif os.path.isdir(model_name):
                self._resolved_path = model_name
            else:
                self._resolved_path = model_name
            self._st = True
        else:
            self._st = False

    def _get_model(self):
        """????????????lru_cache ??????"""
        if self._st:
            return _load_st_model(self._resolved_path or self._model_path, self._device)
        return _load_hf_model(self._model_path, self._device)

    def encode_sync(self, text: str) -> List[float]:
        """?????????"""
        model = self._get_model()
        if self._st:
            return model.encode(text, normalize_embeddings=True).tolist()
        return model.get_text_embedding(text)

    def encode_batch_sync(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """???????"""
        if not texts:
            return []
        model = self._get_model()
        if self._st:
            embs = model.encode(texts, normalize_embeddings=True, batch_size=batch_size, show_progress_bar=False)
            return [e.tolist() for e in embs]
        return [model.get_text_embedding(t) for t in texts]

    async def encode(self, text: str) -> List[float]:
        """?????????"""
        return await asyncio.to_thread(self.encode_sync, text)

    async def encode_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """???????"""
        return await asyncio.to_thread(self.encode_batch_sync, texts, batch_size)

    @property
    def dimension(self) -> int:
        """?? embedding ?????"""
        model = self._get_model()
        if self._st:
            return model.get_embedding_dimension()
        try:
            return model._model.config.hidden_size
        except Exception:
            test_emb = model.get_text_embedding("test")
            return len(test_emb)

    @property
    def is_sentence_transformers(self) -> bool:
        return self._st


def get_llamaindex_embedding():
    """???? llama-index BaseEmbedding ??? embedding ???"""
    from llama_index.core.embeddings import BaseEmbedding

    class _LlamaIndexAdapter(BaseEmbedding):
        """????? EmbeddingModel ??? llama-index BaseEmbedding?"""

        def __init__(self, model: EmbeddingModel, **kwargs: Any) -> None:
            super().__init__(model_name=model._model_name, embed_batch_size=32, **kwargs)
            self._model = model

        def _get_text_embedding(self, text: str) -> List[float]:
            return self._model.encode_sync(text)

        def _get_query_embedding(self, query: str) -> List[float]:
            return self._model.encode_sync(query)

        async def _aget_text_embedding(self, text: str) -> List[float]:
            return await self._model.encode(text)

        async def _aget_query_embedding(self, query: str) -> List[float]:
            return await self._model.encode(query)

    return _LlamaIndexAdapter(get_embedding_model())


@lru_cache(maxsize=1)
def get_embedding_model() -> EmbeddingModel:
    """????? EmbeddingModel?"""
    settings = get_settings()
    device = resolve_inference_device(settings)
    model_name = settings.embedding_model_name
    model_path = settings.embedding_model_path
    log_device_context(f"Embedding: {model_name}", device)
    return EmbeddingModel(
        model_name=model_name,
        model_path=model_path,
        device=device,
    )


async def get_text_embedding(text: str) -> List[float]:
    """????????? embedding?"""
    model = get_embedding_model()
    return await model.encode(text)


async def get_text_embeddings_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """?????? embedding?"""
    model = get_embedding_model()
    return await model.encode_batch(texts, batch_size=batch_size)


def get_text_embedding_sync(text: str) -> List[float]:
    """???? embedding?"""
    return get_embedding_model().encode_sync(text)
