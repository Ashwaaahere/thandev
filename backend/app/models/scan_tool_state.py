"""
ScanToolState model for storing latest tool execution state snapshot
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, JSON, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import os

from app.core.database import Base

# Detect if we're using PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./thandev.db")
is_postgresql = DATABASE_URL.startswith("postgresql")

# Use JSONB for PostgreSQL, JSON for SQLite
if is_postgresql:
    JSONType = JSONB
else:
    JSONType = JSON


class ScanToolState(Base):
    """ScanToolState model for storing latest tool execution state per scan"""
    
    __tablename__ = "scan_tool_states"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String(36), ForeignKey("scan_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Tool identification
    tool = Column(String(50), nullable=False)  # httpx, nuclei, zap, katana, etc.
    phase = Column(String(50), nullable=False)  # prepare, enumerate, scan, correlate, finalize
    
    # Latest state
    stage = Column(String(100), nullable=False)  # queued, starting, running, parsing, uploading, completed, failed
    message = Column(Text, nullable=False)  # Latest status message
    progress = Column(Float, nullable=True)  # Optional progress percentage (0.0 to 1.0)
    meta = Column(JSONType, nullable=True)  # Additional metadata
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, index=True)
    
    # Relationships
    scan_job = relationship("ScanJob", back_populates="tool_states")
    
    __table_args__ = (
        UniqueConstraint("scan_id", "tool", "phase", name="uq_scan_tool_phase"),
        Index("idx_scan_tool_states_scan_id", "scan_id"),
        Index("idx_scan_tool_states_updated_at", "updated_at"),
    )

