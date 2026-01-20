"""
ScanArtifact model for storing dependency scanning artifacts
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, JSON
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


class ScanArtifact(Base):
    """ScanArtifact model for storing dependency scanning results"""
    
    __tablename__ = "scan_artifacts"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String(36), ForeignKey("scan_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Text, nullable=False, index=True)  # 'url_sca' or 'repo_sca'
    payload = Column(JSONType, nullable=False)  # JSON payload with scan results
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    scan_job = relationship("ScanJob", back_populates="artifacts")
    
    __table_args__ = (
        Index("idx_scan_artifacts_scan_id", "scan_id"),
        Index("idx_scan_artifacts_type", "type"),
    )
