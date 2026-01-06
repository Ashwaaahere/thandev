"""
Celery application configuration and tasks

NOTE: Celery is used as a FALLBACK when the Brain Service is disabled or unavailable.
When BRAIN_SERVICE_ENABLED=true (default), the Brain Service handles scan orchestration
via Redis Streams and the Runner Service. Celery tasks are only triggered when:
1. BRAIN_SERVICE_ENABLED=false, OR
2. Brain session creation fails AND BRAIN_REQUIRED=false

See backend/app/api/scans.py for the conditional logic that chooses between
Brain sessions and Celery tasks.
"""
from celery import Celery
from app.core.config import settings

celery = Celery(
    "thandev",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery configuration
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 minutes soft limit
    # Allow dynamic queue creation for user-specific queues
    task_create_missing_queues=True,
    # Process queues with minimal prefetch to ensure sequential processing per queue
    worker_prefetch_multiplier=1,  # Only prefetch one task at a time per worker
    # Configure worker to consume from all queues (default + user-specific)
    # This allows the worker to pick up tasks from dynamically created user queues
    worker_direct=True,  # Use direct exchange for simpler routing
)


@celery.task(name="thandev.run_scan_task", bind=True, max_retries=10)
def run_scan_task(self, scan_job_id: str, target_url: str, scan_level: str, user_id: str = None):
    """
    Celery task to execute a security scan (FALLBACK MODE ONLY).
    
    NOTE: This task is only used when Brain Service is disabled or unavailable.
    When Brain Service is enabled (default), scans are orchestrated via Redis Streams
    and the Runner Service, not via Celery.
    
    This task delegates to the scan orchestrator's run_scan_for_job function,
    which handles the actual execution based on the scan level profile.
    
    Triggered from: backend/app/api/scans.py (create_scan/quick_scan endpoints)
    when BRAIN_SERVICE_ENABLED=false or brain session creation fails.
    
    Args:
        scan_job_id: ID of the scan job
        target_url: URL to scan (used for logging, actual URL comes from job.project)
        scan_level: Scan level string (basic, pro, advanced)
        user_id: User ID for per-user concurrency control (optional, will be extracted from scan_job if not provided)
    """
    from app.core.database import SessionLocal
    from app.models.scan import ScanJob, ScanStatus
    from app.services.scan_orchestrator import run_scan_for_job
    from app.services.queue_manager import get_queue_manager, TooManyScansForUser
    from datetime import datetime, timezone
    import logging
    
    logger = logging.getLogger(__name__)
    db = SessionLocal()
    scan_job = None
    
    try:
        # Get scan job
        scan_job = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
        if not scan_job:
            logger.error(f"Scan job {scan_job_id} not found")
            return {"error": "Scan job not found"}
        
        # Extract user_id from scan_job if not provided
        if not user_id and scan_job.project:
            user_id = scan_job.project.owner_id
        
        if not user_id:
            logger.warning(f"No user_id available for scan {scan_job_id}, skipping concurrency control")
            user_id = "unknown"
        
        # Per-user concurrency control using Redis
        queue_manager = get_queue_manager()
        max_per_user = 3  # Allow 3 concurrent scans per user (increased from 1 for better usability)
        
        try:
            with queue_manager.user_scan_slot(user_id, max_per_user=max_per_user):
                # Update status to running
                scan_job.status = ScanStatus.RUNNING
                scan_job.started_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(scan_job)
                
                logger.info(f"Starting scan {scan_job_id} for {target_url} at level {scan_level} (user: {user_id})")
                
                # Delegate to the orchestrator - it handles everything based on scan level
                # The orchestrator will:
                # - Get the scan profile for this level
                # - Run all tools in the profile
                # - Parse findings
                # - Generate AI report
                # - Update job status to completed/failed
                run_scan_for_job(scan_job)
        except TooManyScansForUser as e:
            # User has too many active scans, retry later
            logger.info(f"Scan {scan_job_id} deferred: {str(e)}. Retrying in 30 seconds...")
            # Retry the task after 30 seconds
            raise self.retry(countdown=30, exc=e)
        
        # Reload job to get final state
        db.refresh(scan_job)
        
        # Get findings count for return value
        findings_count = len(scan_job.findings) if scan_job.findings else 0
        
        logger.info(f"Scan {scan_job_id} completed with {findings_count} findings")
        
        # Get tools that were run from the profile
        from app.services.scan_profiles import get_tool_names
        try:
            tools_run = get_tool_names(scan_level)
        except ValueError:
            tools_run = []
        
        return {
            "scan_job_id": scan_job_id,
            "status": scan_job.status.value,
            "findings_count": findings_count,
            "tools_run": tools_run,
        }
        
    except Exception as e:
        logger.error(f"Scan {scan_job_id} failed: {str(e)}", exc_info=True)
        
        if scan_job:
            try:
                scan_job.status = ScanStatus.FAILED
                scan_job.error_message = str(e)
                scan_job.completed_at = datetime.now(timezone.utc)
                db.commit()
            except Exception as db_error:
                logger.error(f"Failed to update scan job status: {db_error}")
                db.rollback()
        
        return {"error": str(e)}
    
    finally:
        db.close()


@celery.task
def ingest_nvd():
    """Ingest NVD (National Vulnerability Database) data"""
    # TODO: implement
    return "ok"


@celery.task
def ingest_kev():
    """Ingest KEV (Known Exploited Vulnerabilities) data"""
    # TODO: implement
    return "ok"


@celery.task
def enrich_pending():
    """Enrich pending findings with additional data"""
    # TODO: implement
    return "ok"


# Export celery app as celery_app for compatibility
celery_app = celery
