"""
Pydantic schemas for Brain service responses
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum


class SessionStatus(str, Enum):
    """Brain session status values"""
    RUNNING = "running"
    PLANNING = "planning"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STOPPING = "stopping"
    STOPPED = "stopped"


class BrainSessionResponse(BaseModel):
    """
    Pydantic model for brain session status response.
    
    Handles timezone-aware datetime parsing and validates brain service responses.
    """
    session_id: str
    status: SessionStatus
    scan_job_id: Optional[str] = None
    org_id: Optional[str] = None
    project_id: Optional[str] = None
    
    # Timestamps (ISO-8601 strings from brain, parsed to timezone-aware datetime)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    
    # Progress and metrics
    progress_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    current_step_count: Optional[int] = Field(None, ge=0)
    total_runtime_sec: Optional[float] = Field(None, ge=0.0)
    
    # Error information
    error_message: Optional[str] = None
    stop_reason_code: Optional[str] = None
    
    # Additional fields (allow extra for forward compatibility)
    model_config = ConfigDict(extra="allow")
    
    @field_validator('started_at', 'finished_at', 'last_updated', mode='before')
    @classmethod
    def parse_iso_datetime(cls, v: Any) -> Optional[datetime]:
        """
        Parse ISO-8601 datetime string to timezone-aware datetime.
        
        Handles:
        - "Z" suffix (UTC)
        - "+00:00" / "-05:00" timezone offsets
        - Invalid strings (returns None)
        """
        if v is None:
            return None
        
        if isinstance(v, datetime):
            # Already a datetime, ensure timezone-aware
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        
        if not isinstance(v, str):
            return None
        
        # Normalize "Z" to "+00:00"
        if v.endswith('Z'):
            v = v[:-1] + '+00:00'
        
        try:
            # Try parsing with timezone
            if '+' in v or (v.count('-') > 2 and ':' in v):
                # Has timezone offset
                dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
            else:
                # No timezone, assume UTC
                dt = datetime.fromisoformat(v)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, AttributeError):
            # Invalid format, return None (will be handled by Optional)
            return None


def parse_iso_datetime_safe(iso_str: Optional[str]) -> Optional[datetime]:
    """
    Safe ISO-8601 datetime parser helper.
    
    Args:
        iso_str: ISO-8601 datetime string (may include "Z" suffix)
        
    Returns:
        timezone-aware datetime or None if invalid
    """
    if not iso_str:
        return None
    
    if isinstance(iso_str, datetime):
        if iso_str.tzinfo is None:
            return iso_str.replace(tzinfo=timezone.utc)
        return iso_str
    
    # Normalize "Z" to "+00:00"
    if iso_str.endswith('Z'):
        iso_str = iso_str[:-1] + '+00:00'
    
    try:
        if '+' in iso_str or (iso_str.count('-') > 2 and ':' in iso_str):
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None

