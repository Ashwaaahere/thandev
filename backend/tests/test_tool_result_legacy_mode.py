"""
Integration tests for tool result POST endpoint legacy mode (no tool_run_id)
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


def test_tool_result_post_legacy_mode_generates_deterministic_id(db_session, test_scan_setup):
    """
    Test that POST without tool_run_id generates deterministic UUIDv5 from scan_id+tool+step_id.
    This ensures legacy callers get idempotency too.
    """
    from app.main import app
    from app.core.database import get_db
    from app.core.tenant_utils import require_tenant, get_current_user
    import uuid
    
    # Override dependencies
    from app.core.dependencies import require_runner_service_auth
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_tenant] = lambda: test_scan_setup["tenant"]
    app.dependency_overrides[get_current_user] = lambda: test_scan_setup["user"]
    app.dependency_overrides[require_runner_service_auth] = lambda: None  # Bypass service auth in tests
    
    try:
        client = TestClient(app)
        scan_id = test_scan_setup["scan_job"].id
        
        # Create payload WITHOUT tool_run_id (legacy mode)
        payload = {
            # tool_run_id omitted - should be generated deterministically
            "step_id": "step-legacy-1",
            "tool_name": "nuclei",
            "tool_id": "tool-nuclei-v2",
            "findings": [{
                "tool_id": "nuclei",
                "title": f"Legacy Finding - run {scan_id[:8]}",
                "severity": "high",
                "description": "Test",
                "url": "https://example.com/legacy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
            "findings_count": 1,
            "exit_code": 0,
            "success": True,
        }
        
        # First POST - should generate deterministic tool_run_id
        response1 = client.post(
            f"/api/internal/scans/{scan_id}/tool-results",
            json=payload,
            headers={
                "X-Thandev-Tenant-Id": test_scan_setup["tenant"].id,
                "X-Thandev-User-Id": test_scan_setup["user"].id,
            }
        )
        assert response1.status_code == 201
        tool_result_id_1 = response1.json()["tool_result_id"]
        
        # Verify ToolResult was created with generated tool_run_id
        tool_result_1 = db_session.query(ToolResult).filter(
            ToolResult.id == tool_result_id_1
        ).first()
        assert tool_result_1 is not None
        assert tool_result_1.tool_run_id is not None  # Should be generated
        
        # Verify it's deterministic: same inputs = same tool_run_id
        # Compute expected UUIDv5
        NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
        expected_tool_run_id = str(uuid.uuid5(
            NAMESPACE,
            f"{scan_id}:nuclei:step-legacy-1"
        ))
        assert tool_result_1.tool_run_id == expected_tool_run_id
        
        # Second POST with same payload (no tool_run_id) - should be idempotent
        response2 = client.post(
            f"/api/internal/scans/{scan_id}/tool-results",
            json=payload,  # Same payload, should generate same tool_run_id
            headers={
                "X-Thandev-Tenant-Id": test_scan_setup["tenant"].id,
                "X-Thandev-User-Id": test_scan_setup["user"].id,
            }
        )
        assert response2.status_code == 201
        tool_result_id_2 = response2.json()["tool_result_id"]
        
        # Should return same tool_result_id (idempotent)
        assert tool_result_id_2 == tool_result_id_1
        
        # Verify only one ToolResult exists
        tool_results = db_session.query(ToolResult).filter(
            ToolResult.scan_job_id == scan_id,
            ToolResult.tool_run_id == expected_tool_run_id,
        ).all()
        assert len(tool_results) == 1
        
    finally:
        # Clean up overrides
        app.dependency_overrides.clear()

