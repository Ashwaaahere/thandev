"""
Public Stats API endpoint for landing page
Returns global statistics (total scans, projects, vulnerabilities)
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models.scan import ScanJob
from app.models.project import Project
from app.models.finding import Finding

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
)


@router.get("", response_class=JSONResponse)
async def get_public_stats(db: Session = Depends(get_db)):
    """
    Public stats endpoint for landing page.
    Returns global statistics across all tenants (no authentication required).
    
    Returns:
        - total_scans: Total number of scans performed
        - total_projects: Total number of projects using Thandev
        - total_vulnerabilities: Total number of vulnerabilities found
    """
    try:
        # Total scans (all ScanJob entries)
        total_scans = db.query(func.count(ScanJob.id)).scalar() or 0
        
        # Total projects (all verified projects)
        # Count distinct projects that have at least one scan
        total_projects = (
            db.query(func.count(func.distinct(Project.id)))
            .join(ScanJob, Project.id == ScanJob.project_id)
            .scalar() or 0
        )
        
        # If no projects with scans, count all projects as fallback
        if total_projects == 0:
            total_projects = db.query(func.count(Project.id)).scalar() or 0
        
        # Total vulnerabilities (all Finding entries)
        total_vulnerabilities = db.query(func.count(Finding.id)).scalar() or 0
        
        return {
            "total_scans": total_scans,
            "total_projects": total_projects,
            "total_vulnerabilities": total_vulnerabilities,
            # Legacy fields for backward compatibility
            "signals_today": 0,
            "exploits_today": 0,
            "vendors_today": 0,
            "checks_per_run": 0,
            "issues_prevented_7d": 0,
        }
    except Exception as e:
        # Log error but return zeros to prevent frontend breakage
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching public stats: {e}", exc_info=True)
        return {
            "total_scans": 0,
            "total_projects": 0,
            "total_vulnerabilities": 0,
            "signals_today": 0,
            "exploits_today": 0,
            "vendors_today": 0,
            "checks_per_run": 0,
            "issues_prevented_7d": 0,
        }

