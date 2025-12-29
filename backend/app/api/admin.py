"""
Admin endpoints: list users/tenants, approve users, assign entitlements, usage view.
"""
import os
import uuid
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
import logging

from app.core.database import get_db
from app.core.dependencies import require_admin_user
from app.models.user import User
from app.models.tenant import Tenant
from app.models.entitlement import Entitlement
from app.models.audit_log import AuditLog
from app.models.allowed_domain import AllowedDomain
from app.core.domain_utils import registrable_domain_from_url, registrable_domain_from_host
from app.schemas.admin import (
    UserSummary,
    TenantSummary,
    EntitlementRequest,
    EntitlementResponse,
    AllowedDomainRequest,
    AllowedDomainResponse,
)
from app.core.config import settings
from fastapi import Query
from app.schemas.admin import AllowedDomainRequest, AllowedDomainResponse

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


def _log_admin_action(
    db: Session,
    actor: Optional[User],
    action: str,
    target_user_id: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    entry = AuditLog(
        user_id=actor.id if actor else None,
        tenant_id=getattr(actor, "tenant_id", None),
        action_type=action,
        target_type="user",
        target_id=target_user_id,
        event_metadata=metadata or {},
    )
    db.add(entry)
    db.commit()


@router.get("/users", response_model=List[UserSummary])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    users = db.query(User).all()
    return [
        UserSummary(
            id=u.id,
            email=u.email,
            username=u.username,
            is_admin=u.is_admin,
            is_approved=u.is_approved,
            tenant_id=u.tenant_id,
        )
        for u in users
    ]


@router.get("/tenants", response_model=List[TenantSummary])
def list_tenants(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    tenants = db.query(Tenant).all()
    return [
        TenantSummary(
            id=t.id,
            name=t.name,
            plan=str(t.plan.value if hasattr(t.plan, "value") else t.plan),
        )
        for t in tenants
    ]


@router.get("/plan-templates", response_model=Dict[str, Dict[str, Any]])
def get_plan_templates(
    current_user: User = Depends(require_admin_user),
):
    """
    Get plan templates for admin UI.
    Returns a dict mapping plan names to their default limits.
    """
    from app.core.plans import PLAN_CONFIG, PlanName
    
    templates = {}
    for plan_name, limits in PLAN_CONFIG.items():
        plan_key = plan_name.value if hasattr(plan_name, 'value') else str(plan_name)
        templates[plan_key] = dict(limits)
    
    return templates


@router.post("/users/{user_id}/approve")
def approve_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = True
    db.commit()
    _log_admin_action(db, current_user, "user_approved", target_user_id=user_id)
    return {"status": "ok", "user_id": user.id, "is_approved": user.is_approved}


@router.post("/users/{user_id}/entitlement", response_model=EntitlementResponse)
def set_entitlement(
    user_id: str,
    payload: EntitlementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    tenant = db.query(Tenant).filter(Tenant.id == payload.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # UPSERT: Check if entitlement already exists
    ent = None
    if payload.user_scoped:
        # User-scoped entitlement
        ent = (
            db.query(Entitlement)
            .filter(
                Entitlement.tenant_id == tenant.id,
                Entitlement.user_id == user.id
            )
            .first()
        )
    else:
        # Tenant-wide entitlement (user_id is None)
        ent = (
            db.query(Entitlement)
            .filter(
                Entitlement.tenant_id == tenant.id,
                Entitlement.user_id.is_(None)
            )
            .first()
        )
    
    if ent:
        # Update existing entitlement
        ent.plan_name = payload.plan_name
        ent.limits_json = payload.limits_json
        # Note: user_id and tenant_id don't change
        action_metadata = {"limits": payload.limits_json, "plan": payload.plan_name, "action": "updated"}
    else:
        # Create new entitlement
        ent = Entitlement(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            user_id=user.id if payload.user_scoped else None,
            plan_name=payload.plan_name,
            limits_json=payload.limits_json,
        )
        db.add(ent)
        action_metadata = {"limits": payload.limits_json, "plan": payload.plan_name, "action": "created"}
    
    db.commit()
    db.refresh(ent)

    _log_admin_action(
        db,
        current_user,
        "user_entitlement_assigned",
        target_user_id=user.id,
        metadata=action_metadata,
    )

    return EntitlementResponse(
        id=ent.id,
        tenant_id=ent.tenant_id,
        user_id=ent.user_id,
        plan_name=ent.plan_name,
        limits_json=ent.limits_json,
    )


@router.get("/allowed-domains", response_model=List[AllowedDomainResponse])
def list_allowed_domains(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    try:
        entries = db.query(AllowedDomain).all()
        return [
            AllowedDomainResponse(
                id=e.id,
                domain=e.domain,
                scope=e.scope,
                tenant_id=e.tenant_id,
                enabled=e.enabled,
                notes=e.notes,
                created_by_admin_id=e.created_by_admin_id,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in entries
        ]
    except Exception as exc:
        logger.warning("allowed-domains list failed: %s", exc)
        # If table missing or other error, return empty list so UI doesn't break
        return []


@router.post("/allowed-domains", response_model=AllowedDomainResponse, status_code=status.HTTP_201_CREATED)
def create_allowed_domain(
    payload: AllowedDomainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    try:
        raw = payload.domain.strip()
        # Accept either a bare domain/host or a full URL; normalize to registrable domain
        normalized_domain = registrable_domain_from_url(raw) if raw.startswith("http") else registrable_domain_from_host(raw)
        if not normalized_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid domain",
            )

        entry = AllowedDomain(
            domain=normalized_domain.lower(),
            scope=payload.scope,
            tenant_id=payload.tenant_id,
            enabled=payload.enabled,
            notes=payload.notes,
            created_by_admin_id=current_user.id,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return AllowedDomainResponse(
            id=entry.id,
            domain=entry.domain,
            scope=entry.scope,
            tenant_id=entry.tenant_id,
            enabled=entry.enabled,
            notes=entry.notes,
            created_by_admin_id=entry.created_by_admin_id,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )
    except Exception as exc:
        logger.error("allowed-domain create failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create allowed domain (check migrations/table).",
        ) from exc


@router.delete("/allowed-domains/{allowed_domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_allowed_domain(
    allowed_domain_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    try:
        entry = db.query(AllowedDomain).filter(AllowedDomain.id == allowed_domain_id).first()
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allowed domain not found")
        db.delete(entry)
        db.commit()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("allowed-domain delete failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete allowed domain (check migrations/table).",
        ) from exc


@router.post("/bootstrap-superadmin")
def bootstrap_superadmin(
    external_provider: str,
    external_user_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    One-time endpoint to seed the first superadmin when none exists.
    Requires Authorization: Bearer <THANDEV_SETUP_TOKEN>.
    """
    setup_token = settings.THANDEV_SETUP_TOKEN or os.getenv("THANDEV_SETUP_TOKEN")
    if not setup_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Setup token not configured")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if token != setup_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid setup token")

    admin_exists = db.query(User).filter(User.is_admin == True).first()  # noqa: E712
    if admin_exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Admin already exists; setup token disabled")

    provider = external_provider.strip().lower()
    external_user_id = external_user_id.strip()
    if not provider or not external_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="external_provider and external_user_id are required")

    user = (
        db.query(User)
        .filter(User.external_provider == provider, User.external_user_id == external_user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found for provided external id")

    user.is_admin = True
    user.is_approved = True
    db.commit()

    _log_admin_action(
        db,
        actor=None,
        action="superadmin_bootstrap",
        target_user_id=user.id,
        metadata={"external_provider": provider, "external_user_id": external_user_id},
    )

    return {"status": "ok", "user_id": user.id}
