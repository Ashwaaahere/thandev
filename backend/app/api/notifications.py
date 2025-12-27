"""
Notifications API endpoints
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import ProgrammingError
from typing import List
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.tenant_utils import require_tenant, get_current_user
from app.core.dependencies import require_approved_user
from app.core.config import settings
from app.models.notification import Notification
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.notification import NotificationListItem, NotificationListResponse

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_approved_user)],
)
logger = logging.getLogger(__name__)


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of notifications to return"),
    offset: int = Query(0, ge=0, description="Number of notifications to skip"),
    unread_only: bool = Query(False, description="Filter to only unread notifications"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get notifications for the current user.
    
    Requires X-Thandev-Tenant-Id and X-Thandev-User-Id headers.
    Returns notifications scoped to the current tenant and user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Defensive handling: if notifications table doesn't exist, return empty list in dev/test
    # In production, this should be a proper error (but still graceful)
    try:
        # Build query with tenant and user filtering
        query = db.query(Notification).filter(
            Notification.tenant_id == tenant.id,
            Notification.owner_id == current_user.id
        )
        
        # Filter by read status if requested
        if unread_only:
            query = query.filter(Notification.is_read == False)
        
        # Get total count before pagination
        total = query.count()
        
        # Order by created_at descending and apply pagination
        notifications = (
            query
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        items = [NotificationListItem.model_validate(n) for n in notifications]
        
        return NotificationListResponse(items=items, total=total)
    
    except ProgrammingError as e:
        # Check if error is about missing table
        error_str = str(e).lower()
        if 'notifications' in error_str and ('does not exist' in error_str or 'no such table' in error_str):
            env_lower = settings.ENVIRONMENT.strip().lower()
            is_dev = env_lower in ("local", "dev", "test", "development")
            
            if is_dev:
                logger.warning(
                    f"Notifications table not found in {env_lower} environment. "
                    "Returning empty list. Run 'alembic upgrade head' to create the table."
                )
                return NotificationListResponse(items=[], total=0)
            else:
                # In production, return 503 with clear message (no stack trace leak)
                logger.error(f"Notifications table missing in production: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Notifications service temporarily unavailable. Please contact support."
                )
        else:
            # Re-raise other programming errors
            raise


@router.post("/{notification_id}/read", response_model=NotificationListItem)
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Mark a notification as read.
    
    Requires X-Thandev-Tenant-Id and X-Thandev-User-Id headers.
    Only allows marking notifications owned by the current user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Defensive handling for missing table
    try:
        # Load notification with tenant and user checks
        notification = (
            db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.tenant_id == tenant.id,
                Notification.owner_id == current_user.id
            )
            .first()
        )
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification with id '{notification_id}' not found"
            )
    
    except ProgrammingError as e:
        # Check if error is about missing table
        error_str = str(e).lower()
        if 'notifications' in error_str and ('does not exist' in error_str or 'no such table' in error_str):
            env_lower = settings.ENVIRONMENT.strip().lower()
            is_dev = env_lower in ("local", "dev", "test", "development")
            
            if is_dev:
                logger.warning(
                    f"Notifications table not found in {env_lower} environment. "
                    "Run 'alembic upgrade head' to create the table."
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Notification with id '{notification_id}' not found (table not available)"
                )
            else:
                logger.error(f"Notifications table missing in production: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Notifications service temporarily unavailable. Please contact support."
                )
        else:
            # Re-raise other programming errors
            raise
    
    # If already read, just return it
    if notification.is_read:
        return NotificationListItem.model_validate(notification)
    
    # Mark as read
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notification)
    
    return NotificationListItem.model_validate(notification)


@router.post("/read-all", response_model=dict)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Mark all unread notifications as read for the current user.
    
    Requires X-Thandev-Tenant-Id and X-Thandev-User-Id headers.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Defensive handling for missing table
    try:
        # Update all unread notifications for this tenant/user
        updated_count = (
            db.query(Notification)
            .filter(
                Notification.tenant_id == tenant.id,
                Notification.owner_id == current_user.id,
                Notification.is_read == False
            )
            .update({
                Notification.is_read: True,
                Notification.read_at: datetime.now(timezone.utc)
            })
        )
        
        db.commit()
        
        return {
            "message": f"Marked {updated_count} notification(s) as read",
            "updated_count": updated_count
        }
    
    except ProgrammingError as e:
        # Check if error is about missing table
        error_str = str(e).lower()
        if 'notifications' in error_str and ('does not exist' in error_str or 'no such table' in error_str):
            env_lower = settings.ENVIRONMENT.strip().lower()
            is_dev = env_lower in ("local", "dev", "test", "development")
            
            if is_dev:
                logger.warning(
                    f"Notifications table not found in {env_lower} environment. "
                    "Returning empty result. Run 'alembic upgrade head' to create the table."
                )
                return {
                    "message": "Marked 0 notification(s) as read (table not found)",
                    "updated_count": 0
                }
            else:
                logger.error(f"Notifications table missing in production: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Notifications service temporarily unavailable. Please contact support."
                )
        else:
            # Re-raise other programming errors
            raise
