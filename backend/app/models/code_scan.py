"""
CodeScan model: records for CI-ingested code scan runs (Semgrep, Gitleaks, SCA, etc.).
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import os

from app.core.database import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./thandev.db")
_is_postgresql = DATABASE_URL.startswith("postgresql")
_JSON = JSONB if _is_postgresql else JSON


class CodeScan(Base):
    """A single code scan run ingested from CI (GitHub Actions, etc.)."""

    __tablename__ = "code_scans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_type = Column(String(16), nullable=False, server_default="code")
    provider = Column(String(32), nullable=False)
    repo_full_name = Column(Text, nullable=False)
    ref = Column(Text, nullable=True)
    sha = Column(Text, nullable=True)
    run_id = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, server_default="running")
    summary_json = Column(_JSON, nullable=True)
    meta_json = Column(_JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="code_scans")

    __table_args__ = (
        Index("idx_code_scans_project_id", "project_id"),
        Index("idx_code_scans_provider_repo", "provider", "repo_full_name"),
        Index("idx_code_scans_provider_repo_run", "provider", "repo_full_name", "run_id"),
    )
