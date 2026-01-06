"""
Scan recovery service
Handles recovery of scans that were interrupted by system downtime.

On system startup, this service:
1. Finds scans in RUNNING or QUEUED status
2. Checks if their Celery tasks are still active
3. Either requeues them or marks them as failed based on configuration
"""
import logging
import asyncio
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.scan import ScanJob, ScanStatus
from app.models.project import Project
from app.services.scan_orchestrator import ScanOrchestrator

logger = logging.getLogger(__name__)


def check_celery_task_status(celery_task_id: str) -> Optional[str]:
    """
    Check if a Celery task is still active.
    
    Args:
        celery_task_id: The Celery task ID to check
        
    Returns:
        Task status string (PENDING, STARTED, SUCCESS, FAILURE, REVOKED, etc.)
        or None if task doesn't exist or can't be checked
    """
    try:
        from celery.result import AsyncResult
        from app.tasks.celery_app import celery
        
        task_result = AsyncResult(celery_task_id, app=celery)
        status = task_result.status
        
        # Check if task is in a terminal state
        # Terminal states: SUCCESS, FAILURE, REVOKED, REJECTED
        if status in ['SUCCESS', 'FAILURE', 'REVOKED', 'REJECTED']:
            return status
        
        # Active states: PENDING, STARTED, RETRY
        # If task is PENDING but was created a while ago, it might be stale
        if status in ['PENDING', 'STARTED', 'RETRY']:
            return status
        
        return status
    except Exception as e:
        logger.warning(f"Failed to check Celery task status for {celery_task_id}: {e}")
        return None


def check_brain_session_status(brain_session_id: str, org_id: Optional[str] = None, 
                               project_id: Optional[str] = None) -> Optional[str]:
    """
    Check if a brain session is still active.
    
    Args:
        brain_session_id: The brain session ID to check
        org_id: Organization ID (optional)
        project_id: Project ID (optional)
        
    Returns:
        Session status string (running, completed, failed, cancelled) or None
    """
    try:
        from app.core.config import settings
        if not settings.BRAIN_SERVICE_ENABLED:
            return None
            
        from app.services.brain_client import get_brain_client
        import asyncio
        
        brain_client = get_brain_client()
        
        # Try to get session status
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        session_status = loop.run_until_complete(
            brain_client.get_session(
                session_id=brain_session_id,
                org_id=org_id,
                project_id=project_id,
            )
        )
        
        return session_status.get("status") if session_status else None
    except Exception as e:
        logger.warning(f"Failed to check brain session status for {brain_session_id}: {e}")
        return None


def recover_stale_scans(
    db: Session,
    recovery_mode: str = "requeue",
    max_stale_age_hours: int = 24
) -> dict:
    """
    Recover scans that were interrupted by system downtime.
    
    Args:
        db: Database session
        recovery_mode: How to handle stale scans - "requeue" (default) or "fail"
        max_stale_age_hours: Maximum age in hours for a scan to be considered stale
        
    Returns:
        Dictionary with recovery statistics
    """
    stats = {
        "total_stale_scans": 0,
        "requeued": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
    }
    
    # Find scans in RUNNING or QUEUED status
    # Only check scans that are at least 5 minutes old (to avoid interfering with new scans)
    # This prevents the recovery system from interfering with scans that were just created
    min_age = datetime.utcnow() - timedelta(minutes=5)
    stale_cutoff = datetime.utcnow() - timedelta(hours=max_stale_age_hours)
    
    stale_scans = db.query(ScanJob).filter(
        ScanJob.status.in_([ScanStatus.RUNNING, ScanStatus.QUEUED]),
        ScanJob.created_at >= stale_cutoff,  # Only check recent scans (within max_stale_age_hours)
        ScanJob.created_at <= min_age,  # Only check scans that are at least 5 minutes old
    ).all()
    
    if stale_scans:
        logger.info(
            f"Found {len(stale_scans)} scans in RUNNING/QUEUED status to check "
            f"(created between {min_age} and {stale_cutoff})"
        )
    else:
        logger.debug("No stale scans found to recover")
    
    orchestrator = ScanOrchestrator()
    
    for scan_job in stale_scans:
        stats["total_stale_scans"] += 1
        is_stale = False
        recovery_action = None
        
        try:
            # Check Celery task status if present
            if scan_job.celery_task_id:
                task_status = check_celery_task_status(scan_job.celery_task_id)
                
                if task_status is None:
                    # Can't check status - don't assume stale, might be temporary issue
                    # Only mark as stale if scan is definitely old (more than 30 minutes)
                    if scan_job.created_at < datetime.utcnow() - timedelta(minutes=30):
                        is_stale = True
                        logger.info(
                            f"Scan {scan_job.id}: Cannot check Celery task status and scan is older than 30 minutes, "
                            f"assuming stale (task_id: {scan_job.celery_task_id})"
                        )
                    else:
                        logger.debug(
                            f"Scan {scan_job.id}: Cannot check Celery task status but scan is recent, "
                            f"skipping (task_id: {scan_job.celery_task_id})"
                        )
                elif task_status in ['SUCCESS', 'FAILURE', 'REVOKED', 'REJECTED']:
                    # Task is in terminal state but scan is still RUNNING/QUEUED
                    is_stale = True
                    logger.info(
                        f"Scan {scan_job.id}: Celery task is in terminal state "
                        f"({task_status}) but scan status is {scan_job.status.value}"
                    )
                elif task_status == 'PENDING':
                    # Task is pending - check if it's been pending too long
                    # If scan was created more than 1 hour ago and still pending, it's likely stale
                    if scan_job.created_at < datetime.utcnow() - timedelta(hours=1):
                        is_stale = True
                        logger.info(
                            f"Scan {scan_job.id}: Celery task is PENDING but scan "
                            f"was created {datetime.utcnow() - scan_job.created_at} ago"
                        )
                # If task_status is 'STARTED' or 'RETRY', assume it's still active
                else:
                    logger.debug(
                        f"Scan {scan_job.id}: Celery task is {task_status}, "
                        f"assuming still active"
                    )
            
            # Check brain session status if present
            elif scan_job.brain_session_id:
                # Load project to get org_id
                if not scan_job.project:
                    db.refresh(scan_job, ["project"])
                
                org_id = None
                project_id = scan_job.project_id
                if scan_job.project and scan_job.project.tenant:
                    org_id = scan_job.project.tenant.id
                
                session_status = check_brain_session_status(
                    scan_job.brain_session_id,
                    org_id=org_id,
                    project_id=project_id
                )
                
                if session_status is None:
                    # Can't check status - don't assume stale, might be temporary issue
                    # Only mark as stale if scan is definitely old (more than 30 minutes)
                    if scan_job.created_at < datetime.utcnow() - timedelta(minutes=30):
                        is_stale = True
                        logger.info(
                            f"Scan {scan_job.id}: Cannot check brain session status and scan is older than 30 minutes, "
                            f"assuming stale (session_id: {scan_job.brain_session_id})"
                        )
                    else:
                        logger.debug(
                            f"Scan {scan_job.id}: Cannot check brain session status but scan is recent, "
                            f"skipping (session_id: {scan_job.brain_session_id})"
                        )
                elif session_status in ['completed', 'failed', 'cancelled']:
                    # Session is in terminal state but scan is still RUNNING
                    is_stale = True
                    logger.info(
                        f"Scan {scan_job.id}: Brain session is {session_status} "
                        f"but scan status is {scan_job.status.value}"
                    )
                # If session_status is 'running' or 'planning', assume it's still active
                else:
                    logger.debug(
                        f"Scan {scan_job.id}: Brain session is {session_status}, "
                        f"assuming still active"
                    )
            
            else:
                # No celery_task_id or brain_session_id - check if scan is old
                # If scan has been RUNNING/QUEUED for more than 1 hour without a task ID,
                # it's likely stale
                if scan_job.created_at < datetime.utcnow() - timedelta(hours=1):
                    is_stale = True
                    logger.info(
                        f"Scan {scan_job.id}: No task/session ID and scan is older "
                        f"than 1 hour, assuming stale"
                    )
            
            # Recover stale scans
            if is_stale:
                if recovery_mode == "requeue":
                    # Requeue the scan
                    try:
                        # Load project to get target_url and owner_id
                        if not scan_job.project:
                            db.refresh(scan_job, ["project"])
                        
                        if not scan_job.project:
                            logger.error(f"Scan {scan_job.id}: Project not found, cannot requeue")
                            stats["errors"] += 1
                            continue
                        
                        target_url = scan_job.project.target_url
                        scan_level = scan_job.scan_level.value if hasattr(scan_job.scan_level, 'value') else str(scan_job.scan_level)
                        user_id = scan_job.project.owner_id if scan_job.project else None
                        
                        # Requeue using orchestrator
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        celery_task_id = loop.run_until_complete(
                            orchestrator.queue_scan(
                                scan_job.id,
                                target_url,
                                scan_level,
                                user_id=user_id
                            )
                        )
                        
                        scan_job.celery_task_id = celery_task_id
                        scan_job.status = ScanStatus.QUEUED
                        scan_job.error_message = None  # Clear any previous error
                        db.commit()
                        
                        stats["requeued"] += 1
                        logger.info(
                            f"Scan {scan_job.id}: Requeued successfully "
                            f"(new task_id: {celery_task_id})"
                        )
                    except Exception as e:
                        logger.error(f"Failed to requeue scan {scan_job.id}: {e}", exc_info=True)
                        stats["errors"] += 1
                        # Fall through to mark as failed
                        recovery_action = "fail"
                
                if recovery_mode == "fail" or recovery_action == "fail":
                    # Mark scan as failed
                    scan_job.status = ScanStatus.FAILED
                    scan_job.error_message = (
                        f"Scan was interrupted by system downtime and could not be recovered. "
                        f"Original status: {scan_job.status.value}, "
                        f"Recovery mode: {recovery_mode}"
                    )
                    scan_job.completed_at = datetime.utcnow()
                    db.commit()
                    
                    stats["failed"] += 1
                    logger.info(f"Scan {scan_job.id}: Marked as failed due to system downtime")
            
            else:
                stats["skipped"] += 1
                logger.debug(f"Scan {scan_job.id}: Still active, skipping recovery")
        
        except Exception as e:
            logger.error(f"Error recovering scan {scan_job.id}: {e}", exc_info=True)
            stats["errors"] += 1
    
    return stats


def recover_scans_on_startup(recovery_mode: str = "requeue", max_stale_age_hours: int = 24):
    """
    Recover stale scans on system startup.
    
    This function should be called during application startup to handle
    scans that were interrupted by system downtime.
    
    Args:
        recovery_mode: How to handle stale scans - "requeue" (default) or "fail"
        max_stale_age_hours: Maximum age in hours for a scan to be considered stale
    """
    logger.info("Starting scan recovery on system startup...")
    
    db = SessionLocal()
    try:
        stats = recover_stale_scans(db, recovery_mode=recovery_mode, max_stale_age_hours=max_stale_age_hours)
        
        logger.info(
            f"Scan recovery completed: {stats['total_stale_scans']} scans checked, "
            f"{stats['requeued']} requeued, {stats['failed']} failed, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )
        
        return stats
    except Exception as e:
        logger.error(f"Scan recovery failed: {e}", exc_info=True)
        return None
    finally:
        db.close()

