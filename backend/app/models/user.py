"""
User model
"""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class User(Base):
    """User model for authentication and authorization"""
    
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("external_provider", "external_user_id", name="uq_users_external_identity"),
    )
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False, default="")
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_approved = Column(Boolean, default=True, nullable=False)  # default True for backward compatibility

    # External identity mapping (e.g., GitHub)
    external_provider = Column(String(50), nullable=True, index=True)
    external_user_id = Column(String(255), nullable=True, index=True)
    
    # Tenant relationship
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True)
    tenant = relationship("Tenant", back_populates="users")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")



