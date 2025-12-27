"""
Pydantic schemas for Tenant API
"""
from pydantic import BaseModel, ConfigDict
from typing import Dict, Any, List, Optional
from datetime import datetime


class TenantPlanUsage(BaseModel):
    """Usage statistics for the current tenant"""
    projects_count: int
    projects_max: int
    scans_this_month: int
    scans_monthly_max: int
    concurrent_scans: int
    concurrent_scans_max: int


class PlanLimits(BaseModel):
    """Plan limits structure"""
    max_projects: int
    max_scans_per_month: int
    max_concurrent_scans: int
    allowed_scan_levels: List[str]


class TenantPlanInfo(BaseModel):
    """Complete tenant plan information with limits and usage"""
    id: str
    name: str
    plan: str  # "free" | "individual" | "team"
    limits: PlanLimits
    usage: TenantPlanUsage


class TenantCreate(BaseModel):
    """Schema for creating a tenant"""
    id: Optional[str] = None  # Optional: if not provided, will be generated as UUID
    name: str
    plan: str = "pro"  # Default to "pro" (maps to "team" plan)


class TenantResponse(BaseModel):
    """Schema for tenant response"""
    id: str
    name: str
    plan: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)



