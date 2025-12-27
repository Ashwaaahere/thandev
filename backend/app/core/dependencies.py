"""
Shared dependency helpers.
"""
from fastapi import Depends, HTTPException, status

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

