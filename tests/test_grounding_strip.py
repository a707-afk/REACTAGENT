"""Grounding strip test."""
import pytest
from app.citation_verify import strip_unsupported_sentences

def test_strip_unsupported_empty():
    assert strip_unsupported_sentences("", "context") == ""
    assert strip_unsupported_sentences("text", "") == "text"
