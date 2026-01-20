"""
RepoConnection model for storing repository connections to projects
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, UniqueConstraint, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class RepoConnection(Base):
    """RepoConnection model linking repositories to projects"""
    
    __tablename__ = "repo_connections"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(Text, nullable=False)  # 'github'
    provider_repo_id = Column(Text, nullable=False)  # GitHub repo ID (numeric)
    full_name = Column(Text, nullable=False)  # 'org/repo'
    default_branch = Column(Text, nullable=True)  # 'main', 'master', etc.
    is_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="repo_connections")
    
    __table_args__ = (
        UniqueConstraint("project_id", "provider", "provider_repo_id", name="uq_repo_connection_project_provider_repo"),
        Index("idx_repo_connections_project_id", "project_id"),
    )
