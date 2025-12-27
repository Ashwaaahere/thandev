import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.tenant import Tenant, PlanTier
import uuid


def _mk_user(db: Session, *, provider="github", external_id="12345", is_admin=False):
    tenant = Tenant(id=str(uuid.uuid4()), name="t", plan=PlanTier.PRO)
    user = User(
        id=str(uuid.uuid4()),
        email=f"user-{external_id}@example.com",
        username=f"user-{external_id}",
        external_provider=provider,
        external_user_id=external_id,
        tenant_id=tenant.id,
        is_admin=is_admin,
        is_approved=True,
    )
    db.add(tenant)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_superadmin_env_bootstrap_sets_admin(client: TestClient, db_session: Session):
    # Arrange env list
    settings.set_superadmin_external_ids({("github", "9999")})
    payload = {
        "provider": "github",
        "external_user_id": "9999",
        "email": "foo@example.com",
        "username": "foo",
        "name": "Foo",
    }
    # Act
    resp = client.post("/api/auth/bootstrap", json=payload)
    assert resp.status_code == 200
    user = db_session.query(User).filter(User.external_user_id == "9999").first()
    assert user is not None
    assert user.is_admin is True
    assert user.is_approved is True


def test_setup_token_bootstrap_when_no_admins(client: TestClient, db_session: Session, monkeypatch):
    user = _mk_user(db_session, external_id="2222")
    monkeypatch.setattr(settings, "THANDEV_SETUP_TOKEN", "setup-secret", raising=False)

    resp = client.post(
        "/api/admin/bootstrap-superadmin",
        params={"external_provider": "github", "external_user_id": "2222"},
        headers={"Authorization": "Bearer setup-secret"},
    )
    assert resp.status_code == 200
    db_session.refresh(user)
    assert user.is_admin is True
    assert user.is_approved is True


def test_setup_token_rejected_if_admin_exists(client: TestClient, db_session: Session, monkeypatch):
    _mk_user(db_session, external_id="3333", is_admin=True)
    monkeypatch.setattr(settings, "THANDEV_SETUP_TOKEN", "setup-secret", raising=False)

    resp = client.post(
        "/api/admin/bootstrap-superadmin",
        params={"external_provider": "github", "external_user_id": "3333"},
        headers={"Authorization": "Bearer setup-secret"},
    )
    assert resp.status_code == 409


def test_setup_token_bad_token(client: TestClient, db_session: Session, monkeypatch):
    _mk_user(db_session, external_id="4444")
    monkeypatch.setattr(settings, "THANDEV_SETUP_TOKEN", "setup-secret", raising=False)

    resp = client.post(
        "/api/admin/bootstrap-superadmin",
        params={"external_provider": "github", "external_user_id": "4444"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 403


def test_non_admin_cannot_access_admin_endpoints(client: TestClient, db_session: Session):
    user = _mk_user(db_session, external_id="5555", is_admin=False)
    headers = {
        "X-Thandev-User-Id": user.id,
        "X-Thandev-Tenant-Id": user.tenant_id,
    }
    resp = client.get("/api/admin/users", headers=headers)
    assert resp.status_code == 403

