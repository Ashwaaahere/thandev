"""
Bootstrap endpoint for external identities (e.g., GitHub) to internal UUIDs.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
import os

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.tenant import Tenant, PlanTier
from app.schemas.auth import BootstrapRequest, BootstrapResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _is_self_service_enabled() -> bool:
    env_lower = settings.ENVIRONMENT.strip().lower()
    explicit_flag = os.getenv("SELF_SERVICE_SIGNUP_ENABLED")
    if explicit_flag is not None:
        return explicit_flag.strip() == "1" or explicit_flag.strip().lower() == "true"
    # Default: enabled for non-production, disabled by default in production
    return env_lower != "production"


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap_identity(payload: BootstrapRequest, db: Session = Depends(get_db)) -> BootstrapResponse:
    """
    Accept external identity (e.g., GitHub) and return internal UUID user/tenant ids.
    - Creates user/tenant when allowed.
    - Updates username/email on each call.
    """
    import logging
    import time
    logger = logging.getLogger(__name__)
    
    start_time = time.time()
    
    try:
        env_lower = settings.ENVIRONMENT.strip().lower()
        self_service_enabled = _is_self_service_enabled()
        
        logger.info(f"[Bootstrap] START: provider={payload.provider}, external_user_id={payload.external_user_id}, email={payload.email}, env={env_lower}, self_service_enabled={self_service_enabled}")

        # Find by external identity first
        user: User | None = (
            db.query(User)
            .filter(
                User.external_provider == payload.provider,
                User.external_user_id == payload.external_user_id,
            )
            .first()
        )

        # Fallback: match by email if external mapping missing
        if not user:
            user = db.query(User).filter(User.email == payload.email).first()
            if user:
                logger.info(f"Bootstrap: Found user by email: {user.id}")

        created = False

        # If no user and self-service disabled in production, block creation
        if not user and env_lower == "production" and not self_service_enabled:
            logger.warning(f"Bootstrap 403: Self-service signup disabled in production. provider={payload.provider}, email={payload.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Self-service signup is disabled. Please contact support.",
            )

        if not user:
            # Check if email or username already exists (shouldn't happen, but handle gracefully)
            existing_email = db.query(User).filter(User.email == payload.email).first()
            existing_username = db.query(User).filter(User.username == payload.username).first()
            
            if existing_email:
                # Email conflict - use existing user
                logger.warning(f"Bootstrap: email {payload.email} already exists, using existing user {existing_email.id}")
                user = existing_email
            elif existing_username:
                # Username conflict - generate unique username
                import random
                unique_username = f"{payload.username}-{random.randint(1000, 9999)}"
                logger.warning(f"Bootstrap: username {payload.username} already exists, using {unique_username}")
                user = User(
                    id=str(uuid.uuid4()),
                    email=payload.email,
                    username=unique_username,
                    full_name=payload.name,
                    hashed_password="",  # OAuth users do not use local password
                    external_provider=payload.provider,
                    external_user_id=payload.external_user_id,
                )
                created = True
                db.add(user)
            else:
                # No conflicts, create new user
                user = User(
                    id=str(uuid.uuid4()),
                    email=payload.email,
                    username=payload.username,
                    full_name=payload.name,
                    hashed_password="",  # OAuth users do not use local password
                    external_provider=payload.provider,
                    external_user_id=payload.external_user_id,
                )
                created = True
                db.add(user)
        else:
            # Update metadata (but don't change email/username if they conflict)
            # Only update if the new values don't conflict with other users
            if user.email != payload.email:
                existing_email = db.query(User).filter(User.email == payload.email, User.id != user.id).first()
                if not existing_email:
                    user.email = payload.email
            
            if user.username != payload.username:
                existing_username = db.query(User).filter(User.username == payload.username, User.id != user.id).first()
                if not existing_username:
                    user.username = payload.username
            
            user.full_name = payload.name
            user.external_provider = payload.provider
            user.external_user_id = payload.external_user_id

        # Ensure tenant exists (owned by this user)
        tenant: Tenant | None = None
        if user.tenant_id:
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()

        if not tenant:
            if env_lower == "production" and not self_service_enabled and created:
                # If creation was already blocked above this shouldn't happen, but guard anyway
                logger.warning(f"Bootstrap 403: Self-service tenant creation disabled. user_id={user.id}, email={payload.email}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Self-service tenant creation is disabled.",
                )
            tenant = Tenant(
                id=str(uuid.uuid4()),
                name=f"{user.username} tenant",
                plan=PlanTier.FREE,
            )
            db.add(tenant)
            created = created or True

        # Link user to tenant
        user.tenant_id = tenant.id

        # Bootstrap admin / approval based on immutable external id
        is_superadmin = (payload.provider.lower(), payload.external_user_id) in settings.superadmin_external_ids_set
        if is_superadmin:
            user.is_admin = True
            user.is_approved = True
        else:
            # Preserve existing flags; new users start unapproved unless otherwise granted elsewhere.
            if created:
                user.is_approved = False

        db.commit()
        db.refresh(user)
        db.refresh(tenant)
        
        elapsed_time = time.time() - start_time
        logger.info(f"[Bootstrap] SUCCESS: user_id={user.id}, tenant_id={tenant.id}, created={created}, elapsed={elapsed_time:.3f}s")

        return BootstrapResponse(
            user_id=user.id,
            tenant_id=tenant.id,
            tenant_plan=tenant.plan.value,
            created=created,
            is_admin=user.is_admin,
            is_approved=user.is_approved,
        )
    except HTTPException:
        raise
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"[Bootstrap] ERROR after {elapsed_time:.3f}s: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bootstrap failed: {str(e)}",
        )


