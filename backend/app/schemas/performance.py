"""
Pydantic schemas for Performance Scan API
"""
from pydantic import BaseModel, Field, HttpUrl, model_validator
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from app.models.scan import ScanLevel
from app.models.performance_scan import PerformanceScanStatus


class PerformanceScanCreate(BaseModel):
    """Schema for creating a performance scan"""
    project_id: Optional[str] = Field(None, description="Project ID to scan (optional)")
    target_url: Optional[str] = Field(None, description="Target URL to scan (optional)")
    scan_level: Literal["basic", "pro", "advanced"] = Field(
        default="pro",
        description="Scan level: basic, pro, or advanced"
    )
    
    @model_validator(mode='after')
    def validate_at_least_one(self):
        """Ensure at least one of project_id or target_url is provided"""
        if not self.project_id and not self.target_url:
            raise ValueError('At least one of project_id or target_url must be provided')
        return self


class PerformanceScanDetail(BaseModel):
    """Schema for performance scan detail response"""
    id: str
    project_id: Optional[str]
    target_url: str
    scan_level: str
    status: str
    metrics: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class PerformanceScanListItem(BaseModel):
    """Schema for performance scan list item (optimized for table rows)"""
    id: str
    project_id: Optional[str]
    project_name: Optional[str]
    target_url: str
    scan_level: str
    status: str
    perf_score: Optional[float] = None  # Extracted from metrics.overall_score
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class PerformanceScanListResponse(BaseModel):
    """Schema for performance scan list response"""
    items: List[PerformanceScanListItem]
    total: int


class QuickPerformanceScanResponse(BaseModel):
    """Schema for quick performance scan response"""
    project_id: Optional[str]
    scan_id: str
