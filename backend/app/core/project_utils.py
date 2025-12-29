"""
Project utility functions for filtering and counting verified projects
"""
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.domain_verification import DomainVerification, DomainVerificationStatus
from app.models.allowed_domain import AllowedDomain
from app.models.tenant import Tenant
from app.models.user import User
import sqlalchemy as sa
import logging

logger = logging.getLogger(__name__)


def get_verified_projects_query(
    db: Session,
    tenant: Tenant,
    current_user: User,
    include_all_for_admin: bool = True,
):
    """
    Get a query that returns only verified/allowlisted projects.
    This matches the filtering logic used in list_projects endpoint.
    
    Args:
        db: Database session
        tenant: Tenant to filter by
        current_user: User to filter by (also checks if admin)
        include_all_for_admin: If True, admins see all projects (default: True)
    
    Returns:
        Query object that can be used for .all(), .count(), etc.
    """
    # Base query: only this tenant + this user
    base_q = (
        db.query(Project)
        .filter(
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id,
        )
    )
    
    # Check if user is admin
    is_admin = bool(getattr(current_user, "is_admin", False) or getattr(current_user, "is_superuser", False))
    
    if is_admin and include_all_for_admin:
        # Admins see all projects
        return base_q
    
    # For non-admins, filter by verification/allowlist status
    # We'll filter in Python since the logic is complex (needs to check DomainVerification and AllowedDomain)
    # First get all projects
    all_projects = base_q.all()
    
    # Filter by verification status
    verified_project_ids = []
    for p in all_projects:
        # Skip projects without root_domain
        if not p.root_domain:
            continue
        
        # Check if domain is allowlisted
        allowed = (
            db.query(AllowedDomain)
            .filter(
                AllowedDomain.enabled == True,  # noqa: E712
                AllowedDomain.domain == p.root_domain.lower(),
                sa.or_(AllowedDomain.scope == "global", AllowedDomain.tenant_id == tenant.id),
            )
            .first()
        )
        
        if allowed:
            verified_project_ids.append(p.id)
            continue
        
        # Check verification - must exist AND be VERIFIED
        dv = (
            db.query(DomainVerification)
            .filter(
                DomainVerification.project_id == p.id,
                DomainVerification.domain == p.root_domain,
                DomainVerification.tenant_id == tenant.id,
            )
            .first()
        )
        
        if not dv:
            # No verification record exists (was deleted) - skip this project
            continue
        
        # Check status - must be VERIFIED (not PENDING, FAILED, or EXPIRED)
        dv_status = dv.status.value if hasattr(dv.status, "value") else dv.status
        if dv_status != DomainVerificationStatus.VERIFIED.value:
            # Verification exists but is not VERIFIED - skip this project
            continue
        
        # Project is verified, include it
        verified_project_ids.append(p.id)
    
    # Return query filtered to only verified projects
    return base_q.filter(Project.id.in_(verified_project_ids)) if verified_project_ids else base_q.filter(False)


def get_verified_projects_count(
    db: Session,
    tenant: Tenant,
    current_user: User,
    include_all_for_admin: bool = True,
) -> int:
    """
    Get count of verified/allowlisted projects for a tenant/user.
    This matches the count used in list_projects endpoint.
    
    Args:
        db: Database session
        tenant: Tenant to filter by
        current_user: User to filter by (also checks if admin)
        include_all_for_admin: If True, admins count all projects (default: True)
    
    Returns:
        Count of verified projects
    """
    query = get_verified_projects_query(db, tenant, current_user, include_all_for_admin)
    return query.count()


def get_all_projects_count(
    db: Session,
    tenant: Tenant,
    current_user: User,
) -> int:
    """
    Get count of ALL projects for a tenant/user (regardless of verification status).
    
    Use this for limit enforcement when creating NEW projects, because:
    - Projects are created before verification happens
    - Users shouldn't be able to create multiple pending projects to exceed limits
    
    Args:
        db: Database session
        tenant: Tenant to filter by
        current_user: User to filter by
    
    Returns:
        Count of all projects (verified and unverified)
    """
    return (
        db.query(Project)
        .filter(
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id,
        )
        .count()
    )

