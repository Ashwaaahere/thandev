"""
Background health check service to automatically fix stuck scans.
Runs periodically to detect scans that are RUNNING but have no tool states,
and automatically retries publishing steps.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.scan import ScanJob, ScanStatus
from app.models.scan_tool_state import ScanToolState
from app.models.finding import ToolResult
from app.models.project import Project
from app.models.tenant import Tenant
from app.services.runner_client import publish_scan_steps_to_runner

logger = logging.getLogger(__name__)

# Global flag to control the health check loop
_health_check_running = False
_health_check_task = None


async def check_and_fix_stuck_scans():
    """
    Check for stuck scans (RUNNING but no tool states) and fix them.
    This runs in a background loop.
    """
    global _health_check_running
    
    logger.info("[SCAN-HEALTH] Starting scan health check service")
    _health_check_running = True
    
    while _health_check_running:
        try:
            db = SessionLocal()
            try:
                # Find scans that are RUNNING but have no tool states or results
                # Only check scans created in the last hour (to avoid old stuck scans)
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
                
                stuck_scans = db.query(ScanJob).filter(
                    ScanJob.status == ScanStatus.RUNNING,
                    ScanJob.created_at >= cutoff_time,
                ).all()
                
                logger.info(f"[SCAN-HEALTH] Checking {len(stuck_scans)} RUNNING scans")
                
                for scan_job in stuck_scans:
                    # Check if scan has tool states or results
                    tool_state_count = db.query(ScanToolState).filter(
                        ScanToolState.scan_id == scan_job.id
                    ).count()
                    
                    tool_result_count = db.query(ToolResult).filter(
                        ToolResult.scan_job_id == scan_job.id
                    ).count()
                    
                    # If scan is RUNNING but has no tool states or results, it's stuck
                    if tool_state_count == 0 and tool_result_count == 0:
                        logger.warning(
                            f"[SCAN-HEALTH] Found stuck scan {scan_job.id}: "
                            f"RUNNING but no tool states ({tool_state_count}) or results ({tool_result_count})"
                        )
                        
                        # Get project and tenant info
                        project = db.query(Project).filter(Project.id == scan_job.project_id).first()
                        if not project:
                            logger.error(f"[SCAN-HEALTH] Project not found for scan {scan_job.id}")
                            continue
                        
                        tenant = db.query(Tenant).filter(Tenant.id == project.tenant_id).first()
                        if not tenant:
                            logger.error(f"[SCAN-HEALTH] Tenant not found for scan {scan_job.id}")
                            continue
                        
                        # Try to publish steps
                        logger.info(f"[SCAN-HEALTH] Attempting to fix stuck scan {scan_job.id}")
                        try:
                            success = await publish_scan_steps_to_runner(
                                scan_job_id=scan_job.id,
                                target_url=project.target_url,
                                scan_level=scan_job.scan_level,
                                org_id=tenant.id,
                                project_id=project.id,
                                background_tasks=None,  # No background tasks in health check
                            )
                            
                            if success:
                                logger.info(f"[SCAN-HEALTH] Successfully fixed stuck scan {scan_job.id}")
                            else:
                                logger.error(f"[SCAN-HEALTH] Failed to fix stuck scan {scan_job.id}")
                                # Mark as failed if we can't fix it
                                scan_job.status = ScanStatus.FAILED
                                scan_job.error_message = "Scan stuck: failed to publish steps (auto-recovery failed)"
                                db.commit()
                        except Exception as fix_error:
                            logger.error(
                                f"[SCAN-HEALTH] Exception fixing stuck scan {scan_job.id}: {fix_error}",
                                exc_info=True
                            )
                            # Mark as failed
                            scan_job.status = ScanStatus.FAILED
                            scan_job.error_message = f"Scan stuck: auto-recovery exception: {str(fix_error)}"
                            db.commit()
            finally:
                db.close()
            
            # Wait 60 seconds before next check
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"[SCAN-HEALTH] Error in health check loop: {e}", exc_info=True)
            # Wait 30 seconds before retrying on error
            await asyncio.sleep(30)


def start_scan_health_check():
    """Start the background health check task"""
    global _health_check_task
    
    if _health_check_task is None or _health_check_task.done():
        try:
            # Get event loop (should already exist in FastAPI context)
            loop = asyncio.get_event_loop()
            _health_check_task = loop.create_task(check_and_fix_stuck_scans())
            logger.info("[SCAN-HEALTH] Started background health check task")
        except RuntimeError:
            # No event loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _health_check_task = loop.create_task(check_and_fix_stuck_scans())
            logger.info("[SCAN-HEALTH] Started background health check task (new event loop)")
        except Exception as e:
            logger.error(f"[SCAN-HEALTH] Failed to start health check task: {e}", exc_info=True)
    else:
        logger.info("[SCAN-HEALTH] Health check task already running")


def stop_scan_health_check():
    """Stop the background health check task"""
    global _health_check_running, _health_check_task
    
    _health_check_running = False
    if _health_check_task and not _health_check_task.done():
        _health_check_task.cancel()
        logger.info("[SCAN-HEALTH] Stopped background health check task")

