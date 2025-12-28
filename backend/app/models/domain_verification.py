"""
Domain verification model
"""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Text,
    Index,
)
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base


class DomainVerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


class DomainVerification(Base):
    __tablename__ = "domain_verifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)  # registrable domain (eTLD+1)
    # Use native PostgreSQL enum - SQLAlchemy will use enum.value automatically when we pass .value
    status = Column(SQLEnum(DomainVerificationStatus, name="domain_verification_status", native_enum=True, create_constraint=True), nullable=False)
    token = Column(String(255), nullable=False)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# Composite index for quick lookup by project+domain
Index("ix_domain_verifications_project_domain", DomainVerification.project_id, DomainVerification.domain)

