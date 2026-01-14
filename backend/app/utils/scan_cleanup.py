"""
Scan cleanup utilities to fix duplicate PENDING records and other scan issues.
"""
import logging
from sqlalchemy.orm import Session
from app.models.finding import ToolResult, ToolExecutionStatus
from app.models.scan import ScanJob, ScanStatus

logger = logging.getLogger(__name__)


def cleanup_duplicate_pending_records(db: Session, scan_job_id: str = None) -> int:
    """
    Remove duplicate PENDING ToolResult records that block scan completion.
    
    Problem: Backend creates initial PENDING records at scan start.
    When tools actually run, they create new COMPLETED/RUNNING records.
    This leaves orphaned PENDING records that make the UI show "Pending" forever.
    
    Solution: Delete PENDING records for tools that have COMPLETED/RUNNING/TIMED_OUT records.
    
    Args:
        db: Database session
        scan_job_id: Optional scan ID to clean up. If None, cleans all running scans.
        
    Returns:
        Number of duplicate records deleted
    """
    try:
        # Build query for PENDING records
        query = db.query(ToolResult).filter(ToolResult.status == ToolExecutionStatus.PENDING)
        
        if scan_job_id:
            query = query.filter(ToolResult.scan_job_id == scan_job_id)
            logger.info(f"Cleaning duplicate PENDING records for scan {scan_job_id}")
        else:
            # Only clean running scans if no specific scan ID provided
            running_scan_ids = db.query(ScanJob.id).filter(
                ScanJob.status.in_([ScanStatus.RUNNING, ScanStatus.PENDING])
            ).all()
            scan_ids = [s[0] for s in running_scan_ids]
            query = query.filter(ToolResult.scan_job_id.in_(scan_ids))
            logger.info(f"Cleaning duplicate PENDING records for {len(scan_ids)} running scans")
        
        pending_records = query.all()
        
        if not pending_records:
            logger.debug("No PENDING records to clean up")
            return 0
        
        deleted_count = 0
        
        for pending in pending_records:
            # Check if this tool has a COMPLETED/RUNNING/TIMED_OUT record
            actual_status = db.query(ToolResult).filter(
                ToolResult.scan_job_id == pending.scan_job_id,
                ToolResult.tool_name == pending.tool_name,
                ToolResult.status.in_([
                    ToolExecutionStatus.COMPLETED,
                    ToolExecutionStatus.RUNNING,
                    ToolExecutionStatus.TIMED_OUT,
                    ToolExecutionStatus.FAILED,
                    ToolExecutionStatus.CANCELLED
                ])
            ).first()
            
            if actual_status:
                # This tool has an actual status, delete the duplicate PENDING
                logger.debug(
                    f"Deleting duplicate PENDING record for {pending.tool_name} in scan {pending.scan_job_id} "
                    f"(actual status: {actual_status.status})"
                )
                db.delete(pending)
                deleted_count += 1
        
        if deleted_count > 0:
            db.commit()
            logger.info(f"Deleted {deleted_count} duplicate PENDING records")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error cleaning duplicate PENDING records: {e}", exc_info=True)
        db.rollback()
        return 0


def fix_sslscan_pending_for_http(db: Session, scan_job_id: str = None) -> int:
    """
    Mark SSLScan as SKIPPED for HTTP (non-HTTPS) targets.
    
    Problem: SSLScan is created as PENDING for all scans, including HTTP targets.
    Brain correctly doesn't run SSLScan for HTTP, but the PENDING record blocks completion.
    
    Solution: Mark SSLScan as SKIPPED for scans with HTTP (not HTTPS) targets.
    
    Args:
        db: Database session
        scan_job_id: Optional scan ID to fix. If None, fixes all scans.
        
    Returns:
        Number of records fixed
    """
    try:
        # Find SSLScan PENDING records
        query = db.query(ToolResult).filter(
            ToolResult.tool_name == "sslscan",
            ToolResult.status == ToolExecutionStatus.PENDING
        )
        
        if scan_job_id:
            query = query.filter(ToolResult.scan_job_id == scan_job_id)
        
        sslscan_pending = query.all()
        
        if not sslscan_pending:
            return 0
        
        fixed_count = 0
        
        for sslscan in sslscan_pending:
            # Get scan job URL
            scan_job = db.query(ScanJob).filter(ScanJob.id == sslscan.scan_job_id).first()
            
            if not scan_job or not scan_job.url:
                continue
            
            # Check if target is HTTP (not HTTPS)
            if scan_job.url.startswith("http://"):
                logger.info(
                    f"Marking SSLScan as SKIPPED for HTTP target in scan {scan_job.id}: {scan_job.url}"
                )
                sslscan.status = ToolExecutionStatus.SKIPPED
                sslscan.error_message = "HTTP target - SSL/TLS scan not applicable"
                fixed_count += 1
        
        if fixed_count > 0:
            db.commit()
            logger.info(f"Marked {fixed_count} SSLScan records as SKIPPED for HTTP targets")
        
        return fixed_count
        
    except Exception as e:
        logger.error(f"Error fixing SSLScan PENDING records: {e}", exc_info=True)
        db.rollback()
        return 0


def auto_complete_stalled_scans(db: Session) -> int:
    """
    Auto-complete scans that are stuck in RUNNING state but all tools are done.
    
    Problem: Scans show as "running" forever if duplicate PENDING records exist,
    even though all actual tools have completed.
    
    Solution: Mark scan as COMPLETED if all non-PENDING tools are done.
    
    Args:
        db: Database session
        
    Returns:
        Number of scans completed
    """
    try:
        # Find scans stuck in RUNNING
        running_scans = db.query(ScanJob).filter(ScanJob.status == ScanStatus.RUNNING).all()
        
        completed_count = 0
        
        for scan in running_scans:
            # Get all tool results (excluding PENDING)
            non_pending_tools = db.query(ToolResult).filter(
                ToolResult.scan_job_id == scan.id,
                ToolResult.status != ToolExecutionStatus.PENDING
            ).all()
            
            if not non_pending_tools:
                # No tools have started yet, skip
                continue
            
            # Check if all non-pending tools are in a final state
            all_done = all(
                tool.status in [
                    ToolExecutionStatus.COMPLETED,
                    ToolExecutionStatus.FAILED,
                    ToolExecutionStatus.TIMED_OUT,
                    ToolExecutionStatus.CANCELLED,
                    ToolExecutionStatus.SKIPPED
                ]
                for tool in non_pending_tools
            )
            
            if all_done:
                logger.info(
                    f"Auto-completing stalled scan {scan.id}: all {len(non_pending_tools)} tools are done"
                )
                scan.status = ScanStatus.COMPLETED
                completed_count += 1
        
        if completed_count > 0:
            db.commit()
            logger.info(f"Auto-completed {completed_count} stalled scans")
        
        return completed_count
        
    except Exception as e:
        logger.error(f"Error auto-completing stalled scans: {e}", exc_info=True)
        db.rollback()
        return 0


def cleanup_scan(db: Session, scan_job_id: str) -> dict:
    """
    Run all cleanup functions for a specific scan.
    
    Args:
        db: Database session
        scan_job_id: Scan ID to clean up
        
    Returns:
        Dict with counts of records cleaned/fixed
    """
    logger.info(f"Running cleanup for scan {scan_job_id}")
    
    results = {
        "duplicate_pending_deleted": cleanup_duplicate_pending_records(db, scan_job_id),
        "sslscan_fixed": fix_sslscan_pending_for_http(db, scan_job_id),
        "scan_completed": 0
    }
    
    # Check if scan should be completed
    scan = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
    if scan and scan.status == ScanStatus.RUNNING:
        results["scan_completed"] = auto_complete_stalled_scans(db)
    
    logger.info(f"Cleanup complete for scan {scan_job_id}: {results}")
    return results
