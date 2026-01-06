"""
Tenant model for multi-tenancy and plan management
"""
from sqlalchemy import Column, String, DateTime, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base


class PlanTier(str, enum.Enum):
    """Subscription plan tiers"""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Tenant(Base):
    """Tenant model for multi-tenancy and subscription plans"""
    
    __tablename__ = "tenants"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    plan = Column(SQLEnum(PlanTier), default=PlanTier.FREE, nullable=False)
    
    # Plan limits
    max_projects = Column(Integer, default=3, nullable=False)
    max_scans_per_month = Column(Integer, default=10, nullable=False)
    max_concurrent_scans = Column(Integer, default=1, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    users = relationship("User", back_populates="tenant")
    projects = relationship("Project", back_populates="tenant", cascade="all, delete-orphan")



