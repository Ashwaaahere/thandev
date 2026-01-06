"""
Regression tests for tenant/user ID validation
Ensures invalid IDs (non-UUID) are rejected with 400, not 500
"""
import pytest
from unittest.mock import patch
import uuid


@pytest.fixture
def valid_uuid():
    """Generate a valid UUID for testing"""
    return str(uuid.uuid4())


def test_invalid_tenant_id_rejected_400(client):
    """Test that invalid tenant ID (non-UUID) returns 400, not 500"""
    # Use a long non-UUID string like "test-tenant-0b5ccc58-914f-41af-813d-510eb8aa0b2c"
    invalid_tenant_id = "test-tenant-0b5ccc58-914f-41af-813d-510eb8aa0b2c"
    valid_user_id = str(uuid.uuid4())
    
    response = client.post(
        "/api/scans",
        headers={
            "X-Thandev-Tenant-Id": invalid_tenant_id,
            "X-Thandev-User-Id": valid_user_id,
        },
        json={
            "project_id": str(uuid.uuid4()),
            "scan_level": "basic"
        }
    )
    
    # Should return 400 Bad Request, not 500 Internal Server Error
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    assert "Invalid tenant_id" in response.json()["detail"] or "Must be a valid UUID" in response.json()["detail"]


def test_invalid_user_id_rejected_400(client):
    """Test that invalid user ID (non-UUID) returns 400, not 500"""
    # Use invalid user_id as tenant_id fallback to trigger validation
    invalid_user_id = "test-user-0b5ccc58-914f-41af-813d-510eb8aa0b2c"
    
    response = client.post(
        "/api/scans",
        headers={
            "X-Thandev-User-Id": invalid_user_id,
            # Don't provide tenant_id so it falls back to user_id
        },
        json={
            "project_id": str(uuid.uuid4()),
            "scan_level": "basic"
        }
    )
    
    # Should return 400 Bad Request, not 500 Internal Server Error
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    assert "Invalid" in response.json()["detail"] and ("user_id" in response.json()["detail"] or "tenant_id" in response.json()["detail"] or "UUID" in response.json()["detail"])


def test_valid_uuid_ids_accepted(client, db_session):
    """Test that valid UUID IDs are accepted (may fail for other reasons like missing project, but not 400)"""
    valid_uuid = str(uuid.uuid4())
    
    # This test may fail with 404 (project not found) or 401 (missing auth), but should NOT fail with 400
    response = client.post(
        "/api/scans",
        headers={
            "X-Thandev-Tenant-Id": valid_uuid,
            "X-Thandev-User-Id": valid_uuid,
        },
        json={
            "project_id": str(uuid.uuid4()),
            "scan_level": "basic"
        }
    )
    
    # Should NOT be 400 (invalid ID)
    assert response.status_code != 400, f"Valid UUID was rejected with 400: {response.text}"
    # Could be 401, 404, 403, etc. but not 400 for invalid ID format


def test_empty_tenant_id_rejected_400(client):
    """Test that empty tenant ID returns 400"""
    # Use empty string as tenant_id, which should fall back to user_id
    # But if both are problematic, we should get 400
    response = client.post(
        "/api/scans",
        headers={
            "X-Thandev-Tenant-Id": "",
            "X-Thandev-User-Id": "",  # Also empty to trigger validation
        },
        json={
            "project_id": str(uuid.uuid4()),
            "scan_level": "basic"
        }
    )
    
    # Should return 400 or 401 (missing headers), but not 500
    assert response.status_code in (400, 401), f"Expected 400 or 401, got {response.status_code}: {response.text}"


def test_malformed_uuid_rejected_400(client):
    """Test that malformed UUID strings are rejected"""
    malformed_ids = [
        "not-a-uuid",
        "12345",
        "uuid-1234-5678",
        "00000000-0000-0000-0000-00000000000",  # Too short
        "00000000-0000-0000-0000-0000000000000",  # Too long
    ]
    
    for malformed_id in malformed_ids:
        response = client.post(
            "/api/scans",
            headers={
                "X-Thandev-Tenant-Id": malformed_id,
                "X-Thandev-User-Id": str(uuid.uuid4()),
            },
            json={
                "project_id": str(uuid.uuid4()),
                "scan_level": "basic"
            }
        )
        
        assert response.status_code == 400, f"Malformed ID '{malformed_id}' was not rejected: {response.text}"

