import uuid
import enum
from sqlalchemy import Column, String, Boolean, DateTime, Text, Index
from sqlalchemy.sql import func
from app.core.database import Base


class AllowedDomainScope(str, enum.Enum):
    GLOBAL = "global"
    TENANT = "tenant"


class AllowedDomain(Base):
    __tablename__ = "allowed_domains"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain = Column(String(255), nullable=False, index=True)
    scope = Column(String(50), nullable=False, default=AllowedDomainScope.GLOBAL.value, index=True)
    tenant_id = Column(String(36), nullable=True, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_by_admin_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_allowed_domains_domain_scope_tenant", "domain", "scope", "tenant_id"),
    )

