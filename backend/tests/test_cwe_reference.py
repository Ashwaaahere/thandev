"""
Tests for CWE reference endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_cwe_reference_valid():
    """Test getting CWE reference for a valid CWE ID in dataset."""
    response = client.get("/api/v1/reference/cwe/1021")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1021
    assert data["title"] is not None
    assert data["summary"] is not None
    assert "mitre" in data["links"]
    assert "nvd_search" in data["links"]
    assert "cwe.mitre.org" in data["links"]["mitre"]
    assert "nvd.nist.gov" in data["links"]["nvd_search"]


def test_get_cwe_reference_with_cwe_prefix():
    """Test getting CWE reference with CWE- prefix."""
    response = client.get("/api/v1/reference/cwe/CWE-1021")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1021


def test_get_cwe_reference_not_in_dataset():
    """Test getting CWE reference for CWE not in local dataset."""
    response = client.get("/api/v1/reference/cwe/9999")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 9999
    assert data["title"] is None
    assert data["summary"] is None
    assert "mitre" in data["links"]
    assert "nvd_search" in data["links"]


def test_get_cwe_reference_invalid_format():
    """Test getting CWE reference with invalid format."""
    response = client.get("/api/v1/reference/cwe/invalid")
    assert response.status_code == 400
    assert "Invalid CWE ID format" in response.json()["detail"]


def test_get_cwe_reference_out_of_range():
    """Test getting CWE reference with ID out of valid range."""
    response = client.get("/api/v1/reference/cwe/10000")
    assert response.status_code == 400
    assert "out of valid range" in response.json()["detail"]


def test_get_cwe_reference_zero():
    """Test getting CWE reference with ID 0."""
    response = client.get("/api/v1/reference/cwe/0")
    assert response.status_code == 400
    assert "out of valid range" in response.json()["detail"]


def test_get_cwe_links():
    """Test getting just the links for a CWE."""
    response = client.get("/api/v1/reference/cwe/1021/links")
    assert response.status_code == 200
    data = response.json()
    assert "mitre" in data
    assert "nvd_search" in data
    assert "cwe.mitre.org" in data["mitre"]
    assert "nvd.nist.gov" in data["nvd_search"]

