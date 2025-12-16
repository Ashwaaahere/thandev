"""
Report prompt schemas
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class ReportJsonSchema(BaseModel):
    """JSON Schema for report structure"""
    type: str = Field(default="object", description="Schema type")
    properties: Dict[str, Any] = Field(..., description="Schema properties")
    required: List[str] = Field(default_factory=list, description="Required fields")
    additionalProperties: bool = Field(default=False, description="Reject unknown properties")
    
    class Config:
        extra = "forbid"


class BuildReportPromptRequest(BaseModel):
    """Request to build a report prompt package"""
    scan_job_id: str = Field(..., description="Scan job ID")
    finding_ids: List[str] = Field(..., description="List of finding IDs")
    artifact_refs: Optional[List[Dict[str, Any]]] = Field(None, description="Artifact references")
    org_id: Optional[str] = Field(None, description="Organization ID")
    project_id: Optional[str] = Field(None, description="Project ID")
    
    class Config:
        extra = "forbid"


class BuildReportPromptResponse(BaseModel):
    """Response containing the report prompt package"""
    system_message: str = Field(..., description="System message for OpenAI")
    user_content: Dict[str, Any] = Field(..., description="User message content")
    report_json_schema: ReportJsonSchema = Field(..., description="Strict JSON schema")
    artifact_index: Dict[str, Any] = Field(default_factory=dict, description="Artifact index")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        extra = "forbid"




