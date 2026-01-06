from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class UserSummary(BaseModel):
    id: str
    email: str
    username: str
    is_admin: bool
    is_approved: bool
    tenant_id: Optional[str] = None


class TenantSummary(BaseModel):
    id: str
    name: str
    plan: str


class EntitlementRequest(BaseModel):
    tenant_id: str
    plan_name: str
    limits_json: Dict[str, Any] = Field(default_factory=dict)
    user_scoped: bool = Field(default=True, description="If false, applies to entire tenant")


class EntitlementResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: Optional[str] = None
    plan_name: str
    limits_json: Optional[Dict[str, Any]] = None


class AllowedDomainRequest(BaseModel):
    domain: str
    scope: str = "global"  # "global" or "tenant"
    tenant_id: Optional[str] = None
    enabled: bool = True
    notes: Optional[str] = None


class AllowedDomainResponse(BaseModel):
    id: str
    domain: str
    scope: str
    tenant_id: Optional[str] = None
    enabled: bool
    notes: Optional[str] = None
    created_by_admin_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

