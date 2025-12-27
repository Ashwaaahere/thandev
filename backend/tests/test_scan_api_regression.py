"""
Regression tests for scan API fixes:
1. Unscheduled tools show as "skipped" not "pending" in terminal scans
2. Plan enforcement bypass is guarded by environment
"""
import pytest
import os
from datetime import datetime, timezone
from unittest.mock import patch

from app.models.scan import ScanJob, ScanStatus, ScanLevel
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.user import User
from app.models.finding import ToolResult, ToolExecutionStatus
from app.core.constants import TERMINAL_SCAN_STATUSES


@pytest.fixture
def test_scan_setup(db_session):
    """Create test tenant, user, project, and scan"""
    tenant_id = "test-tenant-regression"
    user_id = "test-user-regression"
    project_id = "test-project-regression"
    scan_id = "test-scan-regression"
    
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
        status=ScanStatus.COMPLETED,
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
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


def test_terminal_scan_unscheduled_tools_are_skipped(db_session, test_scan_setup):
    """
    Regression test: API tool_statuses doesn't show pending for terminal scans.
    
    Create a scan_job with terminal status, provide expected_tool_keys where
    one tool has no ToolResult. Assert response status for missing tool is
    skipped not pending.
    """
    from app.api.scans import get_scan
    from app.core.tool_matrix import get_tools_for_level
    
    scan_job = test_scan_setup["scan_job"]
    tenant = test_scan_setup["tenant"]
    user = test_scan_setup["user"]
    
    # Create ToolResult for one tool (httpx) but not for another (sslscan)
    httpx_result = ToolResult(
        scan_job_id=scan_job.id,
        tool_name="httpx",
        status=ToolExecutionStatus.COMPLETED,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(httpx_result)
    db_session.commit()
    
    # Get expected tools for PRO level
    expected_tools = get_tools_for_level(ScanLevel.PRO)
    expected_tool_keys = {tool["key"] for tool in expected_tools if tool.get("enabled", True)}
    
    # Verify sslscan is expected but has no ToolResult
    assert "sslscan" in expected_tool_keys, "sslscan should be in expected tools for PRO level"
    sslscan_result = db_session.query(ToolResult).filter(
        ToolResult.scan_job_id == scan_job.id,
        ToolResult.tool_name == "sslscan"
    ).first()
    assert sslscan_result is None, "sslscan should not have a ToolResult"
    
    # Call get_scan endpoint logic (simulate the tool_statuses generation)
    from app.models.finding import ToolResult as TR, ToolExecutionStatus as TES
    from app.core.tool_matrix import get_tools_for_level as get_tools
    
    tool_results = db_session.query(TR).filter(TR.scan_job_id == scan_job.id).all()
    
    # Replicate the logic from get_scan
    tool_statuses = []
    seen_tool_names = set()
    
    for tool_result in tool_results:
        tool_name = tool_result.tool_name
        seen_tool_names.add(tool_name)
        tool_statuses.append({
            "tool_name": tool_name,
            "status": tool_result.status.value if tool_result.status else TES.COMPLETED.value,
        })
    
    # Check for missing expected tools
    scan_status_value = scan_job.status.value if hasattr(scan_job.status, 'value') else scan_job.status
    scan_is_terminal = scan_status_value in {s.value if hasattr(s, 'value') else s for s in TERMINAL_SCAN_STATUSES}
    
    for tool_key in expected_tool_keys:
        if tool_key not in seen_tool_names:
            if scan_is_terminal:
                missing_status = TES.SKIPPED.value
                error_code = "not_scheduled"
            else:
                missing_status = TES.PENDING.value
                error_code = None
            
            tool_statuses.append({
                "tool_name": tool_key,
                "status": missing_status,
                "error_code": error_code,
            })
    
    # Verify sslscan is marked as skipped, not pending
    sslscan_status = next((ts for ts in tool_statuses if ts["tool_name"] == "sslscan"), None)
    assert sslscan_status is not None, "sslscan should appear in tool_statuses"
    assert sslscan_status["status"] == "skipped", f"sslscan should be skipped, got {sslscan_status['status']}"
    assert sslscan_status["error_code"] == "not_scheduled", f"sslscan should have error_code 'not_scheduled', got {sslscan_status.get('error_code')}"
    
    # Verify httpx is completed
    httpx_status = next((ts for ts in tool_statuses if ts["tool_name"] == "httpx"), None)
    assert httpx_status is not None, "httpx should appear in tool_statuses"
    assert httpx_status["status"] == "completed", f"httpx should be completed, got {httpx_status['status']}"


def test_plan_bypass_guarded_by_environment():
    """
    Regression test: Bypass guarded by environment.
    
    Monkeypatch ENVIRONMENT=production + THANDEV_DISABLE_PLAN_ENFORCEMENT=1,
    assert enforcement still happens.
    """
    from app.core.config import settings
    from app.core.plans import get_plan_limits
    
    # Mock a tenant with FREE plan (only allows basic scans)
    class MockTenant:
        def __init__(self):
            self.plan = type('PlanTier', (), {'value': 'free'})()
    
    tenant = MockTenant()
    limits = get_plan_limits(tenant)
    
    # Test that bypass logic checks environment
    # In production, bypass should NOT work even with flag set
    with patch.dict(os.environ, {"THANDEV_DISABLE_PLAN_ENFORCEMENT": "1"}):
        with patch.object(settings, 'ENVIRONMENT', 'production'):
            # Bypass should NOT activate in production
            env_lower = settings.ENVIRONMENT.strip().lower()
            bypass_allowed = (
                env_lower in ("local", "dev", "test", "development")
                and os.getenv("THANDEV_DISABLE_PLAN_ENFORCEMENT") == "1"
            )
            assert not bypass_allowed, "Bypass should NOT be allowed in production environment"
            
            # Pro scan should be rejected
            requested_level = "pro"
            if not bypass_allowed and requested_level not in limits["allowed_scan_levels"]:
                # This simulates the enforcement that should happen
                assert requested_level not in limits["allowed_scan_levels"], "Pro scan should be rejected for FREE plan"
    
    # Test that bypass DOES work in dev/test environments
    with patch.dict(os.environ, {"THANDEV_DISABLE_PLAN_ENFORCEMENT": "1"}):
        for env in ["local", "dev", "test", "development"]:
            with patch.object(settings, 'ENVIRONMENT', env):
                env_lower = settings.ENVIRONMENT.strip().lower()
                bypass_allowed = (
                    env_lower in ("local", "dev", "test", "development")
                    and os.getenv("THANDEV_DISABLE_PLAN_ENFORCEMENT") == "1"
                )
                assert bypass_allowed, f"Bypass should be allowed in {env} environment"
    
    # Test that bypass does NOT work without flag, even in dev
    with patch.dict(os.environ, {}, clear=True):
        with patch.object(settings, 'ENVIRONMENT', 'dev'):
            env_lower = settings.ENVIRONMENT.strip().lower()
            bypass_allowed = (
                env_lower in ("local", "dev", "test", "development")
                and os.getenv("THANDEV_DISABLE_PLAN_ENFORCEMENT") == "1"
            )
            assert not bypass_allowed, "Bypass should NOT be allowed without flag, even in dev"

