"""
Domain verifications API router - URL-based domain verification workflow
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl, Field

from app.core.database import get_db
from app.core.tenant_utils import get_current_user, require_tenant
from app.core.dependencies import require_approved_user
from app.models.project import Project
from app.models.user import User
from app.models.tenant import Tenant
from app.models.domain_verification import DomainVerification, DomainVerificationStatus
from app.models.allowed_domain import AllowedDomain
from app.core.domain_utils import registrable_domain_from_url
from app.services.domain_verification import (
    get_or_create_verification,
    verify_dns_token,
    build_record_name,
    normalize_domain_from_url,
)
from app.schemas.domain_verification import DomainVerificationStatusResponse
import sqlalchemy as sa
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/domain-verifications",
    tags=["domain-verifications"],
    dependencies=[Depends(require_approved_user)],
)


class DomainVerificationStartRequest(BaseModel):
    """Request to start domain verification for a URL"""
    url: HttpUrl = Field(..., description="URL to verify (e.g., https://sub.example.com/path)")
    project_id: Optional[str] = Field(None, description="Optional project ID to associate with")


class DomainVerificationStartResponse(BaseModel):
    """Response from starting domain verification"""
    verification_id: str
    project_id: str
    root_domain: str
    txt_name: str
    txt_value: str
    status: str
    message: Optional[str] = None


class DomainVerificationCheckRequest(BaseModel):
    """Request to check domain verification status"""
    verification_id: Optional[str] = Field(None, description="Verification ID to check")
    root_domain: Optional[str] = Field(None, description="Root domain to check (alternative to verification_id)")


class DomainVerificationCheckResponse(BaseModel):
    """Response from checking domain verification"""
    status: str
    verified_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    last_check_error: Optional[str] = None


def _get_or_create_project_for_domain(
    db: Session,
    tenant: Tenant,
    user: User,
    root_domain: str,
    target_url: str,
) -> Project:
    """Get or create a project for the given root domain"""
    # Try to find existing project with this root_domain
    project = (
        db.query(Project)
        .filter(
            Project.tenant_id == tenant.id,
            Project.root_domain == root_domain,
        )
        .first()
    )
    
    if project:
        return project
    
    # Create new project
    from app.core.plans import get_plan_limits
    limits = get_plan_limits(tenant)
    
    # Check project count limit
    current_count = (
        db.query(Project)
        .filter(Project.tenant_id == tenant.id)
        .count()
    )
    
    if current_count >= limits["max_projects"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your plan only allows {limits['max_projects']} project(s). Upgrade your plan to create more.",
        )
    
    # Derive project name from domain
    project_name = root_domain.replace(".", "-")
    
    project = Project(
        name=project_name,
        target_url=target_url,
        root_domain=root_domain,
        owner_id=user.id,
        tenant_id=tenant.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return project


def _check_allowed_domain(db: Session, tenant: Tenant, root_domain: str) -> bool:
    """Check if domain is in allowlist"""
    # Check DB allowlist
    allowed = (
        db.query(AllowedDomain)
        .filter(
            AllowedDomain.enabled == True,  # noqa: E712
            AllowedDomain.domain == root_domain.lower(),
            sa.or_(AllowedDomain.scope == "global", AllowedDomain.tenant_id == tenant.id),
        )
        .first()
    )
    if allowed:
        return True
    
    # Check config allowlist
    raw_allowlist = getattr(settings, "ALLOWED_SCAN_DOMAINS", "") or ""
    allowlist = [d.strip().lower() for d in raw_allowlist.split(",") if d.strip()]
    if root_domain.lower() in allowlist:
        return True
    
    return False


@router.post("/start", response_model=DomainVerificationStartResponse, status_code=status.HTTP_200_OK)
def start_domain_verification(
    payload: DomainVerificationStartRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Start domain verification for a URL.
    
    - Extracts root_domain from URL
    - Checks if domain is allowlisted (returns ALLOWLISTED status if so)
    - Creates or reuses project for tenant+root_domain
    - Creates or reuses PENDING verification
    - Returns TXT record name and value
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required",
        )
    
    target_url = str(payload.url)
    root_domain = normalize_domain_from_url(target_url)
    
    if not root_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to determine registrable domain from URL",
        )
    
    # Check if domain is allowlisted
    if _check_allowed_domain(db, tenant, root_domain):
        # Find or create project for allowlisted domain
        project = _get_or_create_project_for_domain(db, tenant, current_user, root_domain, target_url)
        
        return DomainVerificationStartResponse(
            verification_id="",  # No verification needed
            project_id=project.id,
            root_domain=root_domain,
            txt_name="",
            txt_value="",
            status="ALLOWLISTED",
            message="Demo target - DNS verification not required",
        )
    
    # Get or create project
    if payload.project_id:
        # Use provided project if it exists and belongs to tenant
        project = (
            db.query(Project)
            .filter(
                Project.id == payload.project_id,
                Project.tenant_id == tenant.id,
            )
            .first()
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied",
            )
        # Ensure root_domain matches
        if project.root_domain and project.root_domain != root_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project root_domain ({project.root_domain}) does not match URL root_domain ({root_domain})",
            )
        if not project.root_domain:
            project.root_domain = root_domain
            db.commit()
            db.refresh(project)
    else:
        project = _get_or_create_project_for_domain(db, tenant, current_user, root_domain, target_url)
    
    # Get or create verification
    dv = get_or_create_verification(db, project, root_domain)
    
    # If already verified, return that status (compare against value since DB stores string)
    if dv.status == DomainVerificationStatus.VERIFIED.value or dv.status == DomainVerificationStatus.VERIFIED:
        return DomainVerificationStartResponse(
            verification_id=dv.id,
            project_id=project.id,
            root_domain=root_domain,
            txt_name=build_record_name(root_domain),
            txt_value=dv.token,
            status="VERIFIED",
        )
    
    # Return PENDING status with TXT record info
    return DomainVerificationStartResponse(
        verification_id=dv.id,
        project_id=project.id,
        root_domain=root_domain,
        txt_name=build_record_name(root_domain),
        txt_value=dv.token,
        status="PENDING",
    )


@router.post("/check", response_model=DomainVerificationCheckResponse, status_code=status.HTTP_200_OK)
def check_domain_verification(
    payload: DomainVerificationCheckRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Check domain verification status by performing DNS lookup.
    
    Accepts either verification_id or root_domain.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required",
        )
    
    # Find verification
    if payload.verification_id:
        dv = (
            db.query(DomainVerification)
            .filter(
                DomainVerification.id == payload.verification_id,
                DomainVerification.tenant_id == tenant.id,
            )
            .first()
        )
        if not dv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification not found or access denied",
            )
    elif payload.root_domain:
        # Find verification by root_domain for this tenant
        dv = (
            db.query(DomainVerification)
            .join(Project, DomainVerification.project_id == Project.id)
            .filter(
                DomainVerification.domain == payload.root_domain.lower(),
                DomainVerification.tenant_id == tenant.id,
            )
            .order_by(DomainVerification.created_at.desc())
            .first()
        )
        if not dv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification not found for this domain",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either verification_id or root_domain must be provided",
        )
    
    # If already verified, return immediately (compare against value since DB stores string)
    if dv.status == DomainVerificationStatus.VERIFIED.value or dv.status == DomainVerificationStatus.VERIFIED:
        return DomainVerificationCheckResponse(
            status="VERIFIED",
            verified_at=dv.verified_at.isoformat() if dv.verified_at else None,
            last_checked_at=dv.last_checked_at.isoformat() if dv.last_checked_at else None,
            last_check_error=None,
        )
    
    # Perform DNS check
    try:
        dv = verify_dns_token(db, dv)
        logger.info(f"DNS verification check for {dv.domain}: status={dv.status}")
    except Exception as e:
        logger.error(f"DNS verification check failed for {dv.domain}: {e}", exc_info=True)
        # Update last_error even if check failed
        dv.last_checked_at = dv.last_checked_at or None
        db.commit()
        db.refresh(dv)
    
    return DomainVerificationCheckResponse(
        status=dv.status.value if hasattr(dv.status, "value") else str(dv.status),
        verified_at=dv.verified_at.isoformat() if dv.verified_at else None,
        last_checked_at=dv.last_checked_at.isoformat() if dv.last_checked_at else None,
        last_check_error=dv.last_error,
    )

