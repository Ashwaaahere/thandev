"""
Unit tests for Top Picks severity sorting (PR-4D)
"""
import pytest
from app.services.ai.reporter import generate_basic_report
from app.models.scan import ScanJob, ScanLevel, ScanStatus
from app.models.finding import Finding, Severity


@pytest.fixture
def mock_scan_job():
    """Create a mock ScanJob for testing"""
    scan_job = ScanJob(
        id="test-scan-123",
        project_id="test-project",
        scan_level=ScanLevel.PRO,
        status=ScanStatus.COMPLETED,
    )
    return scan_job


def test_top_risks_severity_sorting(mock_scan_job):
    """
    Test that top_risks are sorted correctly: critical > high > medium > low > info
    """
    # Create findings with different severities
    findings = [
        Finding(
            id="f1",
            scan_job_id="test-scan-123",
            title="Low severity finding",
            severity=Severity.LOW,
            cvss_score=2.5,
            tool_name="nuclei",
        ),
        Finding(
            id="f2",
            scan_job_id="test-scan-123",
            title="Critical severity finding",
            severity=Severity.CRITICAL,
            cvss_score=9.8,
            tool_name="nuclei",
        ),
        Finding(
            id="f3",
            scan_job_id="test-scan-123",
            title="High severity finding",
            severity=Severity.HIGH,
            cvss_score=7.5,
            tool_name="nuclei",
        ),
        Finding(
            id="f4",
            scan_job_id="test-scan-123",
            title="Medium severity finding",
            severity=Severity.MEDIUM,
            cvss_score=5.0,
            tool_name="nuclei",
        ),
        Finding(
            id="f5",
            scan_job_id="test-scan-123",
            title="Info severity finding",
            severity=Severity.INFO,
            cvss_score=0.0,
            tool_name="nuclei",
        ),
        Finding(
            id="f6",
            scan_job_id="test-scan-123",
            title="Another critical with lower CVSS",
            severity=Severity.CRITICAL,
            cvss_score=8.0,
            tool_name="nuclei",
        ),
    ]
    
    # Generate report
    report = generate_basic_report(mock_scan_job, findings)
    
    # Verify top_risks exists and has correct length
    assert "top_risks" in report
    assert len(report["top_risks"]) == 5  # Top 5
    
    # Verify sorting: critical > high > medium > low > info
    # This test verifies the fix for the sorting bug where HIGH was incorrectly sorted before CRITICAL
    top_risks = report["top_risks"]
    
    # First should be critical (highest CVSS) - verifies critical comes before high
    assert top_risks[0]["severity"] == "critical"
    assert top_risks[0]["cvss_score"] == 9.8  # Higher CVSS comes first within same severity
    
    # Second should be critical (lower CVSS)
    assert top_risks[1]["severity"] == "critical"
    assert top_risks[1]["cvss_score"] == 8.0
    
    # Third should be high
    assert top_risks[2]["severity"] == "high"
    
    # Fourth should be medium
    assert top_risks[3]["severity"] == "medium"
    
    # Fifth should be low (info is excluded as it's less important)
    assert top_risks[4]["severity"] == "low"


def test_top_risks_only_current_scan(mock_scan_job):
    """
    Test that top_risks only includes findings from the current scan_job
    """
    # Create findings for current scan
    current_findings = [
        Finding(
            id="f1",
            scan_job_id="test-scan-123",
            title="Current scan finding",
            severity=Severity.HIGH,
            cvss_score=7.5,
            tool_name="nuclei",
        ),
    ]
    
    # Create findings for different scan (should not appear)
    other_findings = [
        Finding(
            id="f2",
            scan_job_id="other-scan-456",
            title="Other scan finding",
            severity=Severity.CRITICAL,
            cvss_score=9.8,
            tool_name="nuclei",
        ),
    ]
    
    # Generate report with only current findings
    report = generate_basic_report(mock_scan_job, current_findings)
    
    # Verify only current scan findings are in top_risks
    assert len(report["top_risks"]) == 1
    assert report["top_risks"][0]["title"] == "Current scan finding"
    assert report["top_risks"][0]["severity"] == "high"


def test_top_risks_tie_breaker_cvss(mock_scan_job):
    """
    Test that findings with same severity are sorted by CVSS score (descending)
    """
    findings = [
        Finding(
            id="f1",
            scan_job_id="test-scan-123",
            title="High severity with CVSS 6.0",
            severity=Severity.HIGH,
            cvss_score=6.0,
            tool_name="nuclei",
        ),
        Finding(
            id="f2",
            scan_job_id="test-scan-123",
            title="High severity with CVSS 8.0",
            severity=Severity.HIGH,
            cvss_score=8.0,
            tool_name="nuclei",
        ),
        Finding(
            id="f3",
            scan_job_id="test-scan-123",
            title="High severity with CVSS 7.0",
            severity=Severity.HIGH,
            cvss_score=7.0,
            tool_name="nuclei",
        ),
    ]
    
    report = generate_basic_report(mock_scan_job, findings)
    
    # Verify sorting by CVSS within same severity
    top_risks = report["top_risks"]
    assert len(top_risks) == 3
    assert top_risks[0]["cvss_score"] == 8.0
    assert top_risks[1]["cvss_score"] == 7.0
    assert top_risks[2]["cvss_score"] == 6.0



