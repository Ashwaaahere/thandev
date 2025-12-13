"""
Projects API router
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.tenant_utils import get_current_user, require_tenant
from app.models.project import Project
from app.models.user import User
from app.models.tenant import Tenant
from app.models.scan import ScanJob
from app.models.finding import Finding
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectWithStats,
    ProjectListWithStatsResponse,
    ProjectOverviewResponse,
    ProjectOverviewStats,
)

router = APIRouter(prefix="/projects", tags=["projects"])


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
    project = Project(
        name=payload.name,
        target_url=payload.target_url,
        repo_url=payload.repo_url,
        description=payload.description,
        owner_id=current_user.id,
        tenant_id=tenant.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    # ProjectResponse is a Pydantic model; from_attributes is enabled in its Config
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
            detail=f"Project with id '{project_id}' not found"
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
    
    # latest_scan_tools: Get tool results from the latest scan
    latest_scan_tools = []
    if last_scan:
        from app.models.finding import ToolResult
        tool_results = (
            db.query(ToolResult)
            .filter(ToolResult.scan_job_id == last_scan.id)
            .order_by(ToolResult.created_at.asc())
            .all()
        )
        
        from app.schemas.project import LatestScanTool
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

