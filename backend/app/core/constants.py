"""
Canonical summary field names constants.

Use these everywhere to prevent drift between canonical and deprecated keys.
"""
# Canonical summary field names (use these everywhere)
CANON_FINDINGS_COUNT = "findings_count"
CANON_SEV_BREAKDOWN = "severity_breakdown"
CANON_RISK_SCORE = "risk_score"

# Deprecated aliases (for backward compatibility during migration)
DEPRECATED_TOTAL_FINDINGS = "total_findings"
DEPRECATED_FINDINGS_BY_SEVERITY = "findings_by_severity"

# Terminal scan statuses (scan is finished, no longer running)
from app.models.scan import ScanStatus

TERMINAL_SCAN_STATUSES = {
    ScanStatus.COMPLETED,
    ScanStatus.COMPLETED_WITH_ERRORS,
    ScanStatus.FAILED,
    ScanStatus.CANCELLED,
}

