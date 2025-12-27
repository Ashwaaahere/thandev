#!/usr/bin/env python3
"""
Manual sanity check script for schema consistency.
Verifies that report summaries have correct canonical keys and deprecated aliases.
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.services.ai.reporter import generate_basic_report
from app.models.scan import ScanJob, ScanLevel, ScanStatus
from app.models.finding import Finding, Severity
from app.core.constants import (
    CANON_FINDINGS_COUNT, CANON_SEV_BREAKDOWN, CANON_RISK_SCORE,
    DEPRECATED_TOTAL_FINDINGS, DEPRECATED_FINDINGS_BY_SEVERITY
)


def print_summary(title: str, summary: dict):
    """Pretty print a summary dictionary"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"findings_count (canonical): {summary.get(CANON_FINDINGS_COUNT)}")
    print(f"total_findings (deprecated): {summary.get(DEPRECATED_TOTAL_FINDINGS)}")
    print(f"risk_score (canonical): {summary.get(CANON_RISK_SCORE)} (type: {type(summary.get(CANON_RISK_SCORE)).__name__})")
    print(f"\nseverity_breakdown (canonical):")
    sev_breakdown = summary.get(CANON_SEV_BREAKDOWN, {})
    for sev in ["critical", "high", "medium", "low", "info"]:
        count = sev_breakdown.get(sev, 0)
        print(f"  {sev}: {count}")
    print(f"\nfindings_by_severity (deprecated):")
    findings_by_sev = summary.get(DEPRECATED_FINDINGS_BY_SEVERITY, {})
    for sev in ["critical", "high", "medium", "low", "info"]:
        count = findings_by_sev.get(sev, 0)
        print(f"  {sev}: {count}")
    print(f"\nKeys present: {list(summary.keys())}")
    print(f"{'='*60}\n")


def test_empty_findings():
    """Test empty findings summary"""
    print("TEST 1: Empty Findings")
    scan_job = ScanJob(
        id="test-empty",
        project_id="test-project",
        scan_level=ScanLevel.BASIC,
        status=ScanStatus.COMPLETED,
    )
    
    summary = generate_basic_report(scan_job, [])
    print_summary("Empty Findings Summary", summary)
    
    # Verify
    assert CANON_FINDINGS_COUNT in summary, "Missing findings_count"
    assert CANON_SEV_BREAKDOWN in summary, "Missing severity_breakdown"
    assert CANON_RISK_SCORE in summary, "Missing risk_score"
    assert DEPRECATED_TOTAL_FINDINGS in summary, "Missing total_findings (deprecated)"
    assert DEPRECATED_FINDINGS_BY_SEVERITY in summary, "Missing findings_by_severity (deprecated)"
    assert isinstance(summary[CANON_RISK_SCORE], float), "risk_score must be float"
    assert summary[CANON_FINDINGS_COUNT] == 0, "findings_count should be 0"
    assert len(summary[CANON_SEV_BREAKDOWN]) == 5, "severity_breakdown must have 5 keys"
    assert summary[DEPRECATED_TOTAL_FINDINGS] == summary[CANON_FINDINGS_COUNT], "Deprecated alias must match canonical"
    print("✅ Empty findings test PASSED\n")


def test_mixed_severities():
    """Test mixed severities summary"""
    print("TEST 2: Mixed Severities (Critical + High + Medium)")
    scan_job = ScanJob(
        id="test-mixed",
        project_id="test-project",
        scan_level=ScanLevel.PRO,
        status=ScanStatus.COMPLETED,
    )
    
    findings = [
        Finding(
            id="f1",
            scan_job_id="test-mixed",
            title="Critical vulnerability",
            severity=Severity.CRITICAL,
            cvss_score=9.5,
            tool_name="nuclei",
        ),
        Finding(
            id="f2",
            scan_job_id="test-mixed",
            title="High severity issue",
            severity=Severity.HIGH,
            cvss_score=7.2,
            tool_name="nuclei",
        ),
        Finding(
            id="f3",
            scan_job_id="test-mixed",
            title="Medium severity finding",
            severity=Severity.MEDIUM,
            cvss_score=5.0,
            tool_name="nuclei",
        ),
    ]
    
    summary = generate_basic_report(scan_job, findings)
    print_summary("Mixed Severities Summary", summary)
    
    # Verify
    assert CANON_FINDINGS_COUNT in summary, "Missing findings_count"
    assert CANON_SEV_BREAKDOWN in summary, "Missing severity_breakdown"
    assert CANON_RISK_SCORE in summary, "Missing risk_score"
    assert DEPRECATED_TOTAL_FINDINGS in summary, "Missing total_findings (deprecated)"
    assert DEPRECATED_FINDINGS_BY_SEVERITY in summary, "Missing findings_by_severity (deprecated)"
    assert isinstance(summary[CANON_RISK_SCORE], float), "risk_score must be float"
    assert summary[CANON_FINDINGS_COUNT] == 3, "findings_count should be 3"
    assert len(summary[CANON_SEV_BREAKDOWN]) == 5, "severity_breakdown must have all 5 keys"
    assert summary[CANON_SEV_BREAKDOWN]["critical"] == 1, "Should have 1 critical"
    assert summary[CANON_SEV_BREAKDOWN]["high"] == 1, "Should have 1 high"
    assert summary[CANON_SEV_BREAKDOWN]["medium"] == 1, "Should have 1 medium"
    assert summary[CANON_SEV_BREAKDOWN]["low"] == 0, "Should have 0 low"
    assert summary[CANON_SEV_BREAKDOWN]["info"] == 0, "Should have 0 info"
    assert summary[DEPRECATED_TOTAL_FINDINGS] == summary[CANON_FINDINGS_COUNT], "Deprecated alias must match canonical"
    assert summary[DEPRECATED_FINDINGS_BY_SEVERITY] == summary[CANON_SEV_BREAKDOWN], "Deprecated alias must match canonical"
    print("✅ Mixed severities test PASSED\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SCHEMA CONSISTENCY VERIFICATION")
    print("="*60)
    
    try:
        test_empty_findings()
        test_mixed_severities()
        print("\n" + "="*60)
        print("✅ ALL VERIFICATION TESTS PASSED")
        print("="*60 + "\n")
    except AssertionError as e:
        print(f"\n❌ VERIFICATION FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

