import os
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal, Base, engine
from app.models.user import User
from app.models.tenant import Tenant, PlanTier

client = TestClient(app)


def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(User).delete()
        db.query(Tenant).delete()
        db.commit()
    finally:
        db.close()


def test_bootstrap_existing_user_returns_uuids():
    _reset_db()
    db = SessionLocal()
    try:
        tenant = Tenant(id=str(uuid.uuid4()), name="test-tenant", plan=PlanTier.FREE)
        user = User(
            id=str(uuid.uuid4()),
            email="tester@example.com",
            username="tester",
            full_name="Tester",
            hashed_password="",
            external_provider="github",
            external_user_id="ext-123",
            tenant_id=tenant.id,
        )
        db.add(tenant)
        db.add(user)
        db.commit()

        payload = {
            "provider": "github",
            "external_user_id": "ext-123",
            "username": "tester",
            "email": "tester@example.com",
            "name": "Tester",
        }
        resp = client.post("/api/auth/bootstrap", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == user.id
        assert data["tenant_id"] == tenant.id
    finally:
        db.close()
        _reset_db()


def test_bootstrap_blocks_new_user_when_self_service_disabled(monkeypatch):
    _reset_db()
    from app.core.config import settings

    original_env = settings.ENVIRONMENT
    original_flag = os.getenv("SELF_SERVICE_SIGNUP_ENABLED")

    try:
        settings.ENVIRONMENT = "production"
        if "SELF_SERVICE_SIGNUP_ENABLED" in os.environ:
            del os.environ["SELF_SERVICE_SIGNUP_ENABLED"]

        payload = {
            "provider": "github",
            "external_user_id": "ext-new",
            "username": "newuser",
            "email": "newuser@example.com",
            "name": "New User",
        }
        resp = client.post("/api/auth/bootstrap", json=payload)
        assert resp.status_code == 403
        assert "Self-service signup is disabled" in resp.text
    finally:
        settings.ENVIRONMENT = original_env
        if original_flag is not None:
            os.environ["SELF_SERVICE_SIGNUP_ENABLED"] = original_flag
        _reset_db()
"""
Tests for /api/auth/bootstrap endpoint.
"""
import pytest
from unittest.mock import patch
from app.core.config import settings


@pytest.fixture
def bootstrap_payload():
    return {
        "provider": "github",
        "external_user_id": "123456",
        "username": "octocat",
        "email": "octocat@example.com",
        "name": "The Octocat",
    }


def test_bootstrap_creates_user_and_tenant(client, db_session, bootstrap_payload):
    with patch.object(settings, "ENVIRONMENT", "local"):
        resp = client.post("/api/auth/bootstrap", json=bootstrap_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] is True
        assert len(data["user_id"]) == 36
        assert len(data["tenant_id"]) == 36
        assert data["tenant_plan"] in ("free", "basic", "pro", "enterprise")

        # Second call returns same ids, created=False
        resp2 = client.post("/api/auth/bootstrap", json=bootstrap_payload)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["created"] is False
        assert data2["user_id"] == data["user_id"]
        assert data2["tenant_id"] == data["tenant_id"]


def test_bootstrap_blocked_in_production_when_disabled(client, bootstrap_payload):
    # Ensure flag is not set
    with patch.object(settings, "ENVIRONMENT", "production"):
        with patch.object(settings, "SELF_SERVICE_SIGNUP_ENABLED", False):
            resp = client.post("/api/auth/bootstrap", json=bootstrap_payload)
            assert resp.status_code == 403
            assert "disabled" in resp.json()["detail"].lower()


def test_bootstrap_allows_existing_in_production(client, bootstrap_payload):
    # First create in dev
    with patch.object(settings, "ENVIRONMENT", "local"):
        resp = client.post("/api/auth/bootstrap", json=bootstrap_payload)
        assert resp.status_code == 200
        user_id = resp.json()["user_id"]

    # Then set prod + disabled, should still return existing mapping
    with patch.object(settings, "ENVIRONMENT", "production"):
        with patch.object(settings, "SELF_SERVICE_SIGNUP_ENABLED", False):
            resp2 = client.post("/api/auth/bootstrap", json=bootstrap_payload)
            assert resp2.status_code == 200
            assert resp2.json()["user_id"] == user_id
            assert resp2.json()["created"] is False

"""
Tests for the auth bootstrap endpoint.
"""
import uuid
from unittest.mock import patch

from app.core.config import settings


def test_bootstrap_creates_user_and_tenant(client, db_session):
    """Bootstrap should create user+tenant in local/dev."""
    payload = {
        "provider": "github",
        "external_user_id": "123456",
        "username": "octocat",
        "email": "octocat@example.com",
        "name": "The Octo Cat",
    }
    with patch.object(settings, "ENVIRONMENT", "local"):
        resp = client.post("/api/auth/bootstrap", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] is True
    assert uuid.UUID(data["user_id"])
    assert uuid.UUID(data["tenant_id"])
    assert data["tenant_plan"] == "free"


def test_bootstrap_idempotent_returns_existing(client, db_session):
    """Second call should return same IDs and created=False."""
    payload = {
        "provider": "github",
        "external_user_id": "999999",
        "username": "repeat",
        "email": "repeat@example.com",
        "name": "Repeat User",
    }
    with patch.object(settings, "ENVIRONMENT", "local"):
        first = client.post("/api/auth/bootstrap", json=payload)
        assert first.status_code == 200
        first_data = first.json()

        second = client.post("/api/auth/bootstrap", json=payload)
        assert second.status_code == 200
        second_data = second.json()

    assert first_data["user_id"] == second_data["user_id"]
    assert first_data["tenant_id"] == second_data["tenant_id"]
    assert second_data["created"] is False


def test_bootstrap_blocked_in_production_when_disabled(client, db_session):
    """In production with self-service disabled, new identities are blocked."""
    payload = {
        "provider": "github",
        "external_user_id": "prod-block",
        "username": "blocked",
        "email": "blocked@example.com",
        "name": "Blocked User",
    }
    with patch.object(settings, "ENVIRONMENT", "production"), patch.object(settings, "SELF_SERVICE_SIGNUP_ENABLED", False):
        resp = client.post("/api/auth/bootstrap", json=payload)
    assert resp.status_code == 403
    assert "self-service signup is disabled" in resp.json()["detail"].lower()

