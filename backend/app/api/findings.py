"""
Findings API router
"""
import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional

from fastapi import HTTPException, status

from app.core.database import get_db
from app.core.tenant_utils import require_tenant, get_current_user
from app.models.tenant import Tenant
from app.models.user import User
from app.models.scan import ScanJob
from app.models.project import Project
from app.models.finding import Finding, Severity, FindingStatus
from app.schemas.finding import FindingListItem, FindingListResponse, UpdateFindingStatusRequest

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("", response_model=FindingListResponse)
async def list_findings(
    severity: Optional[str] = Query(None, description="Filter by severity (critical, high, medium, low, info)"),
    search: Optional[str] = Query(None, description="Search in title or description"),
    tool: Optional[str] = Query(None, description="Filter by tool (nuclei, nmap, sslscan)"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    status: Optional[FindingStatus] = Query(None, description="Filter by status (open, acknowledged, resolved, suppressed)"),
    category: Optional[str] = Query(None, description="Filter by vulnerability category (xss, sqli, ssrf, ssti, xxe, dir_traversal, csrf, cors, command_injection, idor)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of findings to return"),
    offset: int = Query(0, ge=0, description="Number of findings to skip"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    List findings for the current tenant and user.
    
    Supports filtering by severity, tool, project_id, status, and searching in title/description.
    Results are ordered by created_at DESC (newest first).
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Base query: Finding → ScanJob → Project, filtered by tenant and user
    query = (
        db.query(Finding, ScanJob, Project)
        .join(ScanJob, Finding.scan_job_id == ScanJob.id)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id
        )
    )
    
    # Apply severity filter if provided
    if severity:
        try:
            # Normalize severity string to enum (accept both lowercase and uppercase)
            severity_normalized = severity.upper()
            severity_enum = Severity[severity_normalized]
            query = query.filter(Finding.severity == severity_enum)
        except (ValueError, KeyError):
            # Invalid severity value, return empty results
            pass
    
    # Apply search filter if provided
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Finding.title.ilike(search_pattern),
                Finding.description.ilike(search_pattern),
                Finding.cve_id.ilike(search_pattern),
                Finding.cwe_id.ilike(search_pattern),
                Finding.url.ilike(search_pattern),
                Finding.path.ilike(search_pattern),
            )
        )
    
    # Apply tool filter if provided
    if tool:
        tool_value = tool.lower().strip()
        # Only accept valid tool names
        valid_tools = {"nuclei", "nmap", "sslscan", "http_headers"}
        if tool_value in valid_tools:
            query = query.filter(Finding.tool_name == tool_value)
    
    # Apply project_id filter if provided
    if project_id:
        query = query.filter(ScanJob.project_id == project_id)
    
    # Apply status filter if provided
    if status is not None:
        query = query.filter(Finding.status == status)
    
    # Apply category filter if provided
    if category:
        category_lower = category.lower().strip()
        # Detect database type for appropriate JSON query
        from app.core.database import engine
        is_postgresql = engine.url.drivername.startswith("postgresql")
        
        if is_postgresql:
            # PostgreSQL: Use JSONB operators
            # Check if raw_data["categories"] array contains the category
            from sqlalchemy import text
            query = query.filter(
                Finding.raw_data["categories"].astext.ilike(f"%{category_lower}%")
            )
        else:
            # SQLite: Use string contains on JSON text
            # Since raw_data is stored as Text in SQLite, we need to check if the JSON string contains the category
            # Check for the category in the categories array (handles various JSON formats)
            # Pattern matches: "categories":["xss",...] or "categories":["xss"] or "categories":["...xss..."]
            category_patterns = [
                f'"categories":["{category_lower}"',  # First item in array
                f'"{category_lower}"',  # Anywhere in categories array
            ]
            filters = [Finding.raw_data.contains(pattern) for pattern in category_patterns]
            query = query.filter(or_(*filters))
    
    # Get total count before pagination
    total = query.count()
    
    # Order by created_at DESC and apply pagination
    findings_with_scan_project = (
        query
        .order_by(Finding.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    # Map to FindingListItem
    items = []
    for finding, scan_job, project in findings_with_scan_project:
        # Extract categories from raw_data if available
        categories = None
        if finding.raw_data:
            try:
                raw_data_dict = json.loads(finding.raw_data)
                if isinstance(raw_data_dict, dict) and "categories" in raw_data_dict:
                    categories = raw_data_dict["categories"]
            except (json.JSONDecodeError, TypeError):
                # raw_data is not valid JSON, ignore
                pass
        
        items.append(
            FindingListItem(
                id=finding.id,
                scan_id=scan_job.id,
                project_id=project.id,
                project_name=project.name,
                target_url=project.target_url,
                severity=finding.severity.value if hasattr(finding.severity, 'value') else str(finding.severity),
                status=finding.status.value if hasattr(finding.status, 'value') else str(finding.status) if finding.status else 'open',
                title=finding.title,
                description=finding.description,
                cve_id=finding.cve_id,
                cwe_id=finding.cwe_id,
                tool=finding.tool_name,
                categories=categories,
                first_seen=finding.created_at,
                last_seen=finding.created_at,  # For now, use created_at as both first_seen and last_seen
            )
        )
    
    return FindingListResponse(items=items, total=total)


@router.patch("/{finding_id}/status", response_model=FindingListItem)
def update_finding_status(
    finding_id: str,
    payload: UpdateFindingStatusRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Update the status of a finding.
    
    Ensures the finding belongs to the current tenant and user.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Ensure finding belongs to this tenant and user: Finding → ScanJob → Project
    finding = (
        db.query(Finding)
        .join(ScanJob, Finding.scan_job_id == ScanJob.id)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            Finding.id == finding_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id,
        )
        .first()
    )
    
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")
    
    finding.status = payload.status
    db.commit()
    db.refresh(finding)
    
    # Reload with joins to get project info for response
    finding_with_project = (
        db.query(Finding, ScanJob, Project)
        .join(ScanJob, Finding.scan_job_id == ScanJob.id)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(Finding.id == finding_id)
        .first()
    )
    
    if not finding_with_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found after update")
    
    finding_obj, scan_job, project = finding_with_project
    
    return FindingListItem(
        id=finding_obj.id,
        scan_id=scan_job.id,
        project_id=project.id,
        project_name=project.name,
        target_url=project.target_url,
        severity=finding_obj.severity.value if hasattr(finding_obj.severity, 'value') else str(finding_obj.severity),
        status=finding_obj.status.value if hasattr(finding_obj.status, 'value') else str(finding_obj.status),
        title=finding_obj.title,
        description=finding_obj.description,
        cve_id=finding_obj.cve_id,
        cwe_id=finding_obj.cwe_id,
        cvss_score=finding_obj.cvss_score,
        tool=finding_obj.tool_name,
        url=finding_obj.url,
        path=finding_obj.path,
        first_seen=finding_obj.created_at,
        last_seen=finding_obj.created_at,
    )

