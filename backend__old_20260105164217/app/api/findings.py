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
from app.core.dependencies import require_approved_user
from app.models.tenant import Tenant
from app.models.user import User
from app.models.scan import ScanJob
from app.models.project import Project
from app.models.finding import Finding, Severity, FindingStatus
from app.schemas.finding import FindingListItem, FindingListResponse, FindingDetailResponse, UpdateFindingStatusRequest

router = APIRouter(
    prefix="/findings",
    tags=["findings"],
    dependencies=[Depends(require_approved_user)],
)


@router.get("", response_model=FindingListResponse)
async def list_findings(
    severity: Optional[str] = Query(None, description="Filter by severity (critical, high, medium, low, info). Supports comma-separated values (e.g., 'high,critical')"),
    search: Optional[str] = Query(None, description="Search in title, description, URL, or parameter"),
    tool: Optional[str] = Query(None, description="Filter by tool (nuclei, nmap, sslscan)"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    scan_id: Optional[str] = Query(None, description="Filter by scan ID"),
    status: Optional[FindingStatus] = Query(None, description="Filter by status (open, acknowledged, resolved, suppressed)"),
    category: Optional[str] = Query(None, description="Filter by vulnerability category (xss, sqli, ssrf, ssti, xxe, dir_traversal, csrf, cors, command_injection, idor)"),
    vuln_type: Optional[str] = Query(None, description="Filter by vuln_type (xss, sqli, csrf, etc.)"),
    limit: int = Query(20, ge=1, le=1000, description="Maximum number of findings to return"),
    offset: int = Query(0, ge=0, description="Number of findings to skip"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    List findings for the current tenant and user.
    
    Supports filtering by severity (single or comma-separated), tool, project_id, scan_id, status, vuln_type,
    and searching in title, description, URL, or parameter.
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
    
    # Apply severity filter if provided (supports comma-separated values)
    if severity:
        severity_values = [s.strip().upper() for s in severity.split(',')]
        valid_severities = []
        for sv in severity_values:
            try:
                severity_enum = Severity[sv]
                valid_severities.append(severity_enum)
            except (ValueError, KeyError):
                # Skip invalid severity values
                continue
        
        if valid_severities:
            # Filter by any of the valid severities
            from sqlalchemy import or_
            query = query.filter(or_(*[Finding.severity == sv for sv in valid_severities]))
    
    # Apply search filter if provided (prioritizes URL and parameter fields)
    if search:
        search_pattern = f"%{search}%"
        # Prioritize URL and parameter fields, but also search in title, description, CVE, CWE, path
        query = query.filter(
            or_(
                Finding.url.ilike(search_pattern),
                Finding.parameter.ilike(search_pattern),
                Finding.title.ilike(search_pattern),
                Finding.description.ilike(search_pattern),
                Finding.cve_id.ilike(search_pattern),
                Finding.cwe_id.ilike(search_pattern),
                Finding.path.ilike(search_pattern),
            )
        )
    
    # Apply tool filter if provided
    if tool:
        tool_value = tool.lower().strip()
        # Only accept valid tool names (include all active tools)
        valid_tools = {"nuclei", "nmap", "sslscan", "http_headers", "httpx", "ffuf", "dalfox", "sqlmap"}
        if tool_value in valid_tools:
            query = query.filter(Finding.tool_name == tool_value)
    
    # Apply project_id filter if provided
    if project_id:
        query = query.filter(ScanJob.project_id == project_id)
    
    # Apply scan_id filter if provided
    if scan_id:
        query = query.filter(ScanJob.id == scan_id)
    
    # Apply status filter if provided
    if status is not None:
        query = query.filter(Finding.status == status)
    
    # Apply vuln_type filter if provided
    if vuln_type:
        vuln_type_lower = vuln_type.lower().strip()
        query = query.filter(Finding.vuln_type.ilike(f"%{vuln_type_lower}%"))
    
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
        
        # Use lifecycle fields if available, otherwise fall back to created_at
        first_seen_at = finding.first_seen_at if finding.first_seen_at else finding.created_at
        last_seen_at = finding.last_seen_at if finding.last_seen_at else finding.created_at
        
        # Extract evidence from finding.evidence field
        evidence = finding.evidence if hasattr(finding, 'evidence') else None
        
        # Use reusable helper functions for location, impact, and remediation
        from app.utils.finding_response_builder import (
            extract_location_from_raw_data,
            get_impact_summary,
            get_remediation_data
        )
        
        location_data = extract_location_from_raw_data(finding)
        impact_summary = get_impact_summary(finding)
        remediation_data = get_remediation_data(finding)
        
        # Build raw_data_preview (trimmed dict with selected keys)
        raw_data_preview = None
        if finding.raw_data:
            try:
                raw_data_dict = json.loads(finding.raw_data)
                if isinstance(raw_data_dict, dict):
                    # Select only relevant keys for preview (avoid huge payloads)
                    preview_keys = ["payload", "dbms", "template_id", "param", "parameter", "technique", "type", "xss_type", "extracted-results", "matcher-name"]
                    raw_data_preview = {
                        k: v for k, v in raw_data_dict.items() 
                        if k in preview_keys and v is not None
                    }
                    # Truncate long values
                    for key in raw_data_preview:
                        if isinstance(raw_data_preview[key], str) and len(raw_data_preview[key]) > 200:
                            raw_data_preview[key] = raw_data_preview[key][:200] + "..."
            except (json.JSONDecodeError, TypeError):
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
                # New fields
                vuln_type=finding.vuln_type,
                http_method=location_data["http_method"],
                parameter=location_data["parameter"],
                url=location_data["url"],
                path=finding.path,
                evidence=evidence,
                # Lifecycle fields
                first_seen_at=first_seen_at,
                last_seen_at=last_seen_at,
                not_seen_in_latest_scan=finding.not_seen_in_latest_scan if hasattr(finding, 'not_seen_in_latest_scan') else None,
                found_count=finding.found_count if hasattr(finding, 'found_count') else None,
                # Remediation fields
                remediation_summary=remediation_data["remediation_summary"],
                remediation_steps=finding.remediation_steps if hasattr(finding, 'remediation_steps') else None,
                impact_summary=impact_summary,
                default_remediation_steps=remediation_data["default_remediation_steps"],
                ai_source=finding.ai_source if hasattr(finding, 'ai_source') else None,
                ai_model=finding.ai_model if hasattr(finding, 'ai_model') else None,
                ai_confidence=finding.ai_confidence if hasattr(finding, 'ai_confidence') else None,
                raw_data_preview=raw_data_preview,
                # Legacy fields (for backward compatibility)
                first_seen=first_seen_at,
                last_seen=last_seen_at,
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Finding not found. The finding ID does not exist or you don't have permission to access it."
        )
    
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
        evidence=finding_obj.evidence if hasattr(finding_obj, 'evidence') else None,
        first_seen=finding_obj.created_at,
        last_seen=finding_obj.created_at,
    )


@router.get("/{finding_id}", response_model=FindingDetailResponse)
def get_finding_details(
    finding_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a specific finding.
    
    Returns full finding details including raw_data for power users.
    Ensures the finding belongs to the current tenant and user.
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Ensure finding belongs to this tenant and user: Finding → ScanJob → Project
    finding_with_project = (
        db.query(Finding, ScanJob, Project)
        .join(ScanJob, Finding.scan_job_id == ScanJob.id)
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            Finding.id == finding_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id,
        )
        .first()
    )
    
    if not finding_with_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found. The finding ID does not exist or you don't have permission to access it."
        )
    
    finding, scan_job, project = finding_with_project
    
    # Extract categories from raw_data if available
    categories = None
    raw_data_dict = None
    if finding.raw_data:
        try:
            raw_data_dict = json.loads(finding.raw_data)
            if isinstance(raw_data_dict, dict) and "categories" in raw_data_dict:
                categories = raw_data_dict["categories"]
        except (json.JSONDecodeError, TypeError):
            # raw_data is not valid JSON, ignore
            pass
    
    # Use lifecycle fields if available, otherwise fall back to created_at
    first_seen_at = finding.first_seen_at if finding.first_seen_at else finding.created_at
    last_seen_at = finding.last_seen_at if finding.last_seen_at else finding.created_at
    
    # Use reusable helper functions for location, impact, and remediation
    from app.utils.finding_response_builder import (
        extract_location_from_raw_data,
        get_impact_summary,
        get_remediation_data
    )
    
    location_data = extract_location_from_raw_data(finding)
    impact_summary = get_impact_summary(finding)
    remediation_data = get_remediation_data(finding)
    
    # Build raw_data_preview (trimmed dict with selected keys)
    raw_data_preview = None
    if finding.raw_data:
        try:
            raw_data_dict = json.loads(finding.raw_data) if isinstance(finding.raw_data, str) else finding.raw_data
            if isinstance(raw_data_dict, dict):
                # Select only relevant keys for preview (avoid huge payloads)
                preview_keys = ["payload", "dbms", "template_id", "param", "parameter", "technique", "type", "xss_type", "extracted-results", "matcher-name"]
                raw_data_preview = {
                    k: v for k, v in raw_data_dict.items() 
                    if k in preview_keys and v is not None
                }
                # Truncate long values
                for key in raw_data_preview:
                    if isinstance(raw_data_preview[key], str) and len(raw_data_preview[key]) > 200:
                        raw_data_preview[key] = raw_data_preview[key][:200] + "..."
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Ensure raw_data_dict is set for full response
    if not raw_data_dict and finding.raw_data:
        try:
            raw_data_dict = json.loads(finding.raw_data) if isinstance(finding.raw_data, str) else finding.raw_data
        except (json.JSONDecodeError, TypeError):
            raw_data_dict = None
    
    return FindingDetailResponse(
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
        cvss_score=finding.cvss_score,
        tool=finding.tool_name,
        categories=categories,
        vuln_type=finding.vuln_type,
        http_method=location_data["http_method"],
        parameter=location_data["parameter"],
        url=location_data["url"],
        path=finding.path,
        evidence=finding.evidence if hasattr(finding, 'evidence') else None,
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        not_seen_in_latest_scan=finding.not_seen_in_latest_scan if hasattr(finding, 'not_seen_in_latest_scan') else None,
        found_count=finding.found_count if hasattr(finding, 'found_count') else None,
        # Remediation fields
        remediation_summary=remediation_data["remediation_summary"],
        remediation_steps=finding.remediation_steps if hasattr(finding, 'remediation_steps') else None,
        default_remediation_steps=remediation_data["default_remediation_steps"],
        impact_summary=impact_summary,
        ai_source=finding.ai_source if hasattr(finding, 'ai_source') else None,
        ai_model=finding.ai_model if hasattr(finding, 'ai_model') else None,
        ai_confidence=finding.ai_confidence if hasattr(finding, 'ai_confidence') else None,
        raw_data_preview=raw_data_preview,
        raw_data=raw_data_dict,  # Full raw_data as JSON object
        first_seen=first_seen_at,
        last_seen=last_seen_at,
    )

