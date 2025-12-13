"""
Pydantic schemas for Project API
"""
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
from datetime import datetime


class ProjectCreate(BaseModel):
    """Schema for creating a project"""
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    target_url: HttpUrl = Field(..., description="Target URL to scan")
    repo_url: Optional[HttpUrl] = Field(None, description="Optional repository URL")
    description: Optional[str] = Field(None, description="Project description")


class ProjectResponse(BaseModel):
    """Schema for project response"""
    id: str
    name: str
    target_url: str
    repo_url: Optional[str]
    description: Optional[str]
    owner_id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProjectWithStats(BaseModel):
    """Schema for project with statistics for list view"""
    id: str
    name: str
    target_url: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    last_scan_at: Optional[datetime] = None
    last_scan_status: Optional[str] = None
    last_risk_score: Optional[float] = None
    total_scans: int = 0
    open_findings: int = 0
    
    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """Schema for project list response"""
    items: list[ProjectResponse]
    total: int


class ProjectListWithStatsResponse(BaseModel):
    """Schema for project list response with statistics"""
    items: list[ProjectWithStats]
    total: int


class LatestScanTool(BaseModel):
    """Schema for latest scan tool execution"""
    tool_name: str
    exit_code: Optional[int] = None


class ProjectOverviewStats(BaseModel):
    """Schema for project overview statistics"""
    total_scans: int
    last_scan_at: Optional[datetime] = None
    last_scan_status: Optional[str] = None
    last_risk_score: Optional[float] = None
    open_findings_total: int
    open_findings_by_severity: dict[str, int]
    tools_used: list[str]
    latest_scan_tools: list[LatestScanTool] = Field(default_factory=list)


class ProjectOverviewResponse(BaseModel):
    """Schema for project overview response"""
    id: str
    name: str
    target_url: str
    created_at: datetime
    stats: ProjectOverviewStats




