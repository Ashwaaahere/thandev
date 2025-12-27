"""
Metrics API router
"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.tenant_utils import require_tenant, get_current_user
from app.core.dependencies import require_approved_user
from app.models.tenant import Tenant
from app.models.user import User
from app.models.scan import ScanJob, ScanStatus
from app.models.project import Project
from app.models.finding import Finding, Severity, FindingStatus
from app.schemas.metrics import (
    DashboardOverviewMetrics,
    RecentScanItem,
    TotalsMetrics,
    RecentActivityMetrics,
    FindingsBySeverityMetrics,
    LatestScanItem,
)
from fastapi import HTTPException, status

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
    dependencies=[Depends(require_approved_user)],
)


def _extract_summary_fields(summary: dict | None) -> tuple[Optional[float], Optional[int]]:
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


@router.get("/overview", response_model=DashboardOverviewMetrics)
async def get_dashboard_overview(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get dashboard overview metrics for the current tenant and user.
    
    Returns:
        DashboardOverviewMetrics with counts, scores, recent scans, and Phase 2 metrics
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    All data is scoped to the current tenant and user.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Check if columns exist in scan_jobs table
    from sqlalchemy import inspect
    try:
        inspector = inspect(db.bind)
        scan_jobs_columns = [col['name'] for col in inspector.get_columns('scan_jobs')] if 'scan_jobs' in inspector.get_table_names() else []
        has_project_id = 'project_id' in scan_jobs_columns
        has_scan_level = 'scan_level' in scan_jobs_columns
        logger.info(f"Metrics overview: scan_jobs has project_id column: {has_project_id}, scan_level column: {has_scan_level}")
    except Exception as e:
        logger.warning(f"Could not check scan_jobs columns: {e}, assuming columns exist")
        has_project_id = True  # Assume it exists and let the query fail if it doesn't
        has_scan_level = True
    
    if not has_project_id:
        logger.warning("scan_jobs table does not have project_id column yet, returning empty metrics")
        # Return empty metrics if column doesn't exist
        from app.schemas.metrics import (
            TotalsMetrics,
            RecentActivityMetrics,
            FindingsBySeverityMetrics,
        )
        return DashboardOverviewMetrics(
            total_scans=0,
            security_scans=0,
            performance_scans=0,
            vulnerabilities_found=0,
            avg_security_score=0.0,
            scans_this_month=0,
            recent_scans=[],
            latest_scans=[],
            totals=TotalsMetrics(
                total_projects=0,
                total_scans=0,
                total_findings=0,
                total_vulnerabilities=0,
            ),
            recent_activity=RecentActivityMetrics(
                scans_today=0,
                scans_this_week=0,
                scans_this_month=0,
            ),
            findings_by_severity=FindingsBySeverityMetrics(
                critical=0,
                high=0,
                medium=0,
                low=0,
                info=0,
            ),
        )
    
    try:
        # Base query for scans for this tenant and user
        # Use outerjoin to handle cases where project_id might be NULL (from old schema)
        # Then filter to only include scan_jobs with valid projects
        scans_query = (
            db.query(ScanJob)
            .outerjoin(Project, ScanJob.project_id == Project.id)
            .filter(
                ScanJob.project_id.isnot(None),  # Exclude scan_jobs without project_id
                Project.id.isnot(None),  # Ensure project exists
                Project.tenant_id == tenant.id,
                Project.owner_id == current_user.id
            )
        )
    except Exception as e:
        logger.error(f"Error creating scans_query: {type(e).__name__}: {str(e)}", exc_info=True)
        # If query fails, return empty results
        scans_query = db.query(ScanJob).filter(False)  # Empty query
    
    # Base query for projects for this tenant and user
    projects_query = (
        db.query(Project)
        .filter(
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id
        )
    )
    
    try:
        # Base query for findings for this tenant and user
        # Use outerjoin to handle cases where project_id might be NULL (from old schema)
        # Then filter to only include findings from scan_jobs with valid projects
        findings_query = (
            db.query(Finding)
            .join(ScanJob, Finding.scan_job_id == ScanJob.id)
            .outerjoin(Project, ScanJob.project_id == Project.id)
            .filter(
                ScanJob.project_id.isnot(None),  # Exclude scan_jobs without project_id
                Project.id.isnot(None),  # Ensure project exists
                Project.tenant_id == tenant.id,
                Project.owner_id == current_user.id
            )
        )
    except Exception as e:
        logger.error(f"Error creating findings_query: {type(e).__name__}: {str(e)}", exc_info=True)
        # If project_id column doesn't exist, return empty results
        findings_query = db.query(Finding).filter(False)  # Empty query
    
    # Check if scan_level column exists
    try:
        inspector = inspect(db.bind)
        scan_jobs_columns = [col['name'] for col in inspector.get_columns('scan_jobs')] if 'scan_jobs' in inspector.get_table_names() else []
        has_scan_level = 'scan_level' in scan_jobs_columns
        logger.info(f"Metrics overview: scan_jobs has scan_level column: {has_scan_level}")
    except Exception as e:
        logger.warning(f"Could not check scan_jobs columns: {e}, assuming scan_level exists")
        has_scan_level = True  # Assume it exists and let the query fail if it doesn't
    
    # Total scans (all ScanJob entries for this tenant)
    # Use count() on id only to avoid loading columns that might not exist
    try:
        if has_scan_level:
            total_scans = scans_query.count()
        else:
            # If scan_level doesn't exist, count using id only
            total_scans = scans_query.with_entities(ScanJob.id).count()
    except Exception as e:
        logger.error(f"Error counting scans: {type(e).__name__}: {str(e)}", exc_info=True)
        total_scans = 0
    
    security_scans = total_scans  # For now, all scans are security scans
    performance_scans = 0  # Placeholder for future Lighthouse work
    
    # Vulnerabilities found (count of Finding rows for this tenant and user)
    try:
        vulnerabilities_found = findings_query.count()
    except Exception as e:
        logger.error(f"Error counting findings: {type(e).__name__}: {str(e)}", exc_info=True)
        vulnerabilities_found = 0
    
    # Average security score
    # For completed scans with risk_score, convert to score = 100 - risk_score
    try:
        # Try to fetch completed scans - if it fails due to missing columns, return empty
        try:
            completed_scans = (
                scans_query
                .filter(ScanJob.status == ScanStatus.COMPLETED)
                .all()
            )
        except Exception as fetch_error:
            logger.warning(f"Error fetching completed scans, likely due to missing columns: {fetch_error}")
            completed_scans = []
    except Exception as e:
        logger.error(f"Error fetching completed scans: {type(e).__name__}: {str(e)}", exc_info=True)
        completed_scans = []
    
    scores = []
    for scan in completed_scans:
        risk_score, _ = _extract_summary_fields(scan.summary)
        if risk_score is not None:
            # Convert risk_score (0-100, where higher is worse) to security score (0-100, where higher is better)
            security_score = 100 - risk_score
            scores.append(security_score)
    
    avg_security_score = sum(scores) / len(scores) if scores else 0.0
    avg_security_score = round(avg_security_score, 1)
    
    # Scans this month (UTC)
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    try:
        scans_this_month = (
            scans_query
            .filter(ScanJob.created_at >= month_start)
            .count()
        )
    except Exception as count_error:
        try:
            scans_this_month = (
                scans_query
                .with_entities(ScanJob.id)
                .filter(ScanJob.created_at >= month_start)
                .count()
            )
        except Exception:
            logger.error(f"Error counting scans this month: {count_error}", exc_info=True)
            scans_this_month = 0
    
    # Recent scans (last 10, ordered by created_at DESC)
    # Use joinedload to avoid N+1 queries
    from sqlalchemy.orm import joinedload
    try:
        # Try to fetch recent scans - if it fails due to missing columns, return empty
        try:
            recent_scan_jobs = (
                scans_query
                .options(joinedload(ScanJob.project))
                .order_by(ScanJob.created_at.desc())
                .limit(10)
                .all()
            )
        except Exception as fetch_error:
            logger.warning(f"Error fetching recent scans, likely due to missing columns: {fetch_error}")
            recent_scan_jobs = []
    except Exception as e:
        logger.error(f"Error fetching recent scans: {type(e).__name__}: {str(e)}", exc_info=True)
        recent_scan_jobs = []
    
    # Map to RecentScanItem
    recent_scans = []
    latest_scans = []
    for scan_job in recent_scan_jobs:
        # Get project info (already loaded via join)
        project = scan_job.project
        if not project:
            continue
        
        # Extract risk_score and findings_count from summary
        risk_score, findings_count = _extract_summary_fields(scan_job.summary)
        
        # Get scan level as string - handle missing scan_level column
        if has_scan_level and hasattr(scan_job, 'scan_level') and scan_job.scan_level:
            scan_level = scan_job.scan_level.value if hasattr(scan_job.scan_level, 'value') else str(scan_job.scan_level)
        else:
            scan_level = "basic"  # Default value if column doesn't exist
        
        # Get status as string
        scan_status = scan_job.status.value if hasattr(scan_job.status, 'value') else str(scan_job.status)
        
        recent_scans.append(RecentScanItem(
            id=scan_job.id,
            project_id=scan_job.project_id,
            project_name=project.name,
            target_url=project.target_url,
            level=scan_level,
            status=scan_status,
            created_at=scan_job.created_at,
            risk_score=risk_score,
            findings_count=findings_count,
            completed_at=scan_job.completed_at,
            scan_level=scan_level,
        ))
        
        latest_scans.append(LatestScanItem(
            id=scan_job.id,
            project_id=scan_job.project_id,
            project_name=project.name,
            target_url=project.target_url,
            scan_level=scan_level,
            status=scan_status,
            risk_score=risk_score,
            findings_count=findings_count,
            completed_at=scan_job.completed_at,
        ))
    
    # Phase 2: Totals
    total_projects = projects_query.count()
    total_findings = findings_query.count()
    
    totals = TotalsMetrics(
        projects=total_projects,
        scans=total_scans,
        findings=total_findings,
    )
    
    # Phase 2: Recent activity
    now = datetime.now(timezone.utc)
    seven_days_ago = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Subtract 7 days
    from datetime import timedelta
    seven_days_ago = seven_days_ago - timedelta(days=7)
    
    scans_last_7_days = (
        scans_query
        .filter(ScanJob.created_at >= seven_days_ago)
        .count()
    )
    
    # Get last scan timestamp
    last_scan = (
        scans_query
        .order_by(ScanJob.created_at.desc())
        .first()
    )
    last_scan_at = last_scan.created_at if last_scan else None
    
    recent_activity = RecentActivityMetrics(
        last_scan_at=last_scan_at,
        scans_last_7_days=scans_last_7_days,
    )
    
    # Phase 2: Findings by severity (only open findings)
    findings_by_severity_counts = (
        findings_query
        .filter(Finding.status == FindingStatus.OPEN)
        .with_entities(Finding.severity, func.count(Finding.id))
        .group_by(Finding.severity)
        .all()
    )
    
    findings_by_severity_dict = {
        Severity.CRITICAL.value: 0,
        Severity.HIGH.value: 0,
        Severity.MEDIUM.value: 0,
        Severity.LOW.value: 0,
        Severity.INFO.value: 0,
    }
    
    for severity, count in findings_by_severity_counts:
        if severity and hasattr(severity, 'value'):
            severity_str = severity.value
        else:
            severity_str = str(severity)
        findings_by_severity_dict[severity_str] = count
    
    findings_by_severity = FindingsBySeverityMetrics(
        critical=findings_by_severity_dict[Severity.CRITICAL.value],
        high=findings_by_severity_dict[Severity.HIGH.value],
        medium=findings_by_severity_dict[Severity.MEDIUM.value],
        low=findings_by_severity_dict[Severity.LOW.value],
        info=findings_by_severity_dict[Severity.INFO.value],
    )
    
    result = DashboardOverviewMetrics(
        # Legacy fields
        total_scans=total_scans,
        security_scans=security_scans,
        performance_scans=performance_scans,
        vulnerabilities_found=vulnerabilities_found,
        avg_security_score=avg_security_score,
        scans_this_month=scans_this_month,
        recent_scans=recent_scans,
        # Phase 2 fields
        totals=totals,
        recent_activity=recent_activity,
        findings_by_severity=findings_by_severity,
        latest_scans=latest_scans,
    )

    return result
