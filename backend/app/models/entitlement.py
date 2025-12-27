"""
Entitlement model for plan/limit assignments (tenant or user scoped).
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class Entitlement(Base):
    __tablename__ = "entitlements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)  # nullable => tenant-wide
    plan_name = Column(String(50), nullable=False)
    limits_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

