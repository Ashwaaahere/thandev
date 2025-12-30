"""
ScanJob model

Note: In development with SQLite, if you change the stack_info column type,
you may need to drop the DB file and let SQLAlchemy recreate the tables.

The stack_info column stores lightweight metadata about the target (URL, HTTP headers)
for AI planning purposes. It uses SQLAlchemy's JSON type, which automatically
serializes/deserializes Python dicts.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text, JSON, TypeDecorator
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects import postgresql
import uuid
import enum
import os

from app.core.database import Base

# Detect if we're using PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./thandev.db")
is_postgresql = DATABASE_URL.startswith("postgresql")


class ScanLevel(str, enum.Enum):
    """Scan level enumeration
    
    Values are lowercase strings to match PostgreSQL enum type 'scanlevel'.
    CRITICAL: When persisting to PostgreSQL, SQLAlchemy must use enum VALUES ('basic', 'pro', 'advanced'),
    not enum NAMES ('BASIC', 'PRO', 'ADVANCED'). This is enforced via TypeDecorator.
    """
    BASIC = "basic"
    PRO = "pro"
    ADVANCED = "advanced"


class ScanLevelType(TypeDecorator):
    """
    TypeDecorator that ensures ScanLevel enum is always stored as its VALUE (lowercase string)
    in the database, never as the enum NAME (uppercase).
    
    CRITICAL: This prevents PostgreSQL errors like "invalid input value for enum scanlevel: 'BASIC'"
    by explicitly extracting the .value property from ScanLevel enum instances before binding to DB.
    
    The process_bind_param() method ensures that when SQLAlchemy binds the parameter,
    it sends the lowercase enum VALUE ('basic', 'pro', 'advanced') to the database,
    not the uppercase enum NAME ('BASIC', 'PRO', 'ADVANCED').
    """
    # Use String as base type - PostgreSQL enum will be handled via process_bind_param
    impl = String(20)
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """
        Convert Python enum to database value (lowercase string).
        This is called when SQLAlchemy binds the parameter to the SQL statement.
        
        CRITICAL: Always extract .value from ScanLevel enum to ensure lowercase string is sent to DB.
        This is the key fix - without this, SQLAlchemy might send 'BASIC' instead of 'basic'.
        """
        if value is None:
            return None
        
        # If it's already a ScanLevel enum, extract its VALUE (not name)
        # This is the critical fix: value.value returns 'basic', not 'BASIC'
        if isinstance(value, ScanLevel):
            return value.value  # Returns 'basic', 'pro', or 'advanced' (lowercase)
        
        # If it's a string, validate it's a valid lowercase value
        if isinstance(value, str):
            normalized = value.lower().strip()
            if normalized not in {'basic', 'pro', 'advanced'}:
                raise ValueError(
                    f"Invalid scan_level value: '{value}'. "
                    f"Must be one of: 'basic', 'pro', 'advanced'"
                )
            return normalized
        
        # Fallback: convert to string and normalize
        value_str = str(value).lower().strip()
        if value_str not in {'basic', 'pro', 'advanced'}:
            raise ValueError(f"Invalid scan_level value: {value}")
        return value_str
    
    def process_result_value(self, value, dialect):
        """
        Convert database value (string) to Python enum.
        This is called when SQLAlchemy reads a value from the database.
        """
        if value is None:
            return None
        
        # If it's already a ScanLevel enum, return as-is
        if isinstance(value, ScanLevel):
            return value
        
        # Convert string from database to ScanLevel enum
        value_str = value.lower().strip() if isinstance(value, str) else str(value).lower().strip()
        enum_map = {
            'basic': ScanLevel.BASIC,
            'pro': ScanLevel.PRO,
            'advanced': ScanLevel.ADVANCED,
        }
        
        if value_str not in enum_map:
            raise ValueError(
                f"Invalid scan_level value from database: '{value}'. "
                f"Expected one of: 'basic', 'pro', 'advanced'"
            )
        
        return enum_map[value_str]
    
    def load_dialect_impl(self, dialect):
        """Return the appropriate SQL type for the database dialect"""
        if dialect.name == 'postgresql':
            # For PostgreSQL, use the native enum type (already exists in database)
            return postgresql.ENUM(
                'basic', 'pro', 'advanced',
                name='scanlevel',
                create_type=False,  # Type already exists, don't create it
            )
        else:
            # For SQLite and other databases, use String
            return String(20)


class ScanStatus(str, enum.Enum):
    """Scan job status enumeration"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALLED = "stalled"  # Scan running too long without progress (brain unreachable or no updates)


class AIStatus(str, enum.Enum):
    """AI planner status enumeration"""
    IDLE = "idle"
    PLANNED = "planned"
    FAILED = "failed"


class ScanJob(Base):
    """ScanJob model representing a security scan execution"""
    
    __tablename__ = "scan_jobs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True, index=True)  # nullable=True to support migration from old schema
    # CRITICAL: Use ScanLevelType TypeDecorator to ensure enum VALUES are persisted, not enum NAMES
    # This prevents PostgreSQL errors like "invalid input value for enum scanlevel: 'BASIC'"
    # The TypeDecorator.process_bind_param() method explicitly extracts .value from ScanLevel enum
    scan_level = Column(ScanLevelType(), nullable=False)
    # Status is stored as String(20) in the database, not as an enum type
    # SQLAlchemy will automatically use enum values for str, enum.Enum
    status = Column(SQLEnum(ScanStatus), default=ScanStatus.PENDING, nullable=False, index=True)
    
    # Celery task tracking
    celery_task_id = Column(String(255), nullable=True, index=True)
    
    # PR-4E: Brain session tracking
    brain_session_id = Column(String(36), nullable=True, index=True)
    
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
    
    # Completion timestamps - both columns exist for backward/forward compatibility
    # Migration 0024 ensures both columns exist and are kept in sync
    # Use completed_at in application code (preferred), but finished_at is available for compatibility
    finished_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    def set_completion_time(self, completion_time):
        """
        Set completion time on both columns to keep them in sync.
        Use this method instead of setting completed_at or finished_at directly.
        """
        self.finished_at = completion_time
        self.completed_at = completion_time
    
    @property
    def completion_time(self):
        """
        Get the effective completion time from either column.
        Prefers completed_at, falls back to finished_at.
        """
        return self.completed_at if self.completed_at is not None else self.finished_at
    
    # Relationships
    project = relationship("Project", back_populates="scan_jobs")
    # Specify primaryjoin explicitly because Finding has two FKs to scan_jobs (scan_job_id and last_seen_in_scan_id)
    # This tells SQLAlchemy to use scan_job_id for the findings relationship
    findings = relationship(
        "Finding", 
        back_populates="scan_job", 
        cascade="all, delete-orphan",
        primaryjoin="ScanJob.id == Finding.scan_job_id"
    )
    tool_results = relationship("ToolResult", back_populates="scan_job", cascade="all, delete-orphan")




