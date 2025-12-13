"""
Scans API router
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.tenant_utils import require_tenant, get_current_user, get_current_tenant
from app.core.plans import get_plan_limits
from app.models.user import User
from app.models.scan import ScanJob, ScanStatus
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.finding import Finding
from urllib.parse import urlparse
from fastapi.responses import StreamingResponse
import io
from app.schemas.scan import (
    ScanCreate, ScanResponse, ScanSummary, ScanListResponse,
    ScanJobListItem, ScanJobListResponse, QuickScanRequest, QuickScanResponse,
    ToolExecutionResult, ScanToolsResponse
)
from app.services.scan_orchestrator import ScanOrchestrator
from app.services.pdf_reports import generate_scan_report_pdf

router = APIRouter(prefix="/scans", tags=["scans"])
logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """
    Normalize URL (ensure trailing / if needed, consistent format).
    """
    url_str = str(url).strip()
    # If it's a domain without scheme, add https://
    if not url_str.startswith(('http://', 'https://')):
        url_str = f'https://{url_str}'
    # Ensure trailing / for consistency
    parsed = urlparse(url_str)
    if not parsed.path or parsed.path == '/':
        url_str = url_str.rstrip('/') + '/'
    return url_str


def _extract_domain_name(url: str) -> str:
    """
    Extract domain name from URL for project naming.
    """
    parsed = urlparse(str(url))
    domain = parsed.netloc or parsed.path.split('/')[0]
    # Remove port if present
    if ':' in domain:
        domain = domain.split(':')[0]
    return domain


def _extract_summary_fields(summary: Optional[dict]) -> tuple[Optional[float], Optional[int]]:
    """
    Helper to safely extract risk_score and findings_count from summary JSON.
    
    Returns:
        Tuple of (risk_score, findings_count)
    """
    if not summary or not isinstance(summary, dict):
        return (None, None)
    
    risk_score = summary.get("risk_score")
    if risk_score is not None:
        try:
            risk_score = float(risk_score)
        except (ValueError, TypeError):
            risk_score = None
    
    findings_count = summary.get("findings_count")
    if findings_count is not None:
        try:
            findings_count = int(findings_count)
        except (ValueError, TypeError):
            findings_count = None
    
    return (risk_score, findings_count)


@router.get("", response_model=ScanJobListResponse)
async def list_scans(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of scans to return"),
    offset: int = Query(0, ge=0, description="Number of scans to skip"),
    tenant: Tenant = Depends(require_tenant),
):
    """
    List security scans for the current tenant, newest first.
    
    Returns lightweight scan items with project info, status, and summary metrics.
    Used by the dashboard history page.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    """
    
    # Filter ScanJob by tenant via project.tenant_id == tenant.id
    # JOIN with Project to get name + target_url
    query = (
        db.query(ScanJob, Project)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(Project.tenant_id == tenant.id)
    )
    
    # Get total count before pagination
    total = query.count()
    
    # Fetch scans ordered by newest first, with pagination
    results = (
        query
        .order_by(ScanJob.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    # Map ORM rows to ScanJobListItem
    items = []
    for scan_job, project in results:
        # Extract risk_score and findings_count from summary JSON
        risk_score, findings_count = _extract_summary_fields(scan_job.summary)
        
        item = ScanJobListItem(
            id=scan_job.id,
            project_id=scan_job.project_id,
            project_name=project.name,
            target_url=project.target_url,
            scan_level=scan_job.scan_level,
            status=scan_job.status,
            created_at=scan_job.created_at,
            completed_at=scan_job.completed_at,
            risk_score=risk_score,
            findings_count=findings_count,
        )
        items.append(item)
    
    return ScanJobListResponse(
        items=items,
        total=total
    )


@router.get("/project/{project_id}", response_model=ScanListResponse)
async def list_scans_by_project(
    project_id: str,
    skip: int = Query(0, ge=0, description="Number of scans to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of scans to return"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    List scans with project_id filter.
    
    Used by the frontend scans page to display scan history for a project.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    Only returns scans for projects belonging to the current tenant and user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Verify project belongs to tenant and user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Build query - filter by project_id (already verified above)
    query = db.query(ScanJob).filter(ScanJob.project_id == project_id)
    
    # Get total count before pagination
    total = query.count()
    
    # Fetch scans ordered by newest first
    scans = (
        query
        .order_by(ScanJob.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    # Ensure findings relationship is accessible for each scan
    for scan in scans:
        try:
            # Access findings to trigger lazy load while session is still open
            _ = list(scan.findings)
        except Exception as e:
            logger.warning(f"Could not load findings for scan {scan.id}: {e}")
    
    return ScanListResponse(
        items=scans,
        total=total
    )


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    scan: ScanCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new scan job
    
    Plan-aware: Enforces scan level, monthly quota, and concurrent scan limits
    based on tenant's plan.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    
    This will queue a background task using Celery to execute the scan.
    """
    from app.core.plans import get_plan_limits
    from datetime import datetime, timezone
    
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Verify project exists and belongs to tenant and user
    project = db.query(Project).filter(
        Project.id == scan.project_id,
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with id '{scan.project_id}' not found"
        )
    
    # Get plan limits
    limits = get_plan_limits(tenant)
    
    # Check allowed scan levels
    requested_level = scan.scan_level.value if hasattr(scan.scan_level, 'value') else str(scan.scan_level)
    
    if requested_level not in limits["allowed_scan_levels"]:
        allowed_levels_str = ', '.join(limits["allowed_scan_levels"])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Your plan does not allow '{requested_level}' scans. "
                f"Allowed levels: {allowed_levels_str}."
            ),
        )
    
    # Check monthly scan quota
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    monthly_scans = (
        db.query(ScanJob)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            Project.tenant_id == tenant.id,
            ScanJob.created_at >= month_start,
        )
        .count()
    )
    
    if monthly_scans >= limits["max_scans_per_month"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Monthly scan limit reached for your plan "
                f"({limits['max_scans_per_month']} scans)."
            ),
        )
    
    # Check concurrent scans
    in_progress = (
        db.query(ScanJob)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            Project.tenant_id == tenant.id,
            ScanJob.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING]),
        )
        .count()
    )
    
    if in_progress >= limits["max_concurrent_scans"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Too many scans in progress for your plan. "
                f"Max concurrent scans: {limits['max_concurrent_scans']}."
            ),
        )
    
    # TODO: Add authorization check (verify project belongs to current_user)
    
    # Create scan job
    scan_job = ScanJob(
        project_id=scan.project_id,
        scan_level=scan.scan_level,
        status=ScanStatus.PENDING,
    )
    
    db.add(scan_job)
    db.commit()
    db.refresh(scan_job)
    
    # Queue scan task using orchestrator
    try:
        orchestrator = ScanOrchestrator()
        # Convert enum to string value
        scan_level_str = scan.scan_level.value if hasattr(scan.scan_level, 'value') else str(scan.scan_level)
        # Pass user_id for user-specific queue routing
        celery_task_id = await orchestrator.queue_scan(
            scan_job.id, 
            project.target_url, 
            scan_level_str,
            user_id=current_user.id
        )
        
        # Update scan job with celery task ID
        scan_job.celery_task_id = celery_task_id
        scan_job.status = ScanStatus.QUEUED
        db.commit()
        db.refresh(scan_job)
    except Exception as e:
        # If Celery queueing fails, mark scan as failed but still return the scan job
        error_msg = f"Failed to queue scan task: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        scan_job.status = ScanStatus.FAILED
        scan_job.error_message = error_msg
        db.commit()
        db.refresh(scan_job)
        
        # Raise HTTPException with detailed error for debugging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue scan task. Error: {str(e)}. Make sure Celery worker is running."
        )
    
    # Ensure findings relationship is accessible (empty list if none)
    try:
        # Access findings to trigger lazy load while session is still open
        findings_list = list(scan_job.findings)
    except Exception as e:
        logger.warning(f"Could not load findings relationship: {e}")
        # If findings can't be loaded, that's okay - it will be an empty list
    
    try:
        return scan_job
    except Exception as e:
        logger.error(f"Error serializing scan_job response: {e}", exc_info=True)
        # Return a simplified response if serialization fails
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating scan response: {str(e)}"
        )


@router.post("/quick", response_model=QuickScanResponse, status_code=status.HTTP_201_CREATED)
async def quick_scan(
    payload: QuickScanRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Quick scan endpoint: ensure a project exists for this tenant + target_url
    and create a scan at the given scan level.
    
    Either project_id or target_url must be provided.
    If project_id is provided, uses the project's target_url.
    Returns project_id and scan_id. Respects plan limits.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    """
    from datetime import datetime, timezone
    
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Get plan limits
    limits = get_plan_limits(tenant)
    
    # Handle project_id or target_url
    project = None
    normalized_url = None
    
    if payload.project_id:
        # Use existing project
        project = (
            db.query(Project)
            .filter(
                Project.id == payload.project_id,
                Project.tenant_id == tenant.id,
                Project.owner_id == current_user.id,
            )
            .first()
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied"
            )
        
        normalized_url = project.target_url
    else:
        # New target URL provided - find or create project
        if not payload.target_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either project_id or target_url must be provided"
            )
        
        normalized_url = _normalize_url(str(payload.target_url))
        
        # Try to find existing project for this tenant with the same target_url
        existing_project = (
            db.query(Project)
            .filter(
                Project.tenant_id == tenant.id,
                Project.target_url == normalized_url
            )
            .first()
        )
        
        if existing_project:
            project = existing_project
        else:
            # Check project count limit before creating new project
            current_count = (
                db.query(Project)
                .filter(Project.tenant_id == tenant.id)
                .count()
            )
            
            if current_count >= limits["max_projects"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Your plan only allows {limits['max_projects']} project(s). "
                        "Upgrade your plan to create more."
                    ),
                )
            
            # Derive project name from domain
            domain_name = _extract_domain_name(normalized_url)
            base_name = domain_name
            
            # Ensure uniqueness per tenant
            project_name = base_name
            counter = 1
            while (
                db.query(Project)
                .filter(
                    Project.tenant_id == tenant.id,
                    Project.name == project_name
                )
                .first()
            ):
                counter += 1
                project_name = f"{base_name}-{counter}"
            
            # Create new project
            project = Project(
                name=project_name,
                target_url=normalized_url,
                repo_url=None,
                description=payload.description or f"Quick scan for {normalized_url}",
                owner_id=current_user.id,
                tenant_id=tenant.id,
            )
            
            db.add(project)
            db.commit()
            db.refresh(project)
    
    # Now create the scan job (reuse same validation logic as POST /api/scans)
    # Check allowed scan levels
    requested_level = payload.scan_level.value if hasattr(payload.scan_level, 'value') else str(payload.scan_level)
    
    if requested_level not in limits["allowed_scan_levels"]:
        allowed_levels_str = ', '.join(limits["allowed_scan_levels"])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Your plan does not allow '{requested_level}' scans. "
                f"Allowed levels: {allowed_levels_str}."
            ),
        )
    
    # Check monthly scan quota
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    monthly_scans = (
        db.query(ScanJob)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            Project.tenant_id == tenant.id,
            ScanJob.created_at >= month_start,
        )
        .count()
    )
    
    if monthly_scans >= limits["max_scans_per_month"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Monthly scan limit reached for your plan "
                f"({limits['max_scans_per_month']} scans)."
            ),
        )
    
    # Check concurrent scans
    in_progress = (
        db.query(ScanJob)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            Project.tenant_id == tenant.id,
            ScanJob.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING]),
        )
        .count()
    )
    
    if in_progress >= limits["max_concurrent_scans"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Too many scans in progress for your plan. "
                f"Max concurrent scans: {limits['max_concurrent_scans']}."
            ),
        )
    
    # Create scan job
    scan_job = ScanJob(
        project_id=project.id,
        scan_level=payload.scan_level,
        status=ScanStatus.PENDING,
    )
    
    db.add(scan_job)
    db.commit()
    db.refresh(scan_job)
    
    # Queue scan task using orchestrator
    try:
        orchestrator = ScanOrchestrator()
        scan_level_str = payload.scan_level.value if hasattr(payload.scan_level, 'value') else str(payload.scan_level)
        celery_task_id = await orchestrator.queue_scan(
            scan_job.id, 
            project.target_url, 
            scan_level_str,
            user_id=current_user.id
        )
        
        # Update scan job with celery task ID
        scan_job.celery_task_id = celery_task_id
        scan_job.status = ScanStatus.QUEUED
        db.commit()
        db.refresh(scan_job)
    except Exception as e:
        # If Celery queueing fails, mark scan as failed but still return the scan job
        error_msg = f"Failed to queue scan task: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        scan_job.status = ScanStatus.FAILED
        scan_job.error_message = error_msg
        db.commit()
        db.refresh(scan_job)
        
        # Still return the scan, but log the error
        logger.warning(f"Quick scan created but queueing failed: {error_msg}")
    
    return QuickScanResponse(
        project_id=project.id,
        scan_id=scan_job.id
    )


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get scan job status, findings, and summary.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    Only returns scan if it belongs to the current tenant and user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Verify scan belongs to tenant and user via project
    scan_job = (
        db.query(ScanJob)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            ScanJob.id == scan_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id
        )
        .first()
    )
    
    if not scan_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan with id '{scan_id}' not found"
        )
    
    # Don't load all findings here - use paginated endpoint instead
    # Just get the count for summary generation
    findings_count = db.query(Finding).filter(Finding.scan_job_id == scan_id).count()
    
    # For summary generation, we only need a sample or count
    # Load findings only if needed for summary (limit to first 100 for summary stats)
    findings_for_summary = []
    if not scan_job.summary and scan_job.status == ScanStatus.COMPLETED:
        findings_for_summary = db.query(Finding).filter(Finding.scan_job_id == scan_id).limit(100).all()
    
    # Only generate basic summary if AI report doesn't exist and scan is completed
    # The Celery task should generate the AI report, but if it's missing, use basic summary
    if not scan_job.summary and scan_job.status == ScanStatus.COMPLETED:
        # Check if summary is None (not just empty dict)
        # If Celery task failed to generate AI report, create basic summary as fallback
        summary = _generate_summary(scan_job, findings_for_summary)
        scan_job.summary = summary
        db.commit()
        db.refresh(scan_job)
    elif scan_job.summary and isinstance(scan_job.summary, dict):
        # If summary exists but doesn't have AI report fields, it might be old format
        # Check if it's the old format and upgrade it
        if "executive_summary" not in scan_job.summary and "total_findings" in scan_job.summary:
            # Old format detected - this shouldn't happen if Celery task worked correctly
            logger.warning(f"Scan {scan_id} has old format summary, AI report may have failed")
    
    # Set findings to empty list - frontend should use paginated endpoint
    # This prevents loading thousands of findings in one request
    scan_job.findings = []
    
    return scan_job


@router.patch("/{scan_id}/cancel", response_model=ScanResponse)
async def cancel_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel a queued or running scan.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    Only allows cancellation if scan belongs to the current tenant and user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Verify scan belongs to tenant and user via project
    scan_job = (
        db.query(ScanJob)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            ScanJob.id == scan_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id
        )
        .first()
    )
    
    if not scan_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan with id '{scan_id}' not found"
        )
    
    # Only allow cancellation of queued or running scans
    if scan_job.status not in [ScanStatus.QUEUED, ScanStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel scan with status '{scan_job.status.value}'. Only queued or running scans can be cancelled."
        )
    
    # Update scan status to cancelled
    from datetime import datetime, timezone
    scan_job.status = ScanStatus.CANCELLED
    scan_job.completed_at = datetime.now(timezone.utc)
    scan_job.error_message = "Cancelled by user"
    
    # Try to revoke the Celery task if it exists
    if scan_job.celery_task_id:
        try:
            from app.tasks.celery_app import celery
            celery.control.revoke(scan_job.celery_task_id, terminate=True)
            logger.info(f"Revoked Celery task {scan_job.celery_task_id} for cancelled scan {scan_id}")
        except Exception as e:
            logger.warning(f"Failed to revoke Celery task {scan_job.celery_task_id}: {e}")
            # Don't fail the cancellation if we can't revoke the task
    
    db.commit()
    db.refresh(scan_job)
    
    logger.info(f"Scan {scan_id} cancelled by user {current_user.id}")
    
    return scan_job


def _generate_summary(scan_job: ScanJob, findings: list) -> dict:
    """
    Generate summary statistics for a scan
    """
    from collections import Counter
    
    findings_by_severity = Counter(finding.severity.value for finding in findings)
    tools_used = list(set(finding.tool_name for finding in findings if finding.tool_name))
    
    duration = None
    if scan_job.started_at and scan_job.completed_at:
        duration = (scan_job.completed_at - scan_job.started_at).total_seconds()
    
    return {
        "total_findings": len(findings),
        "findings_by_severity": dict(findings_by_severity),
        "tools_used": tools_used,
        "scan_duration_seconds": duration,
    }


@router.get("/{scan_id}/tools", response_model=ScanToolsResponse)
async def get_scan_tools(
    scan_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get tool execution results for a scan.
    Returns aggregated tool_results with tool_name, exit_code, timestamps, and output size.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    Only returns tools if scan belongs to the current tenant and user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Verify scan belongs to tenant and user via project
    scan_job = (
        db.query(ScanJob)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            ScanJob.id == scan_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id
        )
        .first()
    )
    
    if not scan_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan with id '{scan_id}' not found"
        )
    
    # Get tool results for this scan
    from app.models.finding import ToolResult
    from datetime import timedelta
    
    tool_results = (
        db.query(ToolResult)
        .filter(ToolResult.scan_job_id == scan_id)
        .order_by(ToolResult.created_at.asc())
        .all()
    )
    
    items = []
    for tool_result in tool_results:
        # Calculate output size
        output_size = len(tool_result.output.encode('utf-8')) if tool_result.output else 0
        
        # Calculate completed_at from created_at + execution_time
        completed_at = None
        if tool_result.execution_time is not None:
            completed_at = tool_result.created_at + timedelta(seconds=tool_result.execution_time)
        
        # Convert timed_out from integer (0/1) to boolean
        timed_out = bool(tool_result.timed_out) if hasattr(tool_result, 'timed_out') and tool_result.timed_out else False
        
        items.append(
            ToolExecutionResult(
                tool_name=tool_result.tool_name,
                exit_code=tool_result.exit_code,
                started_at=tool_result.created_at,
                completed_at=completed_at,
                output_size=output_size,
                execution_time=tool_result.execution_time,
                error_message=tool_result.error_message,
                timed_out=timed_out,
            )
        )
    
    return ScanToolsResponse(items=items)


@router.get("/{scan_id}/findings")
async def get_scan_findings(
    scan_id: str,
    skip: int = Query(0, ge=0, description="Number of findings to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of findings to return"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    tool: Optional[str] = Query(None, description="Filter by tool name"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get paginated findings for a scan.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    Only returns findings if scan belongs to the current tenant and user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Verify scan belongs to tenant and user via project
    scan_job = (
        db.query(ScanJob)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            ScanJob.id == scan_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id
        )
        .first()
    )
    
    if not scan_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan with id '{scan_id}' not found"
        )
    
    # Build query for findings
    query = db.query(Finding).filter(Finding.scan_job_id == scan_id)
    
    # Apply filters
    if severity:
        try:
            from app.models.finding import Severity
            severity_enum = Severity(severity.lower())
            query = query.filter(Finding.severity == severity_enum)
        except ValueError:
            pass  # Invalid severity, ignore filter
    
    if tool:
        query = query.filter(Finding.tool_name == tool)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    findings = (
        query
        .order_by(Finding.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    # Convert to response format
    from app.schemas.scan import FindingResponse
    items = [FindingResponse.model_validate(f) for f in findings]
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{scan_id}/report.pdf")
def download_scan_report_pdf(
    scan_id: str,
    mode: str = Query("full", pattern="^(full|executive)$"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Download PDF report for a scan.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    Only returns PDF if scan belongs to the current tenant and user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Verify scan belongs to tenant and user via project (PDF generation will also check this)
    scan_job = (
        db.query(ScanJob)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            ScanJob.id == scan_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id
        )
        .first()
    )
    
    if not scan_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan with id '{scan_id}' not found"
        )
    
    try:
        pdf_bytes = generate_scan_report_pdf(db, scan_id, tenant, mode=mode)  # type: ignore[arg-type]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Failed to generate PDF report for scan %s", scan_id)
        raise HTTPException(status_code=500, detail="Failed to generate PDF report")

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="scan-{scan_id}-{mode}.pdf"'
        },
    )

