"""
Projects API router
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.tenant_utils import get_current_user, require_tenant
from app.core.dependencies import require_approved_user
from app.models.project import Project
from app.models.user import User
from app.models.tenant import Tenant
from app.models.scan import ScanJob
from app.models.finding import Finding
from app.core.domain_utils import registrable_domain_from_url
from app.services.domain_verification import ensure_project_root_domain
from app.core.config import settings
from app.models.domain_verification import DomainVerification, DomainVerificationStatus
from app.schemas.domain_verification import (
    DomainVerificationStatusResponse,
    DomainVerificationRequest,
    DomainVerificationVerifyResponse,
)
from app.services.domain_verification import (
    get_or_create_verification,
    rotate_token,
    verify_dns_token,
    build_record_name,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectWithStats,
    ProjectListWithStatsResponse,
    ProjectOverviewResponse,
    ProjectOverviewStats,
)

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(require_approved_user)],
)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(require_tenant),
):
    """
    Create a new project for the current user & tenant.
    """
    # Convert Pydantic HttpUrl to string for database storage
    target_url_str = str(payload.target_url) if payload.target_url else None
    repo_url_str = str(payload.repo_url) if payload.repo_url else None
    
    project = Project(
        name=payload.name,
        target_url=target_url_str,
        repo_url=repo_url_str,
        description=payload.description,
        owner_id=current_user.id,
        tenant_id=tenant.id,
    )
    # Set and lock root_domain based on target_url
    root_domain = registrable_domain_from_url(target_url_str) if target_url_str else None
    if not root_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to determine registrable domain from target_url"
        )
    project.root_domain = root_domain
    db.add(project)
    db.commit()
    
    # Refresh to get timestamps, but avoid loading relationships that might query missing tables
    try:
        db.refresh(project)
    except Exception as e:
        # If refresh fails due to missing table (e.g., performance_scans), 
        # we can still return the project with the data we have
        # The timestamps are set by the database, so we can query them separately if needed
        if "performance_scans" in str(e).lower() or "undefinedtable" in str(e).lower():
            # Re-query the project to get fresh data without loading relationships
            project = db.query(Project).filter(Project.id == project.id).first()
        else:
            raise
    
    # ProjectResponse is a Pydantic model; from_attributes is enabled in its Config
    # ProjectResponse doesn't include performance_scans, so this should be safe
    return ProjectResponse.model_validate(project)


@router.get("", response_model=ProjectListWithStatsResponse)
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(require_tenant),
    limit: int = 20,
    offset: int = 0,
):
    """
    List projects for the current user & tenant, including stats.
    """
    # base query: only this tenant + this user
    base_q = (
        db.query(Project)
        .filter(
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id,
        )
        .order_by(Project.created_at.desc())
    )

    projects = base_q.offset(offset).limit(limit).all()
    total = base_q.count()

    # If you already have stats calculation in this file, keep that logic
    # and only wrap the result into ProjectListWithStatsResponse; this is
    # just a safe placeholder shape:
    items: list[ProjectWithStats] = []
    for p in projects:
        items.append(
            ProjectWithStats(
                id=p.id,
                name=p.name,
                target_url=getattr(p, "target_url", None),
                root_domain=getattr(p, "root_domain", None),
                description=getattr(p, "description", None),
                created_at=p.created_at,
                last_scan_at=None,
                last_scan_status=None,
                last_risk_score=None,
                total_scans=0,
                open_findings=0,
            )
        )

    return ProjectListWithStatsResponse(
        items=items,
        total=total,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific project by ID.
    Requires X-Thandev-Tenant-Id and X-Thandev-User-Id headers.
    Only returns project if it belongs to the current tenant and user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found. The project ID '{project_id}' does not exist or you don't have permission to access it."
        )
    
    return project


@router.get("/{project_id}/overview", response_model=ProjectOverviewResponse)
def get_project_overview(
    project_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get project overview with statistics.
    Requires X-Thandev-Tenant-Id and X-Thandev-User-Id headers.
    
    Returns project info and aggregated stats:
    - Total scans
    - Last scan info (timestamp, status, risk score)
    - Open findings count and breakdown by severity
    - Tools used across all scans
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Load project for this tenant and user
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id
        )
        .first()
    )
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Scan stats
    scans_q = (
        db.query(ScanJob)
        .filter(ScanJob.project_id == project.id)
        .order_by(ScanJob.created_at.desc())
    )
    
    total_scans = scans_q.count()
    last_scan = scans_q.first()
    
    last_scan_at = last_scan.created_at if last_scan else None
    last_scan_status = last_scan.status.value if last_scan and hasattr(last_scan.status, 'value') else (str(last_scan.status) if last_scan else None)
    
    # risk_score is in JSON summary if present
    last_risk_score = None
    if last_scan and last_scan.summary:
        # summary is a JSON/dict, key "risk_score" should exist
        if isinstance(last_scan.summary, dict):
            last_risk_score = last_scan.summary.get("risk_score")
    
    # Findings stats (treat all findings as "open" for now)
    findings_q = (
        db.query(Finding)
        .join(ScanJob, Finding.scan_job_id == ScanJob.id)
        .filter(ScanJob.project_id == project.id)
    )
    
    open_findings_total = findings_q.count()
    
    # Group by severity
    severities = ["critical", "high", "medium", "low", "info"]
    open_findings_by_severity = {s: 0 for s in severities}
    
    for row in (
        db.query(Finding.severity, func.count(Finding.id))
        .join(ScanJob, Finding.scan_job_id == ScanJob.id)
        .filter(ScanJob.project_id == project.id)
        .group_by(Finding.severity)
    ):
        severity_value, count_value = row
        key = severity_value.value if hasattr(severity_value, "value") else str(severity_value)
        if key in open_findings_by_severity:
            open_findings_by_severity[key] = count_value
    
    # tools_used
    tools_used_rows = (
        db.query(Finding.tool_name)
        .join(ScanJob, Finding.scan_job_id == ScanJob.id)
        .filter(ScanJob.project_id == project.id)
        .distinct()
        .all()
    )
    tools_used = sorted(
        {t[0] for t in tools_used_rows if t[0]}  # flatten row tuples
    )
    
    # latest_scan_tools: Get tool results from the latest scan (deduplicated by tool_name)
    latest_scan_tools = []
    if last_scan:
        from app.models.finding import ToolResult
        from app.schemas.project import LatestScanTool
        
        # Get the latest execution of each tool (deduplicate by tool_name)
        # This prevents showing duplicate tools from multiple brain service iterations
        latest_tool_results = (
            db.query(
                ToolResult.tool_name,
                func.max(ToolResult.created_at).label('latest_created_at')
            )
            .filter(ToolResult.scan_job_id == last_scan.id)
            .group_by(ToolResult.tool_name)
            .subquery()
        )
        
        # Get the actual ToolResult records for the latest executions
        tool_results = (
            db.query(ToolResult)
            .join(
                latest_tool_results,
                (ToolResult.tool_name == latest_tool_results.c.tool_name) &
                (ToolResult.created_at == latest_tool_results.c.latest_created_at)
            )
            .filter(ToolResult.scan_job_id == last_scan.id)
            .all()
        )
        
        latest_scan_tools = [
            LatestScanTool(
                tool_name=tool_result.tool_name,
                exit_code=tool_result.exit_code
            )
            for tool_result in tool_results
        ]
    
    return ProjectOverviewResponse(
        id=str(project.id),
        name=project.name,
        target_url=project.target_url,
        root_domain=project.root_domain,
        created_at=project.created_at,
        stats=ProjectOverviewStats(
            total_scans=total_scans,
            last_scan_at=last_scan_at,
            last_scan_status=last_scan_status,
            last_risk_score=last_risk_score,
            open_findings_total=open_findings_total,
            open_findings_by_severity=open_findings_by_severity,
            tools_used=tools_used,
            latest_scan_tools=latest_scan_tools,
        ),
    )


# ---------------- Domain Verification ----------------


def _project_for_tenant_user(db: Session, project_id: str, tenant: Tenant, user: User) -> Project:
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )
    return project


def _domain_verification_response(project: Project, dv: DomainVerification) -> DomainVerificationStatusResponse:
    domain = dv.domain
    token = dv.token
    record_name = build_record_name(domain)
    return DomainVerificationStatusResponse(
        id=dv.id,  # Include verification ID
        project_id=project.id,
        domain=domain,
        status=dv.status.value if hasattr(dv.status, "value") else dv.status,
        token=token,
        record_name=record_name,
        record_value=token,
        last_checked_at=dv.last_checked_at,
        verified_at=dv.verified_at,
        expires_at=dv.expires_at,
        last_error=dv.last_error,
    )


@router.post("/{project_id}/domain-verification/request", response_model=DomainVerificationStatusResponse)
def request_domain_verification(
    project_id: str,
    payload: DomainVerificationRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required",
        )

    project = _project_for_tenant_user(db, project_id, tenant, current_user)

    # Set or lock root_domain based on target_url
    try:
        ensure_project_root_domain(project, project.target_url, allow_admin_override=True, is_admin=False)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    db.commit()
    db.refresh(project)

    domain = project.root_domain
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to determine registrable domain for project",
        )

    dv = get_or_create_verification(db, project, domain)
    # Compare against value since DB stores string
    if payload.force_rotate or (dv.status != DomainVerificationStatus.PENDING.value and dv.status != DomainVerificationStatus.PENDING):
        dv = rotate_token(db, dv)

    return _domain_verification_response(project, dv)


@router.post("/{project_id}/domain-verification/verify", response_model=DomainVerificationVerifyResponse)
def verify_domain(
    project_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required",
        )

    project = _project_for_tenant_user(db, project_id, tenant, current_user)
    domain = project.root_domain
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no root_domain set. Request verification first.",
        )

    dv = get_or_create_verification(db, project, domain)
    dv = verify_dns_token(db, dv)
    return _domain_verification_response(project, dv)


@router.get("/{project_id}/domain-verification", response_model=DomainVerificationStatusResponse)
def get_domain_verification_status(
    project_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get domain verification status for a project.
    
    Returns existing verification if found, or 404 if not found.
    Does NOT auto-create verification - use /request endpoint for that.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required",
        )

    project = _project_for_tenant_user(db, project_id, tenant, current_user)
    domain = project.root_domain
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no root_domain set. Request verification first.",
        )

    # Only return existing verification - do NOT auto-create
    # This prevents deleted verifications from being recreated automatically
    dv = (
        db.query(DomainVerification)
        .filter(
            DomainVerification.project_id == project.id,
            DomainVerification.domain == domain,
            DomainVerification.tenant_id == tenant.id,
        )
        .order_by(DomainVerification.created_at.desc())
        .first()
    )
    
    if not dv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No domain verification found for this project. Use /request endpoint to create one.",
        )

    return _domain_verification_response(project, dv)


# ---------------- Project Targets (URLs) ----------------


@router.get("/{project_id}/targets", response_model=list[str])
def list_project_targets(
    project_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    List all URLs for this project.
    Returns project's target_url and any URLs from scan history (stack_info).
    Only returns URLs if the project's root_domain is verified or allowlisted.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required",
        )
    
    project = _project_for_tenant_user(db, project_id, tenant, current_user)
    
    # Check if domain is verified or allowlisted
    is_admin = bool(getattr(current_user, "is_admin", False) or getattr(current_user, "is_superuser", False))
    if not is_admin and project.root_domain:
        # Check allowlist
        from app.models.allowed_domain import AllowedDomain
        import sqlalchemy as sa
        allowed = (
            db.query(AllowedDomain)
            .filter(
                AllowedDomain.enabled == True,  # noqa: E712
                AllowedDomain.domain == project.root_domain.lower(),
                sa.or_(AllowedDomain.scope == "global", AllowedDomain.tenant_id == tenant.id),
            )
            .first()
        )
        
        if not allowed:
            # Check verification
            dv = (
                db.query(DomainVerification)
                .filter(
                    DomainVerification.project_id == project.id,
                    DomainVerification.domain == project.root_domain,
                    DomainVerification.status == DomainVerificationStatus.VERIFIED,
                )
                .first()
            )
            
            if not dv:
                # Domain not verified - return empty list
                return []
    
    # Collect URLs
    urls = []
    
    # Add project's target_url
    if project.target_url:
        urls.append(project.target_url)
    
    # Get unique URLs from scan jobs' stack_info
    from app.models.scan import ScanJob
    scan_jobs = (
        db.query(ScanJob.stack_info)
        .filter(
            ScanJob.project_id == project.id,
            ScanJob.stack_info.isnot(None),
        )
        .all()
    )
    
    for stack_info in scan_jobs:
        if isinstance(stack_info[0], dict) and "target_url" in stack_info[0]:
            url = stack_info[0]["target_url"]
            if url and url not in urls:
                urls.append(url)
    
    return urls


@router.post("/{project_id}/targets", status_code=status.HTTP_201_CREATED)
def add_project_target(
    project_id: str,
    payload: dict,  # Simple dict with "url" key
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Add a URL to a project's target list.
    Validates that the URL's root_domain matches the project's root_domain.
    Also checks domain verification status.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required",
        )
    
    project = _project_for_tenant_user(db, project_id, tenant, current_user)
    
    if "url" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="url field is required",
        )
    
    target_url = payload["url"]
    if not isinstance(target_url, str) or not target_url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="url must be a non-empty string",
        )
    
    # Extract root_domain
    root_domain = registrable_domain_from_url(target_url)
    if not root_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to determine registrable domain from URL",
        )
    
    # Check root_domain matches project
    if project.root_domain and project.root_domain != root_domain:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"URL root_domain ({root_domain}) does not match project root_domain ({project.root_domain})",
        )
    
    # Check domain verification or allowlist
    is_admin = bool(getattr(current_user, "is_admin", False) or getattr(current_user, "is_superuser", False))
    if not is_admin:
        # Check allowlist
        from app.models.allowed_domain import AllowedDomain
        import sqlalchemy as sa
        allowed = (
            db.query(AllowedDomain)
            .filter(
                AllowedDomain.enabled == True,  # noqa: E712
                AllowedDomain.domain == root_domain.lower(),
                sa.or_(AllowedDomain.scope == "global", AllowedDomain.tenant_id == tenant.id),
            )
            .first()
        )
        
        if not allowed:
            # Check verification
            dv = (
                db.query(DomainVerification)
                .filter(
                    DomainVerification.project_id == project.id,
                    DomainVerification.domain == root_domain,
                    DomainVerification.status == DomainVerificationStatus.VERIFIED,
                )
                .first()
            )
            
            if not dv:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "DOMAIN_NOT_VERIFIED",
                        "root_domain": root_domain,
                        "message": "Domain must be verified or allowlisted before adding URLs.",
                    },
                )
    
    # URL is valid - it will be tracked when a scan is created
    # For now, just return success
    # In the future, we could create a project_targets table to explicitly track URLs
    return {"url": target_url, "message": "URL added to project"}

