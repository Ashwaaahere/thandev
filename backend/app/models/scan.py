"""
ScanJob model

Note: In development with SQLite, if you change the stack_info column type,
you may need to drop the DB file and let SQLAlchemy recreate the tables.

The stack_info column stores lightweight metadata about the target (URL, HTTP headers)
for AI planning purposes. It uses SQLAlchemy's JSON type, which automatically
serializes/deserializes Python dicts.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base


class ScanLevel(str, enum.Enum):
    """Scan level enumeration"""
    BASIC = "basic"
    PRO = "pro"
    ADVANCED = "advanced"


class ScanStatus(str, enum.Enum):
    """Scan job status enumeration"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIStatus(str, enum.Enum):
    """AI planner status enumeration"""
    IDLE = "idle"
    PLANNED = "planned"
    FAILED = "failed"


class ScanJob(Base):
    """ScanJob model representing a security scan execution"""
    
    __tablename__ = "scan_jobs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    scan_level = Column(SQLEnum(ScanLevel), nullable=False)
    status = Column(SQLEnum(ScanStatus), default=ScanStatus.PENDING, nullable=False, index=True)
    
    # Celery task tracking
    celery_task_id = Column(String(255), nullable=True, index=True)
    
    # Results summary (JSON field for flexibility)
    summary = Column(JSON, nullable=True)
    
    # Stack information for AI planning (lightweight metadata about target)
    # Stores: target_url, scan_level, and optionally HTTP response info (status_code, headers)
    # Note: If you change the stack_info column type in development on SQLite,
    # you may need to drop the DB file and let SQLAlchemy recreate the tables.
    stack_info = Column(JSON, nullable=True)
    
    # AI planner fields
    ai_plan = Column(JSON, nullable=True)  # Stores the AI-generated scan plan (next_tools, attack_paths)
    # Store as String to avoid enum validation issues; convert to/from AIStatus enum in application code
    ai_status = Column(String(20), nullable=True, default=lambda: AIStatus.IDLE.value)  # AI planner status
    
    # Error information
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    project = relationship("Project", back_populates="scan_jobs")
    findings = relationship("Finding", back_populates="scan_job", cascade="all, delete-orphan")
    tool_results = relationship("ToolResult", back_populates="scan_job", cascade="all, delete-orphan")




