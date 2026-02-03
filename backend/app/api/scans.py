"""
Scans API router
"""
import os
import json
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_
import json
import time

from app.core.database import get_db
from app.core.tenant_utils import require_tenant, get_current_user, get_current_tenant
from app.core.dependencies import require_approved_user
from app.core.plans import get_plan_limits
from app.core.config import settings
from app.core.constants import TERMINAL_SCAN_STATUSES
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
    ToolExecutionResult, ScanToolsResponse, ToolResultCreate, ToolResultResponse,
    ProScanRequest, AdvancedScanRequest, ScanArtifactResponse, ScanArtifactsResponse
)
from app.schemas.brain import BrainSessionResponse, SessionStatus, parse_iso_datetime_safe
from app.services.scan_orchestrator import ScanOrchestrator
from app.services.pdf_reports import generate_scan_report_pdf
from app.services.domain_verification import (
    enforce_domain_verification_for_scan,
    ensure_project_root_domain,
)
from app.services.scan_enforcement import enforce_scan_permissions
from app.utils.raw_data_parser import parse_raw_json, extract_zap_metadata, normalize_cwe_id
from app.core.severity import zap_to_severity

router = APIRouter(
    prefix="/scans",
    tags=["scans"],
    dependencies=[Depends(require_approved_user)],
)
logger = logging.getLogger(__name__)


def _log_scan_state(hypothesis_id: str, location: str, scan: ScanJob | None):
    return


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
    current_user: User = Depends(get_current_user),
):
    """
    List security scans for the current tenant and user, newest first.
    
    Returns lightweight scan items with project info, status, and summary metrics.
    Used by the dashboard history page.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    Only returns scans for projects owned by the current user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Filter ScanJob by tenant and user via project.tenant_id == tenant.id and project.owner_id == current_user.id
    # JOIN with Project to get name + target_url
    query = (
        db.query(ScanJob, Project)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id
        )
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
        
        # CRITICAL FIX: If findings_count is not in summary, calculate it from database
        # Exclude surface assets (HTTPX enumeration data) from findings count
        # Include findings where category IS NULL (existing findings) or category != "surface"
        if findings_count is None:
            from sqlalchemy import or_
            findings_count = (
                db.query(Finding)
                .filter(Finding.scan_job_id == scan_job.id)
                .filter(or_(Finding.category.is_(None), Finding.category != "surface"))
                .count()
            )
            # Update summary with findings_count for future queries
            if scan_job.summary:
                if isinstance(scan_job.summary, dict):
                    scan_job.summary["findings_count"] = findings_count
                else:
                    scan_job.summary = {"findings_count": findings_count}
            else:
                scan_job.summary = {"findings_count": findings_count}
            db.commit()
        
        item = ScanJobListItem(
            id=scan_job.id,
            project_id=scan_job.project_id,
            project_name=project.name,
            target_url=project.target_url,
            scan_level=scan_job.scan_level,
            status=scan_job.status,
            created_at=scan_job.created_at,
            completed_at=scan_job.completion_time,  # Use effective completion time
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
    # Use EXACT same query logic as get_project_overview which works correctly
    # Ensure project.id is a string for consistent comparison
    project_id_str = str(project.id)
    logger.info(f"Project {project_id} ({project.name}): Querying scans with project_id={project_id_str} (type: {type(project_id_str)})")
    
    query = db.query(ScanJob).filter(ScanJob.project_id == project_id_str)
    
    # Get total count before pagination
    total_by_id = query.count()
    logger.info(f"Project {project_id} ({project.name}): Found {total_by_id} scans by project_id")
    
    # If no scans found by project_id, try matching by URL/domain (for legacy scans)
    if total_by_id == 0 and project.target_url:
        # Try to match by URL or domain
        url_query = db.query(ScanJob).filter(
            or_(
                ScanJob.url == project.target_url,
                ScanJob.domain == project.root_domain
            )
        )
        url_total = url_query.count()
        logger.info(f"Project {project_id} ({project.name}): Found {url_total} scans by URL/domain match (target_url={project.target_url}, root_domain={project.root_domain})")
        
        if url_total > 0:
            # Use URL-matched scans
            query = url_query
            total = url_total
        else:
            total = 0
    else:
        total = total_by_id
    
    # Fetch scans ordered by newest first
    scans = (
        query
        .order_by(ScanJob.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    logger.info(f"Project {project_id}: Returning {len(scans)} scans (total: {total})")
    if len(scans) > 0:
        logger.info(f"Project {project_id}: First scan id={scans[0].id}, project_id={scans[0].project_id}, created_at={scans[0].created_at}")
    
    # Ensure findings relationship is accessible for each scan
    # Also ensure summary has findings_count set and is a dict (not string)
    for scan in scans:
        try:
            # Access findings to trigger lazy load while session is still open
            _ = list(scan.findings)
        except Exception as e:
            logger.warning(f"Could not load findings for scan {scan.id}: {e}")
        
        # CRITICAL FIX: Ensure summary is a dict (not a JSON string) and has findings_count set
        # Parse summary if it's a string
        summary_dict = None
        if scan.summary:
            if isinstance(scan.summary, dict):
                summary_dict = scan.summary
            elif isinstance(scan.summary, str):
                try:
                    import json
                    summary_dict = json.loads(scan.summary)
                except (json.JSONDecodeError, TypeError):
                    summary_dict = {}
        
        # Get or calculate findings_count
        findings_count = None
        if summary_dict:
            findings_count = summary_dict.get("findings_count")
        
        if findings_count is None:
            # Calculate from database
            # Exclude surface assets from findings count
            # Include findings where category IS NULL (existing findings) or category != "surface"
            from sqlalchemy import or_
            findings_count = (
                db.query(Finding)
                .filter(Finding.scan_job_id == scan.id)
                .filter(or_(Finding.category.is_(None), Finding.category != "surface"))
                .count()
            )
            if not summary_dict:
                summary_dict = {}
            summary_dict["findings_count"] = findings_count
        
        # Ensure summary is always a dict for Pydantic validation
        scan.summary = summary_dict if summary_dict else {}
    
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
    # Import settings locally to avoid scoping issues
    from app.core.config import settings
    
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
            detail=f"Project not found. The project ID '{scan.project_id}' does not exist or you don't have permission to access it."
        )
    
    is_admin = bool(getattr(current_user, "is_admin", False) or getattr(current_user, "is_superuser", False))
    from app.core.limits import get_effective_limits
    limits = get_effective_limits(db, tenant, current_user)
    try:
        ensure_project_root_domain(project, project.target_url, allow_admin_override=True, is_admin=is_admin)
        db.commit()
        db.refresh(project)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    enforce_domain_verification_for_scan(
        db,
        project,
        project.target_url,
        is_admin=is_admin,
        user_id=current_user.id,
    )
    
    # Central enforcement (approval, plan/limits, domain lock/verification, quotas)
    enforce_scan_permissions(
        db=db,
        tenant=tenant,
        user=current_user,
        project=project,
        target_url=project.target_url,
        requested_level=scan.scan_level,
    )
    
    # TODO: Add authorization check (verify project belongs to current_user)
    
    # Map scan_level to tier (tier must match scan_level value)
    scan_level_value = scan.scan_level.value if hasattr(scan.scan_level, 'value') else str(scan.scan_level).lower()
    tier = scan_level_value  # 'basic', 'pro', or 'advanced'
    
    # Extract domain from project target_url
    domain = _extract_domain_name(project.target_url) if project.target_url else (project.root_domain or None)
    
    # Create scan job with ALL required fields
    # CRITICAL: Always set user_id, url, domain, tier, and created_at to prevent NotNullViolation errors
    from datetime import datetime, timezone
    scan_job = ScanJob(
        user_id=current_user.id,  # REQUIRED: Always set user_id
        url=project.target_url,  # REQUIRED: Always set url
        domain=domain,  # Set domain (nullable, but set for consistency)
        tier=tier,  # REQUIRED: Always set tier (maps to scan_level: 'basic', 'pro', or 'advanced')
        project_id=scan.project_id,
        scan_level=scan.scan_level,
        status=ScanStatus.PENDING,
        created_at=datetime.now(timezone.utc),  # REQUIRED: Explicitly set created_at to prevent NotNullViolation
    )
    
    db.add(scan_job)
    db.commit()
    db.refresh(scan_job)
    
    # PR-4E: Start brain session instead of (or in addition to) Celery task
    from app.services.brain_client import get_brain_client
    
    if settings.BRAIN_SERVICE_ENABLED:
        try:
            # Get stack_info (lightweight HTTP probe)
            stack_info = {}
            try:
                import requests
                resp = requests.head(project.target_url, timeout=5, allow_redirects=True)
                stack_info["http"] = {
                    "status_code": resp.status_code,
                    "headers": {
                        "server": resp.headers.get("Server"),
                        "content_type": resp.headers.get("Content-Type"),
                    },
                }
            except Exception:
                pass  # stack_info can be empty
            
            # Convert enum to string value
            scan_level_str = scan.scan_level.value if hasattr(scan.scan_level, 'value') else str(scan.scan_level)
            
            # Start brain session
            try:
                from app.services.brain_client import get_brain_client
                brain_client = get_brain_client()
            except ImportError as e:
                logger.warning(f"Could not import brain_client: {e}. Skipping brain session.")
                brain_client = None
            
            if not brain_client:
                raise ValueError("Brain client is not available. Cannot start brain session.")
            
            session_response = await brain_client.start_session(
                scan_job_id=scan_job.id,
                target_url=project.target_url,
                scan_level=scan_level_str,
                org_id=tenant.id,
                project_id=project.id,
                stack_info=stack_info,
                policy={
                    "max_steps": 20,
                    "max_runtime_sec": 3600,
                },
            )
            
            # Store session_id in scan_job
            scan_job.brain_session_id = session_response.get("session_id")
            scan_job.status = ScanStatus.RUNNING  # Brain owns the loop now
            db.commit()
            db.refresh(scan_job)
            
            # CRITICAL LOG: This must appear in logs to confirm we reach this point
            logger.error(f"[BRAIN-PENDING-ENTRY] CRITICAL: About to create PENDING ToolResult records for brain scan {scan_job.id}")
            
            # CRITICAL: Create PENDING ToolResult records so UI can show tool status
            # Brain service will publish steps dynamically, but we need initial PENDING records
            # based on expected tools for this scan level
            # Use a fresh database session to avoid transaction issues
            try:
                logger.info(f"[BRAIN-PENDING-STEP1] Importing modules...")
                from app.core.database import SessionLocal
                from app.core.tool_matrix import get_tools_for_level
                from app.models.finding import ToolResult, ToolExecutionStatus
                logger.info(f"[BRAIN-PENDING-STEP2] Modules imported successfully")
                
                logger.info(f"[BRAIN-PENDING-STEP3] Starting to create PENDING ToolResult records for brain scan {scan_job.id}")
                scan_level_enum = scan.scan_level
                logger.info(f"[BRAIN-PENDING-STEP4] Scan level enum: {scan_level_enum}, value: {scan_level_enum.value if hasattr(scan_level_enum, 'value') else scan_level_enum}")
                expected_tools = get_tools_for_level(scan_level_enum)
                logger.info(f"[BRAIN-PENDING-STEP5] Got {len(expected_tools)} expected tools for scan level {scan_level_enum.value}")
                
                # Use a fresh database session for PENDING record creation
                pending_db = SessionLocal()
                try:
                    pending_count = 0
                    for tool_config in expected_tools:
                        if not tool_config.get("enabled", True):
                            logger.debug(f"[BRAIN-PENDING] Skipping disabled tool: {tool_config.get('key')}")
                            continue
                        
                        tool_id = tool_config.get("key") or tool_config.get("name")
                        logger.debug(f"[BRAIN-PENDING] Processing tool: {tool_id}")
                        
                        # Check if ToolResult already exists (idempotent)
                        existing = pending_db.query(ToolResult).filter(
                            ToolResult.scan_job_id == scan_job.id,
                            ToolResult.tool_name == tool_id
                        ).first()
                        
                        if not existing:
                            tool_result = ToolResult(
                                scan_job_id=scan_job.id,
                                tool_name=tool_id,
                                status=ToolExecutionStatus.PENDING,
                            )
                            pending_db.add(tool_result)
                            pending_count += 1
                            logger.debug(f"[BRAIN-PENDING] Added PENDING record for {tool_id}")
                        else:
                            logger.debug(f"[BRAIN-PENDING] ToolResult already exists for {tool_id}: {existing.status}")
                    
                    if pending_count > 0:
                        pending_db.commit()
                        logger.info(f"[BRAIN-PENDING] Created {pending_count} PENDING ToolResult records for brain scan {scan_job.id}")
                    else:
                        logger.warning(f"[BRAIN-PENDING] No PENDING records created (all tools may already exist or be disabled)")
                except Exception as inner_e:
                    logger.error(f"[BRAIN-PENDING] Error in PENDING record creation loop: {inner_e}", exc_info=True)
                    pending_db.rollback()
                    raise
                finally:
                    pending_db.close()
            except Exception as e:
                logger.error(f"[BRAIN-PENDING] Failed to create PENDING ToolResult records for brain scan {scan_job.id}: {e}", exc_info=True)
                # Don't fail the scan if this fails - brain will still work
            
            logger.info(
                f"Started brain session {scan_job.brain_session_id} for scan {scan_job.id}. "
                f"Brain will own the closed-loop scanning process."
            )
            
            
            # Verify PENDING records were created (for debugging)
            try:
                from app.models.finding import ToolResult
                pending_count_check = db.query(ToolResult).filter(
                    ToolResult.scan_job_id == scan_job.id,
                    ToolResult.status == ToolExecutionStatus.PENDING
                ).count()
                logger.info(f"[BRAIN-PENDING-VERIFY] Scan {scan_job.id} has {pending_count_check} PENDING ToolResult records after brain session start")
            except Exception as verify_e:
                logger.debug(f"[BRAIN-PENDING-VERIFY] Failed to verify PENDING records: {verify_e}")
        except Exception as e:
            # Log the error with full details for debugging
            error_detail = str(e) if str(e) else repr(e)
            if not error_detail:
                error_detail = f"Unknown error: {type(e).__name__}"
            
            # CRITICAL: Log full error details including connection info
            logger.error(
                f"[BRAIN-SESSION-FAILED] Failed to start brain session for scan {scan_job.id}: {error_detail}. "
                f"BRAIN_SERVICE_URL={settings.BRAIN_SERVICE_URL}, BRAIN_URL={settings.BRAIN_URL}, "
                f"BRAIN_SERVICE_ENABLED={settings.BRAIN_SERVICE_ENABLED}, Error type: {type(e).__name__}",
                exc_info=True
            )
            
            # If brain session fails and BRAIN_REQUIRED=true, fail the scan
            if settings.BRAIN_REQUIRED:
                error_msg = f"Failed to start brain session: {error_detail}. Brain service is required (BRAIN_REQUIRED=true)."
                scan_job.status = ScanStatus.FAILED
                scan_job.error_message = error_msg
                db.commit()
                db.refresh(scan_job)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_msg
                )
            else:
                # Brain not required, fall back to legacy Celery orchestrator
                logger.warning(
                    f"Brain session failed but BRAIN_REQUIRED=false, falling back to Celery/Runner. "
                    f"Error: {error_detail}"
                )
                # Fall through to Celery queueing below
    else:
        logger.info("Brain service disabled, using Runner-based execution path")
        # Fall through to Runner path below
    
    # Default path: Use Runner via Redis streams (when brain is disabled or not required)
    if not settings.BRAIN_SERVICE_ENABLED or (not settings.BRAIN_REQUIRED and not scan_job.brain_session_id):
        # Use Runner via Redis streams
        logger.info(f"Publishing scan steps to Runner for scan {scan_job.id}")
        try:
            from app.services.runner_client import publish_scan_steps_to_runner
            
            # Publish step requests to Runner
            success = await publish_scan_steps_to_runner(
                scan_job_id=scan_job.id,
                target_url=project.target_url,
                scan_level=scan.scan_level,
                org_id=tenant.id,
                project_id=project.id,
            )
            
            if success:
                # CRITICAL: Always set status to RUNNING when steps are published successfully
                # This ensures scans don't get stuck in QUEUED or PENDING status
                scan_job.status = ScanStatus.RUNNING
                if not scan_job.started_at:
                    scan_job.started_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(scan_job)
                logger.info(
                    f"Scan {scan_job.id} started via Runner (steps published to Redis streams). "
                    f"Status updated to RUNNING."
                )
            else:
                error_msg = "Failed to publish scan steps to Runner. Make sure Runner service is running and Redis is accessible."
                logger.error(
                    f"Scan {scan_job.id}: {error_msg}. "
                    f"Current status: {scan_job.status.value if hasattr(scan_job.status, 'value') else scan_job.status}"
                )
                scan_job.status = ScanStatus.FAILED
                scan_job.error_message = error_msg
                db.commit()
                db.refresh(scan_job)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_msg
                )
            
        except HTTPException:
            raise
        except Exception as e:
            error_msg = f"Failed to publish scan steps to Runner: {str(e)}"
            logger.error(error_msg, exc_info=True)
            scan_job.status = ScanStatus.FAILED
            scan_job.error_message = error_msg
            db.commit()
            db.refresh(scan_job)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )
    else:
        logger.info(f"Scan {scan_job.id} is being handled by brain service (session_id: {scan_job.brain_session_id}), skipping Runner path")
    
    # Enqueue dependency scan jobs for PRO and ADVANCED scans (Universal Path)
    # This ensures dependency scans run regardless of whether Brain or Runner orchestrates the main scan
    try:
        scan_level_value = scan.scan_level.value if hasattr(scan.scan_level, 'value') else str(scan.scan_level).lower()
        logger.info(f"[DEPENDENCY-SCAN-CHECK] Checking eligibility for scan {scan_job.id} with level {scan_level_value}")
        
        if scan_level_value in ('pro', 'advanced'):
            try:
                from app.services.dependency_scanner import enqueue_dependency_scan_job
                from app.core.capabilities import check_capability
                
                # Check capability (will raise 403 if not allowed)
                try:
                    check_capability(db, tenant, current_user, "url_sca")
                    
                    callback_url = f"{settings.BACKEND_URL}/api/runner/callback" if hasattr(settings, 'BACKEND_URL') else None
                    logger.info(f"[DEPENDENCY-SCAN] Enqueuing URL-SCA job for {scan_level_value} scan {scan_job.id}")
                    
                    result = await enqueue_dependency_scan_job(
                        scan_id=scan_job.id,
                        job_type="url_sca",
                        target_url=project.target_url,
                        callback_url=callback_url,
                    )
                    
                    if result:
                        logger.info(f"[DEPENDENCY-SCAN] Successfully enqueued URL-SCA job for scan {scan_job.id}")
                    else:
                        logger.error(f"[DEPENDENCY-SCAN] Failed to enqueue URL-SCA job for scan {scan_job.id}")
                except HTTPException:
                    # Capability check failed - user doesn't have access, skip dependency scanning
                    logger.warning(f"[DEPENDENCY-SCAN] Skipping dependency scan for {scan_job.id} - capability check failed")
            except Exception as inner_e:
                logger.error(f"[DEPENDENCY-SCAN] Inner exception enqueuing dependency scan job for scan {scan_job.id}: {inner_e}", exc_info=True)
    except Exception as e:
        logger.error(f"[DEPENDENCY-SCAN] Exception in dependency scan block for scan {scan_job.id}: {e}", exc_info=True)
    
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
    
    # Log incoming payload for debugging (sanitized)
    logger.info(f"Quick scan request: project_id={payload.project_id}, target_url={'***' if payload.target_url else None}, scan_level={payload.scan_level}")
    
    # Defensive check: ensure current_user and user_id are valid BEFORE any processing
    if not current_user or not current_user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHENTICATED",
                "message": "Login required"
            }
        )
    
    try:
        is_admin = bool(getattr(current_user, "is_admin", False) or getattr(current_user, "is_superuser", False))
        from app.core.limits import get_effective_limits
        limits = get_effective_limits(db, tenant, current_user)

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
            
                # Enforce max_projects limit using centralized limits utility
                # Use get_all_projects_count() because projects are created before verification,
                # so we need to count ALL projects (not just verified) to prevent limit bypass
                from app.core.limits import check_limit_exceeded
                from app.core.project_utils import get_all_projects_count
            
                current_count = get_all_projects_count(db, tenant, current_user)
                check_limit_exceeded(
                    db=db,
                    tenant=tenant,
                    user=current_user,
                    limit_key="max_projects",
                    current_count=current_count,
                    limit_override=limits.get("max_projects"),
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
    
        # Lock/ensure root_domain
        try:
            ensure_project_root_domain(project, normalized_url, allow_admin_override=True, is_admin=is_admin)
            db.commit()
            db.refresh(project)
        except PermissionError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Domain verification / allowlist enforcement
        enforce_domain_verification_for_scan(
            db,
            project,
            normalized_url,
            is_admin=is_admin,
            user_id=current_user.id,
        )
    
        # Central enforcement (approval, plan/limits, domain lock/verification, quotas)
        enforce_scan_permissions(
            db=db,
            tenant=tenant,
            user=current_user,
            project=project,
            target_url=normalized_url,
            requested_level=payload.scan_level,
        )
    
        # Normalize scan_level to ScanLevel enum instance
        # normalize_scan_level() handles all input variations and returns ScanLevel enum
        # The TypeDecorator in ScanJob model will extract .value when binding to database
        from app.core.scan_utils import normalize_scan_level
        
        try:
            scan_level_enum = normalize_scan_level(payload.scan_level)
            logger.info(
                f"Normalized scan_level: '{payload.scan_level}' -> {scan_level_enum.name} "
                f"(value: '{scan_level_enum.value}')"
            )
        except ValueError as e:
            canonical_values = ['basic', 'pro', 'advanced']
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_SCAN_LEVEL",
                    "message": str(e),
                    "allowed": canonical_values,
                    "received": str(payload.scan_level),
                }
            )
        
        # Extract domain from normalized URL
        domain = _extract_domain_name(normalized_url) if normalized_url else (project.root_domain or None)
        
        # Map scan_level to tier (tier must match scan_level value)
        # tier is a legacy column that maps directly to scan_level: 'basic' -> 'basic', 'pro' -> 'pro', 'advanced' -> 'advanced'
        scan_level_value = scan_level_enum.value  # 'basic', 'pro', or 'advanced'
        
        # Validate scan_level_value is valid (defensive check)
        if scan_level_value not in {'basic', 'pro', 'advanced'}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_SCAN_LEVEL",
                    "message": f"Invalid scan_level value: '{scan_level_value}'. Must be one of: basic, pro, advanced",
                    "allowed": ['basic', 'pro', 'advanced'],
                    "received": scan_level_value,
                }
            )
        
        # Set tier to match scan_level value
        tier = scan_level_value  # 'basic', 'pro', or 'advanced'
        
        # Log scan creation with user_id for debugging
        logger.info(
            f"Quick scan user_id={current_user.id} project_id={project.id} "
            f"url={normalized_url} scan_level={scan_level_value} tier={tier} domain={domain}"
        )
    
        # Create scan job with ALL required fields
        # CRITICAL: Always set user_id, url, domain, tier, and created_at to prevent NotNullViolation errors
        # ScanLevelType.process_bind_param() will extract .value ('basic', 'pro', 'advanced')
        # ensuring database receives lowercase string, not enum name
        from datetime import datetime, timezone
        scan_job = ScanJob(
            user_id=current_user.id,  # REQUIRED: Always set user_id
            url=normalized_url,  # REQUIRED: Always set url
            domain=domain,  # Set domain (nullable, but set for consistency)
            tier=tier,  # REQUIRED: Always set tier (maps to scan_level: 'basic', 'pro', or 'advanced')
            project_id=project.id,
            scan_level=scan_level_enum,  # ScanLevel.BASIC, ScanLevel.PRO, or ScanLevel.ADVANCED
            status=ScanStatus.PENDING,
            created_at=datetime.now(timezone.utc),  # REQUIRED: Explicitly set created_at to prevent NotNullViolation
        )
    
        db.add(scan_job)
    
        # Wrap commit in try/except to catch DB errors and return structured JSON response
        try:
            db.commit()
            db.refresh(scan_job)
        except Exception as e:
            db.rollback()
            # Log detailed error information for debugging
        
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
        
            # If it's a SQLAlchemy DBAPI error, extract more details
            from sqlalchemy.exc import SQLAlchemyError, DBAPIError
            if isinstance(e, DBAPIError) and hasattr(e, 'orig'):
                error_details["db_error_code"] = getattr(e.orig, 'pgcode', None) if hasattr(e.orig, 'pgcode') else None
                error_details["db_error_message"] = str(e.orig) if e.orig else None
                logger.error(
                    f"Database error during scan_job commit: {error_details}",
                    exc_info=True,
                    extra={
                        "error_type": type(e).__name__,
                        "error_repr": repr(e),
                        "db_error_code": error_details.get("db_error_code"),
                        "db_error_message": error_details.get("db_error_message"),
                    }
                )
            else:
                logger.error(
                    f"Error during scan_job commit: {error_details}",
                    exc_info=True,
                    extra={
                        "error_type": type(e).__name__,
                        "error_repr": repr(e),
                    }
                )
        
            # Return structured JSON error response
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "DB_COMMIT_FAILED",
                    "message": "Failed to create scan job due to database error",
                    "error_type": error_details["error_type"],
                    "error_message": error_details["error_message"],
                }
            )
    
        # PR-4E: Start brain session instead of (or in addition to) Celery task
        if settings.BRAIN_SERVICE_ENABLED:
            try:
                from app.services.brain_client import get_brain_client
            except ImportError as e:
                logger.warning(f"Could not import brain_client: {e}. Brain service features will be disabled.")
                get_brain_client = None
        
        if settings.BRAIN_SERVICE_ENABLED and get_brain_client:
            try:
                # Use target_url from payload if provided, otherwise use project.target_url
                scan_target_url = normalized_url if normalized_url else project.target_url
            
                # Get stack_info (lightweight HTTP probe)
                stack_info = {}
                try:
                    import requests
                    resp = requests.head(scan_target_url, timeout=5, allow_redirects=True)
                    stack_info["http"] = {
                        "status_code": resp.status_code,
                        "headers": {
                            "server": resp.headers.get("Server"),
                            "content_type": resp.headers.get("Content-Type"),
                        },
                    }
                except Exception:
                    pass  # stack_info can be empty
            
                # Store target_url in stack_info for tracking
                stack_info["target_url"] = scan_target_url
            
                # Convert enum to string value
                scan_level_str = payload.scan_level.value if hasattr(payload.scan_level, 'value') else str(payload.scan_level)
            
                # Start brain session
                brain_client = get_brain_client()
                session_response = await brain_client.start_session(
                    scan_job_id=scan_job.id,
                    target_url=scan_target_url,
                    scan_level=scan_level_str,
                    org_id=tenant.id,
                    project_id=project.id,
                    stack_info=stack_info,
                    policy={
                        "max_steps": 20,
                        "max_runtime_sec": 3600,
                    },
                )
            
                # Store session_id in scan_job
                scan_job.brain_session_id = session_response.get("session_id")
                # Mark as RUNNING since brain session started successfully
                # The brain will manage the scan execution
                scan_job.status = ScanStatus.RUNNING
                if not scan_job.started_at:
                    scan_job.started_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(scan_job)
            
                # CRITICAL LOG: Must appear to confirm we reach PENDING creation
                logger.error(f"[QUICK-SCAN-PENDING-ENTRY] CRITICAL: About to create PENDING ToolResult records for quick scan {scan_job.id}")
            
                # CRITICAL: Create PENDING ToolResult records so UI can show tool status
                # Brain service will publish steps dynamically, but we need initial PENDING records
                try:
                    logger.info(f"[QUICK-SCAN-PENDING-STEP1] Importing modules for quick scan {scan_job.id}")
                    from app.core.database import SessionLocal
                    from app.core.tool_matrix import get_tools_for_level
                    from app.models.finding import ToolResult, ToolExecutionStatus
                    logger.info(f"[QUICK-SCAN-PENDING-STEP2] Modules imported successfully")
                    
                    logger.info(f"[QUICK-SCAN-PENDING-STEP3] Getting tools for level {payload.scan_level}")
                    expected_tools = get_tools_for_level(payload.scan_level)
                    logger.info(f"[QUICK-SCAN-PENDING-STEP4] Got {len(expected_tools)} expected tools")
                    pending_db = SessionLocal()
                    try:
                        pending_count = 0
                        logger.info(f"[QUICK-SCAN-PENDING-STEP5] Starting to create PENDING records")
                        for tool_config in expected_tools:
                            if not tool_config.get("enabled", True):
                                continue
                            
                            tool_id = tool_config.get("key") or tool_config.get("name")
                            
                            # Check if ToolResult already exists (idempotent)
                            existing = pending_db.query(ToolResult).filter(
                                ToolResult.scan_job_id == scan_job.id,
                                ToolResult.tool_name == tool_id
                            ).first()
                            
                            if not existing:
                                tool_result = ToolResult(
                                    scan_job_id=scan_job.id,
                                    tool_name=tool_id,
                                    status=ToolExecutionStatus.PENDING,
                                )
                                pending_db.add(tool_result)
                                pending_count += 1
                        
                        if pending_count > 0:
                            pending_db.commit()
                            logger.info(f"[QUICK-SCAN-PENDING] Created {pending_count} PENDING ToolResult records for quick scan {scan_job.id}")
                    except Exception as inner_e:
                        logger.error(f"[QUICK-SCAN-PENDING] Error creating PENDING records: {inner_e}", exc_info=True)
                        pending_db.rollback()
                    finally:
                        pending_db.close()
                except Exception as e:
                    logger.error(f"[QUICK-SCAN-PENDING] Failed to create PENDING ToolResult records: {e}", exc_info=True)
            
                logger.info(
                    f"Started brain session {scan_job.brain_session_id} for quick scan {scan_job.id}. "
                    f"Brain will own the closed-loop scanning process."
                )
                
                # Enqueue dependency scan jobs for PRO and ADVANCED scans (even when using Brain in quick scan)
                scan_level_value = payload.scan_level.value if hasattr(payload.scan_level, 'value') else str(payload.scan_level).lower()
                if scan_level_value in ('pro', 'advanced'):
                    try:
                        from app.services.dependency_scanner import enqueue_dependency_scan_job
                        from app.core.capabilities import check_capability
                        
                        # Check capability (will raise 403 if not allowed)
                        try:
                            check_capability(db, tenant, current_user, "url_sca")
                            
                            callback_url = f"{settings.BACKEND_URL}/api/runner/callback" if hasattr(settings, 'BACKEND_URL') else None
                            logger.info(f"[DEPENDENCY-SCAN] Enqueuing URL-SCA job for {scan_level_value} quick scan {scan_job.id} (Brain-based)")
                            
                            result = await enqueue_dependency_scan_job(
                                scan_id=scan_job.id,
                                job_type="url_sca",
                                target_url=scan_target_url,
                                callback_url=callback_url,
                            )
                            
                            if result:
                                logger.info(f"[DEPENDENCY-SCAN] Successfully enqueued URL-SCA job for quick scan {scan_job.id} (Brain-based)")
                            else:
                                logger.error(f"[DEPENDENCY-SCAN] Failed to enqueue URL-SCA job for quick scan {scan_job.id} (Brain-based)")
                        except HTTPException:
                            # Capability check failed - user doesn't have access, skip dependency scanning
                            logger.warning(f"[DEPENDENCY-SCAN] Skipping dependency scan for quick scan {scan_job.id} - capability check failed")
                    except Exception as e:
                        logger.error(f"[DEPENDENCY-SCAN] Exception enqueuing dependency scan job for quick scan {scan_job.id}: {e}", exc_info=True)
                        # Don't fail the scan if dependency scanning fails
                
                # CRITICAL: Return early after successful brain session creation to prevent Runner path execution
                logger.info(f"[QUICK-SCAN] Brain session created successfully for scan {scan_job.id}, returning early (Brain will handle execution)")
                return QuickScanResponse(
                    project_id=project.id,
                    scan_id=scan_job.id,
                )
            except Exception as e:
                # Log the error with full details for debugging
                error_detail = str(e) if str(e) else repr(e)
                if not error_detail:
                    error_detail = f"Unknown error: {type(e).__name__}"
                
                # CRITICAL: Log full error details including connection info
                logger.error(
                    f"[BRAIN-SESSION-FAILED] Failed to start brain session for scan {scan_job.id}: {error_detail}. "
                    f"BRAIN_SERVICE_URL={settings.BRAIN_SERVICE_URL}, BRAIN_URL={settings.BRAIN_URL}, "
                    f"BRAIN_SERVICE_ENABLED={settings.BRAIN_SERVICE_ENABLED}, Error type: {type(e).__name__}",
                    exc_info=True
                )
                
                # If brain session fails and BRAIN_REQUIRED=true, fail the scan
                if settings.BRAIN_REQUIRED:
                    error_msg = f"Failed to start brain session: {error_detail}. Brain service is required (BRAIN_REQUIRED=true)."
                    scan_job.status = ScanStatus.FAILED
                    scan_job.error_message = error_msg
                    db.commit()
                    db.refresh(scan_job)
                else:
                    # Brain not required, fall back to legacy Celery orchestrator
                    logger.warning(
                        f"Brain session failed but BRAIN_REQUIRED=false, falling back to Celery/Runner. "
                        f"Error: {error_detail}"
                    )
                    # Fall through to Celery queueing below
        else:
            logger.info("Brain service disabled, using Runner-based execution path")
            # Fall through to Runner path below
    
        # Default path: Use Runner via Redis streams (when brain is disabled or not required)
        brain_enabled = settings.BRAIN_SERVICE_ENABLED
        brain_required = settings.BRAIN_REQUIRED
        has_brain_session = bool(scan_job.brain_session_id)
        
        logger.info(
            f"[QUICK-SCAN] Scan {scan_job.id}: brain_enabled={brain_enabled}, "
            f"brain_required={brain_required}, has_brain_session={has_brain_session}, "
            f"will_use_runner={not brain_enabled or (not brain_required and not has_brain_session)}"
        )
        
        if not brain_enabled or (not brain_required and not has_brain_session):
            # Use Runner via Redis streams
            logger.info(f"[QUICK-SCAN] Publishing quick scan steps to Runner for scan {scan_job.id}")
            try:
                from app.services.runner_client import publish_scan_steps_to_runner
            
                # Publish step requests to Runner
                logger.info(f"[QUICK-SCAN] Calling publish_scan_steps_to_runner for scan {scan_job.id}")
                success = await publish_scan_steps_to_runner(
                    scan_job_id=scan_job.id,
                    target_url=project.target_url,
                    scan_level=payload.scan_level,
                    org_id=tenant.id,
                    project_id=project.id,
                    background_tasks=background_tasks,
                )
                
                logger.info(f"[QUICK-SCAN] publish_scan_steps_to_runner returned success={success} for scan {scan_job.id}")
            
                if success:
                    scan_job.status = ScanStatus.RUNNING
                    scan_job.started_at = datetime.now(timezone.utc)
                    db.commit()
                    db.refresh(scan_job)
                    logger.info(f"[QUICK-SCAN] Quick scan {scan_job.id} started via Runner (steps published to Redis streams)")
                else:
                    error_msg = "Failed to publish scan steps to Runner. Make sure Runner service is running and Redis is accessible."
                    logger.error(f"[QUICK-SCAN] {error_msg} for scan {scan_job.id}")
                    scan_job.status = ScanStatus.FAILED
                    scan_job.error_message = error_msg
                    db.commit()
                    db.refresh(scan_job)
                    logger.warning(f"[QUICK-SCAN] Quick scan created but Runner publishing failed: {error_msg}")
                
                # Enqueue dependency scan jobs for PRO and ADVANCED scans (Runner path for quick scan)
                scan_level_value = payload.scan_level.value if hasattr(payload.scan_level, 'value') else str(payload.scan_level).lower()
                if scan_level_value in ('pro', 'advanced'):
                    try:
                        from app.services.dependency_scanner import enqueue_dependency_scan_job
                        from app.core.capabilities import check_capability
                        
                        # Check capability (will raise 403 if not allowed)
                        try:
                            check_capability(db, tenant, current_user, "url_sca")
                            
                            callback_url = f"{settings.BACKEND_URL}/api/runner/callback" if hasattr(settings, 'BACKEND_URL') else None
                            logger.info(f"[DEPENDENCY-SCAN] Enqueuing URL-SCA job for {scan_level_value} quick scan {scan_job.id} (Runner-based)")
                            
                            result = await enqueue_dependency_scan_job(
                                scan_id=scan_job.id,
                                job_type="url_sca",
                                target_url=project.target_url,
                                callback_url=callback_url,
                            )
                            
                            if result:
                                logger.info(f"[DEPENDENCY-SCAN] Successfully enqueued URL-SCA job for quick scan {scan_job.id} (Runner-based)")
                            else:
                                logger.error(f"[DEPENDENCY-SCAN] Failed to enqueue URL-SCA job for quick scan {scan_job.id} (Runner-based)")
                        except HTTPException:
                            # Capability check failed - user doesn't have access, skip dependency scanning
                            logger.warning(f"[DEPENDENCY-SCAN] Skipping dependency scan for quick scan {scan_job.id} - capability check failed")
                    except Exception as e:
                        logger.error(f"[DEPENDENCY-SCAN] Exception enqueuing dependency scan job for quick scan {scan_job.id}: {e}", exc_info=True)
                        # Don't fail the scan if dependency scanning fails
            except Exception as e:
                error_msg = f"Failed to publish scan steps to Runner: {str(e)}"
                logger.error(f"[QUICK-SCAN] Exception publishing scan steps for scan {scan_job.id}: {error_msg}", exc_info=True)
                scan_job.status = ScanStatus.FAILED
                scan_job.error_message = error_msg
                db.commit()
                db.refresh(scan_job)
                logger.warning(f"[QUICK-SCAN] Quick scan created but Runner publishing failed: {error_msg}")
        else:
            # Brain is enabled and has session, or brain is required but no session
            logger.warning(
                f"[QUICK-SCAN] Scan {scan_job.id} not using Runner path: "
                f"brain_enabled={brain_enabled}, brain_required={brain_required}, "
                f"has_brain_session={has_brain_session}"
            )
            # If brain is required but not available, fail the scan
            if brain_required and not has_brain_session:
                error_msg = "Brain service is required but no session was created"
                logger.error(f"[QUICK-SCAN] {error_msg} for scan {scan_job.id}")
                scan_job.status = ScanStatus.FAILED
                scan_job.error_message = error_msg
                db.commit()
                db.refresh(scan_job)
            elif has_brain_session:
                # Brain session exists, should have returned early above
                # This shouldn't happen, but if it does, log it
                logger.warning(
                    f"[QUICK-SCAN] Scan {scan_job.id} has brain session but reached Runner path check. "
                    f"This should not happen - brain session should have returned early."
                )
            else:
                # Brain enabled but no session and not required - this is unexpected
                logger.error(
                    f"[QUICK-SCAN] Scan {scan_job.id}: Brain enabled but no session created and not required. "
                    f"This is unexpected - should have used Runner path."
                )
                # Fallback: Try to use Runner anyway
                logger.info(f"[QUICK-SCAN] Attempting fallback to Runner for scan {scan_job.id}")
                try:
                    from app.services.runner_client import publish_scan_steps_to_runner
                    success = await publish_scan_steps_to_runner(
                        scan_job_id=scan_job.id,
                        target_url=project.target_url,
                        scan_level=payload.scan_level,
                        org_id=tenant.id,
                        project_id=project.id,
                        background_tasks=background_tasks,
                    )
                    if success:
                        scan_job.status = ScanStatus.RUNNING
                        if not scan_job.started_at:
                            scan_job.started_at = datetime.now(timezone.utc)
                        db.commit()
                        db.refresh(scan_job)
                        logger.info(f"[QUICK-SCAN] Fallback Runner publishing succeeded for scan {scan_job.id}")
                    else:
                        error_msg = "Failed to publish scan steps to Runner (fallback)"
                        logger.error(f"[QUICK-SCAN] {error_msg} for scan {scan_job.id}")
                        scan_job.status = ScanStatus.FAILED
                        scan_job.error_message = error_msg
                        db.commit()
                        db.refresh(scan_job)
                except Exception as fallback_error:
                    logger.error(f"[QUICK-SCAN] Fallback Runner publishing failed for scan {scan_job.id}: {fallback_error}", exc_info=True)
                    scan_job.status = ScanStatus.FAILED
                    scan_job.error_message = f"Both Brain and Runner publishing failed: {str(fallback_error)}"
                    db.commit()
                    db.refresh(scan_job)
    
        # Always return a response (Brain path or Runner path)
        logger.info(f"[QUICK-SCAN] Returning response for scan {scan_job.id}, status={scan_job.status}")
        return QuickScanResponse(
            project_id=project.id,
            scan_id=scan_job.id,
        )
    except HTTPException as e:
        # Log 4xx errors with detail before re-raising
        detail_str = str(e.detail) if e.detail else "No detail provided"
        logger.warning(f"Quick scan 4xx: status={e.status_code} detail={detail_str}")
        raise
    except Exception as e:
        # Log unexpected errors before re-raising with full context
        error_type = type(e).__name__
        error_msg = str(e) if str(e) else repr(e)
        logger.error(
            f"[QUICK-SCAN-ERROR] Quick scan crashed: {error_type}: {error_msg}",
            exc_info=True,
            extra={
                "error_type": error_type,
                "error_message": error_msg,
                "error_repr": repr(e),
            }
        )
        # Re-raise as HTTPException to return proper error response
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "SCAN_CREATION_FAILED",
                "message": f"Failed to create scan: {error_msg}",
                "error_type": error_type,
            }
        )


@router.get("/{scan_id}/artifacts", response_model=ScanArtifactsResponse)
async def get_scan_artifacts(
    scan_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get scan artifacts (dependency scanning results) for a scan.
    
    Returns all artifacts (URL-SCA and Repo-SCA) associated with the scan.
    """
    from app.models.scan_artifact import ScanArtifact
    
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
            detail=f"Scan not found. The scan ID '{scan_id}' does not exist or you don't have permission to access it."
        )
    
    # Get artifacts
    artifacts = db.query(ScanArtifact).filter(
        ScanArtifact.scan_id == scan_id
    ).order_by(ScanArtifact.created_at).all()
    
    logger.info(f"Retrieved {len(artifacts)} artifacts for scan {scan_id}")
    
    return ScanArtifactsResponse(
        items=[
            ScanArtifactResponse(
                id=artifact.id,
                scan_id=artifact.scan_id,
                type=artifact.type,
                payload=artifact.payload,
                created_at=artifact.created_at,
            )
            for artifact in artifacts
        ]
    )



@router.get("/{scan_id}/inventory")
async def get_scan_inventory(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get enumeration inventory for a scan.
    Returns the asset inventory collected during the enumeration phase.
    """
    # Verify scan exists and user has access
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
    if not scan_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan not found: {scan_id}"
        )
    
    # Check user access (user owns the scan or scan's project belongs to user's tenant)
    has_access = False
    if scan_job.user_id == current_user.id:
        has_access = True
    elif scan_job.project_id:
        project = db.query(Project).filter(Project.id == scan_job.project_id).first()
        # Safer check for tenant_id
        user_tenant_id = getattr(current_user, "tenant_id", None)
        if project and user_tenant_id and project.tenant_id == user_tenant_id:
            has_access = True
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get inventory from scan_artifacts
    from app.models.scan_artifact import ScanArtifact
    from sqlalchemy import and_
    
    artifact = db.query(ScanArtifact).filter(
        and_(
            ScanArtifact.scan_id == scan_id,
            ScanArtifact.type == "asset_inventory"
        )
    ).first()
    
    if not artifact:
        # Fallback: Try to build inventory from HTTPX findings if inventory artifact doesn't exist
        # This handles cases where enumeration ran but inventory wasn't posted
        from app.models.finding import Finding
        httpx_findings = db.query(Finding).filter(
            Finding.scan_job_id == scan_id,
            Finding.tool_name == "httpx"
        ).limit(100).all()
        
        if httpx_findings:
            # Extract tech from HTTPX findings
            technologies = []
            httpx_data = {}
            for finding in httpx_findings:
                if finding.raw_data:
                    try:
                        import json as json_module
                        raw = json_module.loads(finding.raw_data) if isinstance(finding.raw_data, str) else finding.raw_data
                        if isinstance(raw, dict):
                            tech_list = raw.get("tech", [])
                            if tech_list and isinstance(tech_list, list):
                                for tech_item in tech_list:
                                    if isinstance(tech_item, str) and tech_item not in technologies:
                                        technologies.append(tech_item)
                                    elif isinstance(tech_item, dict):
                                        tech_name = tech_item.get("name") or tech_item.get("value") or ""
                                        if tech_name and tech_name not in technologies:
                                            technologies.append(tech_name)
                            # Extract other httpx data from first finding
                            if not httpx_data.get("final_url") and finding.url:
                                httpx_data["final_url"] = finding.url
                            if not httpx_data.get("status") and raw.get("status_code"):
                                httpx_data["status"] = raw.get("status_code")
                            if not httpx_data.get("title") and raw.get("title"):
                                httpx_data["title"] = raw.get("title")
                    except Exception as e:
                        logger.debug(f"Failed to extract tech from httpx finding: {e}")
                        continue
            
            # Build minimal inventory structure
            if technologies or httpx_data:
                inventory_payload = {
                    "target": scan_job.url or "",
                    "scope": {
                        "allowed_hosts": [],
                        "start_url": scan_job.url or "",
                        "final_url": httpx_data.get("final_url", scan_job.url or "")
                    },
                    "discovery": {
                        "httpx": {
                            "status": httpx_data.get("status", 0),
                            "title": httpx_data.get("title", ""),
                            "tech": technologies,
                            "final_url": httpx_data.get("final_url", scan_job.url or "")
                        }
                    }
                }
                return {
                    "scan_id": scan_id,
                    "inventory": inventory_payload,
                    "created_at": scan_job.created_at
                }
        
        return {"scan_id": scan_id, "inventory": None}
    
    # Ensure tech array is populated in inventory if missing
    inventory_payload = artifact.payload
    if isinstance(inventory_payload, dict):
        discovery = inventory_payload.get("discovery", {})
        httpx_data = discovery.get("httpx", {})
        
        # If tech array is missing or empty, try to populate from HTTPX findings
        if not httpx_data.get("tech") or len(httpx_data.get("tech", [])) == 0:
            from app.models.finding import Finding
            httpx_findings = db.query(Finding).filter(
                Finding.scan_job_id == scan_id,
                Finding.tool_name == "httpx"
            ).limit(100).all()
            
            technologies = []
            for finding in httpx_findings:
                if finding.raw_data:
                    try:
                        import json as json_module
                        raw = json_module.loads(finding.raw_data) if isinstance(finding.raw_data, str) else finding.raw_data
                        if isinstance(raw, dict):
                            tech_list = raw.get("tech", [])
                            if tech_list and isinstance(tech_list, list):
                                for tech_item in tech_list:
                                    if isinstance(tech_item, str) and tech_item not in technologies:
                                        technologies.append(tech_item)
                                    elif isinstance(tech_item, dict):
                                        tech_name = tech_item.get("name") or tech_item.get("value") or ""
                                        if tech_name and tech_name not in technologies:
                                            technologies.append(tech_name)
                    except Exception as e:
                        logger.debug(f"Failed to extract tech from httpx finding: {e}")
                        continue
            
            if technologies:
                httpx_data["tech"] = technologies
                discovery["httpx"] = httpx_data
                inventory_payload["discovery"] = discovery
                logger.info(f"Populated {len(technologies)} technologies in inventory from HTTPX findings")
    
    return {
        "scan_id": scan_id,
        "inventory": inventory_payload,
        "created_at": artifact.created_at
    }


@router.get("/{scan_id}/tech-stack")
async def get_scan_tech_stack(
    scan_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get aggregated tech stack and dependencies for a scan.
    
    Aggregates data from:
    1. url_sca artifact (primary source - from wappalyzer/retire.js)
    2. ToolResult.meta from various tools (fallback aggregation)
    3. Findings from tech-detection tools
    
    Returns normalized tech/deps payload matching URLSCAArtifact interface.
    This ensures Tech & Dependencies tab always shows data, even when
    dependency scanning tools fail or aren't triggered.
    """
    logger.warning(f"[TECH-STACK-ENTRY] get_scan_tech_stack called for scan_id={scan_id}")
    from app.models.scan_artifact import ScanArtifact
    from app.models.finding import ToolResult, Finding
    
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
            detail=f"Scan not found. The scan ID '{scan_id}' does not exist or you don't have permission to access it."
        )
    
    # Try url_sca artifact first (primary source - created by dependency_scanner.py)
    url_sca_artifact = db.query(ScanArtifact).filter(
        ScanArtifact.scan_id == scan_id,
        ScanArtifact.type == "url_sca"
    ).first()
    
    if url_sca_artifact and url_sca_artifact.payload:
        # Return artifact payload directly (already in correct URLSCAArtifact format)
        logger.info(f"[TECH-STACK] Returning url_sca artifact for scan {scan_id}")
        payload = url_sca_artifact.payload
        # Ensure payload is a dict (JSONB columns are already dicts, but be safe)
        if isinstance(payload, str):
            import json as json_module
            payload = json_module.loads(payload)
        return payload
    
    # Fallback: Aggregate from ToolResult.meta (when wappalyzer/retire didn't run or failed)
    logger.warning(f"[TECH-STACK] No url_sca artifact for scan {scan_id}, aggregating from tool results and findings")
    
    tool_results = db.query(ToolResult).filter(
        ToolResult.scan_job_id == scan_id
    ).all()
    
    # Initialize aggregated data structures
    fingerprint = {
        "status": 0,
        "title": "",
        "server": "",
        "cdn": "",
        "technologies": [],
        "confidence": 0.0
    }
    client_dependencies = []
    findings = []
    technologies = []
    
    logger.warning(f"[TECH-STACK-DEBUG] Starting aggregation: {len(tool_results)} tool results found")
    
    # Aggregate from each tool's meta
    for tr in tool_results:
        meta = tr.meta or {}
        
        # httpx: extract headers/server info and tech detection
        if tr.tool_name == "httpx" and meta:
            if "status_code" in meta:
                fingerprint["status"] = meta["status_code"]
            if "title" in meta:
                fingerprint["title"] = meta["title"]
            if "server" in meta:
                fingerprint["server"] = meta["server"]
            if "cdn" in meta:
                fingerprint["cdn"] = meta["cdn"]
            # httpx may include tech-detect results
            if "technologies" in meta and isinstance(meta["technologies"], list):
                technologies.extend(meta["technologies"])
        
        # wappalyzer: extract detected technologies
        if tr.tool_name == "wappalyzer" and meta:
            if "technologies" in meta and isinstance(meta["technologies"], list):
                technologies.extend(meta["technologies"])
        
        # retire: extract client dependencies and vulnerability findings
        if tr.tool_name == "retire" and meta:
            if "client_dependencies" in meta and isinstance(meta["client_dependencies"], list):
                client_dependencies.extend(meta["client_dependencies"])
            if "findings" in meta and isinstance(meta["findings"], list):
                findings.extend(meta["findings"])
    
    # Also aggregate from Findings table for httpx, nmap, and sslscan (they store results as Findings, not in meta)
    from app.models.finding import Finding
    httpx_findings = db.query(Finding).filter(
        Finding.scan_job_id == scan_id,
        Finding.tool_name == "httpx"
    ).all()
    nmap_findings = db.query(Finding).filter(
        Finding.scan_job_id == scan_id,
        Finding.tool_name == "nmap"
    ).all()
    sslscan_findings = db.query(Finding).filter(
        Finding.scan_job_id == scan_id,
        Finding.tool_name == "sslscan"
    ).all()
    
    # Extract info from httpx findings (status_code, title, server, technologies)
    # Prioritize findings with status 200 that match the target URL, then collect all technologies from all findings
    logger.warning(f"[TECH-STACK-DEBUG] Found {len(httpx_findings)} httpx findings for scan {scan_id}")
    
    # CRITICAL: Force extraction to run - ensure httpx_findings are processed
    if httpx_findings and len(httpx_findings) > 0:
        logger.warning(f"[TECH-STACK-DEBUG] Processing {len(httpx_findings)} httpx findings for extraction")
        # Get target URL for matching
        target_url = scan_job.url or ""
        target_domain = ""
        if target_url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(target_url)
                target_domain = parsed.netloc or parsed.hostname or ""
            except:
                pass
        
        # Sort findings: prioritize status 200 that match target domain, then any status 200, then by status code descending
        def sort_key(f):
            score = 0
            if f.raw_data:
                try:
                    import json as json_module
                    raw = json_module.loads(f.raw_data) if isinstance(f.raw_data, str) else f.raw_data
                    if isinstance(raw, dict):
                        status = raw.get("status_code", 0)
                        url = raw.get("url", "")
                        # Prioritize status 200
                        if status == 200:
                            score += 1000
                            # Extra priority if URL matches target domain
                            if target_domain and target_domain in url:
                                score += 500
                        # Then by status code
                        score += status
                except:
                    pass
            return score
        
        sorted_findings = sorted(httpx_findings, key=sort_key, reverse=True)
        logger.warning(f"[TECH-STACK-DEBUG] Sorted {len(sorted_findings)} findings, processing for extraction")
        
        primary_finding_processed = False
        processed_count = 0
        for f in sorted_findings:
            # Extract from raw_data if available (backend stores "raw" field as raw_data JSON string)
            if f.raw_data:
                try:
                    # raw_data is stored as JSON string of the "raw" field value from httpx parser
                    # The httpx parser stores full JSON in "raw", backend does: json.dumps(finding_data.get("raw", finding_data))
                    # So raw_data contains the httpx JSON object directly
                    import json as json_module
                    raw = json_module.loads(f.raw_data) if isinstance(f.raw_data, str) else f.raw_data
                    # raw should be the httpx JSON object directly (not nested)
                    actual_data = raw
                    
                    if not isinstance(actual_data, dict):
                        continue
                    
                    # Extract status code (only set from primary finding or if not set yet)
                    status_val = actual_data.get("status_code")
                    if status_val is not None and (not primary_finding_processed or fingerprint["status"] == 0):
                        fingerprint["status"] = int(status_val)
                        logger.warning(f"[TECH-STACK-DEBUG] Extracted status_code={status_val}")
                    
                    # Extract title (only set from primary finding or if not set yet)
                    title_val = actual_data.get("title")
                    if title_val and isinstance(title_val, str) and (not primary_finding_processed or not fingerprint["title"]):
                        fingerprint["title"] = title_val
                        logger.warning(f"[TECH-STACK-DEBUG] Extracted title={title_val[:50]}")
                    
                    # Extract server header (httpx uses "webserver" field) (only set from primary finding or if not set yet)
                    server_val = actual_data.get("webserver")
                    if server_val and isinstance(server_val, str) and (not primary_finding_processed or not fingerprint["server"]):
                        fingerprint["server"] = server_val
                        logger.warning(f"[TECH-STACK-DEBUG] Extracted webserver={server_val}")
                    
                    # Extract CDN (httpx uses "cdn" field)
                    cdn_val = actual_data.get("cdn")
                    if cdn_val and isinstance(cdn_val, str) and (not primary_finding_processed or not fingerprint["cdn"]):
                        fingerprint["cdn"] = cdn_val
                        logger.warning(f"[TECH-STACK-DEBUG] Extracted cdn={cdn_val}")
                    
                    # Extract technologies from tech field (httpx tech-detect output) - collect from ALL findings
                    tech_list = actual_data.get("tech")
                    if tech_list and isinstance(tech_list, list):
                        logger.warning(f"[TECH-STACK-DEBUG] Found {len(tech_list)} technologies in httpx finding: {tech_list}")
                        for tech_item in tech_list:
                            if isinstance(tech_item, str):
                                technologies.append({
                                    "name": tech_item,
                                    "version": None,
                                    "confidence": 0.8,
                                })
                            elif isinstance(tech_item, dict):
                                tech_name = tech_item.get("name") or tech_item.get("value") or ""
                                if tech_name:
                                    technologies.append({
                                        "name": tech_name,
                                        "version": tech_item.get("version"),
                                        "confidence": 0.8,
                                    })
                        logger.warning(f"[TECH-STACK-DEBUG] Added {len(tech_list)} technologies to list, total now: {len(technologies)}")
                    
                    if not primary_finding_processed:
                        primary_finding_processed = True
                    processed_count += 1
                except Exception as e:
                    logger.error(f"[TECH-STACK-DEBUG] Failed to parse httpx finding raw_data: {e}", exc_info=True)
                    continue
        
        logger.warning(f"[TECH-STACK-DEBUG] Processed {processed_count} findings. Fingerprint: status={fingerprint['status']}, title={fingerprint['title'][:30] if fingerprint['title'] else 'N/A'}, server={fingerprint['server']}, tech_count={len(technologies)}")
        
        # Also extract from evidence/description if raw_data not available
        if not fingerprint["status"]:
            for f in sorted_findings:
                if f.evidence and not fingerprint["status"]:
                    # Try to extract status code from evidence like "Status: 200"
                    import re
                    status_match = re.search(r'Status:\s*(\d+)', f.evidence)
                    if status_match:
                        fingerprint["status"] = int(status_match.group(1))
                        break
    else:
        logger.warning(f"[TECH-STACK-DEBUG] No httpx findings found for scan {scan_id}")
    
    # Extract port/service info from nmap findings for fingerprint
    if nmap_findings:
        # Add nmap results summary to fingerprint
        open_ports = []
        for f in nmap_findings:
            if f.raw_data:
                try:
                    import json as json_module
                    raw = json_module.loads(f.raw_data) if isinstance(f.raw_data, str) else f.raw_data
                    port = raw.get("port") or raw.get("portid")
                    service = raw.get("service") or raw.get("service_name")
                    if port:
                        open_ports.append(f"Port {port}" + (f" ({service})" if service else ""))
                except:
                    pass
        if open_ports:
            fingerprint["open_ports"] = open_ports[:10]  # Limit to first 10
    
    # Extract TLS info from sslscan findings
    if sslscan_findings:
        tls_issues = []
        for f in sslscan_findings:
            if f.title and "TLS" in f.title.upper() or "SSL" in f.title.upper() or "certificate" in f.title.lower():
                tls_issues.append(f.title)
        if tls_issues:
            fingerprint["tls_issues"] = tls_issues[:10]  # Limit to first 10
    
    # Deduplicate technologies by (name, version) tuple
    seen_tech = set()
    unique_tech = []
    for tech in technologies:
        if not isinstance(tech, dict):
            continue
        tech_key = (tech.get("name"), tech.get("version"))
        if tech_key not in seen_tech and tech.get("name"):
            seen_tech.add(tech_key)
            # Ensure required fields
            unique_tech.append({
                "name": tech.get("name"),
                "version": tech.get("version"),
                "confidence": tech.get("confidence", 0.8),
            })
    
    fingerprint["technologies"] = unique_tech
    logger.warning(f"[TECH-STACK] Aggregated result: status={fingerprint['status']}, title={fingerprint['title'][:50] if fingerprint['title'] else 'N/A'}, server={fingerprint['server']}, technologies={len(unique_tech)}, client_deps={len(client_dependencies)}")
    
    # Calculate confidence score based on data quality
    confidence = 0.0
    if fingerprint["status"] == 200:
        confidence += 0.3
    if fingerprint["title"]:
        confidence += 0.1
    if unique_tech:
        confidence += min(0.4, len(unique_tech) * 0.1)
    if client_dependencies:
        confidence += min(0.2, len(client_dependencies) * 0.1)
    fingerprint["confidence"] = min(1.0, confidence)
    
    # Get target URL from scan or project
    target_url = scan_job.url
    if not target_url and scan_job.project:
        target_url = scan_job.project.target_url
    if not target_url:
        target_url = ""
    
    # Return aggregated payload in URLSCAArtifact format
    result = {
        "mode": "url_sca",
        "target": target_url,
        "fingerprint": fingerprint,
        "client_dependencies": client_dependencies,
        "findings": findings,
        "meta": {
            "tool_versions": {},
            "duration_ms": 0,
            "aggregated": True,  # Flag to indicate this was aggregated from ToolResult.meta, not from artifact
        }
    }
    # CRITICAL DEBUG: Log what we're actually returning
    logger.error(f"[TECH-STACK-RETURN-CRITICAL] Returning for scan {scan_id}: status={fingerprint['status']}, title='{fingerprint['title']}', server='{fingerprint['server']}', tech_count={len(fingerprint['technologies'])}")
    logger.error(f"[TECH-STACK-RETURN-CRITICAL] Fingerprint dict keys: {list(fingerprint.keys())}")
    logger.error(f"[TECH-STACK-RETURN-CRITICAL] Result fingerprint status: {result['fingerprint']['status']}")
    logger.warning(f"[TECH-STACK-RETURN] Returning result for scan {scan_id}: status={fingerprint['status']}, title={fingerprint['title'][:30] if fingerprint['title'] else 'N/A'}, server={fingerprint['server']}, tech_count={len(fingerprint['technologies'])}")
    return result


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
            detail=f"Scan not found. The scan ID '{scan_id}' does not exist or you don't have permission to access it."
        )

    # CRITICAL: Check for stuck tools and update scan completion status
    # This ensures that tools stuck in RUNNING status are marked as TIMED_OUT
    # and scans with all tools done are marked as COMPLETED
    if scan_job.status in (ScanStatus.RUNNING, ScanStatus.QUEUED):
        try:
            from app.api.runner_ingest import _check_and_update_scan_completion
            _check_and_update_scan_completion(scan_job, db)
            db.refresh(scan_job)  # Refresh to get updated status
        except Exception as e:
            logger.warning(f"Failed to check scan completion for {scan_id}: {e}")

    _log_scan_state("H2", "get_scan:loaded", scan_job)
    
    # PR-4E: If brain session exists, fetch latest status from brain
    status_source = "db"  # Default to DB, will be set to "brain" if brain is available
    status_reason = None
    brain_session_response: Optional[BrainSessionResponse] = None
    all_tools_done = False  # Initialize to prevent UnboundLocalError if brain_session_id is None
    
    if scan_job.brain_session_id:
        brain_fetch_start = datetime.now(timezone.utc)
        try:
            if settings.BRAIN_SERVICE_ENABLED:
                try:
                    from app.services.brain_client import get_brain_client
                    brain_client = get_brain_client()
                except ImportError as e:
                    logger.warning(f"Could not import brain_client: {e}. Skipping brain session status fetch.")
                    brain_client = None
                
                if brain_client:
                    logger.info(
                        "Fetching brain session status",
                        extra={
                            "scan_id": scan_id,
                            "brain_session_id": scan_job.brain_session_id,
                            "org_id": tenant.id,
                            "project_id": scan_job.project_id,
                        }
                    )
                    
                    # Wrap brain client call with timeout to prevent hanging
                    # Use shorter timeout (10s) for get_session to avoid blocking scan page loads
                    import asyncio
                    try:
                        session_status_raw = await asyncio.wait_for(
                            brain_client.get_session(
                                session_id=scan_job.brain_session_id,
                                org_id=tenant.id,
                                project_id=scan_job.project_id,
                            ),
                            timeout=10.0  # 10 second timeout for brain status fetch
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"Brain session status fetch timed out after 10s for scan {scan_id}, continuing without brain status",
                            extra={
                                "scan_id": scan_id,
                                "brain_session_id": scan_job.brain_session_id,
                            }
                        )
                        session_status_raw = None  # Continue without brain status
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch brain session status for scan {scan_id}: {e}, continuing without brain status",
                            extra={
                                "scan_id": scan_id,
                                "brain_session_id": scan_job.brain_session_id,
                                "error": str(e),
                            }
                        )
                        session_status_raw = None  # Continue without brain status
                
                brain_fetch_latency_ms = (datetime.now(timezone.utc) - brain_fetch_start).total_seconds() * 1000
                
                # Handle case where session doesn't exist (404 - may have expired or never existed)
                if session_status_raw is None:
                    logger.debug(
                        "Brain session not found - may have expired or never existed",
                        extra={
                            "scan_id": scan_id,
                            "brain_session_id": scan_job.brain_session_id,
                            "latency_ms": round(brain_fetch_latency_ms, 2),
                        }
                    )
                    status_source = "db"
                    status_reason = "session_not_found"
                    # Continue with DB status - don't fail the request
                # Parse with Pydantic model (handles validation and datetime parsing)
                elif isinstance(session_status_raw, dict):
                    try:
                        brain_session_response = BrainSessionResponse(**session_status_raw)
                        status_source = "brain"
                    
                        logger.info(
                            "Brain session status fetched successfully",
                            extra={
                            "scan_id": scan_id,
                            "brain_session_id": scan_job.brain_session_id,
                                "brain_status": brain_session_response.status.value,
                                "latency_ms": round(brain_fetch_latency_ms, 2),
                                "progress_percentage": brain_session_response.progress_percentage,
                                "current_step_count": brain_session_response.current_step_count,
                            }
                        )
                    except Exception as parse_error:
                        # Brain returned malformed payload - log but don't crash
                        logger.warning(
                            "Brain session response validation failed, using raw status",
                            extra={
                                "scan_id": scan_id,
                                "brain_session_id": scan_job.brain_session_id,
                                "error": str(parse_error),
                                "raw_response_keys": list(session_status_raw.keys()) if isinstance(session_status_raw, dict) else "not_dict",
                            },
                            exc_info=True
                        )
                        # Fallback: use raw dict
                        brain_status_raw = session_status_raw.get("status", "running") if isinstance(session_status_raw, dict) else "running"
                        status_source = "db"  # Can't trust brain response
                        status_reason = "brain_response_invalid"
                else:
                    # session_status_raw is not a dict (shouldn't happen, but handle gracefully)
                    logger.warning(
                        "Brain session returned unexpected type",
                        extra={
                            "scan_id": scan_id,
                            "brain_session_id": scan_job.brain_session_id,
                            "type": type(session_status_raw).__name__,
                        }
                    )
                    status_source = "db"
                    status_reason = "brain_response_invalid"
                
                # Update scan_job status based on brain session status
                if brain_session_response:
                    brain_status = brain_session_response.status
                elif session_status_raw is None:
                    # Session not found - use DB status
                    brain_status = None
                else:
                    # Fallback to raw status
                    brain_status = session_status_raw.get("status", "running") if isinstance(session_status_raw, dict) else "running"
                
                # Check if all tools are done (fallback if brain session status is stuck)
                from app.models.finding import ToolResult, ToolExecutionStatus
                all_tool_results = db.query(ToolResult).filter(
                    ToolResult.scan_job_id == scan_id
                ).all()
                
                # Get unique tool names and their latest status
                tool_statuses_dict = {}
                for tr in all_tool_results:
                    tool_name = tr.tool_name
                    if tool_name not in tool_statuses_dict or (tr.created_at and tool_statuses_dict[tool_name].created_at < tr.created_at):
                        tool_statuses_dict[tool_name] = tr
                
                # Check if all tools are in terminal states
                # Also check completed_at as fallback if status is None
                all_tools_done = True
                if tool_statuses_dict:
                    for tool_name, tr in tool_statuses_dict.items():
                        # If status is set, check it's in a terminal state
                        if tr.status:
                            if tr.status not in [
                            ToolExecutionStatus.COMPLETED,
                            ToolExecutionStatus.FAILED,
                            ToolExecutionStatus.SKIPPED,
                            ToolExecutionStatus.TIMED_OUT
                        ]:
                                all_tools_done = False
                                break
                        # If status is None but completed_at is set, consider it done
                        elif tr.completed_at is None:
                            all_tools_done = False
                            break
                else:
                    all_tools_done = False  # No tools yet
                
                logger.debug(
                    "Tool completion check",
                    extra={
                            "scan_id": scan_id,
                        "brain_status": brain_status.value if isinstance(brain_status, SessionStatus) else (str(brain_status) if brain_status is not None else "none"),
                            "all_tools_done": all_tools_done,
                        "tool_count": len(tool_statuses_dict),
                    }
                )
                
                # Status reconciliation: Core DB is the source of truth.
                # Brain session status is advisory only and MUST NOT override scan status in DB
                # (otherwise UI can show COMPLETED/FAILED while runner is still executing).
                if all_tools_done and scan_job.status in (ScanStatus.RUNNING, ScanStatus.QUEUED):
                    # Fallback: If all tools are done but scan status is still RUNNING, mark scan as completed
                    # This handles cases where brain session doesn't update status or Celery path completes
                    logger.info(
                        "Updating scan to COMPLETED (all tools done fallback)",
                        extra={
                            "scan_id": scan_id,
                            "old_status": scan_job.status.value,
                            "all_tools_done": all_tools_done,
                            "tool_count": len(tool_statuses_dict),
                            "has_brain_session": bool(scan_job.brain_session_id),
                        }
                    )
                    scan_job.status = ScanStatus.COMPLETED
                    if not scan_job.completion_time:
                        scan_job.set_completion_time(datetime.now(timezone.utc))
                    db.commit()
                    db.refresh(scan_job)
                    status_source = "db"
                    status_reason = "all_tools_done"
                elif scan_job.status == ScanStatus.RUNNING and not scan_job.brain_session_id:
                    # For non-brain scans (Celery path), check if all tools are done
                    # This is a safety check for Celery-managed scans
                    if all_tools_done:
                        logger.info(
                            "Updating Celery scan to COMPLETED (all tools done)",
                            extra={
                                "scan_id": scan_id,
                                "old_status": scan_job.status.value,
                                "all_tools_done": all_tools_done,
                                "tool_count": len(tool_statuses_dict),
                            }
                        )
                        scan_job.status = ScanStatus.COMPLETED
                        if not scan_job.completion_time:
                            scan_job.set_completion_time(datetime.now(timezone.utc))
                        db.commit()
                        db.refresh(scan_job)
                        status_source = "db"
                        status_reason = "celery_all_tools_done"
                # "running" or "planning" status is already set
                
        except Exception as e:
            logger.warning(
                "Failed to fetch brain session status, using DB status",
                extra={
                    "scan_id": scan_id,
                    "brain_session_id": scan_job.brain_session_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            status_source = "db"
            status_reason = "brain_unreachable"
            # Continue with DB status - don't fail the request
    
    # If no brain_session_id, calculate all_tools_done from DB
    if not scan_job.brain_session_id:
        from app.models.finding import ToolResult, ToolExecutionStatus
        all_tool_results = db.query(ToolResult).filter(
            ToolResult.scan_job_id == scan_id
        ).all()
        
        # Get unique tool names and their latest status
        tool_statuses_dict = {}
        for tr in all_tool_results:
            tool_name = tr.tool_name
            if tool_name not in tool_statuses_dict or (tr.created_at and tool_statuses_dict[tool_name].created_at < tr.created_at):
                tool_statuses_dict[tool_name] = tr
        
        # Check if all tools are in terminal states
        all_tools_done = True
        if tool_statuses_dict:
            for tool_name, tr in tool_statuses_dict.items():
                # If status is set, check it's in a terminal state
                if tr.status:
                    if tr.status not in [
                        ToolExecutionStatus.COMPLETED,
                        ToolExecutionStatus.FAILED,
                        ToolExecutionStatus.SKIPPED,
                        ToolExecutionStatus.TIMED_OUT
                    ]:
                        all_tools_done = False
                        break
                # If status is None but completed_at is set, consider it done
                elif tr.completed_at is None:
                    all_tools_done = False
                    break
        else:
            all_tools_done = False  # No tools yet
    
    # Stalled scan detection: If scan is RUNNING for too long without progress, mark as STALLED
    if scan_job.status == ScanStatus.RUNNING:
        now = datetime.now(timezone.utc)
        # Check if scan has been running longer than threshold
        # Ensure timezone-aware datetimes for comparison
        def ensure_timezone_aware(dt: Optional[datetime]) -> Optional[datetime]:
            """Ensure datetime is timezone-aware (assume UTC if naive)"""
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        
        if scan_job.started_at:
            started_at_aware = ensure_timezone_aware(scan_job.started_at)
            if started_at_aware:
                running_duration = (now - started_at_aware).total_seconds() / 60  # minutes
            else:
                running_duration = 0
        else:
            # Fallback to created_at if started_at not set
            created_at_aware = ensure_timezone_aware(scan_job.created_at)
            if created_at_aware:
                running_duration = (now - created_at_aware).total_seconds() / 60
            else:
                running_duration = 0
        
        if running_duration > settings.STALLED_SCAN_THRESHOLD_MINUTES:
            # Check if brain is unreachable or no progress
            if status_source == "db" and status_reason == "brain_unreachable":
                logger.warning(
                    "Marking scan as STALLED (brain unreachable for extended period)",
                    extra={
                        "scan_id": scan_id,
                        "running_duration_minutes": round(running_duration, 2),
                        "threshold_minutes": settings.STALLED_SCAN_THRESHOLD_MINUTES,
                    }
                )
                scan_job.status = ScanStatus.STALLED
                scan_job.error_message = f"Scan stalled: brain service unreachable for {round(running_duration)} minutes"
                scan_job.set_completion_time(datetime.now(timezone.utc))
                db.commit()
                status_reason = "stalled_brain_unreachable"
            elif all_tools_done:
                # All tools done but still running - should have been caught above, but double-check
                logger.info(
                    "Marking scan as COMPLETED (stalled detection: all tools done)",
                    extra={
                        "scan_id": scan_id,
                        "running_duration_minutes": round(running_duration, 2),
                    }
                )
                scan_job.status = ScanStatus.COMPLETED
                if not scan_job.completion_time:
                    scan_job.set_completion_time(datetime.now(timezone.utc))
                db.commit()
                status_source = "db"
                status_reason = "stalled_all_tools_done"
    
    # Don't load all findings here - use paginated endpoint instead
    # Just get the count for summary generation
    # Exclude surface assets from findings count
    # Include findings where category IS NULL (existing findings) or category != "surface"
    from sqlalchemy import or_
    findings_count = (
        db.query(Finding)
        .filter(Finding.scan_job_id == scan_id)
        .filter(or_(Finding.category.is_(None), Finding.category != "surface"))
        .count()
    )
    
    # Get per-tool statuses for progress indicator
    from app.models.finding import ToolResult
    from sqlalchemy import func
    from datetime import timedelta
    
    # Get the latest execution of each tool to determine status
    latest_tool_results = (
        db.query(
            ToolResult.tool_name,
            func.max(ToolResult.created_at).label('latest_created_at')
        )
        .filter(ToolResult.scan_job_id == scan_id)
        .group_by(ToolResult.tool_name)
        .subquery()
    )
    
    tool_results = (
        db.query(ToolResult)
        .join(
            latest_tool_results,
            (ToolResult.tool_name == latest_tool_results.c.tool_name) &
            (ToolResult.created_at == latest_tool_results.c.latest_created_at)
        )
        .filter(ToolResult.scan_job_id == scan_id)
        .all()
    )
    
    # Build per-tool status list and calculate progress
    from app.models.finding import ToolExecutionStatus
    from app.core.tool_matrix import get_tools_for_level
    from app.models.scan import ScanLevel
    
    tool_statuses = []
    done_tools = 0
    running_tools = 0
    done_status_values = {
        ToolExecutionStatus.COMPLETED.value,
        ToolExecutionStatus.FAILED.value,
        ToolExecutionStatus.SKIPPED.value,
        ToolExecutionStatus.TIMED_OUT.value,
    }
    
    # Get expected total tools for this scan level (not just tools that have started)
    # Also account for AI-planned tools if available
    expected_tool_keys = set()
    try:
        scan_level_enum = ScanLevel(scan_job.scan_level.value if hasattr(scan_job.scan_level, 'value') else scan_job.scan_level)
        expected_tools = get_tools_for_level(scan_level_enum)
        # Filter to only enabled tools
        expected_tool_keys = {tool_config["key"] for tool_config in expected_tools if tool_config.get("enabled", True)}
        
        # If AI plan exists, add tools from next_tools
        if scan_job.ai_plan and isinstance(scan_job.ai_plan, dict):
            next_tools = scan_job.ai_plan.get("next_tools", [])
            if isinstance(next_tools, list):
                for tool_rec in next_tools:
                    tool_key = tool_rec.get("key") if isinstance(tool_rec, dict) else tool_rec
                    if tool_key:
                        expected_tool_keys.add(tool_key)
    except (ValueError, AttributeError, KeyError) as e:
        # Log the error but continue - we'll fall back to tool_results
        logger.warning(f"Failed to get expected tools for scan level {scan_job.scan_level}: {e}")
    
    # If we couldn't determine expected tools from scan level, use tools that have started
    # This ensures we always have a count even if get_tools_for_level fails
    if not expected_tool_keys:
        # Use unique tool names from tool_results (tools that have actually started)
        expected_tool_keys = {tr.tool_name for tr in tool_results}
    
    # Ensure we always have a valid total_tools count
    # If expected_tool_keys is still empty, we need to try one more time with get_tools_for_level
    # This handles the case where scan just started and no tool_results exist yet
    if not expected_tool_keys:
        try:
            scan_level_enum = ScanLevel(scan_job.scan_level.value if hasattr(scan_job.scan_level, 'value') else scan_job.scan_level)
            expected_tools = get_tools_for_level(scan_level_enum)
            expected_tool_keys = {tool_config["key"] for tool_config in expected_tools if tool_config.get("enabled", True)}
            logger.info(f"Using tool matrix for scan {scan_id}: {len(expected_tool_keys)} tools expected for level {scan_level_enum.value}")
        except Exception as e:
            logger.error(f"Failed to determine expected tools for scan {scan_id}: {e}")
            # Last resort: default to a reasonable number based on scan level
            if scan_job.scan_level.value == "basic":
                expected_tool_keys = {"httpx", "nuclei"}  # Default BASIC tools
            elif scan_job.scan_level.value == "pro":
                expected_tool_keys = {"httpx", "nuclei", "ffuf", "nmap", "sslscan", "dalfox"}  # Default PRO tools
            elif scan_job.scan_level.value == "advanced":
                expected_tool_keys = {"httpx", "nuclei", "ffuf", "nmap", "sslscan", "dalfox", "sqlmap"}  # Default ADVANCED tools
    
    # We'll compute total_tools after we see both:
    # - expected tools (tool matrix / AI plan)
    # - tools that actually produced ToolResult rows
    total_tools = 0
    
    # Track which tools we've seen
    seen_tool_names = set()
    
    # Check if scan is terminal - if so, mark any PENDING tools as SKIPPED
    scan_status_value = scan_job.status.value if hasattr(scan_job.status, 'value') else scan_job.status
    scan_is_terminal = scan_status_value in {s.value if hasattr(s, 'value') else s for s in TERMINAL_SCAN_STATUSES}
    
    for tool_result in tool_results:
        tool_name = tool_result.tool_name
        seen_tool_names.add(tool_name)
        
        # Use status field if available, otherwise infer from legacy fields
        if tool_result.status:
            tool_status = tool_result.status.value
            
            # FIX: If scan is terminal and tool is still PENDING, mark as SKIPPED
            if scan_is_terminal and tool_status == ToolExecutionStatus.PENDING.value:
                logger.info(
                    f"Marking tool {tool_name} as SKIPPED (scan {scan_id} is terminal with status {scan_status_value})",
                    extra={
                        "scan_id": scan_id,
                        "tool_name": tool_name,
                        "scan_status": scan_status_value,
                    }
                )
                tool_result.status = ToolExecutionStatus.SKIPPED
                tool_result.error_code = "not_scheduled"
                tool_result.error_message = f"Scan completed before tool execution started (scan status: {scan_status_value})"
                tool_result.completed_at = datetime.now(timezone.utc)
                db.commit()
                tool_status = ToolExecutionStatus.SKIPPED.value
        else:
            # Fallback for legacy records without status field
            if tool_result.timed_out:
                tool_status = ToolExecutionStatus.TIMED_OUT.value
            elif tool_result.exit_code is not None and tool_result.exit_code != 0:
                tool_status = ToolExecutionStatus.FAILED.value
            elif tool_result.error_message:
                tool_status = ToolExecutionStatus.FAILED.value
            else:
                tool_status = ToolExecutionStatus.COMPLETED.value
        
        # Count tools that are done (completed, failed, skipped, or timed_out)
        if tool_status in done_status_values:
            done_tools += 1
        
        # Track running tools for progress smoothing
        if tool_status == ToolExecutionStatus.RUNNING.value:
            running_tools += 1

        tool_statuses.append({
            "tool_name": tool_name,
            "status": tool_status,
            "started_at": tool_result.started_at.isoformat() if tool_result.started_at else (tool_result.created_at.isoformat() if tool_result.created_at else None),
            "completed_at": tool_result.completed_at.isoformat() if tool_result.completed_at else None,
            "execution_time": tool_result.execution_time,
            "error_code": tool_result.error_code,  # New field: short error code
            "error_message": tool_result.error_message,
        })

    # Total tools should reflect what we show: expected tools PLUS any actually executed tools.
    all_tool_keys = set(expected_tool_keys) | set(seen_tool_names)
    total_tools = len(all_tool_keys)
    if total_tools == 0:
        total_tools = 1  # avoid division by zero; should be rare due to defaults above
    
    # If we have expected tools but haven't seen all of them yet, check if they're scheduled
    if expected_tool_keys:
        # Determine which tools are actually scheduled in the plan
        scheduled_tool_keys = set()
        try:
            # Check plan waves for scheduled tools
            if scan_job.ai_plan and isinstance(scan_job.ai_plan, dict):
                # Check waves if available
                waves = scan_job.ai_plan.get("waves", [])
                for wave in waves:
                    for tool_config in wave.get("tools", []):
                        tool_key = tool_config.get("tool_id") or tool_config.get("name")
                        if tool_key:
                            scheduled_tool_keys.add(tool_key)
                # Also check next_tools
                next_tools = scan_job.ai_plan.get("next_tools", [])
                for tool_rec in next_tools:
                    tool_key = tool_rec.get("key") if isinstance(tool_rec, dict) else tool_rec
                    if tool_key:
                        scheduled_tool_keys.add(tool_key)
        except (AttributeError, KeyError, TypeError):
            # If we can't determine scheduled tools, assume all expected tools are scheduled
            scheduled_tool_keys = expected_tool_keys
        
        for tool_key in expected_tool_keys:
            if tool_key not in seen_tool_names:
                # Determine status based on scan state and whether tool is scheduled
                scan_status_value = scan_job.status.value if hasattr(scan_job.status, 'value') else scan_job.status
                scan_is_terminal = scan_status_value in {s.value if hasattr(s, 'value') else s for s in TERMINAL_SCAN_STATUSES}
                tool_is_scheduled = tool_key in scheduled_tool_keys if scheduled_tool_keys else True  # Default to True if unknown
                
                if scan_is_terminal or not tool_is_scheduled:
                    # Scan is done OR tool was never scheduled - mark as skipped
                    missing_status = ToolExecutionStatus.SKIPPED.value
                    error_code = "not_scheduled"
                    error_message = "Tool was not scheduled for execution"
                else:
                    # Scan is running and tool is scheduled but not started yet - keep as pending
                    missing_status = ToolExecutionStatus.PENDING.value
                    error_code = None
                    error_message = None
                
                if missing_status in done_status_values:
                    done_tools += 1
                
                tool_statuses.append({
                    "tool_name": tool_key,
                    "status": missing_status,
                    "started_at": None,
                    "completed_at": None,
                    "execution_time": None,
                    "error_code": error_code,
                    "error_message": error_message,
                })
    
    # Calculate progress percentage based on displayed total tools (never exceed 100).
    # Smooth: count RUNNING tools as half-done so UI progress moves during long tool execution.
    progress_numerator = done_tools + (0.5 * running_tools)
    progress_pct = 0 if total_tools == 0 else min(100, round(100 * progress_numerator / total_tools))
    
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
        from app.core.constants import CANON_FINDINGS_COUNT, DEPRECATED_TOTAL_FINDINGS
        if "executive_summary" not in scan_job.summary and (DEPRECATED_TOTAL_FINDINGS in scan_job.summary or CANON_FINDINGS_COUNT in scan_job.summary):
            # Old format detected - this shouldn't happen if Celery task worked correctly
            logger.warning(f"Scan {scan_id} has old format summary, AI report may have failed")
    
    # Set findings to empty list - frontend should use paginated endpoint
    # This prevents loading thousands of findings in one request
    scan_job.findings = []
    
    # Convert tool_statuses to Pydantic models and return ScanResponse
    from app.schemas.scan import ToolStatus, ScanResponse
    tool_status_models = [ToolStatus(**ts) for ts in tool_statuses]
    
    # If scan is failed only because ffuf timed out (and others succeeded), treat as completed with warnings
    try:
        failed_tools = [ts for ts in tool_statuses if ts.get("status") == "failed"]
        has_only_ffuf_timeout = (
            failed_tools
            and all(
                (ts.get("tool_name") == "ffuf") and (ts.get("error_message") or "").lower().find("timed out") != -1
                for ts in failed_tools
            )
        )
        if scan_job.status == ScanStatus.FAILED and has_only_ffuf_timeout and done_tools >= 1:
            scan_job.status = ScanStatus.COMPLETED
            scan_job.error_message = "Completed with warnings: ffuf timed out after 300s; results may be partial."
            if not scan_job.completion_time:
                scan_job.set_completion_time(datetime.now(timezone.utc))
            status_source = "db"
            status_reason = "ffuf_timeout_nonfatal"
            # Update progress to 100 since we’re marking completion
            progress_pct = 100
            db.commit()
            db.refresh(scan_job)
    except Exception:
        pass
    
    # Defensive: some deployments/DBs may store JSON fields as strings.
    # Pydantic expects dicts for these fields.
    summary_val = scan_job.summary
    if isinstance(summary_val, str):
        try:
            import json as _json
            summary_val = _json.loads(summary_val)
        except Exception:
            summary_val = {"raw": summary_val}
    
    response = ScanResponse(
        id=scan_job.id,
        project_id=scan_job.project_id,
        scan_level=scan_job.scan_level,
        status=scan_job.status,
        summary=summary_val,
        stack_info=scan_job.stack_info,
        ai_plan=scan_job.ai_plan,
        status_source=status_source,
        status_reason=status_reason,
        ai_status=scan_job.ai_status,
        error_message=scan_job.error_message,
        created_at=scan_job.created_at,
        started_at=scan_job.started_at,
        completed_at=scan_job.completion_time,  # Use effective completion time
        findings=[],
        tool_statuses=tool_status_models,
        progress_pct=progress_pct,
        total_tools=total_tools,
        completed_tools=done_tools,
    )
    
    _log_scan_state("H2", "get_scan:response", scan_job)

    return response


@router.post("/{scan_id}/retry-publish", response_model=dict)
async def retry_publish_scan_steps(
    scan_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Manually retry publishing scan steps to Runner for a stuck scan.
    Useful when a scan is stuck in prepare stage with no tool states.
    """
    scan_job = db.query(ScanJob).filter(
        ScanJob.id == scan_id,
        ScanJob.project.has(tenant_id=tenant.id)
    ).first()
    
    if not scan_job:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    if scan_job.status not in [ScanStatus.RUNNING, ScanStatus.QUEUED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry publishing for scan with status {scan_job.status.value}"
        )
    
    project = db.query(Project).filter(Project.id == scan_job.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        from app.services.runner_client import publish_scan_steps_to_runner
        
        logger.info(f"Manually retrying to publish scan steps for scan {scan_id}")
        
        success = await publish_scan_steps_to_runner(
            scan_job_id=scan_id,
            target_url=project.target_url,
            scan_level=scan_job.scan_level,
            org_id=tenant.id,
            project_id=project.id,
        )
        
        if success:
            scan_job.status = ScanStatus.RUNNING
            if not scan_job.started_at:
                scan_job.started_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(scan_job)
            logger.info(f"Successfully republished scan steps for scan {scan_id}")
            return {
                "success": True,
                "message": "Scan steps published successfully",
                "scan_id": scan_id
            }
        else:
            error_msg = "Failed to publish scan steps to Runner"
            logger.error(f"Failed to republish scan steps for scan {scan_id}: {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "scan_id": scan_id
            }
    except Exception as e:
        error_msg = f"Error retrying scan step publishing: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)


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
            detail=f"Scan not found. The scan ID '{scan_id}' does not exist or you don't have permission to access it."
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
    scan_job.set_completion_time(datetime.now(timezone.utc))
    scan_job.error_message = "Cancelled by user"
    
    # Try to stop brain session if it exists
    if scan_job.brain_session_id:
        try:
            try:
                from app.services.brain_client import get_brain_client
                brain_client = get_brain_client()
            except ImportError as e:
                logger.warning(f"Could not import brain_client: {e}. Skipping brain session stop.")
                brain_client = None
            
            if brain_client:
                await brain_client.stop_session(
                    session_id=scan_job.brain_session_id,
                    org_id=tenant.id,
                    project_id=scan_job.project_id,
                )
                logger.info(f"Stopped brain session {scan_job.brain_session_id} for cancelled scan {scan_id}")
        except Exception as e:
            logger.warning(f"Failed to stop brain session {scan_job.brain_session_id}: {e}")
            # Don't fail the cancellation if we can't stop the brain session
    
    # NOTE: Celery has been removed. Scans are now cancelled via Runner/Brain.
    # Runner will check scan status and skip cancelled scans automatically.
    # No need to revoke Celery tasks anymore.
    
    # Try to stop the brain session if it exists
    if scan_job.brain_session_id:
        try:
            try:
                from app.services.brain_client import get_brain_client
                brain_client = get_brain_client()
            except ImportError as e:
                logger.warning(f"Could not import brain_client: {e}. Skipping brain session stop.")
                brain_client = None
            
            if brain_client:
                import asyncio
                
                org_id = None
                project_id = scan_job.project_id
                if scan_job.project and scan_job.project.tenant:
                    org_id = scan_job.project.tenant.id
                
                # Get or create event loop
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Call brain service to stop the session
                stop_response = loop.run_until_complete(
                    brain_client.stop_session(
                        session_id=scan_job.brain_session_id,
                        org_id=org_id,
                        project_id=project_id,
                    )
                )
                logger.info(f"Stopped brain session {scan_job.brain_session_id} for cancelled scan {scan_id}: {stop_response.get('status')}")
        except Exception as e:
            logger.warning(f"Failed to stop brain session {scan_job.brain_session_id}: {e}")
            # Don't fail the cancellation if we can't stop the brain session
    
    db.commit()
    db.refresh(scan_job)
    
    logger.info(f"Scan {scan_id} cancelled by user {current_user.id}")
    
    return scan_job


def _generate_summary(scan_job: ScanJob, findings: list) -> dict:
    """
    Generate summary statistics for a scan
    
    Private function - tests can import directly or test via API endpoints.
    """
    from collections import Counter
    from app.core.constants import (
        CANON_FINDINGS_COUNT, CANON_SEV_BREAKDOWN,
        DEPRECATED_TOTAL_FINDINGS, DEPRECATED_FINDINGS_BY_SEVERITY
    )
    
    findings_by_severity = Counter(finding.severity.value for finding in findings)
    
    # Normalize to ensure all 5 severity keys are present
    severity_breakdown = dict(findings_by_severity)
    for sev in ["critical", "high", "medium", "low", "info"]:
        severity_breakdown.setdefault(sev, 0)
    
    tools_used = list(set(finding.tool_name for finding in findings if finding.tool_name))
    
    duration = None
    if scan_job.started_at and scan_job.completed_at:
        duration = (scan_job.completed_at - scan_job.started_at).total_seconds()
    
    return {
        CANON_FINDINGS_COUNT: len(findings),  # canonical
        DEPRECATED_TOTAL_FINDINGS: len(findings),  # deprecated alias
        CANON_SEV_BREAKDOWN: severity_breakdown,  # canonical, all 5 keys
        DEPRECATED_FINDINGS_BY_SEVERITY: severity_breakdown.copy(),  # deprecated alias
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
            detail=f"Scan not found. The scan ID '{scan_id}' does not exist or you don't have permission to access it."
        )
    
    # Get tool results for this scan
    from app.models.finding import ToolResult
    from datetime import timedelta
    
    # Fetch all tool results and dedupe in Python (Option A: simple + robust)
    # This avoids SQL edge cases with tie-breaking when multiple results share same created_at
    tool_results_all = (
        db.query(ToolResult)
        .filter(ToolResult.scan_job_id == scan_id)
        .order_by(ToolResult.created_at.desc(), ToolResult.id.desc())  # Newest first, tie-break by ID
        .all()
    )
    
    # Deduplicate by tool_name (keep first occurrence = latest)
    # Filter out dependency scanning tools (wappalyzer, retire) - they should only appear in artifacts, not in "Tools Executed"
    DEPENDENCY_TOOLS = {"wappalyzer", "retire"}
    seen = set()
    tool_results = []
    for tr in tool_results_all:
        # Skip dependency scanning tools - they should only create artifacts, not ToolResult entries
        if tr.tool_name.lower() in DEPENDENCY_TOOLS:
            continue
        if tr.tool_name in seen:
            continue
        seen.add(tr.tool_name)
        tool_results.append(tr)
    
    # Reverse to show oldest->newest (optional, for display order)
    tool_results.reverse()
    
    items = []
    for tool_result in tool_results:
        # Calculate output size
        output_size = len(tool_result.output.encode('utf-8')) if tool_result.output else 0
        
        # Use completed_at from tool_result if available, otherwise calculate from execution_time
        completed_at = tool_result.completed_at
        if completed_at is None and tool_result.execution_time is not None:
            completed_at = tool_result.started_at + timedelta(seconds=tool_result.execution_time) if tool_result.started_at else None
        
        # Use started_at from tool_result if available, otherwise use created_at
        started_at = tool_result.started_at if tool_result.started_at else tool_result.created_at
        
        # Convert timed_out from integer (0/1) to boolean
        timed_out = bool(tool_result.timed_out) if hasattr(tool_result, 'timed_out') and tool_result.timed_out else False
        
        # Get status value (enum to string)
        status_value = tool_result.status.value if tool_result.status else None
        
        items.append(
            ToolExecutionResult(
                tool_name=tool_result.tool_name,
                exit_code=tool_result.exit_code,
                started_at=started_at,
                completed_at=completed_at,
                output_size=output_size,
                execution_time=tool_result.execution_time,
                error_message=tool_result.error_message,
                timed_out=timed_out,
                status=status_value,
                stdout_preview=tool_result.stdout_preview,
                stderr_preview=tool_result.stderr_preview,
                parsed_findings_count=tool_result.parsed_findings_count or 0,  # Coalesce NULL to 0 for legacy tool runs predating migration
                created_findings_count=tool_result.created_findings_count or 0,  # Coalesce NULL to 0 for legacy tool runs predating migration
                duration_ms=tool_result.duration_ms,
                tool_name_display=tool_result.tool_name.capitalize() if tool_result.tool_name else "Unknown",  # Title Case for UI
                skip_reason=tool_result.skip_reason,
                raw_stdout=tool_result.raw_stdout,
                raw_stderr=tool_result.raw_stderr,
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
    # Eager load project relationship for target_url fallback
    from sqlalchemy.orm import joinedload
    scan_job = (
        db.query(ScanJob)
        .options(joinedload(ScanJob.project))
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
            detail=f"Scan not found. The scan ID '{scan_id}' does not exist or you don't have permission to access it."
        )
    
    # Build query for findings (eager load instances for grouped findings)
    from sqlalchemy.orm import joinedload
    # Filter out surface assets (HTTPX enumeration data, not vulnerabilities)
    # Include findings where category IS NULL (existing findings) or category != "surface"
    # Also explicitly exclude HTTPX tool findings (now stored as ScanArtifacts)
    from sqlalchemy import or_
    query = (
        db.query(Finding)
        .options(joinedload(Finding.instances))
        .filter(Finding.scan_job_id == scan_id)
        .filter(Finding.tool_name != "httpx")  # HTTPX findings are now artifacts, not findings
        .filter(or_(Finding.category.is_(None), Finding.category != "surface"))  # Exclude surface assets, include NULLs
    )
    
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
    
    # Order by severity (critical, high, medium, low, info) then by CVSS score, then by created_at
    from app.models.finding import Severity
    from sqlalchemy import case
    
    # Create severity order mapping for SQL ordering
    severity_order = case(
        (Finding.severity == Severity.CRITICAL, 0),
        (Finding.severity == Severity.HIGH, 1),
        (Finding.severity == Severity.MEDIUM, 2),
        (Finding.severity == Severity.LOW, 3),
        (Finding.severity == Severity.INFO, 4),
        else_=5  # Unknown severity goes last
    )
    
    # Apply pagination and ordering: severity first, then CVSS score (desc), then created_at (desc)
    findings = (
        query
        .order_by(
            severity_order.asc(),  # Lower number = higher priority
            Finding.affected_count.desc().nulls_last(),  # More affected URLs first
            Finding.cvss_score.desc().nulls_last(),  # Higher CVSS first
            Finding.created_at.desc()  # Newer findings first within same severity/CVSS
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    # Convert to response format with enhanced extraction
    from app.schemas.scan import FindingResponse
    from app.utils.finding_response_builder import extract_location_from_raw_data, get_impact_summary, get_remediation_data
    
    # Get scan's target URL from project for fallback
    scan_target_url = None
    if scan_job.project:
        scan_target_url = scan_job.project.target_url
    elif scan_job.stack_info and isinstance(scan_job.stack_info, dict):
        # Fallback to stack_info if project relationship not loaded
        scan_target_url = scan_job.stack_info.get("target_url")
    
    items = []
    for finding in findings:
        try:
            # Load instances for this finding (if using new normalizer)
            instances = []
            affected_count = 1
            mostly_static = False
            instances_sample = []
            if hasattr(finding, 'instances'):
                # Instances relationship may be loaded via joinedload
                instances_list = finding.instances if finding.instances else []
                instances = list(instances_list) if instances_list else []
                affected_count = finding.affected_count if hasattr(finding, 'affected_count') and finding.affected_count else (len(instances) if instances else 1)
                if instances:
                    static_count = sum(1 for inst in instances if inst.is_static_asset)
                    mostly_static = (static_count / len(instances)) > 0.8
                    # Create instances_sample (up to 10 instances)
                    instances_sample = [
                        {
                            "url": inst.url,
                            "path": inst.path,
                            "http_method": inst.http_method,
                            "parameter": inst.parameter,
                            "evidence_snippet": inst.evidence_snippet,
                            "is_static_asset": inst.is_static_asset,
                        }
                        for inst in instances[:10]  # Limit to 10 instances
                    ]
            elif hasattr(finding, 'affected_count') and finding.affected_count and finding.affected_count > 1:
                # Fallback: use affected_count if instances not loaded
                affected_count = finding.affected_count
            
            # Extract location from raw_data if needed
            location_data = extract_location_from_raw_data(finding)
            
            # Fallback: use scan's target URL if tool/DB didn't provide one
            # This ensures we never show "Location information not available" when we know the scan target
            url = location_data.get("url")
            http_method = location_data.get("http_method")
            parameter = location_data.get("parameter")
            
            # If we have instances, use first instance URL as primary
            if instances and len(instances) > 0 and instances[0].url:
                url = instances[0].url
                http_method = instances[0].http_method or http_method
                parameter = instances[0].parameter or parameter
            
            if not url and scan_target_url:
                url = scan_target_url
                # Default method when unknown
                if not http_method:
                    http_method = "GET"
            
            # Get impact summary
            impact_summary = get_impact_summary(finding)
            
            # Get remediation data
            remediation_data = get_remediation_data(finding)
            
            # Debug logging for first finding
            if len(items) == 0:
                logger.info(f"DEBUG Finding extraction - ID: {finding.id}, Title: {finding.title}")
                logger.info(f"  DB fields - url: {finding.url}, http_method: {finding.http_method}, parameter: {finding.parameter}")
                logger.info(f"  Extracted - url: {location_data['url']}, http_method: {location_data['http_method']}, parameter: {location_data['parameter']}")
                logger.info(f"  After fallback - url: {url}, http_method: {http_method}, parameter: {parameter}")
                logger.info(f"  Scan target URL: {scan_target_url}")
                logger.info(f"  Impact: {impact_summary}")
                logger.info(f"  Remediation summary: {remediation_data['remediation_summary']}")
                logger.info(f"  Default steps: {bool(remediation_data['default_remediation_steps'])}")
                if finding.raw_data:
                    try:
                        import json
                        rd = json.loads(finding.raw_data) if isinstance(finding.raw_data, str) else finding.raw_data
                        logger.info(f"  Raw data keys: {list(rd.keys()) if isinstance(rd, dict) else 'Not a dict'}")
                    except:
                        logger.info(f"  Raw data: Could not parse")
            
            # Extract categories from raw_data if available
            categories = None
            if finding.raw_data:
                try:
                    raw_data_dict = json.loads(finding.raw_data) if isinstance(finding.raw_data, str) else finding.raw_data
                    if isinstance(raw_data_dict, dict) and "categories" in raw_data_dict:
                        categories = raw_data_dict["categories"]
                except (json.JSONDecodeError, TypeError):
                    pass

            # Backfill CWE for ZAP findings if missing
            cwe_id = finding.cwe_id
            severity_value = finding.severity
            tool_name = finding.tool_name or ""
            if tool_name.lower() == "zap" and finding.raw_data:
                raw_dict = parse_raw_json(finding.raw_data)
                if raw_dict:
                    zap_meta = extract_zap_metadata(raw_dict)
                    if not cwe_id:
                        cwe_id = normalize_cwe_id(zap_meta.get("cweid"))
                    # Backfill severity for ZAP findings if stored severity is missing/INFO
                    current_severity = None
                    if hasattr(severity_value, "value"):
                        current_severity = severity_value.value
                    else:
                        current_severity = str(severity_value) if severity_value is not None else None
                    if not current_severity or current_severity.lower() == "info":
                        computed_severity, _ = zap_to_severity(
                            zap_meta.get("riskcode", 0),
                            zap_meta.get("confidence", 0),
                            zap_meta.get("alert") or finding.title,
                            zap_meta.get("raw_dict", raw_dict),
                        )
                        severity_value = computed_severity
            
            items.append(
                FindingResponse(
                    id=finding.id,
                    title=finding.title,
                    description=finding.description,
                    severity=severity_value,
                    status=finding.status.value if hasattr(finding.status, 'value') else str(finding.status) if finding.status else 'open',
                    cve_id=finding.cve_id,
                    cwe_id=cwe_id,
                    cvss_score=finding.cvss_score,
                    # ZAP-specific metadata
                    wasc_id=finding.wasc_id if hasattr(finding, 'wasc_id') else None,
                    plugin_id=finding.plugin_id if hasattr(finding, 'plugin_id') else None,
                    alert_ref=finding.alert_ref if hasattr(finding, 'alert_ref') else None,
                    zap_confidence=finding.zap_confidence if hasattr(finding, 'zap_confidence') else None,
                    zap_riskcode=finding.zap_riskcode if hasattr(finding, 'zap_riskcode') else None,
                    url=url,
                    path=finding.path,
                    recommendation=finding.recommendation,
                    tool_name=finding.tool_name,  # This should be canonical "dalfox"
                    created_at=finding.created_at,
                    # Enhanced fields
                    vuln_type=finding.vuln_type,
                    http_method=http_method,
                    parameter=parameter,
                    remediation_summary=remediation_data["remediation_summary"],
                    remediation_steps=finding.remediation_steps if hasattr(finding, 'remediation_steps') else None,
                    default_remediation_steps=remediation_data["default_remediation_steps"],
                    impact_summary=impact_summary,
                    evidence=finding.evidence if hasattr(finding, 'evidence') else None,
                    ai_source=finding.ai_source if hasattr(finding, 'ai_source') else None,
                    ai_model=finding.ai_model if hasattr(finding, 'ai_model') else None,
                    ai_confidence=finding.ai_confidence if hasattr(finding, 'ai_confidence') else None,
                    # Grouping fields
                    affected_count=affected_count,
                    instances_sample=instances_sample,
                    mostly_static=mostly_static,
                    rule_family=finding.rule_family if hasattr(finding, 'rule_family') else None,
                )
            )
        except Exception as e:
            logger.error(f"Error constructing response for finding {finding.id}: {e}", exc_info=True)
            # Continue with next finding instead of failing entire request
            continue
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{scan_id}/findings/{finding_id}/instances")
async def get_finding_instances(
    scan_id: str,
    finding_id: str,
    limit: int = Query(100000, ge=0, le=20000, description="Maximum number of instances to return. Use 0 or 100000 for all (max 20000)"),
    offset: int = Query(0, ge=0, description="Number of instances to skip for pagination"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get all instances for a specific finding with pagination support.
    
    Supports:
    - limit=0 or limit=100000: Returns all instances (up to server max of 20000)
    - Pagination: Use offset and limit for chunked retrieval
    - Returns URLs in stable sorted order (by URL ascending)
    
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
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
            detail="Scan not found or access denied"
        )
    
    # Verify finding belongs to this scan
    from app.models.finding import FindingInstance
    finding = (
        db.query(Finding)
        .filter(
            Finding.id == finding_id,
            Finding.scan_job_id == scan_id
        )
        .first()
    )
    
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found"
        )
    
    # Determine effective limit (0 or 100000 means "all", but cap at 20000)
    # CRITICAL: For large findings, we need to return all instances, not cap at 20000
    # If affected_count > 20000, we should still return up to 20000, but log a warning
    effective_limit = 20000 if (limit == 0 or limit >= 100000) else limit
    
    # If finding has more than 20000 affected URLs, we can't return all in one request
    # But we should at least return the first 20000
    if finding.affected_count and finding.affected_count > 20000:
        logger.warning(
            f"Finding {finding_id} has {finding.affected_count} affected URLs, but API limit is 20000. "
            f"Only returning first 20000 instances. Use pagination to get remaining instances."
        )
    
    # Build query with stable ordering
    query = (
        db.query(FindingInstance)
        .filter(FindingInstance.finding_id == finding_id)
        .order_by(
            FindingInstance.url.asc().nulls_last(),
            FindingInstance.path.asc().nulls_last(),
            FindingInstance.http_method.asc().nulls_last()
        )
    )
    
    # Get total count
    total_count = query.count()
    
    # Apply pagination
    instances = query.offset(offset).limit(effective_limit).all()
    
    logger.info(
        f"Found {total_count} total instances for finding {finding_id} in scan {scan_id} "
        f"(affected_count={finding.affected_count}, returning {len(instances)} with offset={offset}, limit={effective_limit})"
    )
    
    # Convert to response format
    instances_data = [
        {
            "url": inst.url,
            "path": inst.path,
            "http_method": inst.http_method,
            "parameter": inst.parameter,
            "evidence_snippet": inst.evidence_snippet,
            "is_static_asset": inst.is_static_asset,
        }
        for inst in instances
    ]
    
    # WARNING: If affected_count > stored instances, log a warning
    if finding.affected_count and finding.affected_count > total_count:
        logger.warning(
            f"Data inconsistency: Finding {finding_id} has affected_count={finding.affected_count} "
            f"but only {total_count} instances stored. This indicates an ingestion issue."
        )
    
    # Calculate next offset for pagination
    next_offset = None
    if offset + len(instances) < total_count:
        next_offset = offset + len(instances)
    
    logger.info(f"Returning {len(instances_data)} instances for finding {finding_id} (offset={offset}, next_offset={next_offset})")
    
    return {
        "finding_id": finding_id,
        "total": total_count,
        "affected_count": finding.affected_count,  # Include affected_count for frontend comparison
        "offset": offset,
        "limit": effective_limit,
        "next_offset": next_offset,
        "items": instances_data
    }


@router.get("/{scan_id}/findings/tools")
async def get_scan_findings_tools(
    scan_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get all unique tool names that have findings for a scan.
    This is used to populate the tool filter dropdown with ALL tools,
    not just tools from the first page of findings.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
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
            detail=f"Scan not found. The scan ID '{scan_id}' does not exist or you don't have permission to access it."
        )
    
    # Get all distinct tool names from findings for this scan
    from sqlalchemy import func, distinct
    tool_names = (
        db.query(Finding.tool_name)
        .filter(
            Finding.scan_job_id == scan_id,
            Finding.tool_name.isnot(None),
            Finding.tool_name != ''
        )
        .distinct()
        .order_by(Finding.tool_name)
        .all()
    )
    
    # Extract tool names from tuples
    tools = [tool[0] for tool in tool_names if tool[0]]
    
    return {
        "tools": tools,
        "count": len(tools)
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
            detail=f"Scan not found. The scan ID '{scan_id}' does not exist or you don't have permission to access it."
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


@router.get("/{scan_id}/artifacts", response_model=ScanArtifactsResponse)
async def get_scan_artifacts(
    scan_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get artifacts for a scan (e.g., dependency scan results, screenshots).
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    Only returns artifacts if scan belongs to the current tenant and user.
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
            detail=f"Scan not found. The scan ID '{scan_id}' does not exist or you don't have permission to access it."
        )
    
    # Fetch artifacts
    from app.models.scan_artifact import ScanArtifact
    artifacts = db.query(ScanArtifact).filter(ScanArtifact.scan_id == scan_id).all()
    
    # Convert to response
    items = []
    for artifact in artifacts:
        items.append(
            ScanArtifactResponse(
                id=artifact.id,
                scan_id=artifact.scan_id,
                type=artifact.type,
                payload=artifact.payload,
                created_at=artifact.created_at,
            )
        )
    
    return ScanArtifactsResponse(items=items)


# Dependency Scanning Endpoints

@router.post("/pro", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_pro_scan(
    scan_request: ProScanRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Create a PRO dependency scan (URL-SCA only).
    
    Requires PRO plan or higher. Scans externally observable dependencies
    and client-side JavaScript vulnerabilities.
    """
    from app.core.capabilities import check_capability
    from app.models.scan_artifact import ScanArtifact
    from app.services.dependency_scanner import enqueue_dependency_scan_job
    
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Check capability
    check_capability(db, tenant, current_user, "url_sca")
    
    # Verify project exists and belongs to tenant and user
    project = db.query(Project).filter(
        Project.id == scan_request.project_id,
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found. The project ID '{scan_request.project_id}' does not exist or you don't have permission to access it."
        )
    
    # Validate target URL
    if not scan_request.target_url.startswith(('http://', 'https://')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_url must start with http:// or https://"
        )
    
    # Enforce domain verification (reuse existing logic)
    is_admin = bool(getattr(current_user, "is_admin", False) or getattr(current_user, "is_superuser", False))
    try:
        ensure_project_root_domain(project, scan_request.target_url, allow_admin_override=True, is_admin=is_admin)
        db.commit()
        db.refresh(project)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    enforce_domain_verification_for_scan(
        db,
        project,
        scan_request.target_url,
        is_admin=is_admin,
        user_id=current_user.id,
    )
    
    # Create scan job
    scan_job = ScanJob(
        user_id=current_user.id,
        url=scan_request.target_url,
        domain=_extract_domain_name(scan_request.target_url),
        tier="pro",
        project_id=project.id,
        scan_level=ScanLevel.PRO,
        status=ScanStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    
    db.add(scan_job)
    db.commit()
    db.refresh(scan_job)
    
    # Enqueue dependency scan job
    callback_url = f"{settings.BACKEND_URL}/api/runner/callback" if hasattr(settings, 'BACKEND_URL') else None
    try:
        logger.info(f"[PRO-SCAN] Enqueuing dependency scan job for scan {scan_job.id}")
        result = await enqueue_dependency_scan_job(
            scan_id=scan_job.id,
            job_type="url_sca",
            target_url=scan_request.target_url,
            callback_url=callback_url,
        )
        if result:
            logger.info(f"[PRO-SCAN] Successfully enqueued dependency scan job for scan {scan_job.id}")
        else:
            logger.error(f"[PRO-SCAN] Failed to enqueue dependency scan job for scan {scan_job.id}")
    except Exception as e:
        logger.error(f"[PRO-SCAN] Exception enqueuing dependency scan job for scan {scan_job.id}: {e}", exc_info=True)
    
    # Update status to running
    scan_job.status = ScanStatus.RUNNING
    scan_job.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(scan_job)
    
    return ScanResponse(
        id=scan_job.id,
        project_id=scan_job.project_id,
        scan_level=scan_job.scan_level,
        status=scan_job.status,
        summary=scan_job.summary,
        stack_info=scan_job.stack_info,
        ai_plan=scan_job.ai_plan,
        ai_status=scan_job.ai_status,
        error_message=scan_job.error_message,
        created_at=scan_job.created_at,
        started_at=scan_job.started_at,
        completed_at=scan_job.completed_at,
        findings=[],
        tool_statuses=[],
    )


@router.post("/advanced", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_advanced_scan(
    scan_request: AdvancedScanRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Create an ADVANCED dependency scan (URL-SCA + optional Repo-SCA).
    
    Requires ADVANCED plan. If repo_connection_id is provided, performs
    repository SCA using lockfiles/manifests. Otherwise, runs URL-SCA only.
    """
    from app.core.capabilities import check_capability
    from app.models.scan_artifact import ScanArtifact
    from app.models.repo_connection import RepoConnection
    from app.services.dependency_scanner import enqueue_dependency_scan_job
    
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Check capability
    check_capability(db, tenant, current_user, "url_sca")
    if scan_request.repo_connection_id:
        check_capability(db, tenant, current_user, "repo_sca")
    
    # Verify project exists and belongs to tenant and user
    project = db.query(Project).filter(
        Project.id == scan_request.project_id,
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found. The project ID '{scan_request.project_id}' does not exist or you don't have permission to access it."
        )
    
    # Validate target URL
    if not scan_request.target_url.startswith(('http://', 'https://')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_url must start with http:// or https://"
        )
    
    # Verify repo connection if provided
    repo_info = None
    if scan_request.repo_connection_id:
        repo_connection = db.query(RepoConnection).filter(
            RepoConnection.id == scan_request.repo_connection_id,
            RepoConnection.project_id == project.id,
            RepoConnection.is_enabled == True,
        ).first()
        
        if not repo_connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repo connection not found or disabled. The repo_connection_id '{scan_request.repo_connection_id}' does not exist or is not enabled for this project."
            )
        
        # Get integration for GitHub App token
        from app.models.integration import Integration
        integration = db.query(Integration).filter(
            Integration.user_id == current_user.id,
            Integration.provider == "github",
            Integration.revoked_at.is_(None),
        ).first()
        
        if not integration:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub integration not found. Please connect your GitHub account first."
            )
        
        repo_info = {
            "provider": repo_connection.provider,
            "installation_id": integration.installation_id,
            "provider_repo_id": repo_connection.provider_repo_id,
            "full_name": repo_connection.full_name,
            "default_branch": repo_connection.default_branch or "main",
        }
    
    # Enforce domain verification
    is_admin = bool(getattr(current_user, "is_admin", False) or getattr(current_user, "is_superuser", False))
    try:
        ensure_project_root_domain(project, scan_request.target_url, allow_admin_override=True, is_admin=is_admin)
        db.commit()
        db.refresh(project)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    enforce_domain_verification_for_scan(
        db,
        project,
        scan_request.target_url,
        is_admin=is_admin,
        user_id=current_user.id,
    )
    
    # Create scan job
    scan_job = ScanJob(
        user_id=current_user.id,
        url=scan_request.target_url,
        domain=_extract_domain_name(scan_request.target_url),
        tier="advanced",
        project_id=project.id,
        scan_level=ScanLevel.ADVANCED,
        status=ScanStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    
    db.add(scan_job)
    db.commit()
    db.refresh(scan_job)
    
    # Enqueue dependency scan jobs
    callback_url = f"{settings.BACKEND_URL}/api/runner/callback" if hasattr(settings, 'BACKEND_URL') else None
    
    # Always enqueue URL-SCA
    await enqueue_dependency_scan_job(
        scan_id=scan_job.id,
        job_type="url_sca",
        target_url=scan_request.target_url,
        callback_url=callback_url,
    )
    
    # Enqueue Repo-SCA if repo connection provided
    if repo_info:
        await enqueue_dependency_scan_job(
            scan_id=scan_job.id,
            job_type="repo_sca",
            target_url=scan_request.target_url,
            repo_info=repo_info,
            callback_url=callback_url,
        )
    
    # Update status to running
    scan_job.status = ScanStatus.RUNNING
    scan_job.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(scan_job)
    
    return ScanResponse(
        id=scan_job.id,
        project_id=scan_job.project_id,
        scan_level=scan_job.scan_level,
        status=scan_job.status,
        summary=scan_job.summary,
        stack_info=scan_job.stack_info,
        ai_plan=scan_job.ai_plan,
        ai_status=scan_job.ai_status,
        error_message=scan_job.error_message,
        created_at=scan_job.created_at,
        started_at=scan_job.started_at,
        completed_at=scan_job.completed_at,
        findings=[],
        tool_statuses=[],
    )


