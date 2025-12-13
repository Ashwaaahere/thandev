"""
Performance Scans API router
"""
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.core.database import get_db
from app.core.tenant_utils import require_tenant, get_current_user
from app.models.user import User
from app.models.tenant import Tenant
from app.models.project import Project
from app.models.performance_scan import PerformanceScan, PerformanceScanStatus
from app.models.scan import ScanLevel
from app.schemas.performance import (
    PerformanceScanCreate,
    PerformanceScanDetail,
    PerformanceScanListItem,
    PerformanceScanListResponse,
    QuickPerformanceScanResponse,
)

router = APIRouter(prefix="/performance", tags=["performance"])
logger = logging.getLogger(__name__)


@router.post("/quick", response_model=QuickPerformanceScanResponse)
async def quick_performance_scan(
    payload: PerformanceScanCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Create and start a quick performance scan.
    
    Either project_id or target_url must be provided.
    If project_id is provided, uses the project's target_url as fallback.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    target_url_to_use = None
    project_id_to_use = None
    
    # If project_id is provided, load and validate the project
    if payload.project_id:
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
        
        project_id_to_use = project.id
        target_url_to_use = payload.target_url or project.target_url
    else:
        # New target URL provided
        if not payload.target_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either project_id or target_url must be provided"
            )
        target_url_to_use = str(payload.target_url)
    
    # Create performance scan
    now = datetime.now(timezone.utc)
    scan = PerformanceScan(
        project_id=project_id_to_use,
        tenant_id=tenant.id,
        owner_id=current_user.id,
        target_url=target_url_to_use,
        scan_level=ScanLevel(payload.scan_level),
        status=PerformanceScanStatus.QUEUED,
        created_at=now,
    )
    
    db.add(scan)
    db.flush()  # Get the ID
    
    # Run actual Lighthouse scan
    try:
        scan.status = PerformanceScanStatus.RUNNING
        scan.started_at = now
        db.commit()
        
        # Import performance scanner service
        from app.services.performance_scanner import run_lighthouse_scan
        
        # Run Lighthouse scan (device defaults to desktop for now)
        # TODO: Add device selection based on scan_level or user preference
        device = "desktop"
        metrics = await run_lighthouse_scan(target_url_to_use, device)
        
        # Update scan with results
        scan.metrics = metrics
        scan.status = PerformanceScanStatus.COMPLETED
        scan.completed_at = datetime.now(timezone.utc)
        
        logger.info(f"Performance scan completed for {target_url_to_use}: score={metrics.get('overall_score')}")
        
    except Exception as e:
        logger.error(f"Error running performance scan: {e}", exc_info=True)
        scan.status = PerformanceScanStatus.FAILED
        scan.error_message = str(e)
        scan.completed_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(scan)
    
    return QuickPerformanceScanResponse(
        project_id=project_id_to_use,
        scan_id=scan.id,
    )


@router.get("", response_model=PerformanceScanListResponse)
async def list_performance_scans(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    scan_level: Optional[str] = Query(None, description="Filter by scan level"),
    search: Optional[str] = Query(None, description="Search in target URL or project name"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of scans to return"),
    offset: int = Query(0, ge=0, description="Number of scans to skip"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    List performance scans for the current tenant and user.
    
    Supports filtering by project_id, status, scan_level, and searching in target_url or project name.
    Results are ordered by created_at DESC (newest first).
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Base query: PerformanceScan → Project (optional join), filtered by tenant and user
    query = (
        db.query(PerformanceScan, Project)
        .outerjoin(Project, PerformanceScan.project_id == Project.id)
        .filter(
            PerformanceScan.tenant_id == tenant.id,
            PerformanceScan.owner_id == current_user.id,
        )
    )
    
    # Apply filters
    if project_id:
        query = query.filter(PerformanceScan.project_id == project_id)
    
    if status:
        try:
            status_enum = PerformanceScanStatus(status.lower())
            query = query.filter(PerformanceScan.status == status_enum)
        except ValueError:
            # Invalid status, return empty results
            pass
    
    if scan_level:
        try:
            level_enum = ScanLevel(scan_level.lower())
            query = query.filter(PerformanceScan.scan_level == level_enum)
        except ValueError:
            # Invalid level, return empty results
            pass
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                PerformanceScan.target_url.ilike(search_pattern),
                Project.name.ilike(search_pattern),
            )
        )
    
    # Get total count before pagination
    total = query.count()
    
    # Order by created_at DESC and apply pagination
    scans_with_project = (
        query
        .order_by(PerformanceScan.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    # Map to PerformanceScanListItem
    items = []
    for scan, project in scans_with_project:
        # Extract perf_score from metrics
        perf_score = None
        if scan.metrics and isinstance(scan.metrics, dict):
            perf_score = scan.metrics.get("overall_score")
            if perf_score is not None:
                try:
                    perf_score = float(perf_score)
                except (ValueError, TypeError):
                    perf_score = None
        
        items.append(
            PerformanceScanListItem(
                id=scan.id,
                project_id=scan.project_id,
                project_name=project.name if project else None,
                target_url=scan.target_url,
                scan_level=scan.scan_level.value if hasattr(scan.scan_level, 'value') else str(scan.scan_level),
                status=scan.status.value if hasattr(scan.status, 'value') else str(scan.status),
                perf_score=perf_score,
                completed_at=scan.completed_at,
            )
        )
    
    return PerformanceScanListResponse(items=items, total=total)


@router.get("/{scan_id}", response_model=PerformanceScanDetail)
async def get_performance_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific performance scan by ID.
    
    Ensures the scan belongs to the current tenant and user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    scan = (
        db.query(PerformanceScan)
        .filter(
            PerformanceScan.id == scan_id,
            PerformanceScan.tenant_id == tenant.id,
            PerformanceScan.owner_id == current_user.id,
        )
        .first()
    )
    
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Performance scan not found or access denied"
        )
    
    return PerformanceScanDetail(
        id=scan.id,
        project_id=scan.project_id,
        target_url=scan.target_url,
        scan_level=scan.scan_level.value if hasattr(scan.scan_level, 'value') else str(scan.scan_level),
        status=scan.status.value if hasattr(scan.status, 'value') else str(scan.status),
        metrics=scan.metrics,
        error_message=scan.error_message,
        created_at=scan.created_at,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
    )
