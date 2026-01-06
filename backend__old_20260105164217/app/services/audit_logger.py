"""
Audit logging service for tracking user actions and system events
"""
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def log_audit_event(
    db: Session,
    action_type: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    Log an audit event to the audit_logs table.
    
    Args:
        db: Database session
        action_type: Type of action (e.g., "SCAN_STARTED", "SCAN_COMPLETED", "SCAN_FAILED")
        user_id: User who performed the action
        tenant_id: Tenant/org for the action
        target_type: Type of target (e.g., "scan", "project", "finding")
        target_id: ID of the target (scan_id, project_id, etc.)
        metadata: Additional context (scan_level, error_message, etc.)
        ip_address: IP address of the request (optional)
        user_agent: User agent string (optional)
    """
    try:
        audit_log = AuditLog(
            user_id=user_id,
            tenant_id=tenant_id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            event_metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(audit_log)
        db.commit()
        logger.debug(f"Audit log created: {action_type} for {target_type}:{target_id}")
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}", exc_info=True)
        # Don't fail the request if audit logging fails
        db.rollback()

