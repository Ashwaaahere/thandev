"""
ScanEvent model for storing real-time scan progress events
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, JSON, Float
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


class ScanEvent(Base):
    """ScanEvent model for tracking real-time scan progress"""
    
    __tablename__ = "scan_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String(36), ForeignKey("scan_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Event categorization
    phase = Column(String(50), nullable=False, index=True)  # prepare, enumerate, scan, correlate, finalize
    tool = Column(String(50), nullable=True, index=True)  # httpx, nuclei, zap, katana, etc.
    stage = Column(String(100), nullable=False)  # queued, starting, running, parsing, uploading, completed, failed
    
    # Event content
    message = Column(Text, nullable=False)  # Human-readable status message
    progress = Column(Float, nullable=True)  # Optional progress percentage (0.0 to 1.0)
    meta = Column(JSONType, nullable=True)  # Additional metadata (counts, current_url, etc.)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    scan_job = relationship("ScanJob", back_populates="events")
    
    __table_args__ = (
        Index("idx_scan_events_scan_phase", "scan_id", "phase"),
        Index("idx_scan_events_scan_tool", "scan_id", "tool"),
        Index("idx_scan_events_created_at", "created_at"),
    )

