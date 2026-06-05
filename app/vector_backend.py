"""??????????? qdrant?"""
from __future__ import annotations

from typing import Literal

ResolvedBackend = Literal["qdrant"]


def resolve_vector_backend(settings=None) -> Literal["qdrant"]:
    """????????? qdrant?"""
    return "qdrant"
