"""
Shared dependency helpers.
"""
from fastapi import Depends, HTTPException, status, Header

from app.core.tenant_utils import get_current_user
from app.models.user import User


def require_authenticated_user(current_user: User = Depends(get_current_user)) -> User:
    """Ensure a user is present; does not check approval/admin."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return current_user


def require_approved_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Ensure the current user is approved for private beta access.

    Admin users are always allowed. Non-admin users must have is_approved = True.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    is_admin = bool(getattr(current_user, "is_admin", False))
    is_approved = getattr(current_user, "is_approved", True)

    if is_admin:
        # Admins bypass approval to avoid lockout during bootstrap.
        return current_user

    if is_approved is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Private beta: request access",
        )

    return current_user


def require_admin_user(
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
) -> User:
    """Ensure the current user is an admin."""
    is_admin = getattr(current_user, "is_admin", False)
    
    # Fallback: Check if user is a superadmin by external_user_id (to handle cases where admin flag hasn't been set yet)
    if not is_admin:
        from app.core.config import settings
        external_provider = getattr(current_user, "external_provider", None)
        external_user_id = getattr(current_user, "external_user_id", None)
        if external_provider and external_user_id:
            is_superadmin = (external_provider.lower(), external_user_id) in settings.superadmin_external_ids_set
            if is_superadmin:
                # Update the user's admin flag in the database
                current_user.is_admin = True
                current_user.is_approved = True
                db.commit()
                db.refresh(current_user)
                return current_user
    
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_runner_service_auth(authorization: str = Header(None, alias="Authorization")) -> None:
    """
    Require service authentication for runner service endpoints.
    
    Validates Bearer token matches RUNNER_API_TOKEN.
    If RUNNER_API_TOKEN is not configured, logs warning but allows (for development).
    In production, RUNNER_API_TOKEN should always be set.
    """
    from app.core.config import settings
    import hmac
    import logging
    
    logger = logging.getLogger(__name__)
    
    if not settings.RUNNER_API_TOKEN:
        logger.warning(
            "RUNNER_API_TOKEN not configured - allowing unauthenticated request. "
            "This should only happen in development. Set RUNNER_API_TOKEN in production!"
        )
        return  # Allow in development if token not configured
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.replace("Bearer ", "").strip()
    
    # Use hmac.compare_digest for constant-time comparison (prevents timing attacks)
    if not hmac.compare_digest(token, settings.RUNNER_API_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
            headers={"WWW-Authenticate": "Bearer"},
        )

