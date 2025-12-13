"""
Pydantic schemas for Notification API
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class NotificationBase(BaseModel):
    """Base notification schema"""
    id: str
    type: str
    title: str
    message: Optional[str] = None
    link_url: Optional[str] = None
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class NotificationListItem(NotificationBase):
    """Schema for notification list item"""
    pass


class NotificationListResponse(BaseModel):
    """Schema for notification list response"""
    items: list[NotificationListItem]
    total: int
