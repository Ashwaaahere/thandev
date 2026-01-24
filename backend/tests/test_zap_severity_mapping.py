"""
Test ZAP severity mapping to ensure findings are not all INFO.
"""
import pytest
import json
import uuid
from app.models.finding import Finding, Severity
from app.models.scan import ScanJob
from app.models.project import Project
from app.models.user import User
from app.models.tenant import Tenant
from app.core.severity import zap_to_severity, normalize_severity


@pytest.fixture
def mock_scan_job(db_session):
    """Create a mock scan job for testing."""
    # Create tenant
    tenant = Tenant(name="Test Tenant", slug="test-tenant")
    db_session.add(tenant)
    db_session.flush()
    
    # Create user
    user = User(
        email="test@example.com",
        tenant_id=tenant.id,
        is_approved=True,
    )
    db_session.add(user)
    db_session.flush()
    
    # Create project
    project = Project(
        name="Test Project",
        target_url="https://example.com",
        owner_id=user.id,
        tenant_id=tenant.id,
    )
    db_session.add(project)
    db_session.flush()
    
    # Create scan job
    scan_job = ScanJob(
        id=str(uuid.uuid4()),
        project_id=project.id,
        status="completed",
    )
    db_session.add(scan_job)
    db_session.commit()
    
    return scan_job


@pytest.fixture
def mock_zap_alert_medium():
    """Create a mock ZAP alert with riskcode=2 (Medium)."""
    return {
        "tool_id": "zap",
        "title": "Cross Site Scripting (Reflected)",
        "severity": "medium",  # This will be overridden by riskcode mapping
        "description": "Reflected XSS vulnerability found.",
        "evidence": "Payload: <script>alert(1)</script>",
        "url": "http://example.com/search?q=test",
        "raw": json.dumps({
            "alert": "Cross Site Scripting (Reflected)",
            "riskcode": 2,  # Medium
            "confidence": 2,  # High
            "cweid": "79",
            "wascid": "6",
            "pluginId": "40012",
            "alertRef": "40012-1",
            "method": "GET",
            "param": "q",
            "evidence": "<script>alert(1)</script>",
        }),
    }


@pytest.fixture
def mock_zap_alert_high():
    """Create a mock ZAP alert with riskcode=3 (High)."""
    return {
        "tool_id": "zap",
        "title": "SQL Injection",
        "severity": "high",  # This will be overridden by riskcode mapping
        "description": "SQL injection vulnerability found.",
        "evidence": "Parameter: id",
        "url": "http://example.com/user?id=1",
        "raw": json.dumps({
            "alert": "SQL Injection",
            "riskcode": 3,  # High
            "confidence": 3,  # Confirmed
            "cweid": "89",
            "wascid": "19",
            "pluginId": "40019",
            "alertRef": "40019-1",
        }),
    }


@pytest.fixture
def mock_zap_alert_low():
    """Create a mock ZAP alert with riskcode=1 (Low)."""
    return {
        "tool_id": "zap",
        "title": "Cookie Without Secure Flag",
        "severity": "low",
        "description": "Cookie is not marked as secure.",
        "url": "http://example.com",
        "raw": json.dumps({
            "alert": "Cookie Without Secure Flag",
            "riskcode": 1,  # Low
            "confidence": 2,  # High
            "pluginId": "10010",
        }),
    }


def test_zap_severity_mapping_function():
    """Test that zap_to_severity correctly maps riskcodes."""
    # Test riskcode 0 -> INFO
    sev, needs_verification = zap_to_severity(0, 2, "Test Alert", {})
    assert sev == Severity.INFO
    assert not needs_verification
    
    # Test riskcode 1 -> LOW
    sev, needs_verification = zap_to_severity(1, 2, "Test Alert", {})
    assert sev == Severity.LOW
    assert not needs_verification
    
    # Test riskcode 2 -> MEDIUM
    sev, needs_verification = zap_to_severity(2, 2, "Test Alert", {})
    assert sev == Severity.MEDIUM
    assert not needs_verification
    
    # Test riskcode 3 -> HIGH
    sev, needs_verification = zap_to_severity(3, 2, "Test Alert", {})
    assert sev == Severity.HIGH
    assert not needs_verification
    
    # Test riskcode 3 with confirmed confidence and severe attack -> CRITICAL
    sev, needs_verification = zap_to_severity(3, 3, "SQL Injection", {})
    assert sev == Severity.CRITICAL
    assert not needs_verification
    
    # Test riskcode 2 with low confidence -> MEDIUM with needs_verification
    sev, needs_verification = zap_to_severity(2, 0, "Test Alert", {})
    assert sev == Severity.MEDIUM
    assert needs_verification


def test_normalize_severity_handles_integer_riskcodes():
    """Test that normalize_severity handles integer riskcodes."""
    assert normalize_severity(0) == Severity.INFO
    assert normalize_severity(1) == Severity.LOW
    assert normalize_severity(2) == Severity.MEDIUM
    assert normalize_severity(3) == Severity.HIGH
    assert normalize_severity(4) == Severity.CRITICAL
    
    # Test string values still work
    assert normalize_severity("info") == Severity.INFO
    assert normalize_severity("medium") == Severity.MEDIUM
    assert normalize_severity("high") == Severity.HIGH


def test_zap_ingestion_stores_correct_severity(client, db_session, mock_scan_job, mock_zap_alert_medium):
    """Test that ZAP findings are stored with correct severity from riskcode."""
    scan_id = mock_scan_job.id
    project_id = mock_scan_job.project_id
    
    # Simulate runner sending tool result with ZAP finding
    tool_result_data = {
        "tool_run_id": str(uuid.uuid4()),
        "step_id": "zap-scan",
        "tool_name": "zap",
        "tool_id": "zap",
        "findings": [mock_zap_alert_medium],
        "findings_count": 1,
        "exit_code": 0,
        "success": True,
        "output": "ZAP scan completed",
    }
    
    response = client.post(f"/api/runner/scans/{scan_id}/tool-results", json=tool_result_data)
    assert response.status_code == 201, response.json()
    
    # Fetch the finding from the DB
    finding = db_session.query(Finding).filter(Finding.scan_job_id == scan_id).first()
    assert finding is not None
    assert finding.title == "Cross Site Scripting (Reflected)"
    
    # CRITICAL: Severity should be MEDIUM (from riskcode=2), NOT INFO
    assert finding.severity == Severity.MEDIUM, f"Expected MEDIUM, got {finding.severity}"
    assert not finding.needs_verification  # High confidence, so no verification needed
    
    # Verify ZAP metadata
    assert finding.zap_riskcode == 2
    assert finding.zap_confidence == 2


def test_zap_ingestion_high_severity(client, db_session, mock_scan_job, mock_zap_alert_high):
    """Test that ZAP findings with riskcode=3 are stored as HIGH."""
    scan_id = mock_scan_job.id
    
    tool_result_data = {
        "tool_run_id": str(uuid.uuid4()),
        "step_id": "zap-scan",
        "tool_name": "zap",
        "tool_id": "zap",
        "findings": [mock_zap_alert_high],
        "findings_count": 1,
        "exit_code": 0,
        "success": True,
        "output": "ZAP scan completed",
    }
    
    response = client.post(f"/api/runner/scans/{scan_id}/tool-results", json=tool_result_data)
    assert response.status_code == 201
    
    finding = db_session.query(Finding).filter(Finding.scan_job_id == scan_id).first()
    assert finding is not None
    
    # CRITICAL: Severity should be HIGH (from riskcode=3), NOT INFO
    assert finding.severity == Severity.HIGH, f"Expected HIGH, got {finding.severity}"
    assert finding.zap_riskcode == 3


def test_zap_ingestion_low_severity(client, db_session, mock_scan_job, mock_zap_alert_low):
    """Test that ZAP findings with riskcode=1 are stored as LOW."""
    scan_id = mock_scan_job.id
    
    tool_result_data = {
        "tool_run_id": str(uuid.uuid4()),
        "step_id": "zap-scan",
        "tool_name": "zap",
        "tool_id": "zap",
        "findings": [mock_zap_alert_low],
        "findings_count": 1,
        "exit_code": 0,
        "success": True,
        "output": "ZAP scan completed",
    }
    
    response = client.post(f"/api/runner/scans/{scan_id}/tool-results", json=tool_result_data)
    assert response.status_code == 201
    
    finding = db_session.query(Finding).filter(Finding.scan_job_id == scan_id).first()
    assert finding is not None
    
    # CRITICAL: Severity should be LOW (from riskcode=1), NOT INFO
    assert finding.severity == Severity.LOW, f"Expected LOW, got {finding.severity}"
    assert finding.zap_riskcode == 1


def test_multiple_zap_findings_mixed_severities(client, db_session, mock_scan_job, mock_zap_alert_low, mock_zap_alert_medium, mock_zap_alert_high):
    """Test that multiple ZAP findings with different severities are stored correctly."""
    scan_id = mock_scan_job.id
    
    tool_result_data = {
        "tool_run_id": str(uuid.uuid4()),
        "step_id": "zap-scan",
        "tool_name": "zap",
        "tool_id": "zap",
        "findings": [mock_zap_alert_low, mock_zap_alert_medium, mock_zap_alert_high],
        "findings_count": 3,
        "exit_code": 0,
        "success": True,
        "output": "ZAP scan completed",
    }
    
    response = client.post(f"/api/runner/scans/{scan_id}/tool-results", json=tool_result_data)
    assert response.status_code == 201
    
    findings = db_session.query(Finding).filter(Finding.scan_job_id == scan_id).all()
    assert len(findings) == 3
    
    # Verify severities are correct (not all INFO)
    severities = [f.severity for f in findings]
    assert Severity.LOW in severities
    assert Severity.MEDIUM in severities
    assert Severity.HIGH in severities
    assert Severity.INFO not in severities  # None should be INFO

