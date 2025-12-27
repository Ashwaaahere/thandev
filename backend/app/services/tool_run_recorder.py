"""
Tool Run Recorder Service

Helper functions for tracking tool execution runs with detailed metadata.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.finding import ToolResult, ToolExecutionStatus, Finding
from app.services.tool_name_utils import canonical_tool_name

logger = logging.getLogger(__name__)


def start_tool_run(
    db: Session,
    scan_id: str,
    tool_name: str,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Start a tool run by creating a ToolResult record with PENDING status.
    
    Args:
        db: Database session
        scan_id: Scan job ID
        tool_name: Name of the tool being executed (will be normalized to canonical form)
        meta: Optional metadata dict (command, args, version, etc.)
        
    Returns:
        tool_run_id: ID of the created ToolResult record
    """
    # Normalize tool_name to canonical form at persistence (choke point)
    # Rule: Never trust upstream tool_name strings. Normalize at persistence.
    canonical_name = canonical_tool_name(tool_name)
    
    now = datetime.now(timezone.utc)
    
    tool_result = ToolResult(
        scan_job_id=scan_id,
        tool_name=canonical_name,
        status=ToolExecutionStatus.PENDING,
        started_at=now,
        meta=meta,
    )
    
    db.add(tool_result)
    db.flush()  # Flush to get ID
    
    logger.info(
        "Started tool run",
        extra={
            "tool_run_id": tool_result.id,
            "scan_id": scan_id,
            "tool_name": tool_name,
        }
    )
    
    return tool_result.id


def finish_tool_run(
    db: Session,
    tool_run_id: str,
    status: ToolExecutionStatus,
    exit_code: Optional[int],
    stdout: Optional[str] = None,
    stderr: Optional[str] = None,
    output_path: Optional[str] = None,
    duration_ms: Optional[int] = None,
    ingest_error: Optional[str] = None,
) -> None:
    """
    Finish a tool run by updating the ToolResult record with execution results.
    
    Args:
        db: Database session
        tool_run_id: ID of the ToolResult record
        status: Final execution status
        exit_code: Tool exit code
        stdout: Standard output (will be truncated to 1000 chars for preview)
        stderr: Standard error (will be truncated to 1000 chars for preview)
        output_path: Path to output file
        duration_ms: Duration in milliseconds
    """
    tool_result = db.query(ToolResult).filter(ToolResult.id == tool_run_id).first()
    if not tool_result:
        logger.error(f"ToolResult {tool_run_id} not found")
        return
    
    now = datetime.now(timezone.utc)
    
    # Update status and exit code
    tool_result.status = status
    tool_result.exit_code = exit_code
    tool_result.completed_at = now
    
    # Truncate stdout/stderr to 1000 chars for preview
    if stdout is not None:
        tool_result.stdout_preview = stdout[:1000] if len(stdout) > 1000 else stdout
    if stderr is not None:
        tool_result.stderr_preview = stderr[:1000] if len(stderr) > 1000 else stderr
    
    # Store output path
    if output_path:
        tool_result.output_path = output_path
    
    # Store duration in milliseconds
    if duration_ms is not None:
        tool_result.duration_ms = duration_ms
    elif tool_result.execution_time is not None:
        # Compute from execution_time if available
        tool_result.duration_ms = int(tool_result.execution_time * 1000)
    
    # If ingestion failed, update status and error message
    if ingest_error:
        # Mark as failed if ingestion error occurred (even if tool execution succeeded)
        if status == ToolExecutionStatus.COMPLETED:
            status = ToolExecutionStatus.FAILED
            tool_result.status = status
        tool_result.error_code = "ingestion_error"
        if tool_result.error_message:
            tool_result.error_message = f"{tool_result.error_message}; Ingestion error: {ingest_error}"
        else:
            tool_result.error_message = f"Ingestion error: {ingest_error}"
    
    db.commit()
    
    logger.info(
        "Finished tool run",
        extra={
            "tool_run_id": tool_run_id,
            "scan_id": tool_result.scan_job_id,
            "tool_name": tool_result.tool_name,
            "status": status.value,
            "exit_code": exit_code,
            "duration_ms": tool_result.duration_ms,
        }
    )


def update_tool_run_counts(
    db: Session,
    tool_run_id: str,
    parsed_count: int,
    created_count: int,
) -> None:
    """
    Update the parsed and created findings counts for a tool run.
    
    Called after ingestion completes to track how many findings were
    parsed from output vs actually created in the database.
    
    Counts are computed from DB query (source of truth) after ingestion flush/commit.
    
    Args:
        db: Database session
        tool_run_id: ID of the ToolResult record
        parsed_count: Number of findings parsed from output
        created_count: Number of findings actually created in DB (may be overridden by DB query)
    """
    tool_result = db.query(ToolResult).filter(ToolResult.id == tool_run_id).first()
    if not tool_result:
        logger.error(f"ToolResult {tool_run_id} not found")
        return
    
    # Store parsed count (from output parsing)
    tool_result.parsed_findings_count = parsed_count
    
    # Compute actual created count from DB (source of truth)
    # v2: Use tool_result_id if available (more accurate, handles re-runs)
    # v1: Fallback to scan_id + tool_name for legacy findings
    actual_created_count = db.query(Finding).filter(
        Finding.tool_result_id == tool_result.id
    ).count()
    
    count_query_method = "tool_result_id"
    
    # If no findings with tool_result_id (legacy), fallback to scan_id + tool_name
    if actual_created_count == 0:
        fallback_count = db.query(Finding).filter(
            Finding.scan_job_id == tool_result.scan_job_id,
            Finding.tool_name == tool_result.tool_name
        ).count()
        if fallback_count > 0:
            actual_created_count = fallback_count
            count_query_method = "scan_id+tool_name"
            logger.warning(
                f"ToolResult {tool_run_id} has findings without tool_result_id. "
                f"Using fallback query (scan_id+tool_name). Consider updating findings to set tool_result_id."
            )
    
    logger.info(
        "Updated tool run counts",
        extra={
            "tool_run_id": tool_run_id,
            "scan_job_id": tool_result.scan_job_id,
            "tool_name": tool_result.tool_name,
            "parsed_count": parsed_count,
            "created_count": actual_created_count,
            "count_query_method": count_query_method,
            "parameter_created_count": created_count,
        }
    )
    
    # Use DB count as source of truth
    tool_result.created_findings_count = actual_created_count
    
    # Log if parameter count differs from DB count (for debugging)
    if created_count != actual_created_count:
        logger.warning(
            "Tool run count mismatch: parameter count differs from DB count",
            extra={
                "tool_run_id": tool_run_id,
                "scan_id": tool_result.scan_job_id,
                "tool_name": tool_result.tool_name,
                "parameter_count": created_count,
                "db_count": actual_created_count,
            }
        )
    
    db.commit()
    
    logger.info(
        "Updated tool run counts",
        extra={
            "tool_run_id": tool_run_id,
            "scan_id": tool_result.scan_job_id,
            "tool_name": tool_result.tool_name,
            "parsed_count": parsed_count,
            "created_count": actual_created_count,
        }
    )

