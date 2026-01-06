import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from .conftest import auth_headers
from app.models.tenant import Tenant, PlanTier
from app.models.user import User


def _create_user_and_tenant(db_session: Session):
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    tenant = Tenant(
        id=tenant_id,
        name=f"Tenant {tenant_id[:8]}",
        plan=PlanTier.PRO,
    )
    user = User(
        id=user_id,
        email=f"test-{user_id[:8]}@example.com",
        username=f"testuser-{user_id[:8]}",
        hashed_password="",
        tenant_id=tenant_id,
    )
    db_session.add(tenant)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(tenant)
    db_session.refresh(user)

    return {"tenant_id": tenant_id, "user_id": user_id, "tenant": tenant, "user": user}


def test_unapproved_user_blocked(client: TestClient, db_session: Session):
    objs = _create_user_and_tenant(db_session)
    user = objs["user"]
    user.is_approved = False
    db_session.commit()

    headers = auth_headers(objs["tenant_id"], objs["user_id"])

    test_matrix = [
        ("get", "/api/projects", None),
        ("post", "/api/projects", {"name": "p1", "target_url": "https://example.com"}),
        ("post", "/api/scans", {"project_id": "dummy", "scan_level": "basic"}),
        ("get", "/api/notifications", None),
    ]

    for method, path, payload in test_matrix:
        request_kwargs = {"headers": headers}
        if payload is not None and method in ("post", "put", "patch"):
            request_kwargs["json"] = payload
        resp = getattr(client, method)(path, **request_kwargs)
        assert resp.status_code == 403, f"{path} should be blocked for unapproved users"
        assert "Private beta" in resp.text


def test_admin_allowed_even_if_unapproved(client: TestClient, db_session: Session):
    objs = _create_user_and_tenant(db_session)
    user = objs["user"]
    user.is_admin = True
    user.is_approved = False
    db_session.commit()

    headers = auth_headers(objs["tenant_id"], objs["user_id"])
    resp = client.get("/api/projects", headers=headers)
    # Should not be blocked by approval gate
    assert resp.status_code != 403


def test_bootstrap_allowed_for_unapproved(client: TestClient):
    payload = {
        "provider": "github",
        "external_user_id": str(uuid.uuid4()),
        "email": "newuser@example.com",
        "username": "newuser",
        "name": "New User",
    }
    resp = client.post("/api/auth/bootstrap", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "user_id" in data and "tenant_id" in data

