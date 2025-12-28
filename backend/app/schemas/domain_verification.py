"""
Pydantic schemas for domain verification
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DomainVerificationRequest(BaseModel):
    """Request to create/rotate a verification token."""
    force_rotate: bool = Field(default=False, description="If true, regenerate token even if pending.")


class DomainVerificationStatusResponse(BaseModel):
    """Domain verification status response."""
    id: str = Field(..., description="Verification record ID")
    project_id: str
    domain: str
    status: str
    token: str
    record_name: str
    record_value: str
    last_checked_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    last_error: Optional[str] = None


class DomainVerificationVerifyResponse(DomainVerificationStatusResponse):
    """Verification response (same shape as status)."""
    pass

