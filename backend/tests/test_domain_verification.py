import uuid
from datetime import datetime, timedelta, timezone

import dns.resolver
import pytest

from app.models.project import Project
from app.models.domain_verification import DomainVerification, DomainVerificationStatus
from app.core.config import settings
from app.services.domain_verification import build_record_name
from tests.conftest import auth_headers


def _create_project(db_session, tenant_id, user_id, target_url="http://example.com/"):
    project = Project(
        id=str(uuid.uuid4()),
        name="Example",
        target_url=target_url,
        root_domain="example.com",
        owner_id=user_id,
        tenant_id=tenant_id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def _create_dv(db_session, project, status=DomainVerificationStatus.PENDING, token="tok-123"):
    dv = DomainVerification(
        id=str(uuid.uuid4()),
        tenant_id=project.tenant_id,
        project_id=project.id,
        domain=project.root_domain,
        status=status,
        token=token,
    )
    db_session.add(dv)
    db_session.commit()
    db_session.refresh(dv)
    return dv


def test_unverified_blocks_scan(client, db_session, seed_tenant_user):
    tenant_id = seed_tenant_user["tenant_id"]
    user_id = seed_tenant_user["user_id"]
    project = _create_project(db_session, tenant_id, user_id)
    _create_dv(db_session, project, status=DomainVerificationStatus.PENDING)

    resp = client.post(
        "/api/scans/quick",
        json={"project_id": project.id, "scan_level": "basic"},
        headers=auth_headers(tenant_id, user_id),
    )
    assert resp.status_code == 403
    assert "DOMAIN_NOT_VERIFIED" in resp.text


def test_verified_allows_scan(client, db_session, seed_tenant_user):
    tenant_id = seed_tenant_user["tenant_id"]
    user_id = seed_tenant_user["user_id"]
    project = _create_project(db_session, tenant_id, user_id)
    _create_dv(db_session, project, status=DomainVerificationStatus.VERIFIED)

    resp = client.post(
        "/api/scans/quick",
        json={"project_id": project.id, "scan_level": "basic"},
        headers=auth_headers(tenant_id, user_id),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project.id
    assert data["scan_id"]


def test_allowlist_bypass(client, db_session, seed_tenant_user, monkeypatch):
    tenant_id = seed_tenant_user["tenant_id"]
    user_id = seed_tenant_user["user_id"]
    project = _create_project(db_session, tenant_id, user_id, target_url="http://demo.test/")
    project.root_domain = "demo.test"
    db_session.commit()
    db_session.refresh(project)

    monkeypatch.setattr(settings, "ALLOWED_SCAN_DOMAINS", "demo.test")

    resp = client.post(
        "/api/scans/quick",
        json={"project_id": project.id, "scan_level": "basic"},
        headers=auth_headers(tenant_id, user_id),
    )
    assert resp.status_code == 201


def test_token_rotation_changes_token(client, db_session, seed_tenant_user):
    tenant_id = seed_tenant_user["tenant_id"]
    user_id = seed_tenant_user["user_id"]
    project = _create_project(db_session, tenant_id, user_id)
    dv = _create_dv(db_session, project, status=DomainVerificationStatus.PENDING, token="oldtoken")

    resp = client.post(
        f"/api/projects/{project.id}/domain-verification/request",
        json={"force_rotate": True},
        headers=auth_headers(tenant_id, user_id),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] != "oldtoken"
    assert data["status"] == DomainVerificationStatus.PENDING.value


def test_verify_dns_success(monkeypatch, client, db_session, seed_tenant_user):
    tenant_id = seed_tenant_user["tenant_id"]
    user_id = seed_tenant_user["user_id"]
    project = _create_project(db_session, tenant_id, user_id)
    dv = _create_dv(db_session, project, status=DomainVerificationStatus.PENDING, token="verifytoken")

    record_name = build_record_name(project.root_domain)

    class FakeRdata:
        def __init__(self, strings):
            self.strings = strings

    class FakeResolver:
        def __init__(self):
            self.lifetime = 5
            self.timeout = 5

        def resolve(self, name, rtype):
            assert name == record_name
            return [FakeRdata([b"verifytoken"])]

    monkeypatch.setattr(dns.resolver, "Resolver", FakeResolver)

    resp = client.post(
        f"/api/projects/{project.id}/domain-verification/verify",
        headers=auth_headers(tenant_id, user_id),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == DomainVerificationStatus.VERIFIED.value
    assert data["verified_at"] is not None

