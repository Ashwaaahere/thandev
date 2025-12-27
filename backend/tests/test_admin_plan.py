import uuid
from app.models.user import User
from app.models.tenant import Tenant, PlanTier
from app.models.entitlement import Entitlement
from app.core.config import settings
from tests.conftest import auth_headers


def test_admin_bootstrap_sets_admin(client, db_session, monkeypatch):
    # Seed superadmin immutable id
    settings.set_superadmin_external_ids({("github", "123")})

    resp = client.post(
        "/api/auth/bootstrap",
        json={
            "provider": "github",
            "external_user_id": "123",
            "username": "adminuser",
            "email": "admin@example.com",
            "name": "Admin User",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_admin"] is True
    assert data["is_approved"] is True


def test_plan_gating_denies_pro_without_entitlement(client, db_session, seed_tenant_user, monkeypatch):
    # disable domain verification to isolate plan gating
    monkeypatch.setattr(settings, "DOMAIN_VERIFICATION_DISABLED", True)
    tenant_id = seed_tenant_user["tenant_id"]
    user_id = seed_tenant_user["user_id"]
    # Downgrade tenant plan to FREE to enforce pro denial without entitlement
    tenant = seed_tenant_user["tenant"]
    tenant.plan = PlanTier.FREE
    db_session.commit()
    # Create project
    from app.models.project import Project
    project = Project(
        id=str(uuid.uuid4()),
        name="TestProj",
        target_url="http://example.com/",
        root_domain="example.com",
        owner_id=user_id,
        tenant_id=tenant_id,
    )
    db_session.add(project)
    db_session.commit()

    # Attempt PRO scan -> should 403 (plan gating)
    resp = client.post(
        "/api/scans",
        json={"project_id": project.id, "scan_level": "pro"},
        headers=auth_headers(tenant_id, user_id),
    )
    assert resp.status_code == 403


def test_entitlement_allows_pro_scan(client, db_session, seed_tenant_user, monkeypatch):
    monkeypatch.setattr(settings, "DOMAIN_VERIFICATION_DISABLED", True)
    tenant_id = seed_tenant_user["tenant_id"]
    user_id = seed_tenant_user["user_id"]
    from app.models.project import Project
    project = Project(
        id=str(uuid.uuid4()),
        name="TestProj",
        target_url="http://example.com/",
        root_domain="example.com",
        owner_id=user_id,
        tenant_id=tenant_id,
    )
    db_session.add(project)
    db_session.commit()

    ent = Entitlement(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        plan_name="pro",
        limits_json={
            "allowed_scan_levels": ["basic", "pro"],
            "max_scans_per_day": 10,
            "max_concurrent_scans": 5,
        },
    )
    db_session.add(ent)
    db_session.commit()

    resp = client.post(
        "/api/scans",
        json={"project_id": project.id, "scan_level": "pro"},
        headers=auth_headers(tenant_id, user_id),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["scan_level"] == "pro"


def test_concurrency_limit_enforced(client, db_session, seed_tenant_user, monkeypatch):
    monkeypatch.setattr(settings, "DOMAIN_VERIFICATION_DISABLED", True)
    tenant_id = seed_tenant_user["tenant_id"]
    user_id = seed_tenant_user["user_id"]
    from app.models.project import Project
    from app.models.scan import ScanJob, ScanLevel, ScanStatus

    project = Project(
        id=str(uuid.uuid4()),
        name="TestProj",
        target_url="http://example.com/",
        root_domain="example.com",
        owner_id=user_id,
        tenant_id=tenant_id,
    )
    db_session.add(project)
    db_session.commit()

    # Entitlement with concurrency 1
    ent = Entitlement(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        plan_name="pro",
        limits_json={
            "allowed_scan_levels": ["basic", "pro"],
            "max_scans_per_day": 10,
            "max_concurrent_scans": 1,
        },
    )
    db_session.add(ent)
    db_session.commit()

    # Seed one running scan
    sj = ScanJob(
        id=str(uuid.uuid4()),
        project_id=project.id,
        scan_level=ScanLevel.BASIC,
        status=ScanStatus.RUNNING,
    )
    db_session.add(sj)
    db_session.commit()

    # Next scan should 429
    resp = client.post(
        "/api/scans",
        json={"project_id": project.id, "scan_level": "basic"},
        headers=auth_headers(tenant_id, user_id),
    )
    assert resp.status_code == 429

