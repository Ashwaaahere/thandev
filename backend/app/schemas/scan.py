"""
Pydantic schemas for Scan API
"""
from pydantic import BaseModel, Field, HttpUrl, model_validator, field_validator, ConfigDict
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from app.models.scan import ScanLevel, ScanStatus, AIStatus
from app.models.finding import Severity


class ScanCreate(BaseModel):
    """Schema for creating a scan"""
    project_id: str = Field(..., description="Project ID to scan")
    scan_level: ScanLevel = Field(
        default=ScanLevel.BASIC,
        description="Scan level: basic, pro, or advanced. Defaults to 'basic' if not specified."
    )


class FindingResponse(BaseModel):
    """Schema for finding response (used in scan detail page)"""
    id: str
    title: str
    description: Optional[str]
    severity: Severity
    status: str
    cve_id: Optional[str]
    cwe_id: Optional[str]
    cvss_score: Optional[float]
    url: Optional[str]
    path: Optional[str]
    recommendation: Optional[str]
    tool_name: Optional[str]
    created_at: datetime
    # Enhanced fields for better UX
    vuln_type: Optional[str] = None
    http_method: Optional[str] = None
    parameter: Optional[str] = None
    remediation_summary: Optional[str] = None
    remediation_steps: Optional[str] = None
    default_remediation_steps: Optional[str] = None
    impact_summary: Optional[str] = None
    evidence: Optional[str] = None
    # AI metadata (optional, for display purposes)
    ai_source: Optional[str] = None  # Source identifier (e.g., "brain_v1", "fallback")
    ai_model: Optional[str] = None  # AI model used (e.g., "gpt-4o-mini")
    ai_confidence: Optional[float] = None  # Confidence score (0.0-1.0)
    
    model_config = ConfigDict(from_attributes=True)


class ToolStatus(BaseModel):
    """Schema for per-tool status in scan response"""
    tool_name: str
    status: str  # "pending" | "running" | "completed" | "failed" | "timed_out"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time: Optional[float] = None
    error_message: Optional[str] = None


class ScanResponse(BaseModel):
    """Schema for scan response"""
    id: str
    project_id: str
    scan_level: ScanLevel
    status: ScanStatus
    summary: Optional[Dict[str, Any]]
    stack_info: Optional[Dict[str, Any]] = None
    ai_plan: Optional[Dict[str, Any]] = None  # AI-generated scan plan (read-only)
    ai_status: Optional[AIStatus] = None  # AI planner status (read-only)
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    findings: List[FindingResponse] = []
    tool_statuses: List[ToolStatus] = []  # Per-tool execution statuses for progress indicator
    progress_pct: Optional[int] = None  # Overall scan progress percentage (0-100)
    total_tools: Optional[int] = None  # Total number of tools in the scan
    completed_tools: Optional[int] = None  # Number of completed/failed/skipped/timed_out tools
    # Status reconciliation metadata
    status_source: Optional[str] = Field(None, description="Source of status: 'brain' or 'db'")
    status_reason: Optional[str] = Field(None, description="Reason for status (e.g., 'stalled', 'brain_unreachable')")
    
    model_config = ConfigDict(from_attributes=True)


class ScanSummary(BaseModel):
    """Schema for scan summary statistics
    
    Canonical keys: findings_count, severity_breakdown
    Deprecated aliases: total_findings, findings_by_severity (for backward compatibility)
    """
    findings_count: int = 0  # canonical
    total_findings: Optional[int] = None  # deprecated, kept for backward compatibility
    severity_breakdown: Dict[str, int] = Field(default_factory=dict)  # canonical
    findings_by_severity: Optional[Dict[str, int]] = None  # deprecated, kept for backward compatibility
    tools_used: List[str] = Field(default_factory=list)
    scan_duration_seconds: Optional[float] = None
    
    @model_validator(mode='after')
    def populate_deprecated_aliases(self):
        """Auto-populate deprecated keys from canonical if not set"""
        if self.total_findings is None:
            self.total_findings = self.findings_count
        if self.findings_by_severity is None:
            self.findings_by_severity = self.severity_breakdown.copy() if self.severity_breakdown else {}
        return self


class ScanListResponse(BaseModel):
    """Schema for scan list response"""
    items: List[ScanResponse]
    total: int


class ScanJobListItem(BaseModel):
    """Schema for scan job list item (lightweight, for list views)"""
    id: str
    project_id: str
    project_name: Optional[str] = None
    target_url: Optional[str] = None
    scan_level: ScanLevel
    status: ScanStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    risk_score: Optional[float] = None
    findings_count: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


class ScanJobListResponse(BaseModel):
    """Schema for scan job list response"""
    items: List[ScanJobListItem]
    total: int


class QuickScanRequest(BaseModel):
    """Schema for quick scan request"""
    project_id: Optional[str] = Field(None, description="Project ID to scan (optional)")
    target_url: Optional[HttpUrl] = Field(None, description="Target URL to scan (optional)")
    scan_level: Union[str, ScanLevel] = Field(..., description="Scan level: basic, pro, or advanced (case-insensitive)")
    description: Optional[str] = None
    
    @field_validator('scan_level', mode='before')
    @classmethod
    def normalize_scan_level(cls, v):
        """Normalize scan_level to lowercase string"""
        from app.core.scan_utils import normalize_scan_level
        try:
            return normalize_scan_level(v)
        except ValueError as e:
            # Re-raise with clearer message for Pydantic
            raise ValueError(str(e))
    
    @model_validator(mode='after')
    def validate_at_least_one(self):
        """Ensure at least one of project_id or target_url is provided"""
        if not self.project_id and not self.target_url:
            raise ValueError('At least one of project_id or target_url must be provided')
        return self


class QuickScanResponse(BaseModel):
    """Schema for quick scan response"""
    project_id: str
    scan_id: str


class ToolExecutionResult(BaseModel):
    """Schema for tool execution result"""
    tool_name: str  # Canonical lowercase name (e.g., "dalfox")
    tool_name_display: Optional[str] = None  # Title Case for UI (e.g., "Dalfox")
    exit_code: Optional[int]
    started_at: datetime
    completed_at: Optional[datetime]
    output_size: int  # Size of output in bytes
    execution_time: Optional[float]  # Seconds
    error_message: Optional[str] = None
    timed_out: bool = False  # Whether the tool execution timed out
    # New tool run tracking fields
    status: Optional[str] = None  # ToolExecutionStatus enum value
    stdout_preview: Optional[str] = None  # First 1000 chars of stdout
    stderr_preview: Optional[str] = None  # First 1000 chars of stderr
    parsed_findings_count: int = 0  # Number of findings parsed from output (coalesce NULL to 0 for legacy tool runs)
    created_findings_count: int = 0  # Number of findings actually created in DB (coalesce NULL to 0 for legacy tool runs)
    duration_ms: Optional[int] = None  # Duration in milliseconds
    skip_reason: Optional[str] = None  # e.g., no_injection_points, rate_limited, blocked
    raw_stdout: Optional[str] = None
    raw_stderr: Optional[str] = None
    # Note: output_path is backend-only, not exposed to frontend for security
    
    model_config = ConfigDict(from_attributes=True)


class ScanToolsResponse(BaseModel):
    """Schema for scan tools response"""
    items: List[ToolExecutionResult]

