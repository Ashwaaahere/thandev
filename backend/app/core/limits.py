"""
Centralized limits enforcement utilities
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.tenant import Tenant
from app.models.user import User
from app.models.entitlement import Entitlement
from app.core.plans import get_plan_limits, PlanLimits
from fastapi import HTTPException, status


def get_effective_limits(db: Session, tenant: Tenant, user: Optional[User] = None) -> Dict[str, Any]:
    """
    Get effective limits for a tenant/user, considering entitlements.
    
    Entitlements override plan limits. Returns merged limits dict.
    
    Args:
        db: Database session
        tenant: Tenant
        user: User (optional, for user-scoped entitlements)
    
    Returns:
        Dict with limit keys (max_projects, max_domains, max_scans_per_month, etc.)
    """
    # Start with plan limits
    plan_limits = get_plan_limits(tenant)
    effective = dict(plan_limits)
    
    # Check for entitlements (user-scoped first, then tenant-wide)
    ent = None
    if user:
        ent = (
            db.query(Entitlement)
            .filter(Entitlement.tenant_id == tenant.id, Entitlement.user_id == user.id)
            .order_by(Entitlement.created_at.desc())
            .first()
        )
    
    if not ent:
        # Check tenant-wide entitlement
        ent = (
            db.query(Entitlement)
            .filter(Entitlement.tenant_id == tenant.id, Entitlement.user_id.is_(None))
            .order_by(Entitlement.created_at.desc())
            .first()
        )
    
    if ent and ent.limits_json:
        # Merge entitlement limits over plan limits
        effective.update(ent.limits_json)
    
    return effective


def check_limit_exceeded(
    db: Session,
    tenant: Tenant,
    user: Optional[User],
    limit_key: str,
    current_count: int,
    limit_override: Optional[int] = None,
) -> None:
    """
    Check if a limit is exceeded and raise HTTPException if so.
    
    Args:
        db: Database session
        tenant: Tenant
        user: User (optional)
        limit_key: Key in limits dict (e.g., "max_projects", "max_domains")
        current_count: Current count
        limit_override: Optional override limit value (if None, uses effective limits)
    
    Raises:
        HTTPException: 403 if limit exceeded with structured error response
    """
    if limit_override is not None:
        limit = limit_override
    else:
        limits = get_effective_limits(db, tenant, user)
        limit = limits.get(limit_key)
        if limit is None:
            # No limit defined, allow
            return
    
    if current_count >= limit:
        # Return structured error response
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "LIMIT_EXCEEDED",
                "message": f"Limit exceeded: {limit_key} (current: {current_count}, limit: {limit})",
                "limit_key": limit_key,
                "current": current_count,
                "limit": limit,
            },
        )


class LimitExceededError(Exception):
    """Exception raised when a limit is exceeded"""
    def __init__(self, limit_key: str, current: int, limit: int, message: str = None):
        self.limit_key = limit_key
        self.current = current
        self.limit = limit
        self.message = message or f"Limit exceeded: {limit_key} (current: {current}, limit: {limit})"
        super().__init__(self.message)

