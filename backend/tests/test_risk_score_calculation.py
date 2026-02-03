"""
Unit tests for risk score calculation with unique findings and MEDIUM cap.
"""
import pytest
from app.services.pdf_reports import _compute_findings_metrics
from app.models.finding import Finding, Severity


def test_risk_score_uses_unique_findings():
    """Test that risk score uses unique findings count, not instances."""
    # Create mock findings with instances
    findings = []
    for i in range(5):
        finding = Finding()
        finding.id = f"finding-{i}"
        finding.severity = Severity.MEDIUM
        finding.affected_count = 10  # Each finding has 10 instances
        findings.append(finding)
    
    unique_count, breakdown, risk_score, instances_count = _compute_findings_metrics(findings)
    
    # Should count 5 unique findings, not 50 instances
    assert unique_count == 5
    assert instances_count == 50  # Total instances
    assert breakdown["medium"] == 5  # 5 unique medium findings


def test_risk_score_medium_cap():
    """Test that risk score is capped at 5.9 when max severity is MEDIUM and no HIGH/CRITICAL."""
    # Create mock findings with only MEDIUM severity
    findings = []
    for i in range(100):  # Many medium findings
        finding = Finding()
        finding.id = f"finding-{i}"
        finding.severity = Severity.MEDIUM
        finding.affected_count = 1
        findings.append(finding)
    
    unique_count, breakdown, risk_score, instances_count = _compute_findings_metrics(findings)
    
    # Risk score should be capped at 5.9
    assert risk_score <= 5.9
    assert breakdown["medium"] == 100
    assert breakdown["high"] == 0
    assert breakdown["critical"] == 0


def test_risk_score_no_cap_with_high():
    """Test that risk score is NOT capped when HIGH severity is present."""
    findings = []
    # Add one HIGH finding
    high_finding = Finding()
    high_finding.id = "high-1"
    high_finding.severity = Severity.HIGH
    high_finding.affected_count = 1
    findings.append(high_finding)
    
    # Add many MEDIUM findings
    for i in range(50):
        finding = Finding()
        finding.id = f"medium-{i}"
        finding.severity = Severity.MEDIUM
        finding.affected_count = 1
        findings.append(finding)
    
    unique_count, breakdown, risk_score, instances_count = _compute_findings_metrics(findings)
    
    # Risk score should NOT be capped (HIGH severity present)
    assert risk_score > 5.9  # Should be higher than cap
    assert breakdown["high"] == 1
    assert breakdown["medium"] == 50


def test_risk_score_no_cap_with_critical():
    """Test that risk score is NOT capped when CRITICAL severity is present."""
    findings = []
    # Add one CRITICAL finding
    critical_finding = Finding()
    critical_finding.id = "critical-1"
    critical_finding.severity = Severity.CRITICAL
    critical_finding.affected_count = 1
    findings.append(critical_finding)
    
    # Add many MEDIUM findings
    for i in range(50):
        finding = Finding()
        finding.id = f"medium-{i}"
        finding.severity = Severity.MEDIUM
        finding.affected_count = 1
        findings.append(finding)
    
    unique_count, breakdown, risk_score, instances_count = _compute_findings_metrics(findings)
    
    # Risk score should NOT be capped (CRITICAL severity present)
    assert risk_score > 5.9  # Should be much higher than cap
    assert breakdown["critical"] == 1
    assert breakdown["medium"] == 50


def test_risk_score_instances_count():
    """Test that instances_count correctly sums affected_count."""
    findings = []
    for i in range(3):
        finding = Finding()
        finding.id = f"finding-{i}"
        finding.severity = Severity.MEDIUM
        finding.affected_count = i + 1  # 1, 2, 3 instances
        findings.append(finding)
    
    unique_count, breakdown, risk_score, instances_count = _compute_findings_metrics(findings)
    
    assert unique_count == 3
    assert instances_count == 6  # 1 + 2 + 3
    assert breakdown["medium"] == 3


