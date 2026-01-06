"""
Regression tests for notifications API when table is missing
Ensures graceful handling in dev/test, proper error in production
"""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import ProgrammingError
import uuid

from app.core.config import settings
from tests.conftest import auth_headers


def test_notifications_missing_table_returns_empty_in_dev(client, db_session, seed_tenant_user):
    """Test that missing notifications table returns empty list in dev/test, not 500"""
    tenant_id = seed_tenant_user["tenant_id"]
    user_id = seed_tenant_user["user_id"]
    
    # Mock environment to be "local"
    with patch.object(settings, 'ENVIRONMENT', 'local'):
        # Mock the database query to raise ProgrammingError for missing table
        from app.models.notification import Notification
        
        # Create a mock session that raises ProgrammingError on count()
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.count.side_effect = ProgrammingError(
            "relation \"notifications\" does not exist",
            None,
            None
        )
        mock_session.query.return_value = mock_query
        
        # Override get_db to return our mock session
        from app.core.database import get_db
        def get_mock_db():
            yield mock_session
        
        from app.main import app
        app.dependency_overrides[get_db] = get_mock_db
        try:
            response = client.get(
                "/api/notifications",
                headers=auth_headers(tenant_id, user_id)
            )
            
            # Should return 200 with empty list, not 500
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            data = response.json()
            assert data["total"] == 0
            assert data["items"] == []
        finally:
            app.dependency_overrides.clear()


def test_notifications_missing_table_returns_503_in_production(client, db_session, seed_tenant_user):
    """Test that missing notifications table returns 503 in production, not 500"""
    # Mock environment to be "production"
    with patch.object(settings, 'ENVIRONMENT', 'production'):
        # Mock the database query to raise ProgrammingError for missing table
        from app.models.notification import Notification
        
        # Create a mock session that raises ProgrammingError on count()
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.count.side_effect = ProgrammingError(
            "relation \"notifications\" does not exist",
            None,
            None
        )
        mock_session.query.return_value = mock_query
        
        # Override get_db to return our mock session
        from app.core.database import get_db
        def get_mock_db():
            yield mock_session
        
        from app.main import app
        app.dependency_overrides[get_db] = get_mock_db
        try:
            tenant_id = seed_tenant_user["tenant_id"]
            user_id = seed_tenant_user["user_id"]
            
            response = client.get(
                "/api/notifications",
                headers=auth_headers(tenant_id, user_id)
            )
            
            # Should return 503 Service Unavailable, not 500
            assert response.status_code == 503, f"Expected 503, got {response.status_code}: {response.text}"
            assert "temporarily unavailable" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()


def test_notifications_mark_read_handles_missing_table_in_dev(client, db_session, seed_tenant_user):
    """Test that mark notification read handles missing table gracefully in dev"""
    notification_id = str(uuid.uuid4())
    
    with patch.object(settings, 'ENVIRONMENT', 'local'):
        from app.models.notification import Notification
        
        # Create a mock session that raises ProgrammingError
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.side_effect = ProgrammingError(
            "relation \"notifications\" does not exist",
            None,
            None
        )
        mock_session.query.return_value = mock_query
        
        # Override get_db to return our mock session
        from app.core.database import get_db
        def get_mock_db():
            yield mock_session
        
        from app.main import app
        from app.core.tenant_utils import require_tenant, get_current_user
        from app.models.tenant import Tenant
        from app.models.user import User
        
        tenant_id = seed_tenant_user["tenant_id"]
        user_id = seed_tenant_user["user_id"]
        
        def mock_require_tenant():
            return Tenant(id=tenant_id, name="Test", plan=seed_tenant_user["tenant"].plan)
        
        def mock_get_current_user():
            return User(id=user_id, tenant_id=tenant_id, email="test@example.com", username="test", hashed_password="")
        
        # Save original overrides
        original_get_db = app.dependency_overrides.get(get_db)
        original_require_tenant = app.dependency_overrides.get(require_tenant)
        original_get_current_user = app.dependency_overrides.get(get_current_user)
        
        app.dependency_overrides[get_db] = get_mock_db
        app.dependency_overrides[require_tenant] = mock_require_tenant
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            response = client.post(
                f"/api/notifications/{notification_id}/read",
                headers=auth_headers(tenant_id, user_id)
            )
            
            # Should return 404 (not found), not 500
            assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        finally:
            # Restore original overrides
            if original_get_db:
                app.dependency_overrides[get_db] = original_get_db
            else:
                app.dependency_overrides.pop(get_db, None)
            if original_require_tenant:
                app.dependency_overrides[require_tenant] = original_require_tenant
            else:
                app.dependency_overrides.pop(require_tenant, None)
            if original_get_current_user:
                app.dependency_overrides[get_current_user] = original_get_current_user
            else:
                app.dependency_overrides.pop(get_current_user, None)


def test_notifications_mark_all_read_handles_missing_table_in_dev(client, db_session, seed_tenant_user):
    """Test that mark all read handles missing table gracefully in dev"""
    with patch.object(settings, 'ENVIRONMENT', 'local'):
        from app.models.notification import Notification
        
        # Create a mock session that raises ProgrammingError
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.update.side_effect = ProgrammingError(
            "relation \"notifications\" does not exist",
            None,
            None
        )
        mock_session.query.return_value = mock_query
        
        # Override get_db to return our mock session
        from app.core.database import get_db
        def get_mock_db():
            yield mock_session
        
        from app.main import app
        # Save original override from client fixture
        original_get_db = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = get_mock_db
        try:
            tenant_id = seed_tenant_user["tenant_id"]
            user_id = seed_tenant_user["user_id"]
            
            response = client.post(
                "/api/notifications/read-all",
                headers=auth_headers(tenant_id, user_id)
            )
            
            # Should return 200 with 0 count, not 500
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            data = response.json()
            assert data["updated_count"] == 0
        finally:
            # Restore original override
            if original_get_db:
                app.dependency_overrides[get_db] = original_get_db
            else:
                app.dependency_overrides.pop(get_db, None)

