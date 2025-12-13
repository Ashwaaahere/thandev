"""
Pydantic schemas for Metrics API
"""
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Dict


class RecentScanItem(BaseModel):
    """Schema for recent scan item in dashboard overview"""
    id: str
    project_id: str
    project_name: str
    target_url: str
    level: str
    status: str
    created_at: datetime
    risk_score: Optional[float] = None
    findings_count: Optional[int] = None
    completed_at: Optional[datetime] = None
    scan_level: Optional[str] = None  # Alias for level for consistency


class TotalsMetrics(BaseModel):
    """Total counts for projects, scans, and findings"""
    projects: int
    scans: int
    findings: int


class RecentActivityMetrics(BaseModel):
    """Recent activity metrics"""
    last_scan_at: Optional[datetime] = None
    scans_last_7_days: int


class FindingsBySeverityMetrics(BaseModel):
    """Findings count by severity level"""
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class LatestScanItem(BaseModel):
    """Schema for latest scan item with full details"""
    id: str
    project_id: str
    project_name: str
    target_url: str
    scan_level: str
    status: str
    risk_score: Optional[float] = None
    findings_count: Optional[int] = None
    completed_at: Optional[datetime] = None


class DashboardOverviewMetrics(BaseModel):
    """Schema for dashboard overview metrics"""
    # Legacy fields (kept for backward compatibility)
    total_scans: int
    security_scans: int
    performance_scans: int  # placeholder for future
    vulnerabilities_found: int
    avg_security_score: float  # 0-100, where 100 is best
    scans_this_month: int
    recent_scans: List[RecentScanItem]
    
    # New Phase 2 fields
    totals: TotalsMetrics
    recent_activity: RecentActivityMetrics
    findings_by_severity: FindingsBySeverityMetrics
    latest_scans: List[LatestScanItem]






class FindingsBySeverityMetrics(BaseModel):
    """Findings count by severity level"""
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class LatestScanItem(BaseModel):
    """Schema for latest scan item with full details"""
    id: str
    project_id: str
    project_name: str
    target_url: str
    scan_level: str
    status: str
    risk_score: Optional[float] = None
    findings_count: Optional[int] = None
    completed_at: Optional[datetime] = None


class DashboardOverviewMetrics(BaseModel):
    """Schema for dashboard overview metrics"""
    # Legacy fields (kept for backward compatibility)
    total_scans: int
    security_scans: int
    performance_scans: int  # placeholder for future
    vulnerabilities_found: int
    avg_security_score: float  # 0-100, where 100 is best
    scans_this_month: int
    recent_scans: List[RecentScanItem]
    
    # New Phase 2 fields
    totals: TotalsMetrics
    recent_activity: RecentActivityMetrics
    findings_by_severity: FindingsBySeverityMetrics
    latest_scans: List[LatestScanItem]






class FindingsBySeverityMetrics(BaseModel):
    """Findings count by severity level"""
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class LatestScanItem(BaseModel):
    """Schema for latest scan item with full details"""
    id: str
    project_id: str
    project_name: str
    target_url: str
    scan_level: str
    status: str
    risk_score: Optional[float] = None
    findings_count: Optional[int] = None
    completed_at: Optional[datetime] = None


class DashboardOverviewMetrics(BaseModel):
    """Schema for dashboard overview metrics"""
    # Legacy fields (kept for backward compatibility)
    total_scans: int
    security_scans: int
    performance_scans: int  # placeholder for future
    vulnerabilities_found: int
    avg_security_score: float  # 0-100, where 100 is best
    scans_this_month: int
    recent_scans: List[RecentScanItem]
    
    # New Phase 2 fields
    totals: TotalsMetrics
    recent_activity: RecentActivityMetrics
    findings_by_severity: FindingsBySeverityMetrics
    latest_scans: List[LatestScanItem]






class FindingsBySeverityMetrics(BaseModel):
    """Findings count by severity level"""
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class LatestScanItem(BaseModel):
    """Schema for latest scan item with full details"""
    id: str
    project_id: str
    project_name: str
    target_url: str
    scan_level: str
    status: str
    risk_score: Optional[float] = None
    findings_count: Optional[int] = None
    completed_at: Optional[datetime] = None


class DashboardOverviewMetrics(BaseModel):
    """Schema for dashboard overview metrics"""
    # Legacy fields (kept for backward compatibility)
    total_scans: int
    security_scans: int
    performance_scans: int  # placeholder for future
    vulnerabilities_found: int
    avg_security_score: float  # 0-100, where 100 is best
    scans_this_month: int
    recent_scans: List[RecentScanItem]
    
    # New Phase 2 fields
    totals: TotalsMetrics
    recent_activity: RecentActivityMetrics
    findings_by_severity: FindingsBySeverityMetrics
    latest_scans: List[LatestScanItem]



