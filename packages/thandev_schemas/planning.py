"""
Scan planning schemas
"""
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, List, Optional


class PlanScanRequest(BaseModel):
    """Request to generate a scan plan"""
    target_url: str = Field(..., description="Target URL to scan")
    scan_level: str = Field(..., description="Scan level: basic, pro, or advanced")
    org_id: Optional[str] = Field(None, description="Organization ID")
    project_id: Optional[str] = Field(None, description="Project ID")
    stack_info: Optional[Dict[str, Any]] = Field(None, description="Target stack information")
    
    @field_validator("scan_level")
    @classmethod
    def validate_scan_level(cls, v: str) -> str:
        valid_levels = {"basic", "pro", "advanced"}
        if v.lower() not in valid_levels:
            raise ValueError(f"scan_level must be one of {valid_levels}")
        return v.lower()
    
    class Config:
        extra = "forbid"


class PlanStep(BaseModel):
    """A single step in a scan plan"""
    step_id: str = Field(..., description="Unique step identifier")
    tool_id: str = Field(..., description="Tool identifier")
    mode_id: str = Field(..., description="Mode identifier")
    params: Dict[str, Any] = Field(default_factory=dict, description="Validated parameters")
    depends_on: List[str] = Field(default_factory=list, description="Dependencies (step_ids)")
    reason: str = Field(..., description="Explanation for this step")
    estimated_duration_sec: int = Field(..., ge=0, description="Estimated duration in seconds")
    
    class Config:
        extra = "forbid"


class Timeline(BaseModel):
    """Timeline estimates for the scan plan"""
    total_estimated_sec: int = Field(..., ge=0, description="Total estimated duration")
    phases: List[Dict[str, Any]] = Field(default_factory=list, description="Phase breakdown")
    
    class Config:
        extra = "forbid"


class PlanScanResponse(BaseModel):
    """Response containing the scan plan"""
    plan_id: str = Field(..., description="Unique plan identifier")
    steps: List[PlanStep] = Field(..., description="Ordered list of scan steps")
    timeline: Timeline = Field(..., description="Timeline estimates")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        extra = "forbid"




