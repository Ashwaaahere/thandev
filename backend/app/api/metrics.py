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
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Base query for scans for this tenant and user
    # Filter out scan_jobs without project_id (NULL values from old schema)
    scans_query = (
        db.query(ScanJob)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            ScanJob.project_id.isnot(None),  # Exclude scan_jobs without project_id
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id
        )
    )
    
    # Base query for projects for this tenant and user
    projects_query = (
        db.query(Project)
        .filter(
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id
        )
    )
    
    # Base query for findings for this tenant and user
    # Filter out scan_jobs without project_id (NULL values from old schema)
    findings_query = (
        db.query(Finding)
        .join(ScanJob, Finding.scan_job_id == ScanJob.id)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            ScanJob.project_id.isnot(None),  # Exclude scan_jobs without project_id
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id
        )
    )
    
    # Total scans (all ScanJob entries for this tenant)
    total_scans = scans_query.count()
    security_scans = total_scans  # For now, all scans are security scans
    performance_scans = 0  # Placeholder for future Lighthouse work
    
    # Vulnerabilities found (count of Finding rows for this tenant and user)
    vulnerabilities_found = findings_query.count()
    
    # Average security score
    # For completed scans with risk_score, convert to score = 100 - risk_score
    completed_scans = (
        scans_query
        .filter(ScanJob.status == ScanStatus.COMPLETED)
        .all()
    )
    
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
    
    scans_this_month = (
        scans_query
        .filter(ScanJob.created_at >= month_start)
        .count()
    )
    
    # Recent scans (last 10, ordered by created_at DESC)
    # Use joinedload to avoid N+1 queries
    from sqlalchemy.orm import joinedload
    recent_scan_jobs = (
        scans_query
        .options(joinedload(ScanJob.project))
        .order_by(ScanJob.created_at.desc())
        .limit(10)
        .all()
    )
    
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
        
        # Get scan level as string
        scan_level = scan_job.scan_level.value if hasattr(scan_job.scan_level, 'value') else str(scan_job.scan_level)
        
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
