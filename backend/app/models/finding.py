"""
Finding and ToolResult models
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum as SQLEnum, Float, Integer, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base


class Severity(str, enum.Enum):
    """Finding severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingStatus(str, enum.Enum):
    """Finding workflow status"""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class Finding(Base):
    """Finding model representing a security vulnerability or issue"""
    
    __tablename__ = "findings"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_job_id = Column(String(36), ForeignKey("scan_jobs.id"), nullable=False, index=True)
    
    # Direct project link for easier querying (denormalized from scan_job.project_id)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True, index=True)
    
    # Finding details
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(SQLEnum(Severity), nullable=False, index=True)
    
    # CVE/CWE information
    cve_id = Column(String(50), nullable=True, index=True)
    cwe_id = Column(String(50), nullable=True)  # CWE ID as string (e.g., "CWE-79")
    cvss_score = Column(Float, nullable=True)
    
    # ZAP-specific metadata
    wasc_id = Column(Integer, nullable=True)  # WASC ID (integer, e.g., 15)
    plugin_id = Column(String(50), nullable=True)  # ZAP plugin ID (e.g., "10020")
    alert_ref = Column(String(50), nullable=True)  # ZAP alert reference (e.g., "10020")
    zap_confidence = Column(Integer, nullable=True)  # ZAP confidence (0=Low, 1=Medium, 2=High, 3=Confirmed)
    zap_riskcode = Column(Integer, nullable=True)  # ZAP riskcode (0=Info, 1=Low, 2=Medium, 3=High, 4=Critical)
    
    # Identification / Linking
    tool_name = Column(String(100), nullable=True, index=True)  # Kept for backwards compatibility
    tool = Column(String(100), nullable=True, index=True)  # New normalized field (alias for tool_name)
    tool_result_id = Column(String(36), ForeignKey("tool_results.id"), nullable=True, index=True)  # Link to specific tool run (v2)
    template_id = Column(String(255), nullable=True, index=True)  # Template/rule identifier (e.g., nuclei template-id)
    rule_id = Column(String(255), nullable=True)  # Alternative rule identifier
    vuln_type = Column(String(100), nullable=True, index=True)  # Normalized vulnerability type (e.g., "xss", "sqli")
    category = Column(String(100), nullable=True)  # Alternative category field
    
    # Location information (enhanced)
    url = Column(String(2048), nullable=True)
    path = Column(String(2048), nullable=True)
    line_number = Column(Integer, nullable=True)
    http_method = Column(String(10), nullable=True)  # GET, POST, etc.
    parameter = Column(String(255), nullable=True)  # Query/body parameter name
    header_name = Column(String(255), nullable=True)  # Header name if applicable
    cookie_name = Column(String(255), nullable=True)  # Cookie name if applicable
    
    # Evidence
    evidence = Column(Text, nullable=True)  # Short evidence snippet (payload, response snippet)
    raw_data = Column(Text, nullable=True)  # JSON string of raw finding data
    
    # Severity metadata
    needs_verification = Column(Boolean, nullable=False, default=False, server_default="false")  # Flag: true if confidence is low and needs manual verification
    
    # Lifecycle fields
    dedup_key = Column(String(64), nullable=True, index=True)  # Deterministic hash for deduplication
    first_seen_at = Column(DateTime(timezone=True), nullable=True)  # When first detected
    last_seen_at = Column(DateTime(timezone=True), nullable=True)  # When last detected
    last_seen_in_scan_id = Column(String(36), ForeignKey("scan_jobs.id"), nullable=True)  # Most recent scan where seen
    found_count = Column(Integer, nullable=False, default=1, server_default="1")  # Number of scans where appeared
    not_seen_in_latest_scan = Column(Boolean, nullable=False, default=False, server_default="false")  # Flag: true if not seen in latest scan
    
    # Remediation (enhanced)
    recommendation = Column(Text, nullable=True)  # Kept for backwards compatibility
    remediation_summary = Column(Text, nullable=True)  # Short summary of what to fix
    remediation_steps = Column(Text, nullable=True)  # JSON array or newline-separated steps
    framework_hint = Column(String(100), nullable=True)  # Detected framework (django, express, laravel, etc.)
    
    # AI Enrichment fields (from thandev-brain)
    impact_summary = Column(Text, nullable=True)  # AI-generated impact summary
    ai_source = Column(String(50), nullable=True)  # Source identifier (e.g., "brain_v1", "fallback")
    ai_model = Column(String(100), nullable=True)  # AI model used (e.g., "gpt-4o-mini")
    ai_confidence = Column(Float, nullable=True)  # Confidence score (0.0-1.0)
    ai_last_updated_at = Column(DateTime(timezone=True), nullable=True)  # When AI enrichment was last updated
    
    # Workflow status
    status = Column(
        SQLEnum(FindingStatus, name="finding_status"),
        nullable=False,
        default=FindingStatus.OPEN,
        server_default=FindingStatus.OPEN.value,
        index=True,
    )
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    scan_job = relationship("ScanJob", back_populates="findings", foreign_keys=[scan_job_id])
    project = relationship("Project", foreign_keys=[project_id])
    last_seen_in_scan = relationship("ScanJob", foreign_keys=[last_seen_in_scan_id])


class ToolExecutionStatus(str, enum.Enum):
    """Tool execution status enumeration"""
    PENDING = "pending"  # Tool is planned but not yet started
    RUNNING = "running"  # Tool is currently executing
    COMPLETED = "completed"  # Tool finished successfully
    FAILED = "failed"  # Tool failed (non-zero exit, error, etc.)
    SKIPPED = "skipped"  # Tool was skipped (e.g., missing binary, target unreachable)
    TIMED_OUT = "timed_out"  # Tool execution timed out


class ToolResult(Base):
    """ToolResult model for storing raw tool output and execution status"""
    
    __tablename__ = "tool_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_job_id = Column(String(36), ForeignKey("scan_jobs.id"), nullable=False, index=True)
    
    # Tool run ID for idempotency (generated by runner, unique per scan)
    tool_run_id = Column(String(36), nullable=True, unique=False, index=True)  # Will have UNIQUE constraint on (scan_job_id, tool_run_id)
    
    # Tool information
    tool_name = Column(String(100), nullable=False, index=True)
    tool_version = Column(String(50), nullable=True)
    
    # Execution status (new field for lifecycle tracking)
    status = Column(
        SQLEnum(ToolExecutionStatus, name="tool_execution_status"),
        nullable=True,  # Nullable for backward compatibility with existing records
        default=None,
    )
    error_code = Column(String(50), nullable=True)  # Short error code: "timeout", "missing_binary", "target_unreachable", etc.
    
    # Results
    output = Column(Text, nullable=True)  # Raw tool output
    exit_code = Column(Integer, nullable=True)
    execution_time = Column(Float, nullable=True)  # Seconds
    timed_out = Column(Integer, nullable=False, default=0, server_default="0")  # Boolean: 0=False, 1=True (kept for backward compatibility)
    
    # Metadata
    command = Column(Text, nullable=True)  # Command that was executed
    error_message = Column(Text, nullable=True)  # User-safe error message
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)  # When tool execution started
    completed_at = Column(DateTime(timezone=True), nullable=True)  # When tool execution completed
    
    # Tool run tracking fields
    output_path = Column(String(512), nullable=True)  # Path to output file
    stdout_preview = Column(Text, nullable=True)  # First 1000 chars of stdout
    stderr_preview = Column(Text, nullable=True)  # First 1000 chars of stderr
    parsed_findings_count = Column(Integer, nullable=False, default=0, server_default="0")  # Number of findings parsed from output
    created_findings_count = Column(Integer, nullable=False, default=0, server_default="0")  # Number of findings actually created in DB
    targets_count = Column(Integer, nullable=False, default=0, server_default="0")  # Number of targets (URLs/params/requests) fed to tool
    meta = Column(JSON, nullable=True)  # Tool args, version, command details (JSON)
    duration_ms = Column(Integer, nullable=True)  # Duration in milliseconds (computed from execution_time)
    skip_reason = Column(String(100), nullable=True)  # e.g., no_injection_points, rate_limited, blocked
    raw_stdout = Column(Text, nullable=True)
    raw_stderr = Column(Text, nullable=True)
    
    # Relationships
    scan_job = relationship("ScanJob", back_populates="tool_results")
