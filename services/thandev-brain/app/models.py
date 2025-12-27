"""
Pydantic models for Thandev Brain Service API
"""
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, List, Optional
from datetime import datetime
import enum


# Request/Response Models

class PlanScanRequest(BaseModel):
    """Request to generate a scan plan"""
    target_url: str = Field(..., description="Target URL to scan")
    scan_level: str = Field(..., description="Scan level: basic, pro, or advanced")
    org_id: Optional[str] = Field(None, description="Organization ID for RAG filtering")
    project_id: Optional[str] = Field(None, description="Project ID for RAG filtering")
    stack_info: Optional[Dict[str, Any]] = Field(None, description="Target stack information (HTTP headers, status, etc.)")
    
    @field_validator("scan_level")
    @classmethod
    def validate_scan_level(cls, v: str) -> str:
        """Validate scan level"""
        valid_levels = {"basic", "pro", "advanced"}
        if v.lower() not in valid_levels:
            raise ValueError(f"scan_level must be one of {valid_levels}")
        return v.lower()
    
    class Config:
        extra = "forbid"  # Reject unknown fields


class PlanStep(BaseModel):
    """A single step in a scan plan"""
    step_id: str = Field(..., description="Unique step identifier")
    tool_id: str = Field(..., description="Tool identifier (e.g., 'nuclei', 'nmap')")
    mode_id: str = Field(..., description="Mode identifier (e.g., 'cve_fast', 'top_ports')")
    params: Dict[str, Any] = Field(default_factory=dict, description="Validated parameters for this tool/mode")
    depends_on: List[str] = Field(default_factory=list, description="List of step_ids this step depends on")
    reason: str = Field(..., description="Explanation for why this step is included")
    estimated_duration_sec: int = Field(..., ge=0, description="Estimated execution time in seconds")
    
    class Config:
        extra = "forbid"


class Timeline(BaseModel):
    """Timeline estimates for the scan plan"""
    total_estimated_sec: int = Field(..., ge=0, description="Total estimated duration in seconds")
    phases: List[Dict[str, Any]] = Field(default_factory=list, description="Phase breakdown with parallel steps")
    
    class Config:
        extra = "forbid"


class PlanScanResponse(BaseModel):
    """Response containing the scan plan"""
    plan_id: str = Field(..., description="Unique plan identifier")
    steps: List[PlanStep] = Field(..., description="Ordered list of scan steps")
    timeline: Timeline = Field(..., description="Timeline estimates")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional plan metadata")
    
    class Config:
        extra = "forbid"


class BuildReportPromptRequest(BaseModel):
    """Request to build a report prompt package"""
    scan_job_id: str = Field(..., description="Scan job ID")
    finding_ids: List[str] = Field(..., description="List of finding IDs to include in report")
    artifact_refs: Optional[List[Dict[str, Any]]] = Field(None, description="Artifact references (tool outputs, etc.)")
    org_id: Optional[str] = Field(None, description="Organization ID for RAG filtering")
    project_id: Optional[str] = Field(None, description="Project ID for RAG filtering")
    
    class Config:
        extra = "forbid"


class ReportJsonSchema(BaseModel):
    """JSON Schema for report structure (for OpenAI Structured Outputs)"""
    type: str = Field(default="object", description="Schema type")
    properties: Dict[str, Any] = Field(..., description="Schema properties")
    required: List[str] = Field(default_factory=list, description="Required fields")
    additionalProperties: bool = Field(default=False, description="Reject unknown properties")
    
    class Config:
        extra = "forbid"


class BuildReportPromptResponse(BaseModel):
    """Response containing the report prompt package"""
    system_message: str = Field(..., description="System message for OpenAI")
    user_content: Dict[str, Any] = Field(..., description="User message content with findings and evidence")
    report_json_schema: ReportJsonSchema = Field(..., description="Strict JSON schema for report structure")
    artifact_index: Dict[str, Any] = Field(default_factory=dict, description="Index of artifacts referenced in findings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        extra = "forbid"


# Catalog Models

class ModeDefinition(BaseModel):
    """Definition of a tool mode"""
    mode_id: str = Field(..., description="Mode identifier")
    name: str = Field(..., description="Human-readable mode name")
    description: str = Field(..., description="Mode description")
    params_schema: Dict[str, Any] = Field(..., description="JSON Schema for mode parameters")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Mode constraints (timeout, etc.)")
    
    class Config:
        extra = "forbid"


class ToolDefinition(BaseModel):
    """Definition of a tool"""
    tool_id: str = Field(..., description="Tool identifier")
    name: str = Field(..., description="Human-readable tool name")
    description: str = Field(..., description="Tool description")
    allowed_target_types: List[str] = Field(..., description="Target types this tool can scan (e.g., 'http', 'tcp')")
    modes: List[ModeDefinition] = Field(..., description="Available modes for this tool")
    
    class Config:
        extra = "forbid"


class CatalogResponse(BaseModel):
    """Response containing the tool catalog"""
    tools: List[ToolDefinition] = Field(..., description="List of available tools")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Catalog metadata (version, etc.)")
    
    class Config:
        extra = "forbid"


# Session Models (PR-4A)

class StartSessionRequest(BaseModel):
    """Request to start a scan session"""
    scan_job_id: str = Field(..., description="Scan job ID from core")
    target_url: str = Field(..., description="Target URL to scan")
    scan_level: str = Field(..., description="Scan level: basic, pro, or advanced")
    org_id: Optional[str] = Field(None, description="Organization ID")
    project_id: Optional[str] = Field(None, description="Project ID")
    stack_info: Optional[Dict[str, Any]] = Field(None, description="Target stack information")
    policy: Optional[Dict[str, Any]] = Field(None, description="Scan policy (max_steps, max_runtime, etc.)")
    
    @field_validator("scan_level")
    @classmethod
    def validate_scan_level(cls, v: str) -> str:
        """Validate scan level"""
        valid_levels = {"basic", "pro", "advanced"}
        if v.lower() not in valid_levels:
            raise ValueError(f"scan_level must be one of {valid_levels}")
        return v.lower()
    
    class Config:
        extra = "forbid"


class SessionStatus(str, enum.Enum):
    """Session status enumeration"""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class StopReasonCode(str, enum.Enum):
    """Stop reason code enumeration"""
    BUDGET_EXCEEDED = "budget_exceeded"
    DIMINISHING_RETURNS = "diminishing_returns"
    CONFIRMED_PRESENT = "confirmed_present"
    CONFIRMED_ABSENT = "confirmed_absent"
    USER_STOPPED = "user_stopped"
    ERROR = "error"


class SessionState(BaseModel):
    """Session state stored in Redis"""
    session_id: str = Field(..., description="Unique session identifier")
    scan_job_id: str = Field(..., description="Scan job ID from core")
    org_id: Optional[str] = Field(None, description="Organization ID")
    project_id: Optional[str] = Field(None, description="Project ID")
    target_url: str = Field(..., description="Target URL")
    scan_level: str = Field(..., description="Scan level")
    status: SessionStatus = Field(default=SessionStatus.RUNNING, description="Session status")
    stop_reason_code: Optional[StopReasonCode] = Field(None, description="Reason for stopping")
    current_step_count: int = Field(default=0, ge=0, description="Number of steps executed")
    total_runtime_sec: float = Field(default=0.0, ge=0.0, description="Total runtime in seconds")
    consecutive_failures: int = Field(default=0, ge=0, description="Consecutive step failures")
    no_new_findings_iterations: int = Field(default=0, ge=0, description="Iterations with no new findings")
    executed_step_ids: List[str] = Field(default_factory=list, description="List of step IDs that have been executed")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation time")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    error_message: Optional[str] = Field(None, description="Error message if session failed")
    
    class Config:
        extra = "allow"  # Allow extra fields like error_message from Redis


class StartSessionResponse(BaseModel):
    """Response from starting a session"""
    session_id: str = Field(..., description="Unique session identifier")
    status: SessionStatus = Field(..., description="Initial session status")
    message: str = Field(..., description="Status message")
    
    class Config:
        extra = "forbid"


class GetSessionResponse(BaseModel):
    """Response from getting session status"""
    session_id: str = Field(..., description="Session identifier")
    status: SessionStatus = Field(..., description="Current status")
    stop_reason_code: Optional[StopReasonCode] = Field(None, description="Stop reason if stopped")
    current_step_count: int = Field(..., description="Steps executed")
    total_runtime_sec: float = Field(..., description="Total runtime")
    created_at: datetime = Field(..., description="Creation time")
    last_updated: datetime = Field(..., description="Last update time")
    error_message: Optional[str] = Field(None, description="Error message if session failed")
    
    class Config:
        extra = "forbid"


class StopSessionResponse(BaseModel):
    """Response from stopping a session"""
    session_id: str = Field(..., description="Session identifier")
    status: SessionStatus = Field(..., description="Final status")
    message: str = Field(..., description="Status message")
    
    class Config:
        extra = "forbid"


# Finding Enrichment Models

class BrainFindingInput(BaseModel):
    """Input model for finding enrichment"""
    id: str = Field(..., description="Finding ID")
    title: str = Field(..., description="Finding title")
    description: Optional[str] = Field(None, description="Finding description")
    severity: Optional[str] = Field(None, description="Finding severity (critical, high, medium, low, info)")
    tool_name: Optional[str] = Field(None, description="Tool that found this issue")
    vuln_type: Optional[str] = Field(None, description="Vulnerability type (xss, sqli, etc.)")
    url: Optional[str] = Field(None, description="URL where finding was detected")
    parameter: Optional[str] = Field(None, description="Parameter name if applicable")
    target_url: Optional[str] = Field(None, description="Target URL being scanned")
    project_id: Optional[str] = Field(None, description="Project ID")
    org_id: Optional[str] = Field(None, description="Organization ID")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Raw finding data as dict (not string)")
    
    class Config:
        extra = "forbid"


class EnrichedFindingItem(BaseModel):
    """Enriched finding data from AI"""
    finding_id: str = Field(..., description="Finding ID")
    impact_summary: Optional[str] = Field(None, description="AI-generated impact summary")
    remediation_summary: Optional[str] = Field(None, description="AI-generated remediation summary")
    remediation_steps: Optional[List[str]] = Field(None, description="AI-generated remediation steps")
    ai_source: Optional[str] = Field(None, description="Source identifier (e.g., 'brain_v1')")
    ai_model: Optional[str] = Field(None, description="AI model used (e.g., 'gpt-4o-mini')")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    
    class Config:
        extra = "forbid"


class EnrichFindingsRequest(BaseModel):
    """Request to enrich findings with AI"""
    findings: List[BrainFindingInput] = Field(..., description="List of findings to enrich")
    org_id: Optional[str] = Field(None, description="Organization ID for RAG filtering")
    project_id: Optional[str] = Field(None, description="Project ID for RAG filtering")
    target_url: Optional[str] = Field(None, description="Target URL for RAG filtering")
    
    class Config:
        extra = "forbid"


class EnrichFindingsResponse(BaseModel):
    """Response containing enriched findings"""
    items: List[EnrichedFindingItem] = Field(..., description="List of enriched findings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        extra = "forbid"


