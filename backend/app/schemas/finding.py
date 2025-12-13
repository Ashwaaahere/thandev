"""
Pydantic schemas for Finding API
"""
from pydantic import BaseModel
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
    tool: Optional[str] = None
    categories: Optional[List[str]] = None  # Vulnerability categories (e.g., ["xss", "sqli"])
    first_seen: datetime
    last_seen: datetime

    class Config:
        from_attributes = True


class UpdateFindingStatusRequest(BaseModel):
    """Schema for updating finding status"""
    status: FindingStatus


class FindingListResponse(BaseModel):
    """Schema for finding list response"""
    items: List[FindingListItem]
    total: int
