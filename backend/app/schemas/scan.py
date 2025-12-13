"""
Pydantic schemas for Scan API
"""
from pydantic import BaseModel, Field, HttpUrl, model_validator
from typing import Optional, Dict, Any, List
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
    """Schema for finding response"""
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
    
    class Config:
        from_attributes = True


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
    
    class Config:
        from_attributes = True


class ScanSummary(BaseModel):
    """Schema for scan summary statistics"""
    total_findings: int = 0
    findings_by_severity: Dict[str, int] = Field(default_factory=dict)
    tools_used: List[str] = Field(default_factory=list)
    scan_duration_seconds: Optional[float] = None


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
    
    class Config:
        from_attributes = True


class ScanJobListResponse(BaseModel):
    """Schema for scan job list response"""
    items: List[ScanJobListItem]
    total: int


class QuickScanRequest(BaseModel):
    """Schema for quick scan request"""
    project_id: Optional[str] = Field(None, description="Project ID to scan (optional)")
    target_url: Optional[HttpUrl] = Field(None, description="Target URL to scan (optional)")
    scan_level: ScanLevel
    description: Optional[str] = None
    
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
    tool_name: str
    exit_code: Optional[int]
    started_at: datetime
    completed_at: Optional[datetime]
    output_size: int  # Size of output in bytes
    execution_time: Optional[float]  # Seconds
    error_message: Optional[str] = None
    timed_out: bool = False  # Whether the tool execution timed out
    
    class Config:
        from_attributes = True


class ScanToolsResponse(BaseModel):
    """Schema for scan tools response"""
    items: List[ToolExecutionResult]

