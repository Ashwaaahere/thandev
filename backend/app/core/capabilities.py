"""
Capability checks for dependency scanning features
"""
from typing import List
from sqlalchemy.orm import Session
from app.models.tenant import Tenant
from app.models.user import User
from app.core.limits import get_effective_limits
from fastapi import HTTPException, status


def check_capability(
    db: Session,
    tenant: Tenant,
    user: User,
    capability: str,
) -> None:
    """
    Check if user/tenant has a specific capability.
    
    Capabilities:
    - 'url_sca': PRO plan and above
    - 'repo_sca': ADVANCED plan only
    
    Raises HTTPException 403 if capability not available.
    """
    limits = get_effective_limits(db, tenant, user)
    allowed_levels = limits.get("allowed_scan_levels", ["basic"])
    
    if capability == "url_sca":
        # PRO plan and above can run url_sca
        if "pro" not in allowed_levels and "advanced" not in allowed_levels:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="URL dependency scanning requires PRO plan or higher. Upgrade to access this feature.",
            )
    elif capability == "repo_sca":
        # Only ADVANCED plan can run repo_sca
        if "advanced" not in allowed_levels:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Repository dependency scanning requires ADVANCED plan. Upgrade to access this feature.",
            )
    else:
        raise ValueError(f"Unknown capability: {capability}")


def has_capability(
    db: Session,
    tenant: Tenant,
    user: User,
    capability: str,
) -> bool:
    """
    Check if user/tenant has a specific capability (returns bool, doesn't raise).
    """
    try:
        check_capability(db, tenant, user, capability)
        return True
    except HTTPException:
        return False
