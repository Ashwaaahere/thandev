"""
Notification model
Represents user notifications for events like scan completion
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class Notification(Base):
    """Notification model representing user notifications"""
    
    __tablename__ = "notifications"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Multi-tenant scoping
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Notification content
    type = Column(String(50), nullable=False, index=True)  # e.g., "scan_completed"
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    link_url = Column(String(512), nullable=True)  # e.g., "/projects/{id}/scans/{id}"
    
    # Read status
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant")
    owner = relationship("User")
    
    # Composite index for efficient queries
    __table_args__ = (
        Index('idx_notifications_tenant_owner_read_created', 'tenant_id', 'owner_id', 'is_read', 'created_at'),
    )
