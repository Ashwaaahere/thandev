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


def require_admin_user(current_user: User = Depends(require_authenticated_user)) -> User:
    """Ensure the current user is an admin."""
    if not getattr(current_user, "is_admin", False):
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

