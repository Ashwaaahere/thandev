import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.domain_verification import DomainVerification, DomainVerificationStatus
from app.models.allowed_domain import AllowedDomain
from tests.conftest import auth_headers


def _mk_project(db: Session, tenant_id: str, user_id: str, url: str, root: str = "example.com", verified: bool = False):
    project = Project(
        id=str(uuid.uuid4()),
        name="TestProj",
        target_url=url,
        root_domain=root,
        owner_id=user_id,
        tenant_id=tenant_id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    if verified:
        dv = DomainVerification(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=project.id,
            domain="example.com",
            status=DomainVerificationStatus.VERIFIED,
            token="t",
        )
        db.add(dv)
        db.commit()

    return project


def test_forbid_unverified_domain(client: TestClient, db_session: Session, seed_tenant_user):
    tenant_id = seed_tenant_user["tenant_id"]
    user_id = seed_tenant_user["user_id"]
    _mk_project(db_session, tenant_id, user_id, "https://example.com", verified=False)

    resp = client.post(
        "/api/scans/quick",
        json={"target_url": "https://example.com", "scan_level": "basic"},
        headers=auth_headers(tenant_id, user_id),
    )
    assert resp.status_code == 403
    assert "DOMAIN_NOT_VERIFIED" in resp.text


def test_allowlist_domain_allows_scan(client: TestClient, db_session: Session, seed_tenant_user):
    tenant_id = seed_tenant_user["tenant_id"]
    user_id = seed_tenant_user["user_id"]
    project = _mk_project(db_session, tenant_id, user_id, "https://bwapp.test", root="bwapp.test", verified=False)

    allowed = AllowedDomain(
        id=str(uuid.uuid4()),
        domain="bwapp.test",
        scope="tenant",
        tenant_id=tenant_id,
        enabled=True,
    )
    db_session.add(allowed)
    db_session.commit()

    resp = client.post(
        "/api/scans/quick",
        json={"project_id": project.id, "scan_level": "basic"},
        headers=auth_headers(tenant_id, user_id),
    )
    assert resp.status_code == 201, resp.text

