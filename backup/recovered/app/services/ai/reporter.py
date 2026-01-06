"""
AI Reporter service for generating scan reports
"""
import logging
from typing import Dict, List, TYPE_CHECKING
from app.core.constants import (
    CANON_FINDINGS_COUNT, CANON_SEV_BREAKDOWN, CANON_RISK_SCORE,
    DEPRECATED_TOTAL_FINDINGS, DEPRECATED_FINDINGS_BY_SEVERITY
)

if TYPE_CHECKING:
    from app.models.scan import ScanJob
    from app.models.finding import Finding

logger = logging.getLogger(__name__)


def generate_basic_report(scan_job: "ScanJob", findings: List["Finding"]) -> Dict:
    """
    Generate AI-powered report for a basic scan
    
    Args:
        scan_job: ScanJob instance
        findings: List of Finding records
        
    Returns:
        Dictionary with report fields:
        - executive_summary: High-level overview
        - top_risks: List of top 5 critical/high findings
        - remediation_overview: Prioritized remediation steps
        - risk_score: Overall risk score (0-100)
    """
    logger.info(f"Generating AI report for scan {scan_job.id} with {len(findings)} findings")
    
    # Handle empty findings gracefully
    if not findings:
        empty_severity = {sev: 0 for sev in ["critical", "high", "medium", "low", "info"]}
        return {
            "executive_summary": "No security findings detected in this scan. The target appears to be secure based on the scan configuration.",
            "top_risks": [],
            "remediation_overview": "No immediate remediation actions required.",
            CANON_RISK_SCORE: 0.0,  # float
            CANON_FINDINGS_COUNT: 0,  # canonical
            DEPRECATED_TOTAL_FINDINGS: 0,  # deprecated alias
            CANON_SEV_BREAKDOWN: empty_severity.copy(),  # canonical, all keys present
            DEPRECATED_FINDINGS_BY_SEVERITY: empty_severity.copy(),  # deprecated alias
        }
    
    # Sort findings by severity (critical=0 < high=1 < medium=2 < low=3 < info=4), then by CVSS score descending, then by title and id for stability
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_findings = sorted(
        findings,
        key=lambda f: (
            severity_order.get(f.severity.value, 99),  # critical=0 first when ascending
            -(f.cvss_score or 0),  # higher CVSS first
            (getattr(f, "title", "") or ""),  # stable tie-breaker: title (safe guard)
            str(getattr(f, "id", "")),  # final tie-breaker: id (safe guard, handles missing id)
        ),
    )
    
    # Get top 5 risks
    top_risks = [
        {
            "title": f.title,
            "severity": f.severity.value,
            "cve_id": f.cve_id,
            "cvss_score": f.cvss_score,
            "url": f.url,
        }
        for f in sorted_findings[:5]
    ]
    
    # Calculate risk score (0-10 scale)
    # Formula: max severity (Critical=10, High=8, Medium=5, Low=2, Info=0)
    #          + log factor for medium+ findings (min(3, log2(1+count_medium_high)))
    #          clamped to 0-10, rounded to 1 decimal
    import math
    
    # Count findings by severity
    counts = {
        "critical": sum(1 for f in findings if f.severity.value == "critical"),
        "high": sum(1 for f in findings if f.severity.value == "high"),
        "medium": sum(1 for f in findings if f.severity.value == "medium"),
        "low": sum(1 for f in findings if f.severity.value == "low"),
        "info": sum(1 for f in findings if f.severity.value == "info"),
    }
    
    # Max severity score
    max_severity_scores = {
        "critical": 10,
        "high": 8,
        "medium": 5,
        "low": 2,
        "info": 0,
    }
    
    # Find max severity present
    max_severity_score = 0
    for severity, count in counts.items():
        if count > 0:
            max_severity_score = max(max_severity_score, max_severity_scores.get(severity, 0))
    
    # Count medium+ findings for log factor
    count_medium_high = counts["medium"] + counts["high"] + counts["critical"]
    log_factor = min(3.0, math.log2(1 + count_medium_high)) if count_medium_high > 0 else 0.0
    
    # Calculate base score
    base_score = max_severity_score + log_factor
    
    # Clamp to 0-10 and round to 1 decimal
    risk_score = max(0.0, min(10.0, base_score))
    risk_score = round(risk_score, 1)
    
    # Ensure > 0 if there's at least one Medium finding
    if counts["medium"] > 0 and risk_score == 0:
        risk_score = 0.1
    
    # Generate executive summary
    critical_count = sum(1 for f in findings if f.severity.value == "critical")
    high_count = sum(1 for f in findings if f.severity.value == "high")
    
    if critical_count > 0:
        exec_summary = f"CRITICAL: {critical_count} critical vulnerabilities detected requiring immediate attention."
    elif high_count > 0:
        exec_summary = f"HIGH PRIORITY: {high_count} high-severity vulnerabilities found. Review recommended."
    else:
        exec_summary = f"Scan completed with {len(findings)} findings. No critical issues detected."
    
    # Generate remediation overview
    remediation_steps = []
    if critical_count > 0:
        remediation_steps.append(f"1. Address {critical_count} critical vulnerabilities immediately")
    if high_count > 0:
        remediation_steps.append(f"2. Review and patch {high_count} high-severity issues")
    if not remediation_steps:
        remediation_steps.append("1. Review findings and apply security best practices")
    
    remediation_overview = "\n".join(remediation_steps)
    
    # Build severity_breakdown with all 5 keys
    severity_breakdown = {
        "critical": counts.get("critical", 0),
        "high": counts.get("high", 0),
        "medium": counts.get("medium", 0),
        "low": counts.get("low", 0),
        "info": counts.get("info", 0),
    }
    
    # TODO: Integrate with actual LLM (OpenAI, Anthropic, etc.) for richer reports
    # For now, return structured data that can be enhanced later
    
    return {
        "executive_summary": exec_summary,
        "top_risks": top_risks,
        "remediation_overview": remediation_overview,
        CANON_RISK_SCORE: float(risk_score),  # Ensure float
        CANON_FINDINGS_COUNT: len(findings),  # canonical
        DEPRECATED_TOTAL_FINDINGS: len(findings),  # deprecated alias
        CANON_SEV_BREAKDOWN: severity_breakdown,  # canonical
        DEPRECATED_FINDINGS_BY_SEVERITY: severity_breakdown.copy(),  # deprecated alias
    }



