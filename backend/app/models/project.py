"""
Project model
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class Project(Base):
    """Project model representing a target to scan"""
    
    __tablename__ = "projects"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    target_url = Column(String(2048), nullable=False)
    root_domain = Column(String(255), nullable=True, index=True)  # registrable domain lock
    repo_url = Column(String(2048), nullable=True)
    description = Column(Text, nullable=True)
    
    # Relationships
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="projects")
    
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    tenant = relationship("Tenant", back_populates="projects")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    scan_jobs = relationship("ScanJob", back_populates="project", cascade="all, delete-orphan")
    repo_connections = relationship("RepoConnection", back_populates="project", cascade="all, delete-orphan")
    # Performance scans relationship - use noload to avoid querying if table doesn't exist
    # The table name mismatch (performance_scan_jobs vs performance_scans) causes issues
    # TODO: Fix table name mismatch or create proper migration
    performance_scans = relationship("PerformanceScan", back_populates="project", lazy="noload", cascade="save-update")






