"""
AI Reporter service for generating scan reports
"""
import logging
from typing import Dict, List, TYPE_CHECKING

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
        return {
            "executive_summary": "No security findings detected in this scan. The target appears to be secure based on the scan configuration.",
            "top_risks": [],
            "remediation_overview": "No immediate remediation actions required.",
            "risk_score": 0,
            "findings_count": 0
        }
    
    # Sort findings by severity (critical > high > medium > low > info)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_findings = sorted(
        findings,
        key=lambda f: (severity_order.get(f.severity.value, 99), f.cvss_score or 0),
        reverse=True
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
    
    # TODO: Integrate with actual LLM (OpenAI, Anthropic, etc.) for richer reports
    # For now, return structured data that can be enhanced later
    
    return {
        "executive_summary": exec_summary,
        "top_risks": top_risks,
        "remediation_overview": remediation_overview,
        "risk_score": risk_score,
        "findings_count": len(findings),
        "severity_breakdown": {
            "critical": critical_count,
            "high": high_count,
            "medium": sum(1 for f in findings if f.severity.value == "medium"),
            "low": sum(1 for f in findings if f.severity.value == "low"),
            "info": sum(1 for f in findings if f.severity.value == "info"),
        }
    }



