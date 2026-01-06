"""
Audit log model for tracking user actions
"""
from sqlalchemy import Column, String, DateTime, JSON, Text
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class AuditLog(Base):
    """Audit log model for tracking user actions and system events"""
    
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)  # User who performed the action
    tenant_id = Column(String(36), nullable=True, index=True)  # Tenant/org for the action
    action_type = Column(String(50), nullable=False, index=True)  # e.g., SCAN_STARTED, SCAN_COMPLETED, SCAN_FAILED
    target_type = Column(String(50), nullable=True)  # e.g., 'scan', 'project', 'finding'
    target_id = Column(String(36), nullable=True)  # ID of the target (scan_id, project_id, etc.)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    event_metadata = Column(JSON, nullable=True)  # Additional context (scan_level, error_message, etc.) - renamed from 'metadata' as it's reserved in SQLAlchemy
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)  # User agent string

