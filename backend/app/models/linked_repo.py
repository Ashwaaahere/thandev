"""
LinkedRepo model: allowlist of CI-connected repos per project for code scan ingestion.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, UniqueConstraint, Index, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import os

from app.core.database import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./thandev.db")
_is_postgresql = DATABASE_URL.startswith("postgresql")
_JSON = JSONB if _is_postgresql else JSON


class LinkedRepo(Base):
    """Allowlist entry: project + provider + repo_full_name allowed to send code scans via OIDC."""

    __tablename__ = "linked_repos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(32), nullable=False)
    repo_full_name = Column(Text, nullable=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    allowed_refs = Column(_JSON, nullable=True)
    allowed_workflows = Column(_JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project", back_populates="linked_repos")

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "provider",
            "repo_full_name",
            name="uq_linked_repos_project_provider_repo",
        ),
        Index("idx_linked_repos_project_id", "project_id"),
        Index("idx_linked_repos_provider_repo", "provider", "repo_full_name"),
    )
