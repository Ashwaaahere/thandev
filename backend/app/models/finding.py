"""
Finding and ToolResult models
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum as SQLEnum, Float, Integer
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
    
    # Finding details
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(SQLEnum(Severity), nullable=False, index=True)
    
    # CVE/CWE information
    cve_id = Column(String(50), nullable=True, index=True)
    cwe_id = Column(String(50), nullable=True)
    cvss_score = Column(Float, nullable=True)
    
    # Location information
    url = Column(String(2048), nullable=True)
    path = Column(String(2048), nullable=True)
    line_number = Column(Integer, nullable=True)
    
    # Remediation
    recommendation = Column(Text, nullable=True)
    
    # Metadata
    tool_name = Column(String(100), nullable=True, index=True)
    raw_data = Column(Text, nullable=True)  # JSON string of raw finding data
    
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
    scan_job = relationship("ScanJob", back_populates="findings")


class ToolResult(Base):
    """ToolResult model for storing raw tool output"""
    
    __tablename__ = "tool_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_job_id = Column(String(36), ForeignKey("scan_jobs.id"), nullable=False, index=True)
    
    # Tool information
    tool_name = Column(String(100), nullable=False, index=True)
    tool_version = Column(String(50), nullable=True)
    
    # Results
    output = Column(Text, nullable=True)  # Raw tool output
    exit_code = Column(Integer, nullable=True)
    execution_time = Column(Float, nullable=True)  # Seconds
    timed_out = Column(Integer, nullable=False, default=0, server_default="0")  # Boolean: 0=False, 1=True
    
    # Metadata
    command = Column(Text, nullable=True)  # Command that was executed
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    scan_job = relationship("ScanJob", back_populates="tool_results")
