"""
Unit tests for tool run counts accuracy and canonical naming.

Tests:
- Canonical tool name is used consistently
- Counts are computed from DB (source of truth)
- tool_result_id mapping works correctly
- NULL counts are handled in API response
"""
import pytest
from datetime import datetime, timezone

from app.models.scan import ScanJob, ScanLevel, ScanStatus
from app.models.finding import Finding, ToolResult, ToolExecutionStatus, Severity
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.user import User
from app.services.tool_run_recorder import start_tool_run, finish_tool_run, update_tool_run_counts
from app.services.tool_name_utils import canonical_tool_name
from app.services.findings_ingestor import ingest_dalfox_findings
from app.services.findings_ingestor import parse_dalfox_output
from pathlib import Path
import json
import tempfile


def test_canonical_tool_name():
    """Test canonical tool name normalization"""
    assert canonical_tool_name("dalfox") == "dalfox"
    assert canonical_tool_name("Dalfox") == "dalfox"
    assert canonical_tool_name("DALFOX") == "dalfox"
    assert canonical_tool_name("nuclei") == "nuclei"
    assert canonical_tool_name("Nuclei") == "nuclei"
    assert canonical_tool_name("nmap") == "nmap"
    assert canonical_tool_name(None) == "unknown"
    assert canonical_tool_name("") == "unknown"
    assert canonical_tool_name("unknown-tool") == "unknown-tool"  # Unknown tools normalized to lowercase


def test_tool_result_uses_canonical_name(db_session):
    """Test that ToolResult uses canonical tool name when created"""
    import uuid
    # Create a scan for testing
    tenant = Tenant(id=f"test-tenant-{uuid.uuid4()}", name="Test Tenant")
    user = User(
        id=f"test-user-{uuid.uuid4()}",
        email="test@example.com",
        username="testuser",
        hashed_password="hashed",
        tenant_id=tenant.id,
    )
    project = Project(id=f"test-project-{uuid.uuid4()}", name="Test Project", target_url="http://example.com", tenant_id=tenant.id, owner_id=user.id)
    scan = ScanJob(
        id=f"test-scan-{uuid.uuid4()}",
        project_id=project.id,
        scan_level=ScanLevel.BASIC,
        status=ScanStatus.RUNNING,
    )
    
    db_session.add(tenant)
    db_session.add(user)
    db_session.add(project)
    db_session.add(scan)
    db_session.commit()
    
    # Start tool run with mixed case name
    tool_run_id = start_tool_run(db_session, scan.id, "Dalfox")
    
    tool_result = db_session.query(ToolResult).filter(ToolResult.id == tool_run_id).first()
    assert tool_result is not None
    assert tool_result.tool_name == "dalfox"  # Should be canonical lowercase
    assert tool_result.tool_name == canonical_tool_name("Dalfox")


def test_finding_uses_canonical_name(db_session):
    """Test that Finding uses canonical tool name via factory function"""
    # Create a scan for testing
    tenant = Tenant(id="test-tenant-2", name="Test Tenant 2")
    user = User(
        id="test-user-2",
        email="test2@example.com",
        username="testuser2",
        hashed_password="hashed",
        tenant_id=tenant.id,
    )
    project = Project(id="test-project-2", name="Test Project 2", target_url="http://example.com", tenant_id=tenant.id, owner_id=user.id)
    scan = ScanJob(
        id="test-scan-2",
        project_id=project.id,
        scan_level=ScanLevel.BASIC,
        status=ScanStatus.RUNNING,
    )
    
    db_session.add(tenant)
    db_session.add(user)
    db_session.add(project)
    db_session.add(scan)
    db_session.commit()
    
    # Create tool run
    tool_run_id = start_tool_run(db_session, scan.id, "dalfox")
    
    # Create finding via ingestion (which uses factory function)
    dalfox_results = [{
        "type": "V",
        "param": "test",
        "payload": "<script>alert(1)</script>",
        "data": "http://example.com?test=<script>alert(1)</script>",
        "url": "http://example.com"
    }]
    
    findings = ingest_dalfox_findings(db_session, scan.id, dalfox_results, tool_result_id=tool_run_id)
    
    assert len(findings) == 1
    finding = findings[0]
    assert finding.tool_name == "dalfox"  # Should be canonical lowercase
    assert finding.tool_result_id == tool_run_id  # Should be linked to tool run


def test_tool_result_id_counting(db_session):
    """Test that counts are computed from DB using tool_result_id"""
    # Create a scan for testing
    tenant = Tenant(id="test-tenant-3", name="Test Tenant 3")
    user = User(
        id="test-user-3",
        email="test3@example.com",
        username="testuser3",
        hashed_password="hashed",
        tenant_id=tenant.id,
    )
    project = Project(id="test-project-3", name="Test Project 3", target_url="http://example.com", tenant_id=tenant.id, owner_id=user.id)
    scan = ScanJob(
        id="test-scan-3",
        project_id=project.id,
        scan_level=ScanLevel.BASIC,
        status=ScanStatus.RUNNING,
    )
    
    db_session.add(tenant)
    db_session.add(user)
    db_session.add(project)
    db_session.add(scan)
    db_session.commit()
    
    # Create tool run
    tool_run_id = start_tool_run(db_session, scan.id, "dalfox")
    finish_tool_run(
        db_session, tool_run_id, ToolExecutionStatus.COMPLETED, exit_code=0,
        stdout="", stderr="", output_path=None, duration_ms=30000
    )
    
    # Create findings via ingestion
    dalfox_results = [{
        "type": "V",
        "param": "test",
        "payload": "<script>alert(1)</script>",
        "data": "http://example.com?test=<script>alert(1)</script>",
        "url": "http://example.com"
    }]
    
    findings = ingest_dalfox_findings(db_session, scan.id, dalfox_results, tool_result_id=tool_run_id)
    assert len(findings) == 1
    
    # Update counts (should compute from DB)
    update_tool_run_counts(db_session, tool_run_id, parsed_count=1, created_count=0)  # Pass wrong count
    
    # Verify DB count overrides parameter
    tool_result = db_session.query(ToolResult).filter(ToolResult.id == tool_run_id).first()
    assert tool_result.created_findings_count == 1  # Should be 1 from DB, not 0 from parameter
    assert tool_result.parsed_findings_count == 1


def test_null_counts_handled(db_session):
    """Test that counts default to 0 when not set"""
    # Create a scan for testing
    tenant = Tenant(id="test-tenant-4", name="Test Tenant 4")
    user = User(
        id="test-user-4",
        email="test4@example.com",
        username="testuser4",
        hashed_password="hashed",
        tenant_id=tenant.id,
    )
    project = Project(id="test-project-4", name="Test Project 4", target_url="http://example.com", tenant_id=tenant.id, owner_id=user.id)
    scan = ScanJob(
        id="test-scan-4",
        project_id=project.id,
        scan_level=ScanLevel.BASIC,
        status=ScanStatus.RUNNING,
    )
    
    db_session.add(tenant)
    db_session.add(user)
    db_session.add(project)
    db_session.add(scan)
    db_session.commit()
    
    # Create tool run - counts should default to 0 (schema enforces NOT NULL with default=0)
    tool_run_id = start_tool_run(db_session, scan.id, "nuclei")
    tool_result = db_session.query(ToolResult).filter(ToolResult.id == tool_run_id).first()
    
    # Verify counts default to 0 (schema enforces this, not NULL)
    assert tool_result.parsed_findings_count == 0
    assert tool_result.created_findings_count == 0
    
    # Verify safe access (counts are never NULL, but this tests the pattern)
    assert (tool_result.parsed_findings_count or 0) == 0
    assert (tool_result.created_findings_count or 0) == 0


