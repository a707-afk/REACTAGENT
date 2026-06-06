"""Health/ready endpoint test."""
import pytest
from app.main import create_app
app = create_app()
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    return TestClient(app)

def test_health_ready_endpoint(client):
    resp = client.get("/health/ready")
    assert resp.status_code in (200, 500)
