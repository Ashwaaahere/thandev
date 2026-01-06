"""
Tests for health check endpoints
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health_endpoint():
    """Test /health endpoint returns 200"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "thandev-brain"
    assert "version" in data


def test_healthz_endpoint():
    """Test /healthz endpoint returns 200"""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "thandev-brain"
    assert "version" in data


def test_health_and_healthz_return_same_data():
    """Test /health and /healthz return identical data"""
    health_response = client.get("/health")
    healthz_response = client.get("/healthz")
    
    assert health_response.status_code == 200
    assert healthz_response.status_code == 200
    
    assert health_response.json() == healthz_response.json()

