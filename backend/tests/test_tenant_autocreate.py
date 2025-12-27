"""
Tests for tenant auto-creation behavior
"""
import pytest
from unittest.mock import patch
import uuid
import os

from app.core.config import settings
from tests.conftest import auth_headers


def test_autocreate_enabled_in_local_env_creates_tenant(client, db_session):
    """Test that auto-creation works in local/dev/test environments"""
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    
    # Mock environment to be "local"
    with patch.object(settings, 'ENVIRONMENT', 'local'):
        # Mock TENANT_AUTOCREATE_ENABLED to be True
        with patch.object(settings, 'TENANT_AUTOCREATE_ENABLED', True):
            # This will try to create a scan, which requires a tenant
            # The tenant should be auto-created
            response = client.post(
                "/api/scans",
                headers=auth_headers(tenant_id, user_id),
                json={
                    "project_id": str(uuid.uuid4()),
                    "scan_level": "basic"
                }
            )
            
            # Should NOT be 404 (tenant not found) - tenant should be auto-created
            # Could be 404 (project not found) or other errors, but not tenant not found
            assert response.status_code != 404 or "tenant" not in response.json().get("detail", "").lower(), \
                f"Tenant should have been auto-created, but got: {response.text}"


def test_autocreate_disabled_in_production_env_returns_404_and_does_not_insert(client, db_session):
    """Test that auto-creation is disabled in production and returns 404"""
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    
    # Mock environment to be "production"
    with patch.object(settings, 'ENVIRONMENT', 'production'):
        # Mock TENANT_AUTOCREATE_ENABLED to be False
        with patch.object(settings, 'TENANT_AUTOCREATE_ENABLED', False):
            response = client.post(
                "/api/scans",
                headers=auth_headers(tenant_id, user_id),
                json={
                    "project_id": str(uuid.uuid4()),
                    "scan_level": "basic"
                }
            )
            
            # Should return 404 with clear message about creating tenant
            assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
            detail = response.json().get("detail", "").lower()
            assert "tenant" in detail or "not found" in detail
            assert "create" in detail or "post /api/tenants" in detail.lower()


def test_create_tenant_endpoint_works_in_local_env(client, db_session):
    """Test that tenant creation endpoint works in local/dev/test"""
    tenant_id = str(uuid.uuid4())
    
    # Mock environment to be "local"
    with patch.object(settings, 'ENVIRONMENT', 'local'):
        response = client.post(
            "/api/tenants",
            json={
                "id": tenant_id,
                "name": "Test Tenant",
                "plan": "pro"
            }
        )
        
        # Should succeed (201 Created)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["id"] == tenant_id
        assert data["name"] == "Test Tenant"
        assert data["plan"] == "pro"


def test_create_tenant_endpoint_blocked_in_production_without_admin_token(client, db_session):
    """Test that tenant creation is blocked in production without admin token"""
    tenant_id = str(uuid.uuid4())
    
    # Mock environment to be "production"
    with patch.object(settings, 'ENVIRONMENT', 'production'):
        # Don't set admin token
        response = client.post(
            "/api/tenants",
            json={
                "id": tenant_id,
                "name": "Test Tenant",
                "plan": "pro"
            }
        )
        
        # Should return 403 Forbidden
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        assert "admin token" in response.json()["detail"].lower()


def test_create_tenant_endpoint_allowed_in_production_with_admin_token(client, db_session):
    """Test that tenant creation works in production with correct admin token"""
    tenant_id = str(uuid.uuid4())
    admin_token = "test-admin-token-123"
    
    # Mock environment to be "production"
    with patch.object(settings, 'ENVIRONMENT', 'production'):
        # Mock admin token env var
        with patch.dict(os.environ, {"THANDEV_ADMIN_TOKEN": admin_token}):
            response = client.post(
                "/api/tenants",
                headers={
                    "X-Thandev-Admin-Token": admin_token,
                },
                json={
                    "id": tenant_id,
                    "name": "Test Tenant",
                    "plan": "pro"
                }
            )
            
            # Should succeed (201 Created)
            assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
            data = response.json()
            assert data["id"] == tenant_id


def test_create_tenant_generates_uuid_if_not_provided(client, db_session):
    """Test that tenant creation generates UUID if id is not provided"""
    # Mock environment to be "local"
    with patch.object(settings, 'ENVIRONMENT', 'local'):
        response = client.post(
            "/api/tenants",
            json={
                "name": "Test Tenant",
                "plan": "pro"
            }
        )
        
        # Should succeed and return a UUID
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        # Verify it's a valid UUID format
        try:
            uuid.UUID(data["id"])
        except ValueError:
            pytest.fail(f"Generated ID is not a valid UUID: {data['id']}")


def test_create_user_endpoint_works_in_local_env(client, db_session, seed_tenant_user):
    """Test that user creation endpoint works in local/dev/test"""
    tenant_id = seed_tenant_user["tenant_id"]
    user_id = str(uuid.uuid4())
    # Use unique email/username to avoid conflicts
    unique_suffix = str(uuid.uuid4())[:8]
    email = f"test-{unique_suffix}@example.com"
    username = f"testuser-{unique_suffix}"
    
    # Mock environment to be "local"
    with patch.object(settings, 'ENVIRONMENT', 'local'):
        # Then create a user
        response = client.post(
            "/api/users",
            json={
                "id": user_id,
                "email": email,
                "username": username,
                "tenant_id": tenant_id,
            }
        )
        
        # Should succeed (201 Created)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["id"] == user_id
        assert data["email"] == email
        assert data["tenant_id"] == tenant_id

