"""
Notifications API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime

from app.core.database import get_db
from app.core.tenant_utils import require_tenant, get_current_user
from app.models.notification import Notification
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.notification import NotificationListItem, NotificationListResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


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
    
    # If already read, just return it
    if notification.is_read:
        return NotificationListItem.model_validate(notification)
    
    # Mark as read
    notification.is_read = True
    notification.read_at = datetime.utcnow()
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
            Notification.read_at: datetime.utcnow()
        })
    )
    
    db.commit()
    
    return {
        "message": f"Marked {updated_count} notification(s) as read",
        "updated_count": updated_count
    }
