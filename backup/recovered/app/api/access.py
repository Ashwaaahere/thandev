"""
Access request endpoints for private beta gating.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.tenant_utils import get_current_user, require_tenant
from app.core.dependencies import require_authenticated_user
from app.models.notification import Notification
from app.models.user import User
from app.models.tenant import Tenant
from app.models.allowed_domain import AllowedDomain, AllowedDomainScope
from app.schemas.admin import AllowedDomainResponse
from app.core.domain_utils import registrable_domain_from_url, registrable_domain_from_host

router = APIRouter(prefix="/access", tags=["access"])


@router.post("/request", status_code=status.HTTP_200_OK)
def request_access(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(require_tenant),
):
    """
    Allow authenticated but unapproved users to request access.

    Minimal implementation: create a notification record that can be seen by admins.
    """
    notification = Notification(
        tenant_id=tenant.id,
        owner_id=current_user.id,
        type="access_request",
        title="Access requested",
        message=f"User {current_user.email} requested access to private beta.",
        link_url="/admin",
    )
    db.add(notification)
    db.commit()
    return {"status": "ok"}


@router.get("/allowed-domains", response_model=list[AllowedDomainResponse])
def list_allowed_domains_for_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    """
    List enabled allowed domains visible to the current user:
    - Global scope domains
    - Tenant-scoped domains matching the user's tenant
    """
    tenant_id = getattr(current_user, "tenant_id", None)
    entries = (
        db.query(AllowedDomain)
        .filter(
            AllowedDomain.enabled == True,  # noqa: E712
            or_(
                AllowedDomain.scope == AllowedDomainScope.GLOBAL,
                (AllowedDomain.scope == AllowedDomainScope.TENANT) & (AllowedDomain.tenant_id == tenant_id),
            ),
        )
        .all()
    )
    return [
        # Normalize domain in the response so frontend matches correctly even if stored with path/scheme
        # (legacy rows might contain full URLs)
        AllowedDomainResponse(
            id=e.id,
            domain=registrable_domain_from_url(e.domain) or registrable_domain_from_host(e.domain) or e.domain,
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

