"""
Integration tests for tool result POST endpoint idempotency
"""
import pytest
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.models.scan import ScanJob, ScanStatus, ScanLevel
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.user import User
from app.models.finding import ToolResult
from app.schemas.scan import ToolResultCreate


@pytest.fixture
def test_scan_setup(db_session):
    """Create test tenant, user, project, and scan"""
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    scan_id = str(uuid.uuid4())
    
    tenant = Tenant(id=tenant_id, name="Test Tenant")
    user = User(
        id=user_id,
        email="test@example.com",
        username="testuser",
        hashed_password="hashed",
        tenant_id=tenant.id
    )
    project = Project(
        id=project_id,
        name="Test Project",
        target_url="http://example.com",
        tenant_id=tenant.id,
        owner_id=user.id
    )
    scan_job = ScanJob(
        id=scan_id,
        project_id=project.id,
        scan_level=ScanLevel.PRO,
        status=ScanStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
    )
    
    db_session.add(tenant)
    db_session.add(user)
    db_session.add(project)
    db_session.add(scan_job)
    db_session.commit()
    
    return {
        "tenant": tenant,
        "user": user,
        "project": project,
        "scan_job": scan_job,
    }


def test_tool_result_post_creates_new_result(db_session, test_scan_setup):
    """
    Test that first POST creates ToolResult and findings.
    """
    from app.main import app
    from app.core.database import get_db
    from app.core.tenant_utils import require_tenant, get_current_user
    
    # Override dependencies
    from app.core.dependencies import require_runner_service_auth
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_tenant] = lambda: test_scan_setup["tenant"]
    app.dependency_overrides[get_current_user] = lambda: test_scan_setup["user"]
    app.dependency_overrides[require_runner_service_auth] = lambda: None  # Bypass service auth in tests
    
    try:
        client = TestClient(app)
        scan_id = test_scan_setup["scan_job"].id
        tool_run_id = str(uuid.uuid4())
        
        # Create payload
        payload = {
            "tool_run_id": tool_run_id,
            "step_id": "step-1",
            "tool_name": "nuclei",
            "tool_id": "tool-nuclei-v2",
            "findings": [
                {
                    "tool_id": "nuclei",
                    "title": f"Test Finding - run {tool_run_id[:8]}",
                    "severity": "high",
                    "description": "Test description",
                    "url": "https://example.com/test",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "findings_count": 1,
            "exit_code": 0,
            "execution_time": 10.5,
            "success": True,
        }
        
        # POST tool result
        response = client.post(
            f"/api/internal/scans/{scan_id}/tool-results",
            json=payload,
            headers={
                "X-Thandev-Tenant-Id": test_scan_setup["tenant"].id,
                "X-Thandev-User-Id": test_scan_setup["user"].id,
            }
        )
        
        # Assert success
        assert response.status_code == 201
        data = response.json()
        assert "tool_result_id" in data
        assert data["findings_ingested"] == 1
        
        # Verify ToolResult was created
        tool_result = db_session.query(ToolResult).filter(
            ToolResult.id == data["tool_result_id"]
        ).first()
        assert tool_result is not None
        assert tool_result.tool_run_id == tool_run_id
        assert tool_result.scan_job_id == scan_id
        assert tool_result.tool_name == "nuclei"
        assert tool_result.parsed_findings_count == 1
        assert tool_result.created_findings_count == 1
        
        # Verify finding was created
        from app.models.finding import Finding
        findings = db_session.query(Finding).filter(
            Finding.scan_job_id == scan_id
        ).all()
        assert len(findings) == 1
        assert findings[0].title == f"Test Finding - run {tool_run_id[:8]}"
        
    finally:
        # Clean up overrides
        app.dependency_overrides.clear()


def test_tool_result_post_idempotent_duplicate(db_session, test_scan_setup):
    """
    Test that second POST with same tool_run_id is idempotent (returns existing, no duplicate findings).
    """
    from app.main import app
    from app.core.database import get_db
    from app.core.tenant_utils import require_tenant, get_current_user
    
    # Override dependencies
    from app.core.dependencies import require_runner_service_auth
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_tenant] = lambda: test_scan_setup["tenant"]
    app.dependency_overrides[get_current_user] = lambda: test_scan_setup["user"]
    app.dependency_overrides[require_runner_service_auth] = lambda: None  # Bypass service auth in tests
    
    try:
        client = TestClient(app)
        scan_id = test_scan_setup["scan_job"].id
        tool_run_id = str(uuid.uuid4())
        
        # Create payload
        payload = {
            "tool_run_id": tool_run_id,
            "step_id": "step-1",
            "tool_name": "nuclei",
            "tool_id": "tool-nuclei-v2",
            "findings": [
                {
                    "tool_id": "nuclei",
                    "title": f"Test Finding - run {tool_run_id[:8]}",
                    "severity": "high",
                    "description": "Test description",
                    "url": "https://example.com/test",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "findings_count": 1,
            "exit_code": 0,
            "execution_time": 10.5,
            "success": True,
        }
        
        # First POST - should create
        response1 = client.post(
            f"/api/internal/scans/{scan_id}/tool-results",
            json=payload,
            headers={
                "X-Thandev-Tenant-Id": test_scan_setup["tenant"].id,
                "X-Thandev-User-Id": test_scan_setup["user"].id,
            }
        )
        assert response1.status_code == 201
        data1 = response1.json()
        tool_result_id_1 = data1["tool_result_id"]
        findings_count_1 = data1["findings_ingested"]
        
        # Second POST with same tool_run_id - should be idempotent
        response2 = client.post(
            f"/api/internal/scans/{scan_id}/tool-results",
            json=payload,  # Same payload, same tool_run_id
            headers={
                "X-Thandev-Tenant-Id": test_scan_setup["tenant"].id,
                "X-Thandev-User-Id": test_scan_setup["user"].id,
            }
        )
        assert response2.status_code == 201
        data2 = response2.json()
        tool_result_id_2 = data2["tool_result_id"]
        
        # Assert same tool_result_id returned (idempotent)
        assert tool_result_id_2 == tool_result_id_1
        
        # Verify only one ToolResult exists
        tool_results = db_session.query(ToolResult).filter(
            ToolResult.scan_job_id == scan_id,
            ToolResult.tool_run_id == tool_run_id,
        ).all()
        assert len(tool_results) == 1
        
        # Verify findings were not duplicated
        from app.models.finding import Finding
        findings = db_session.query(Finding).filter(
            Finding.scan_job_id == scan_id
        ).all()
        assert len(findings) == 1  # Still only 1 finding, not 2
        
        # Verify the response indicates idempotent behavior
        assert "idempotent" in data2["message"].lower() or findings_count_1 == data2["findings_ingested"]
        
    finally:
        # Clean up overrides
        app.dependency_overrides.clear()


def test_tool_result_post_different_tool_run_id_creates_new(db_session, test_scan_setup):
    """
    Test that POST with different tool_run_id creates new ToolResult.
    """
    from app.main import app
    from app.core.database import get_db
    from app.core.tenant_utils import require_tenant, get_current_user
    
    # Override dependencies
    from app.core.dependencies import require_runner_service_auth
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_tenant] = lambda: test_scan_setup["tenant"]
    app.dependency_overrides[get_current_user] = lambda: test_scan_setup["user"]
    app.dependency_overrides[require_runner_service_auth] = lambda: None  # Bypass service auth in tests
    
    try:
        client = TestClient(app)
        scan_id = test_scan_setup["scan_job"].id
        tool_run_id_1 = str(uuid.uuid4())
        tool_run_id_2 = str(uuid.uuid4())
        
        # First POST
        payload1 = {
            "tool_run_id": tool_run_id_1,
            "step_id": "step-1",
            "tool_name": "nuclei",
            "tool_id": "tool-nuclei-v2",
            "findings": [{
                "tool_id": "nuclei",
                "title": "Finding 1",
                "severity": "high",
                "description": "Test",
                "url": "https://example.com/1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
            "findings_count": 1,
            "exit_code": 0,
            "success": True,
        }
        response1 = client.post(
            f"/api/internal/scans/{scan_id}/tool-results",
            json=payload1,
            headers={
                "X-Thandev-Tenant-Id": test_scan_setup["tenant"].id,
                "X-Thandev-User-Id": test_scan_setup["user"].id,
            }
        )
        assert response1.status_code == 201
        tool_result_id_1 = response1.json()["tool_result_id"]
        
        # Second POST with different tool_run_id
        payload2 = {
            "tool_run_id": tool_run_id_2,
            "step_id": "step-2",
            "tool_name": "nuclei",
            "tool_id": "tool-nuclei-v2",
            "findings": [{
                "tool_id": "nuclei",
                "title": "Finding 2",
                "severity": "medium",
                "description": "Test",
                "url": "https://example.com/2",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
            "findings_count": 1,
            "exit_code": 0,
            "success": True,
        }
        response2 = client.post(
            f"/api/internal/scans/{scan_id}/tool-results",
            json=payload2,
            headers={
                "X-Thandev-Tenant-Id": test_scan_setup["tenant"].id,
                "X-Thandev-User-Id": test_scan_setup["user"].id,
            }
        )
        assert response2.status_code == 201
        tool_result_id_2 = response2.json()["tool_result_id"]
        
        # Assert different tool_result_ids
        assert tool_result_id_2 != tool_result_id_1
        
        # Verify two ToolResults exist
        tool_results = db_session.query(ToolResult).filter(
            ToolResult.scan_job_id == scan_id,
        ).all()
        assert len(tool_results) == 2
        
        # Verify both findings exist
        from app.models.finding import Finding
        findings = db_session.query(Finding).filter(
            Finding.scan_job_id == scan_id
        ).all()
        assert len(findings) == 2
        
    finally:
        # Clean up overrides
        app.dependency_overrides.clear()

