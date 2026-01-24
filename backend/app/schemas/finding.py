"""
Pydantic schemas for Finding API
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

from app.models.finding import FindingStatus


class FindingListItem(BaseModel):
    """Schema for finding item in list view"""
    id: str
    scan_id: str
    project_id: str
    project_name: str
    target_url: str
    severity: str
    status: str
    title: str
    description: Optional[str] = None
    cve_id: Optional[str] = None
    cwe_id: Optional[str] = None
    # ZAP-specific metadata
    wasc_id: Optional[int] = None  # WASC ID (integer, e.g., 15)
    plugin_id: Optional[str] = None  # ZAP plugin ID (e.g., "10020")
    alert_ref: Optional[str] = None  # ZAP alert reference (e.g., "10020")
    zap_confidence: Optional[int] = None  # ZAP confidence (0=Low, 1=Medium, 2=High, 3=Confirmed)
    zap_riskcode: Optional[int] = None  # ZAP riskcode (0=Info, 1=Low, 2=Medium, 3=High, 4=Critical)
    tool: Optional[str] = None
    categories: Optional[List[str]] = None  # Vulnerability categories (e.g., ["xss", "sqli"])
    # New fields for improved UX
    vuln_type: Optional[str] = None  # Normalized vulnerability type (e.g., "xss", "sqli")
    http_method: Optional[str] = None  # HTTP method (e.g., "GET", "POST")
    parameter: Optional[str] = None  # Parameter name (e.g., "q", "username")
    url: Optional[str] = None  # Full URL where finding was detected
    path: Optional[str] = None  # Path component
    # Evidence field
    evidence: Optional[str] = None  # Short evidence snippet (payload, DBMS, template context)
    # Severity metadata
    needs_verification: Optional[bool] = None  # Flag: true if confidence is low and needs manual verification
    # Lifecycle fields
    first_seen_at: Optional[datetime] = None  # When first detected (from lifecycle)
    last_seen_at: Optional[datetime] = None  # When last detected (from lifecycle)
    not_seen_in_latest_scan: Optional[bool] = None  # True if not seen in latest scan
    found_count: Optional[int] = None  # Number of scans where this finding appeared
    # Remediation fields
    remediation_summary: Optional[str] = None  # Short summary of how to fix
    remediation_steps: Optional[str] = None  # JSON array or newline-separated steps
    default_remediation_steps: Optional[str] = None  # Default steps if remediation_steps is empty (newline-separated)
    # Impact field
    impact_summary: Optional[str] = None  # Short explanation of why this vulnerability matters
    # AI metadata (optional, for display purposes)
    ai_source: Optional[str] = None  # Source identifier (e.g., "brain_v1", "fallback")
    ai_model: Optional[str] = None  # AI model used (e.g., "gpt-4o-mini")
    ai_confidence: Optional[float] = None  # Confidence score (0.0-1.0)
    # Raw data preview (trimmed for UI consumption)
    raw_data_preview: Optional[dict] = None  # Selected keys from raw_data (payload, dbms, template_id, etc.)
    # Legacy fields (kept for backward compatibility)
    first_seen: Optional[datetime] = None  # Alias for first_seen_at
    last_seen: Optional[datetime] = None  # Alias for last_seen_at

    model_config = ConfigDict(from_attributes=True)


class UpdateFindingStatusRequest(BaseModel):
    """Schema for updating finding status"""
    status: FindingStatus


class FindingListResponse(BaseModel):
    """Schema for finding list response"""
    items: List[FindingListItem]
    total: int


class FindingDetailResponse(BaseModel):
    """Schema for detailed finding view (includes full raw_data)"""
    id: str
    scan_id: str
    project_id: str
    project_name: str
    target_url: str
    severity: str
    status: str
    title: str
    description: Optional[str] = None
    cve_id: Optional[str] = None
    cwe_id: Optional[str] = None
    cvss_score: Optional[float] = None
    # ZAP-specific metadata
    wasc_id: Optional[int] = None  # WASC ID (integer, e.g., 15)
    plugin_id: Optional[str] = None  # ZAP plugin ID (e.g., "10020")
    alert_ref: Optional[str] = None  # ZAP alert reference (e.g., "10020")
    zap_confidence: Optional[int] = None  # ZAP confidence (0=Low, 1=Medium, 2=High, 3=Confirmed)
    zap_riskcode: Optional[int] = None  # ZAP riskcode (0=Info, 1=Low, 2=Medium, 3=High, 4=Critical)
    tool: Optional[str] = None
    categories: Optional[List[str]] = None
    vuln_type: Optional[str] = None
    http_method: Optional[str] = None
    parameter: Optional[str] = None
    url: Optional[str] = None
    path: Optional[str] = None
    evidence: Optional[str] = None
    needs_verification: Optional[bool] = None  # Flag: true if confidence is low and needs manual verification
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    not_seen_in_latest_scan: Optional[bool] = None
    found_count: Optional[int] = None
    remediation_summary: Optional[str] = None
    remediation_steps: Optional[str] = None
    default_remediation_steps: Optional[str] = None
    impact_summary: Optional[str] = None
    # AI metadata (optional, for display purposes)
    ai_source: Optional[str] = None  # Source identifier (e.g., "brain_v1", "fallback")
    ai_model: Optional[str] = None  # AI model used (e.g., "gpt-4o-mini")
    ai_confidence: Optional[float] = None  # Confidence score (0.0-1.0)
    raw_data: Optional[dict] = None  # Full raw_data as JSON object (for power users)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
