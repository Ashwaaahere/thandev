"""
Unit tests for report schema consistency and correctness
"""
import pytest
import uuid
import json
from app.services.ai.reporter import generate_basic_report
from app.api.scans import _generate_summary
from app.models.scan import ScanJob, ScanLevel, ScanStatus
from app.models.finding import Finding, Severity
from app.core.constants import (
    CANON_FINDINGS_COUNT, CANON_SEV_BREAKDOWN, CANON_RISK_SCORE,
    DEPRECATED_TOTAL_FINDINGS, DEPRECATED_FINDINGS_BY_SEVERITY
)


def make_finding(scan_job_id: str, severity: Severity, title: str = None, cvss_score: float = None, **kwargs) -> Finding:
    """Helper to create a Finding with minimal required fields
    
    Note: Finding is a SQLAlchemy model, but can be instantiated directly for tests
    (as seen in test_top_picks_sorting.py). For tests that need DB persistence, use db_session.
    """
    return Finding(
        id=kwargs.get("id", str(uuid.uuid4())),
        scan_job_id=scan_job_id,
        title=title or f"{severity.value.title()} severity finding",
        severity=severity,
        cvss_score=cvss_score,
        tool_name=kwargs.get("tool_name", "nuclei"),
        **{k: v for k, v in kwargs.items() if k not in ["id", "scan_job_id", "title", "severity", "cvss_score", "tool_name"]}
    )


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


def test_empty_findings_canonical_schema(mock_scan_job):
    """Test that empty findings return full canonical schema with all keys"""
    report = generate_basic_report(mock_scan_job, [])
    
    # Required fields
    assert CANON_FINDINGS_COUNT in report
    assert CANON_SEV_BREAKDOWN in report
    assert CANON_RISK_SCORE in report
    assert "executive_summary" in report
    assert "top_risks" in report
    assert "remediation_overview" in report
    
    # Type checks
    assert isinstance(report[CANON_RISK_SCORE], float)
    assert isinstance(report[CANON_FINDINGS_COUNT], int)
    assert isinstance(report[CANON_SEV_BREAKDOWN], dict)
    
    # Value checks
    assert report[CANON_FINDINGS_COUNT] == 0
    assert report[CANON_RISK_SCORE] == 0.0
    
    # All 5 severity keys present
    assert set(report[CANON_SEV_BREAKDOWN].keys()) == {"critical", "high", "medium", "low", "info"}
    assert all(v == 0 for v in report[CANON_SEV_BREAKDOWN].values())
    
    # Backward compatibility aliases
    assert DEPRECATED_TOTAL_FINDINGS in report
    assert DEPRECATED_FINDINGS_BY_SEVERITY in report
    assert report[DEPRECATED_TOTAL_FINDINGS] == 0
    assert set(report[DEPRECATED_FINDINGS_BY_SEVERITY].keys()) == {"critical", "high", "medium", "low", "info"}


def test_findings_count_matches_severity_breakdown_sum(mock_scan_job):
    """Test that findings_count equals sum of severity_breakdown values"""
    findings = [
        make_finding("test-scan-123", Severity.CRITICAL),
        make_finding("test-scan-123", Severity.HIGH),
        make_finding("test-scan-123", Severity.MEDIUM),
        make_finding("test-scan-123", Severity.LOW),
        make_finding("test-scan-123", Severity.INFO),
    ]
    report = generate_basic_report(mock_scan_job, findings)
    
    assert report[CANON_FINDINGS_COUNT] == len(findings)
    assert sum(report[CANON_SEV_BREAKDOWN].values()) == len(findings)
    assert report[CANON_FINDINGS_COUNT] == sum(report[CANON_SEV_BREAKDOWN].values())
    # Backward compatibility
    assert report[DEPRECATED_TOTAL_FINDINGS] == report[CANON_FINDINGS_COUNT]


def test_all_severity_keys_present(mock_scan_job):
    """Test that severity_breakdown always has all 5 keys"""
    # Test with empty findings
    report = generate_basic_report(mock_scan_job, [])
    assert set(report[CANON_SEV_BREAKDOWN].keys()) == {"critical", "high", "medium", "low", "info"}
    
    # Test with partial findings
    findings = [make_finding("test-scan-123", Severity.CRITICAL)]
    report = generate_basic_report(mock_scan_job, findings)
    assert set(report[CANON_SEV_BREAKDOWN].keys()) == {"critical", "high", "medium", "low", "info"}
    assert report[CANON_SEV_BREAKDOWN]["critical"] == 1
    assert report[CANON_SEV_BREAKDOWN]["high"] == 0


def test_risk_score_bounds_and_type(mock_scan_job):
    """Test that risk_score is between 0 and 10, and is a float"""
    findings = [make_finding("test-scan-123", Severity.CRITICAL)]
    report = generate_basic_report(mock_scan_job, findings)
    
    assert isinstance(report[CANON_RISK_SCORE], float)
    assert 0 <= report[CANON_RISK_SCORE] <= 10
    # Check it's rounded to 1 decimal (or is whole number)
    risk_str = str(report[CANON_RISK_SCORE])
    if "." in risk_str:
        decimal_places = len(risk_str.split(".")[1])
        assert decimal_places <= 1


def test_json_serializability(mock_scan_job):
    """Test that report is JSON-serializable"""
    findings = [make_finding("test-scan-123", Severity.HIGH)]
    report = generate_basic_report(mock_scan_job, findings)
    
    # Should not raise exception
    json_str = json.dumps(report)
    assert isinstance(json_str, str)
    # Should be able to parse back
    parsed = json.loads(json_str)
    assert parsed[CANON_FINDINGS_COUNT] == report[CANON_FINDINGS_COUNT]
    assert isinstance(parsed[CANON_RISK_SCORE], (int, float))  # JSON may convert float to int for whole numbers


def test_backward_compatibility_aliases(mock_scan_job):
    """Test that deprecated aliases are present and match canonical keys"""
    findings = [make_finding("test-scan-123", Severity.MEDIUM)]
    report = generate_basic_report(mock_scan_job, findings)
    
    assert DEPRECATED_TOTAL_FINDINGS in report
    assert DEPRECATED_FINDINGS_BY_SEVERITY in report
    assert report[DEPRECATED_TOTAL_FINDINGS] == report[CANON_FINDINGS_COUNT]
    assert report[DEPRECATED_FINDINGS_BY_SEVERITY] == report[CANON_SEV_BREAKDOWN]


def test_generate_summary_normalizes_severity_keys(mock_scan_job):
    """Test that _generate_summary ensures all 5 severity keys are present"""
    # Test with only high severity findings
    findings = [
        make_finding("test-scan-123", Severity.HIGH, title="High finding 1"),
        make_finding("test-scan-123", Severity.HIGH, title="High finding 2"),
    ]
    
    summary = _generate_summary(mock_scan_job, findings)
    
    # Verify all 5 keys present
    assert set(summary[CANON_SEV_BREAKDOWN].keys()) == {"critical", "high", "medium", "low", "info"}
    assert summary[CANON_SEV_BREAKDOWN]["high"] == 2
    assert summary[CANON_SEV_BREAKDOWN]["critical"] == 0
    assert summary[CANON_SEV_BREAKDOWN]["medium"] == 0
    assert summary[CANON_SEV_BREAKDOWN]["low"] == 0
    assert summary[CANON_SEV_BREAKDOWN]["info"] == 0
    
    # Verify backward compatibility
    assert summary[DEPRECATED_FINDINGS_BY_SEVERITY] == summary[CANON_SEV_BREAKDOWN]
    assert summary[DEPRECATED_TOTAL_FINDINGS] == summary[CANON_FINDINGS_COUNT]


def test_stable_tie_breaker_in_sorting(mock_scan_job):
    """Test that sorting uses stable tie-breaker (title, id) for same severity + CVSS"""
    findings = [
        make_finding("test-scan-123", Severity.HIGH, title="B finding", cvss_score=7.5, id="f1"),
        make_finding("test-scan-123", Severity.HIGH, title="A finding", cvss_score=7.5, id="f2"),
        make_finding("test-scan-123", Severity.HIGH, title="A finding", cvss_score=7.5, id="f3"),
    ]
    
    report = generate_basic_report(mock_scan_job, findings)
    
    # All should be in top_risks (only 3 findings)
    assert len(report["top_risks"]) == 3
    # Should be sorted by title (A before B), then by id (f2 before f3)
    assert report["top_risks"][0]["title"] == "A finding"
    assert report["top_risks"][1]["title"] == "A finding"
    assert report["top_risks"][2]["title"] == "B finding"


def test_top_risks_ordering_critical_before_high(mock_scan_job):
    """Test that top_risks are ordered correctly: critical > high > medium > low > info"""
    findings = [
        make_finding("test-scan-123", Severity.HIGH, title="High finding", cvss_score=7.5),
        make_finding("test-scan-123", Severity.CRITICAL, title="Critical finding", cvss_score=9.0),
        make_finding("test-scan-123", Severity.MEDIUM, title="Medium finding", cvss_score=5.0),
    ]
    
    report = generate_basic_report(mock_scan_job, findings)
    
    # Verify ordering
    assert len(report["top_risks"]) == 3
    assert report["top_risks"][0]["severity"] == "critical"
    assert report["top_risks"][1]["severity"] == "high"
    assert report["top_risks"][2]["severity"] == "medium"

