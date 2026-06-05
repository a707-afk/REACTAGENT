"""LLM zhipu test."""
import pytest
from app.llm_zhipu import chat_completion, get_zhipu_client

def test_chat_completion_no_key():
    """无 API Key 时应报错。"""
    with pytest.raises(RuntimeError, match="未配置"):
        chat_completion("sys", "user")
