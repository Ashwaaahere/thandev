"""
Batch findings endpoint for brain service integration
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.tenant_utils import require_tenant, get_current_tenant
from app.core.dependencies import require_approved_user
from app.models.finding import Finding
from app.models.scan import ScanJob
from app.models.project import Project

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/findings",
    tags=["findings"],
    dependencies=[Depends(require_approved_user)],
)


@router.post("/batch")
async def get_findings_batch(
    finding_ids: List[str],
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant = Depends(require_tenant),
):
    """
    Get multiple findings by IDs (for brain service).
    
    This endpoint allows the brain service to load findings
    for report prompt generation.
    
    Args:
        finding_ids: List of finding IDs to retrieve
        org_id: Organization ID for filtering (optional, uses tenant from header)
        project_id: Project ID for filtering (optional)
        
    Returns:
        List of finding dicts with normalized fields
    """
    if not finding_ids:
        return {"findings": []}
    
    # Use tenant from header if org_id not provided
    if not org_id:
        org_id = tenant.id
    
    # Build query with security filters
    query = db.query(Finding).join(ScanJob).join(Project).filter(
        Finding.id.in_(finding_ids),
        Project.tenant_id == org_id,
    )
    
    # Add project filter if provided
    if project_id:
        query = query.filter(Project.id == project_id)
    
    findings = query.all()
    
    # Convert to dict format
    findings_list = []
    for finding in findings:
        findings_list.append({
            "id": finding.id,
            "title": finding.title or "",
            "description": finding.description,
            "severity": finding.severity.value if finding.severity else "info",
            "cve_id": finding.cve_id,
            "cvss_score": float(finding.cvss_score) if finding.cvss_score is not None else None,
            "url": finding.url,
            "path": finding.path,
            "recommendation": finding.recommendation,
            "tool_name": finding.tool_name or "unknown",
            "tool_id": finding.tool_name or "unknown",
            "raw_data": finding.raw_data,
            "created_at": finding.created_at.isoformat() if finding.created_at else None,
            "scan_job_id": finding.scan_job_id,
            "org_id": org_id,
            "project_id": finding.scan_job.project_id if finding.scan_job else None,
        })
    
    logger.info(f"Returned {len(findings_list)} findings for brain service")
    
    return {"findings": findings_list}




