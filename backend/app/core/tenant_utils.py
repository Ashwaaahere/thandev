"""
Tenant utility functions
Helper functions for working with tenants and users

Multi-tenant Architecture:
- Uses header-based authentication: X-Thandev-User-Id and X-Thandev-Tenant-Id
- For now, uses 1:1 mapping: tenant_id = user_id (temporary until org accounts are added)
- Future: Will support multiple users per tenant (org accounts)
- All authenticated routes require both headers via require_tenant() and get_current_user()
"""
import uuid
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import Optional
from app.models.tenant import Tenant
from app.models.user import User
from app.core.database import get_db
from app.core.config import settings

# Placeholder tenant ID used as fallback (for anonymous/marketing pages only)
PLACEHOLDER_TENANT_ID = "placeholder-tenant-id"


def validate_external_id(id_str: Optional[str], field_name: str) -> str:
    """
    Validate that an external ID (from headers) is a valid UUID.
    
    Args:
        id_str: The ID string to validate (can be None)
        field_name: Name of the field for error messages (e.g., "tenant_id", "user_id")
        
    Returns:
        The validated UUID string (normalized)
        
    Raises:
        HTTPException: 400 if ID is not a valid UUID
    """
    if not id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}. Must be a valid UUID."
        )
    
    try:
        # Parse and normalize UUID (removes any whitespace, validates format)
        uuid_obj = uuid.UUID(id_str.strip())
        return str(uuid_obj)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}. Must be a valid UUID (36 characters). Received: {id_str[:50]}"
        )


def get_current_tenant(
    db: Session,
    x_thandev_tenant_id: Optional[str] = Header(None, alias="X-Thandev-Tenant-Id"),
    x_thandev_user_id: Optional[str] = Header(None, alias="X-Thandev-User-Id"),
) -> Tenant:
    """
    Get the current tenant for the request.
    
    Reads tenant ID from X-Thandev-Tenant-Id header.
    If header is missing, falls back to placeholder tenant (for anonymous routes).
    If tenant doesn't exist, creates it (on-demand creation) ONLY if ID is valid UUID.
    
    Args:
        db: Database session
        x_thandev_tenant_id: Tenant ID from request header
        x_thandev_user_id: User ID from request header (used for 1:1 mapping if tenant_id missing)
        
    Returns:
        Tenant instance (creates one if missing and ID is valid)
    """
    # For now, use user_id as tenant_id if tenant_id header is missing (1:1 mapping)
    # Future: tenant_id will be required and may differ from user_id (org accounts)
    tenant_id = x_thandev_tenant_id or (x_thandev_user_id if x_thandev_user_id else PLACEHOLDER_TENANT_ID)
    
    # Validate tenant_id if it's not the placeholder (placeholder is allowed for anonymous routes)
    if tenant_id != PLACEHOLDER_TENANT_ID:
        tenant_id = validate_external_id(tenant_id, "tenant_id")
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    
    if not tenant:
        # Check if auto-creation is enabled via config
        if not settings.TENANT_AUTOCREATE_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Tenant with id '{tenant_id}' not found. "
                    "Create it via POST /api/tenants or run seed script. "
                    "Auto-creation is disabled."
                )
            )
        
        # Create tenant if missing (auto-creation enabled)
        # Use PRO tier (maps to "team" plan) for development so we don't hit limits immediately
        from app.models.tenant import PlanTier
        tenant = Tenant(
            id=tenant_id,
            name=f"Tenant {tenant_id[:8]}",
            plan=PlanTier.PRO,  # PRO tier maps to "team" plan in plans.py
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    
    return tenant


def ensure_user_and_tenant(
    db: Session,
    user_id: str,
    tenant_id: str
) -> tuple[User, Tenant]:
    """
    Ensure user and tenant exist, creating them if missing.
    
    Ensures user.tenant_id == tenant.id (links user to tenant).
    For now, uses 1:1 mapping: tenant_id = user_id (temporary until org accounts).
    
    Args:
        db: Database session
        user_id: User ID from header (must be valid UUID)
        tenant_id: Tenant ID from header (must be valid UUID, should equal user_id for now)
        
    Returns:
        Tuple of (User, Tenant) instances
    """
    # Validate IDs before any DB operations
    user_id = validate_external_id(user_id, "user_id")
    tenant_id = validate_external_id(tenant_id, "tenant_id")
    
    # Ensure tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        if not settings.TENANT_AUTOCREATE_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Tenant with id '{tenant_id}' not found. "
                    "Create it via POST /api/tenants or run seed script. "
                    "Auto-creation is disabled."
                )
            )
        from app.models.tenant import PlanTier
        tenant = Tenant(
            id=tenant_id,
            name=f"Tenant {tenant_id[:8]}",
            plan=PlanTier.PRO,  # PRO tier maps to "team" plan
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    
    # Ensure user exists and is linked to tenant
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        if not settings.TENANT_AUTOCREATE_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"User with id '{user_id}' not found. "
                    "Create it via POST /api/users or run seed script. "
                    "Auto-creation is disabled."
                )
            )
        user = User(
            id=user_id,
            email=f"user-{user_id[:8]}@example.com",  # Placeholder email (will be updated from GitHub profile)
            username=f"user-{user_id[:8]}",
            hashed_password="",  # Not used with GitHub OAuth
            tenant_id=tenant_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.tenant_id != tenant_id:
        # Update user's tenant if it changed (shouldn't happen with 1:1 mapping, but be safe)
        user.tenant_id = tenant_id
        db.commit()
        db.refresh(user)
    
    return user, tenant


def get_current_user(
    db: Session = Depends(get_db),
    x_thandev_user_id: Optional[str] = Header(None, alias="X-Thandev-User-Id"),
    x_thandev_tenant_id: Optional[str] = Header(None, alias="X-Thandev-Tenant-Id"),
) -> Optional[User]:
    """
    Get the current user for the request.
    
    Reads user ID and tenant ID from headers.
    Creates user/tenant if missing (on-demand creation for new GitHub OAuth users).
    For now, uses 1:1 mapping: tenant_id = user_id.
    
    Args:
        db: Database session
        x_thandev_user_id: User ID from request header
        x_thandev_tenant_id: Tenant ID from request header (should equal user_id for now)
        
    Returns:
        User instance or None if user_id header is missing
    """
    if not x_thandev_user_id:
        return None
    
    # Validate user_id before using it
    user_id = validate_external_id(x_thandev_user_id, "user_id")
    
    # For now, use user_id as tenant_id (1:1 mapping)
    # Future: tenant_id will come from header and may differ from user_id (org accounts)
    tenant_id = x_thandev_tenant_id or user_id
    if tenant_id != user_id:
        tenant_id = validate_external_id(tenant_id, "tenant_id")
    
    user, _ = ensure_user_and_tenant(db, user_id, tenant_id)
    return user


def require_tenant(
    db: Session = Depends(get_db),
    x_thandev_tenant_id: Optional[str] = Header(None, alias="X-Thandev-Tenant-Id"),
    x_thandev_user_id: Optional[str] = Header(None, alias="X-Thandev-User-Id"),
) -> Tenant:
    """
    Require tenant ID or user ID header (for authenticated routes).
    
    Raises 401 if both headers are missing.
    For now, accepts either tenant_id or user_id (uses 1:1 mapping).
    Future: Will require both headers for org accounts.
    
    Args:
        db: Database session
        x_thandev_tenant_id: Tenant ID from request header
        x_thandev_user_id: User ID from request header (used as fallback for tenant_id)
        
    Returns:
        Tenant instance
        
    Raises:
        HTTPException: If both tenant ID and user ID headers are missing
    """
    if not x_thandev_tenant_id and not x_thandev_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-Tenant-Id or X-Thandev-User-Id header is required"
        )
    
    return get_current_tenant(db, x_thandev_tenant_id, x_thandev_user_id)
