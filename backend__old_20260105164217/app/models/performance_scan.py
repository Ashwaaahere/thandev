"""
PerformanceScan model for performance scanning
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base
from app.models.scan import ScanLevel


class PerformanceScanStatus(str, enum.Enum):
    """Performance scan status enumeration"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PerformanceScan(Base):
    """PerformanceScan model representing a performance scan execution"""
    
    __tablename__ = "performance_scans"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    target_url = Column(String(2048), nullable=False)
    scan_level = Column(SQLEnum(ScanLevel), nullable=False)
    status = Column(SQLEnum(PerformanceScanStatus), default=PerformanceScanStatus.QUEUED, nullable=False, index=True)
    
    # Performance metrics (JSON field)
    metrics = Column(JSON, nullable=True)
    
    # Error information
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    project = relationship("Project", back_populates="performance_scans", foreign_keys=[project_id])
    tenant = relationship("Tenant")
    owner = relationship("User")
