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
    token: str = Field(default="", description="Verification token (empty for allowlisted domains)")
    record_name: str = Field(default="", description="DNS record name (empty for allowlisted domains)")
    record_value: str = Field(default="", description="DNS record value (empty for allowlisted domains)")
    last_checked_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    last_error: Optional[str] = None
    method: Optional[str] = Field(None, description="Verification method: 'dns' or 'allowlist'")


class DomainVerificationVerifyResponse(DomainVerificationStatusResponse):
    """Verification response (same shape as status)."""
    pass

