"""
Users API router
Endpoints for creating and managing users
"""
import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.tenant_utils import validate_external_id
from app.core.config import settings
from app.models.user import User
from app.models.tenant import Tenant
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    """Schema for creating a user"""
    id: Optional[str] = None  # Optional: if not provided, will be generated as UUID
    email: str
    username: str
    tenant_id: str  # Required: user must belong to a tenant
    hashed_password: Optional[str] = None  # Optional: for OAuth users, can be empty
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Basic email validation"""
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError('Invalid email format')
        return v


class UserResponse(BaseModel):
    """Schema for user response"""
    id: str
    email: str
    username: str
    tenant_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    x_thandev_admin_token: Optional[str] = Header(None, alias="X-Thandev-Admin-Token"),
):
    """
    Create a new user.
    
    For local/dev/test: No authentication required.
    For production: Requires X-Thandev-Admin-Token header (set via THANDEV_ADMIN_TOKEN env var).
    
    Args:
        payload: User creation data (id optional, will be generated if not provided)
        x_thandev_admin_token: Admin token for production (optional in dev/test)
        
    Returns:
        Created user information
    """
    env_lower = settings.ENVIRONMENT.strip().lower()
    is_production = env_lower == "production"
    
    # In production, require admin token
    if is_production:
        admin_token = os.getenv("THANDEV_ADMIN_TOKEN", "")
        if not x_thandev_admin_token or x_thandev_admin_token != admin_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin token required for user creation in production"
            )
    
    # Validate tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == payload.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant with id '{payload.tenant_id}' not found. Create tenant first via POST /api/tenants"
        )
    
    # Validate or generate user ID
    if payload.id:
        user_id = validate_external_id(payload.id, "user_id")
    else:
        user_id = str(uuid.uuid4())
    
    # Check if user already exists
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with id '{user_id}' already exists"
        )
    
    # Check if email/username already exists
    existing_email = db.query(User).filter(User.email == payload.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{payload.email}' already exists"
        )
    
    existing_username = db.query(User).filter(User.username == payload.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with username '{payload.username}' already exists"
        )
    
    # Create user
    user = User(
        id=user_id,
        email=payload.email,
        username=payload.username,
        tenant_id=payload.tenant_id,
        hashed_password=payload.hashed_password or "",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return UserResponse.model_validate(user)

