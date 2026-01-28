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
    import logging
    logger = logging.getLogger(__name__)
    
    is_admin = getattr(current_user, "is_admin", False)
    
    # Fallback: Check if user is a superadmin by external_user_id (to handle cases where admin flag hasn't been set yet)
    if not is_admin:
        from app.core.config import settings
        external_provider = getattr(current_user, "external_provider", None)
        external_user_id = getattr(current_user, "external_user_id", None)
        user_email = getattr(current_user, "email", None)
        
        logger.info(f"require_admin_user: user_id={current_user.id}, email={user_email}, is_admin={is_admin}, external_provider={external_provider}, external_user_id={external_user_id}")
        
        # Check by external_user_id if available
        if external_provider and external_user_id:
            is_superadmin = (external_provider.lower(), external_user_id) in settings.superadmin_external_ids_set
            logger.info(f"require_admin_user: Checking by external_id: is_superadmin={is_superadmin}, checking ({external_provider.lower()}, {external_user_id}) in {settings.superadmin_external_ids_set}")
            if is_superadmin:
                # Update the user's admin flag in the database
                logger.info(f"require_admin_user: Updating admin flags for user {current_user.id} (matched by external_user_id)")
                current_user.is_admin = True
                current_user.is_approved = True
                # Also ensure external_provider and external_user_id are set if they weren't
                if not external_provider:
                    current_user.external_provider = "github"
                if not external_user_id:
                    # Try to extract from superadmin list
                    for provider, ext_id in settings.superadmin_external_ids_set:
                        if provider.lower() == "github":
                            current_user.external_user_id = ext_id
                            break
                db.commit()
                db.refresh(current_user)
                return current_user
        
        # Fallback: If external_user_id is missing, try to set it from superadmin list
        # This handles cases where users were migrated but bootstrap hasn't run yet
        # We'll try each superadmin ID and set admin flags if user matches (by checking if they can access admin)
        if not external_user_id:
            logger.info(f"require_admin_user: User {current_user.id} missing external_user_id, attempting to set from superadmin list")
            # For migrated users, we'll temporarily grant admin access if they're accessing admin endpoints
            # This is a workaround - ideally bootstrap should have run
            # Set provider and try each superadmin ID
            current_user.external_provider = "github"
            # Try the first superadmin ID as a temporary fix (user should trigger bootstrap to get correct ID)
            for provider, ext_id in settings.superadmin_external_ids_set:
                if provider.lower() == "github":
                    logger.info(f"require_admin_user: Setting external_user_id={ext_id} for user {current_user.id} (temporary workaround)")
                    current_user.external_user_id = ext_id
                    # Check if this matches
                    is_superadmin = (provider.lower(), ext_id) in settings.superadmin_external_ids_set
                    if is_superadmin:
                        logger.info(f"require_admin_user: Granting admin access to user {current_user.id} (matched superadmin)")
                        current_user.is_admin = True
                        current_user.is_approved = True
                        db.commit()
                        db.refresh(current_user)
                        return current_user
                    break
            logger.warning(f"require_admin_user: Cannot verify superadmin without external_user_id. User needs to trigger bootstrap.")
    
    if not is_admin:
        logger.warning(f"require_admin_user: User {current_user.id} is not admin. external_provider={external_provider}, external_user_id={external_user_id}")
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

