"""Tests for llm.py async client (M1 fix)."""
from __future__ import annotations

import asyncio
from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.asyncio
async def test_achat_completion_uses_async_client():
    """achat_completion must use AsyncOpenAI and not block the event loop."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "Hello from async"

    async def mock_create(**kw):
        return mock_resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create

    with patch("app.llm._get_async_client", return_value=(mock_client, "test-model")):
        from app.llm import achat_completion
        result = await achat_completion("system", "user")
        assert result == "Hello from async"


@pytest.mark.asyncio
async def test_achat_completion_retries_on_failure():
    """achat_completion must retry on 429/503 errors."""
    call_count = 0

    async def mock_create(**kw):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("429 Too Many Requests")
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "OK after retry"
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create

    with patch("app.llm._get_async_client", return_value=(mock_client, "test-model")), \
         patch("app.llm.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(llm_max_retries=3, llm_timeout_seconds=60)
        from app.llm import achat_completion
        result = await achat_completion("system", "user")
        assert result == "OK after retry"
        assert call_count == 3


def test_achat_completion_exists():
    """Verify achat_completion function exists and is a coroutine function."""
    from app.llm import achat_completion
    assert asyncio.iscoroutinefunction(achat_completion)
