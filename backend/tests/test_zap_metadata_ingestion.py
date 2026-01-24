"""
Test ZAP metadata ingestion and severity mapping.
"""
import pytest
from app.models.finding import Finding, Severity
from app.core.severity import zap_to_severity
from app.services.findings_ingestor import create_or_update_finding
from app.models.scan import ScanJob
from app.models.project import Project
from app.models.user import User
from app.models.tenant import Tenant


def test_zap_metadata_ingestion(db_session, test_project, test_scan_job):
    """
    Test that ZAP metadata (CWE, WASC, pluginId, alertRef, confidence, riskcode)
    is properly extracted and stored when ingesting ZAP findings.
    """
    # Create a ZAP alert fixture
    zap_alert = {
        "alert": "Missing Anti-clickjacking Header",
        "riskcode": 2,  # Medium
        "confidence": 2,  # High
        "description": "The application does not set X-Frame-Options header",
        "solution": "Set X-Frame-Options header",
        "url": "https://example.com/",
        "method": "GET",
        "evidence": "",
        "cweid": 1021,  # CWE-1021
        "wascid": 15,  # WASC-15
        "pluginId": "10020",
        "alertRef": "10020",
        "param": "",
    }
    
    # Simulate finding data as it would come from runner
    finding_data = {
        "tool": "zap",
        "title": zap_alert["alert"],
        "description": zap_alert["description"],
        "url": zap_alert["url"],
        "http_method": zap_alert["method"],
        "raw": zap_alert,
    }
    
    # Compute severity using severity engine
    severity, needs_verification = zap_to_severity(
        zap_alert["riskcode"],
        zap_alert["confidence"],
        zap_alert["alert"],
        zap_alert
    )
    
    # Verify severity is MEDIUM (not INFO)
    assert severity == Severity.MEDIUM, f"Expected MEDIUM, got {severity}"
    assert needs_verification == False  # High confidence, so no verification needed
    
    # Extract ZAP metadata
    cwe_id = f"CWE-{zap_alert['cweid']}"
    wasc_id = zap_alert["wascid"]
    plugin_id = str(zap_alert["pluginId"])
    alert_ref = str(zap_alert["alertRef"])
    zap_confidence = 2  # High
    zap_riskcode = 2  # Medium
    
    # Create finding with ZAP metadata
    finding = create_or_update_finding(
        db=db_session,
        scan_job_id=test_scan_job.id,
        project_id=test_project.id,
        finding_data={
            **finding_data,
            "severity": severity,
            "needs_verification": needs_verification,
            "cwe_id": cwe_id,
            "wasc_id": wasc_id,
            "plugin_id": plugin_id,
            "alert_ref": alert_ref,
            "zap_confidence": zap_confidence,
            "zap_riskcode": zap_riskcode,
            "raw_data": str(zap_alert),  # Store as JSON string
        }
    )
    
    db_session.commit()
    
    # Verify finding was created
    assert finding is not None
    assert finding.id is not None
    
    # Verify severity is MEDIUM (not INFO)
    assert finding.severity == Severity.MEDIUM, f"Expected MEDIUM, got {finding.severity}"
    
    # Verify ZAP metadata is stored
    assert finding.cwe_id == cwe_id
    assert finding.wasc_id == wasc_id
    assert finding.plugin_id == plugin_id
    assert finding.alert_ref == alert_ref
    assert finding.zap_confidence == zap_confidence
    assert finding.zap_riskcode == zap_riskcode
    assert finding.needs_verification == False


def test_zap_severity_preserved_on_update(db_session, test_project, test_scan_job):
    """
    Test that severity is preserved when updating an existing finding.
    """
    # Create initial finding with MEDIUM severity
    finding = create_or_update_finding(
        db=db_session,
        scan_job_id=test_scan_job.id,
        project_id=test_project.id,
        finding_data={
            "tool": "zap",
            "title": "Test Finding",
            "severity": Severity.MEDIUM,
            "url": "https://example.com/",
            "zap_riskcode": 2,
            "zap_confidence": 2,
        }
    )
    
    db_session.commit()
    finding_id = finding.id
    
    # Update finding - severity should be preserved
    updated_finding = create_or_update_finding(
        db=db_session,
        scan_job_id=test_scan_job.id,
        project_id=test_project.id,
        finding_data={
            "tool": "zap",
            "title": "Test Finding",
            "severity": Severity.MEDIUM,  # Explicitly set to MEDIUM
            "url": "https://example.com/",
        }
    )
    
    db_session.commit()
    
    # Verify severity is still MEDIUM (not overwritten to INFO)
    assert updated_finding.id == finding_id
    assert updated_finding.severity == Severity.MEDIUM, f"Expected MEDIUM, got {updated_finding.severity}"


def test_zap_riskcode_mapping():
    """
    Test ZAP riskcode to severity mapping.
    """
    # Test all riskcode values
    test_cases = [
        (0, None, Severity.INFO, False),
        (1, None, Severity.LOW, False),
        (2, None, Severity.MEDIUM, False),
        (3, None, Severity.HIGH, False),
        (4, None, Severity.CRITICAL, False),
        # Test with confidence
        (2, 0, Severity.MEDIUM, True),  # Low confidence -> needs verification
        (3, 0, Severity.HIGH, True),  # Low confidence -> needs verification
        (2, 2, Severity.MEDIUM, False),  # High confidence -> no verification needed
    ]
    
    for riskcode, confidence, expected_severity, expected_needs_verification in test_cases:
        severity, needs_verification = zap_to_severity(riskcode, confidence, "Test Alert", {})
        assert severity == expected_severity, f"riskcode={riskcode}, confidence={confidence}: expected {expected_severity}, got {severity}"
        assert needs_verification == expected_needs_verification, f"riskcode={riskcode}, confidence={confidence}: expected needs_verification={expected_needs_verification}, got {needs_verification}"

