"""
Integration tests for scan creation
"""
import pytest
from app.models.scan import ScanJob, ScanStatus, ScanLevel
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.user import User


@pytest.mark.integration
def test_create_scan_job(db_session):
    """Test creating a scan job"""
    # Create tenant
    tenant = Tenant(id="test-tenant", name="Test Tenant", plan="free")
    db_session.add(tenant)
    db_session.flush()
    
    # Create user
    user = User(
        id="test-user",
        email="test@example.com",
        username="testuser",
        hashed_password="hashed",
        tenant_id=tenant.id
    )
    db_session.add(user)
    db_session.flush()
    
    # Create project
    project = Project(
        id="test-project",
        name="Test Project",
        target_url="https://example.com",
        tenant_id=tenant.id,
        owner_id=user.id
    )
    db_session.add(project)
    db_session.flush()
    
    # Create scan job
    scan_job = ScanJob(
        project_id=project.id,
        scan_level=ScanLevel.BASIC,
        status=ScanStatus.QUEUED
    )
    db_session.add(scan_job)
    db_session.commit()
    
    assert scan_job.id is not None
    assert scan_job.status == ScanStatus.QUEUED



