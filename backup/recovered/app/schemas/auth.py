from pydantic import BaseModel, EmailStr
from typing import Optional


class BootstrapRequest(BaseModel):
    provider: str
    external_user_id: str
    username: str
    email: EmailStr
    name: Optional[str] = None


class BootstrapResponse(BaseModel):
    user_id: str
    tenant_id: str
    tenant_plan: str
    created: bool
    is_admin: bool | None = None
    is_approved: bool | None = None


