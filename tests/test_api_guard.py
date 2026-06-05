"""API Guard test."""
import pytest
from app.api_guard import ApiGuardMiddleware

def test_api_guard_imports():
    assert ApiGuardMiddleware is not None

def test_public_paths():
    from app.api_guard import PUBLIC_PATHS
    assert "/health" in PUBLIC_PATHS
    assert "/metrics" in PUBLIC_PATHS
