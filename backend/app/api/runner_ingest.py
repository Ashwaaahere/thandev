"""
Runner service API router for tool result ingestion.

This router handles endpoints called by the runner service.
Moved from /api/internal/* to /api/runner/* to avoid Fly.io proxy blocking.
Only requires service authentication (Bearer token), no tenant/user auth.
"""
import json
import logging
import uuid
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from datetime import datetime, timezone
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import require_runner_service_auth
from app.models.scan import ScanJob, ScanStatus
from app.models.finding import ToolResult, ToolExecutionStatus
from app.schemas.scan import ToolResultCreate, ToolResultResponse
from app.services.findings_ingestor import create_or_update_finding

router = APIRouter(
    prefix="/scans",
    tags=["runner-internal"],
    dependencies=[Depends(require_runner_service_auth)],
)
logger = logging.getLogger(__name__)

class ToolStartedCreate(BaseModel):
    tool_run_id: str
    step_id: str
    tool_name: str
    tool_id: str | None = None
    command: str | None = None


@router.get("/{scan_id}", status_code=status.HTTP_200_OK)
async def get_scan_status_for_runner(
    scan_id: str,
    db: Session = Depends(get_db),
):
    """
    Minimal scan status endpoint for the runner.

    This is intentionally service-authenticated (RUNNER_API_TOKEN) and does NOT require tenant/user auth.
    Runner uses this to stop executing steps if a scan is cancelled/failed/completed in core.
    """
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
    if not scan_job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scan not found: {scan_id}")
    return {
        "scan_id": scan_job.id,
        "status": scan_job.status.value if hasattr(scan_job.status, "value") else str(scan_job.status),
        "error_message": scan_job.error_message,
        "completed_at": scan_job.completed_at.isoformat() if scan_job.completed_at else None,
        "started_at": scan_job.started_at.isoformat() if scan_job.started_at else None,
    }


@router.post("/{scan_id}/started", status_code=status.HTTP_200_OK)
async def mark_scan_running_for_runner(
    scan_id: str,
    db: Session = Depends(get_db),
):
    """
    Runner calls this when it begins executing the first step for a scan.

    This lets the UI show RUNNING (instead of QUEUED) even before the first tool result is posted.
    """
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
    if not scan_job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scan not found: {scan_id}")
    if scan_job.status == ScanStatus.QUEUED:
        scan_job.status = ScanStatus.RUNNING
        if not scan_job.started_at:
            scan_job.started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(scan_job)
    return {"scan_id": scan_job.id, "status": scan_job.status.value}


@router.post("/{scan_id}/tool-started", status_code=status.HTTP_200_OK)
async def mark_tool_started_for_runner(
    scan_id: str,
    payload: ToolStartedCreate,
    db: Session = Depends(get_db),
):
    """
    Runner calls this when it begins executing a tool for a scan.

    Creates (or updates) a ToolResult row with status=RUNNING so the UI can reflect progress
    before the final tool-results payload is posted.
    """
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
    if not scan_job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scan not found: {scan_id}")

    # PERMANENT FIX: Look for existing record by tool_run_id OR by tool_name (for multi-mode tools like ZAP)
    # For tools with multiple modes (ZAP: ajax_spider, active_scan), match by tool_name regardless of status
    # This prevents duplicate records when multiple ZAP modes run
    existing = db.query(ToolResult).filter(
        ToolResult.scan_job_id == scan_id,
        (ToolResult.tool_run_id == payload.tool_run_id) | 
        ((ToolResult.tool_name == payload.tool_name) & (ToolResult.status.in_([ToolExecutionStatus.PENDING, ToolExecutionStatus.RUNNING])))
    ).order_by(ToolResult.created_at.asc()).first()  # Get oldest record if multiple match

    now = datetime.now(timezone.utc)
    if existing:
        # Update existing record (whether it's matched by tool_run_id or was PENDING)
        if not existing.tool_run_id:
            existing.tool_run_id = payload.tool_run_id
        if not existing.started_at:
            existing.started_at = now
        if existing.status in (None, ToolExecutionStatus.PENDING):
            existing.status = ToolExecutionStatus.RUNNING
        if payload.command and not existing.command:
            existing.command = payload.command
        db.commit()
        logger.info(f"Updated existing ToolResult {existing.id} for {payload.tool_name} (was {existing.status})")
        return {"tool_result_id": existing.id, "status": existing.status.value if existing.status else None}

    # Only create new record if no existing one found
    tool_result_obj = ToolResult(
        id=str(uuid.uuid4()),
        scan_job_id=scan_id,
        tool_run_id=payload.tool_run_id,
        tool_name=payload.tool_name,
        status=ToolExecutionStatus.RUNNING,
        started_at=now,
        command=payload.command,
        parsed_findings_count=0,
        created_findings_count=0,
    )
    db.add(tool_result_obj)
    db.commit()
    db.refresh(tool_result_obj)
    logger.info(f"Created new ToolResult {tool_result_obj.id} for {payload.tool_name}")
    return {"tool_result_id": tool_result_obj.id, "status": tool_result_obj.status.value}


@router.post("/{scan_id}/tool-results", response_model=ToolResultResponse, status_code=status.HTTP_201_CREATED)
async def create_tool_result(
    scan_id: str,
    tool_result: ToolResultCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Create tool result and ingest findings from runner service.
    
    This endpoint is idempotent - using tool_run_id as unique key prevents duplicates.
    Runner service calls this after each tool execution completes.
    
    Requires service authentication via RUNNER_API_TOKEN (Bearer token).
    
    Args:
        scan_id: Scan job ID
        tool_result: Tool result data including findings
        
    Returns:
        ToolResultResponse with tool_result_id and findings_ingested count
    """
    # Namespace UUID for deterministic UUIDv5 generation (legacy mode)
    TOOL_RUN_ID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # Standard namespace UUID
    
    # Verify scan exists
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
    if not scan_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan not found: {scan_id}"
        )

    # If the scan was queued (e.g., brain started session but runner hadn't begun yet),
    # transition to RUNNING on the first tool result we ingest.
    if scan_job.status in (ScanStatus.QUEUED, ScanStatus.PENDING):
        scan_job.status = ScanStatus.RUNNING
        if not scan_job.started_at:
            scan_job.started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(scan_job)
    
    # Generate deterministic tool_run_id if missing (backward compatibility)
    if not tool_result.tool_run_id:
        # Use UUIDv5 for deterministic generation from stable fields
        tool_result.tool_run_id = str(uuid.uuid5(
            TOOL_RUN_ID_NAMESPACE,
            f"{scan_id}:{tool_result.tool_name}:{tool_result.step_id}"
        ))
        logger.info(f"Derived legacy tool_run_id from scan_id+tool+step_id: {tool_result.tool_run_id}")
    
    # Payload hash versioning for contract stability
    # v1: excluded "raw" from hash (legacy)
    # v2: includes "raw" in hash (current)
    PAYLOAD_HASH_VERSION = 2
    
    def _compute_payload_hash_v1(tr: ToolResultCreate) -> str:
        """Legacy hash (v1): excludes raw field"""
        normalized = {
            "tool_name": tr.tool_name,
            "tool_id": tr.tool_id,
            "findings": sorted(
                [ 
                    {
                        k: v for k, v in f.items()
                        if k not in ["timestamp", "raw"]  # Legacy: exclude raw
                    }
                    for f in tr.findings
                ],
                key=lambda x: json.dumps(x, sort_keys=True, default=str)
            ),
            "findings_count": tr.findings_count,
            "exit_code": tr.exit_code,
            "execution_time": tr.execution_time,
            "success": tr.success,
            "command": tr.command,
            "error_message": tr.error_message,
            "timed_out": tr.timed_out,
        }
        payload_str = json.dumps(normalized, sort_keys=True, default=str)
        return hashlib.sha256(payload_str.encode()).hexdigest()
    
    def _compute_payload_hash_v2(tr: ToolResultCreate) -> str:
        """Current hash (v2): includes raw field for meaningful diff detection"""
        normalized = {
            "tool_name": tr.tool_name,
            "tool_id": tr.tool_id,
            "findings": sorted(
                [
                    {
                        k: v for k, v in f.items()
                        if k not in ["timestamp"]  # Include raw for meaningful diff detection
                    }
                    for f in tr.findings
                ],
                key=lambda x: json.dumps(x, sort_keys=True, default=str)
            ),
            "findings_count": tr.findings_count,
            "exit_code": tr.exit_code,
            "execution_time": tr.execution_time,
            "success": tr.success,
            "command": tr.command,
            "error_message": tr.error_message,
            "timed_out": tr.timed_out,
        }
        payload_str = json.dumps(normalized, sort_keys=True, default=str)
        return hashlib.sha256(payload_str.encode()).hexdigest()
    
    def _compute_payload_hash(tr: ToolResultCreate, version: int = PAYLOAD_HASH_VERSION) -> str:
        """Compute payload hash for specified version"""
        if version == 1:
            return _compute_payload_hash_v1(tr)
        elif version == 2:
            return _compute_payload_hash_v2(tr)
        else:
            raise ValueError(f"Unsupported payload hash version: {version}")
    
    # Compute payload hash for this request (current version)
    payload_hash_v2 = _compute_payload_hash(tool_result, version=2)
    payload_hash_v1 = _compute_payload_hash(tool_result, version=1)  # For backward compatibility
    
    # PERMANENT FIX: Check for existing tool result by tool_run_id OR by tool_name (for PENDING records)
    # This prevents duplicate records when PENDING records exist
    existing_result = None
    # CRITICAL FIX: For tools with multiple modes (like ZAP), match by tool_name regardless of status
    # This prevents duplicate records when multiple ZAP modes run (ajax_spider, active_scan)
    # Match by tool_run_id first (most specific), then by tool_name (for multi-mode tools)
    if tool_result.tool_run_id:
        existing_result = db.query(ToolResult).filter(
            ToolResult.scan_job_id == scan_id,
            (ToolResult.tool_run_id == tool_result.tool_run_id) | 
            ((ToolResult.tool_name == tool_result.tool_name) & (ToolResult.status.in_([ToolExecutionStatus.PENDING, ToolExecutionStatus.RUNNING])))
        ).order_by(ToolResult.created_at.asc()).first()  # Get oldest record if multiple match
    else:
        # Fallback: look for PENDING or RUNNING record by tool_name (for multi-mode tools like ZAP)
        existing_result = db.query(ToolResult).filter(
            ToolResult.scan_job_id == scan_id,
            ToolResult.tool_name == tool_result.tool_name,
            ToolResult.status.in_([ToolExecutionStatus.PENDING, ToolExecutionStatus.RUNNING])
        ).order_by(ToolResult.created_at.asc()).first()  # Get oldest record
    
    # If tool-started created a stub row (status=RUNNING) for this tool_run_id,
    # update that same row with the final tool-results payload instead of treating it
    # as a duplicate.
    # CRITICAL: Check if tool_run_id already exists on a different record (duplicate prevention)
    if tool_result.tool_run_id:
        duplicate_check = db.query(ToolResult).filter(
            ToolResult.scan_job_id == scan_id,
            ToolResult.tool_run_id == tool_result.tool_run_id,
            ToolResult.id != (existing_result.id if existing_result else None)
        ).first()
        if duplicate_check:
            # tool_run_id already exists on a different record - this is a duplicate
            logger.warning(
                f"Duplicate tool_run_id {tool_result.tool_run_id} detected. "
                f"Existing record: {duplicate_check.id}, attempting update: {existing_result.id if existing_result else 'new'}. "
                f"Updating existing record instead."
            )
            # Use the existing record with this tool_run_id
            existing_result = duplicate_check
    
    if existing_result:
        existing_meta = existing_result.meta or {}
        existing_hash_v2 = existing_meta.get("payload_hash_v2")
        existing_hash_v1 = existing_meta.get("payload_hash_v1") or existing_meta.get("payload_hash")  # legacy

        is_stub = (
            not existing_hash_v2
            and not existing_hash_v1
            and (existing_result.status in (None, ToolExecutionStatus.PENDING, ToolExecutionStatus.RUNNING))
        )

        if is_stub:
            findings_created = []
            ingestion_error = None
            try:
                # Update stub ToolResult with final execution data
                final_status = (
                    ToolExecutionStatus.TIMED_OUT
                    if tool_result.timed_out
                    else (ToolExecutionStatus.COMPLETED if tool_result.success else ToolExecutionStatus.FAILED)
                )
                existing_result.tool_name = tool_result.tool_name
                # PERMANENT FIX: Update tool_run_id if not set (for PENDING records)
                # CRITICAL: Check if tool_run_id is already used by another record before setting it
                if not existing_result.tool_run_id and tool_result.tool_run_id:
                    # Check if this tool_run_id is already used by a different record
                    duplicate_by_tool_run_id = db.query(ToolResult).filter(
                        ToolResult.scan_job_id == scan_id,
                        ToolResult.tool_run_id == tool_result.tool_run_id,
                        ToolResult.id != existing_result.id
                    ).first()
                    if duplicate_by_tool_run_id:
                        # tool_run_id already exists on another record - don't set it to avoid unique constraint violation
                        logger.warning(
                            f"tool_run_id {tool_result.tool_run_id} already exists on record {duplicate_by_tool_run_id.id}. "
                            f"Not setting it on record {existing_result.id} to avoid duplicate key violation."
                        )
                    else:
                        existing_result.tool_run_id = tool_result.tool_run_id
                existing_result.output = tool_result.output[:10000] if tool_result.output else None
                existing_result.exit_code = tool_result.exit_code
                existing_result.execution_time = tool_result.execution_time
                existing_result.command = tool_result.command or existing_result.command
                existing_result.error_message = tool_result.error_message
                existing_result.timed_out = 1 if tool_result.timed_out else 0
                existing_result.stdout_preview = tool_result.stdout_preview
                existing_result.stderr_preview = tool_result.stderr_preview
                existing_result.status = final_status
                existing_result.parsed_findings_count = len(tool_result.findings)
                existing_result.completed_at = datetime.now(timezone.utc)
                existing_result.meta = {
                    "payload_hash_v": PAYLOAD_HASH_VERSION,
                    "payload_hash_v1": payload_hash_v1,
                    "payload_hash_v2": payload_hash_v2,
                    # Legacy field for backward compatibility
                    "payload_hash": payload_hash_v1,
                }

                # DEBUG: Log findings payload (stub update path)
                logger.info(
                    f"[STUB UPDATE] Ingesting findings for scan {scan_id}, tool={tool_result.tool_name}: "
                    f"{len(tool_result.findings)} findings in payload"
                )
                if tool_result.findings:
                    logger.info(f"[STUB UPDATE] First finding sample: {tool_result.findings[0]}")

                # Ingest findings (same as create path)
                project_id = scan_job.project_id
                for finding_data in tool_result.findings:
                    try:
                        normalized_finding = {
                            "tool": finding_data.get("tool_id") or tool_result.tool_name,
                            "title": finding_data.get("title", "Security Finding"),
                            "description": finding_data.get("description"),
                            "severity": finding_data.get("severity", "info").lower(),
                            "url": finding_data.get("url"),
                            "host": finding_data.get("host"),
                            "cve_id": finding_data.get("cve_id"),
                            "cwe_id": finding_data.get("cwe_id"),
                            "cvss_score": finding_data.get("cvss_score"),
                            "template_id": finding_data.get("template_id"),
                            "rule_id": finding_data.get("rule_id"),
                            "categories": finding_data.get("categories", []),
                            "http_method": finding_data.get("http_method"),
                            "parameter": finding_data.get("parameter"),
                            "evidence": finding_data.get("evidence"),
                            "raw_data": json.dumps(finding_data.get("raw", finding_data), default=str),
                        }

                        finding = create_or_update_finding(
                            db=db,
                            scan_job_id=scan_id,
                            project_id=project_id,
                            finding_data=normalized_finding,
                            tool_result_id=existing_result.id,
                        )
                        findings_created.append(finding)
                        logger.debug(
                            f"[STUB UPDATE] Created finding {len(findings_created)}: "
                            f"id={finding.id}, title={finding.title}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to ingest finding: {e}", exc_info=True)
                        ingestion_error = str(e)
                        continue

                existing_result.created_findings_count = len(findings_created)
                
                # DEBUG: Log before commit
                logger.info(
                    f"[STUB UPDATE] About to commit for scan {scan_id}: "
                    f"tool_result_id={existing_result.id}, findings_created={len(findings_created)}"
                )
                db.commit()
                logger.info(f"[STUB UPDATE] Commit successful for scan {scan_id}")
                
                # DEBUG: Verify persistence immediately after commit
                db.refresh(existing_result)
                logger.info(
                    f"[STUB UPDATE] After refresh: tool_result_id={existing_result.id}, "
                    f"created_findings_count={existing_result.created_findings_count}"
                )

                try:
                    _check_and_update_scan_completion(scan_job, db)
                except Exception as e:
                    logger.warning(f"Failed to check scan completion for scan {scan_id}: {e}", exc_info=True)

                # 200 OK because the row already existed (we updated it)
                response.status_code = status.HTTP_200_OK
                return ToolResultResponse(
                    tool_result_id=existing_result.id,
                    findings_ingested=len(findings_created),
                    message=f"Tool result updated with {len(findings_created)} findings"
                    + (f" (ingestion_error: {ingestion_error})" if ingestion_error else ""),
                )
            except Exception as e:
                logger.error(
                    f"[STUB UPDATE] EXCEPTION during stub update for scan {scan_id}: {e}",
                    exc_info=True
                )
                logger.error(f"[STUB UPDATE] Rolling back transaction for scan {scan_id}")
                db.rollback()
                logger.error(f"[STUB UPDATE] Rollback complete for scan {scan_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update tool result: {str(e)}",
                )
        
        # If duplicate found (non-stub), validate payload hash with version-aware strictness
        
        if existing_hash_v2:
            # v2-capable row: raw-sensitive
            if existing_hash_v2 != payload_hash_v2:
                logger.error(
                    f"Duplicate tool_run_id {tool_result.tool_run_id} with DIFFERENT payload (v2 mismatch)! "
                    f"Existing v2: {existing_hash_v2}, New v2: {payload_hash_v2}"
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Tool run ID {tool_result.tool_run_id} already exists with different payload. This indicates a bug."
                )
        else:
            # legacy row: raw-insensitive
            if existing_hash_v1 and existing_hash_v1 != payload_hash_v1:
                logger.error(
                    f"Duplicate tool_run_id {tool_result.tool_run_id} with DIFFERENT payload (v1 mismatch)! "
                    f"Existing v1: {existing_hash_v1}, New v1: {payload_hash_v1}"
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Tool run ID {tool_result.tool_run_id} already exists with different payload. This indicates a bug."
                )
        
        logger.info(
            f"Duplicate tool result POST detected for scan {scan_id}, tool_run_id={tool_result.tool_run_id}. "
            f"Returning existing ToolResult {existing_result.id}"
        )
        # Return existing result - no duplicate findings will be created
        # Return 200 OK for idempotent replay (not 201 Created)
        response.status_code = status.HTTP_200_OK
        return ToolResultResponse(
            tool_result_id=existing_result.id,
            findings_ingested=existing_result.created_findings_count or 0,
            message=f"Tool result already exists (idempotent response)"
        )
    
    # Start transaction - wrap ToolResult creation + findings ingestion
    tool_result_id = str(uuid.uuid4())
    project_id = scan_job.project_id
    findings_created = []
    ingestion_error = None
    
    try:
        # Create ToolResult
        # Merge meta from tool_result with payload hashes
        result_meta = {
            "payload_hash_v": PAYLOAD_HASH_VERSION,
            "payload_hash_v1": payload_hash_v1,
            "payload_hash_v2": payload_hash_v2,
            # Legacy field for backward compatibility
            "payload_hash": payload_hash_v1,
        }
        if tool_result.meta:
            result_meta.update(tool_result.meta)
        
        tool_result_obj = ToolResult(
            id=tool_result_id,
            scan_job_id=scan_id,
            tool_run_id=tool_result.tool_run_id,  # Set tool_run_id for idempotency
            tool_name=tool_result.tool_name,
            output=tool_result.output[:10000] if tool_result.output else None,  # Truncate
            exit_code=tool_result.exit_code,
            execution_time=tool_result.execution_time,
            command=tool_result.command,
            error_message=tool_result.error_message,
            timed_out=1 if tool_result.timed_out else 0,
            stdout_preview=tool_result.stdout_preview,
            stderr_preview=tool_result.stderr_preview,
            status=ToolExecutionStatus.COMPLETED if tool_result.success else ToolExecutionStatus.FAILED,
            parsed_findings_count=len(tool_result.findings),
            targets_count=tool_result.targets_count if hasattr(tool_result, 'targets_count') else 0,
            meta=result_meta if tool_result.tool_run_id else None,  # Store hash versions and tool metadata
        )
        db.add(tool_result_obj)
        db.flush()  # Flush to get tool_result_id for findings
        
        # DEBUG: Log findings payload
        logger.info(
            f"Ingesting findings for scan {scan_id}, tool={tool_result.tool_name}: "
            f"{len(tool_result.findings)} findings in payload"
        )
        if tool_result.findings:
            logger.info(f"First finding sample: {tool_result.findings[0]}")
        
        # #region agent log
        import json as json_lib
        import time
        try:
            with open('/app/data/debug.log', 'a') as f:
                f.write(json_lib.dumps({
                    "location": "runner_ingest.py:485",
                    "message": "About to ingest findings",
                    "data": {"scan_id": scan_id, "tool_name": tool_result.tool_name, "findings_count": len(tool_result.findings), "findings_sample": tool_result.findings[0] if tool_result.findings else None},
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "H6"
                }) + '\n')
        except: pass
        # #endregion
        
        # Ingest findings within the same transaction
        for finding_data in tool_result.findings:
            try:
                # Normalize finding data to match backend's expected format
                normalized_finding = {
                    "tool": finding_data.get("tool_id") or tool_result.tool_name,
                    "title": finding_data.get("title", "Security Finding"),
                    "description": finding_data.get("description"),
                    "severity": finding_data.get("severity", "info").lower(),
                    "url": finding_data.get("url"),
                    "host": finding_data.get("host"),
                    "cve_id": finding_data.get("cve_id"),
                    "cwe_id": finding_data.get("cwe_id"),
                    "cvss_score": finding_data.get("cvss_score"),
                    "template_id": finding_data.get("template_id"),
                    "rule_id": finding_data.get("rule_id"),
                    "categories": finding_data.get("categories", []),
                    "http_method": finding_data.get("http_method"),
                    "parameter": finding_data.get("parameter"),
                    "evidence": finding_data.get("evidence"),
                    "raw_data": json.dumps(finding_data.get("raw", finding_data), default=str),
                }
                
                # Create or update finding
                finding = create_or_update_finding(
                    db=db,
                    scan_job_id=scan_id,
                    project_id=project_id,
                    finding_data=normalized_finding,
                    tool_result_id=tool_result_id,
                )
                findings_created.append(finding)
                
                # #region agent log
                try:
                    with open('/app/data/debug.log', 'a') as f:
                        f.write(json_lib.dumps({
                            "location": "runner_ingest.py:515",
                            "message": "Finding created/updated",
                            "data": {"scan_id": scan_id, "finding_id": str(finding.id)[:8], "title": finding.title[:50], "tool": finding.tool_name},
                            "timestamp": int(time.time() * 1000),
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H6"
                        }) + '\n')
                except: pass
                # #endregion
                
            except Exception as e:
                logger.warning(f"Failed to ingest finding: {e}", exc_info=True)
                ingestion_error = str(e)
                # #region agent log
                try:
                    with open('/app/data/debug.log', 'a') as f:
                        f.write(json_lib.dumps({
                            "location": "runner_ingest.py:518",
                            "message": "Failed to ingest finding",
                            "data": {"scan_id": scan_id, "error": str(e), "finding_data_title": normalized_finding.get("title", "N/A")[:50]},
                            "timestamp": int(time.time() * 1000),
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H6"
                        }) + '\n')
                except: pass
                # #endregion
                # Continue processing other findings
                continue
        
        # Update tool result with created findings count
        tool_result_obj.created_findings_count = len(findings_created)
        
        # Commit entire transaction (ToolResult + findings)
        db.commit()
        logger.info(
            f"Created tool result {tool_result_id} for scan {scan_id}, "
            f"tool={tool_result.tool_name}, tool_run_id={tool_result.tool_run_id}, findings={len(findings_created)}"
        )
        
        # #region agent log
        try:
            with open('/app/data/debug.log', 'a') as f:
                f.write(json_lib.dumps({
                    "location": "runner_ingest.py:527",
                    "message": "Tool result committed",
                    "data": {"scan_id": scan_id, "tool_name": tool_result.tool_name, "findings_created": len(findings_created), "findings_in_payload": len(tool_result.findings)},
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "H6"
                }) + '\n')
        except: pass
        # #endregion
        
        # Check if all tools are complete and update scan status if needed
        try:
            _check_and_update_scan_completion(scan_job, db)
        except Exception as e:
            # Log error but don't fail the request - scan status update is best effort
            logger.warning(f"Failed to check scan completion for scan {scan_id}: {e}", exc_info=True)
        
    except IntegrityError as e:
        # Handle UNIQUE constraint violation (race condition - another request created it)
        db.rollback()
        logger.warning(
            f"IntegrityError on tool result creation (likely duplicate tool_run_id): {e}. "
            f"Re-querying existing result."
        )
        # Re-query to get the existing result
        existing_result = db.query(ToolResult).filter(
            and_(
                ToolResult.scan_job_id == scan_id,
                ToolResult.tool_run_id == tool_result.tool_run_id,
            )
        ).first()
        
        if existing_result:
            # Return 200 OK for idempotent replay (not 201 Created)
            response.status_code = status.HTTP_200_OK
            return ToolResultResponse(
                tool_result_id=existing_result.id,
                findings_ingested=existing_result.created_findings_count or 0,
                message=f"Tool result already exists (idempotent response from race condition)"
            )
        else:
            # Unexpected - re-raise
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save tool result: {str(e)}"
            )
    except Exception as e:
        logger.error(f"Failed to commit tool result: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save tool result: {str(e)}"
        )
    
    return ToolResultResponse(
        tool_result_id=tool_result_id,
        findings_ingested=len(findings_created),
        message=f"Tool result created with {len(findings_created)} findings" + (f" (ingestion_error: {ingestion_error})" if ingestion_error else "")
    )


def _check_and_update_scan_completion(scan_job: ScanJob, db: Session) -> None:
    """
    Check if all expected tools for a scan have completed and update scan status to COMPLETED if so.
    
    This function is called after each tool result is saved to automatically mark scans as complete
    when all tools finish, rather than waiting for the frontend to poll and trigger the check.
    """
    # Only check if scan is currently RUNNING (or was still QUEUED when first results arrived)
    if scan_job.status not in (ScanStatus.RUNNING, ScanStatus.QUEUED):
        return
    
    # Get all tool results for this scan
    tool_results = db.query(ToolResult).filter(
        ToolResult.scan_job_id == scan_job.id
    ).all()
    
    # CRITICAL: Check for tools that were started but never completed (stuck in RUNNING)
    # If a tool has been running for more than the max timeout, mark it as TIMED_OUT
    from app.core.scan_timeouts import get_tool_timeout
    from datetime import datetime, timezone, timedelta
    
    stuck_tools = []
    for tr in tool_results:
        if tr.status == ToolExecutionStatus.RUNNING and tr.started_at:
            # Calculate how long the tool has been running
            running_duration = (datetime.now(timezone.utc) - tr.started_at).total_seconds()
            # Get timeout for this tool (default 15 minutes if not configured)
            try:
                timeout_seconds = get_tool_timeout(scan_job.scan_level.value, tr.tool_name, default=900)
            except:
                timeout_seconds = 900  # 15 minutes default
            
            # If tool has been running longer than timeout + 5 minute buffer, mark as timed out
            if running_duration > (timeout_seconds + 300):
                logger.warning(
                    f"Tool {tr.tool_name} for scan {scan_job.id} has been running for {running_duration:.0f}s "
                    f"(timeout: {timeout_seconds}s). Marking as TIMED_OUT."
                )
                tr.status = ToolExecutionStatus.TIMED_OUT
                tr.completed_at = datetime.now(timezone.utc)
                if not tr.error_message:
                    tr.error_message = f"Tool execution timed out after {running_duration:.0f} seconds"
                stuck_tools.append(tr.tool_name)
    
    if stuck_tools:
        db.commit()
        logger.info(f"Marked {len(stuck_tools)} stuck tools as TIMED_OUT: {', '.join(stuck_tools)}")
    
    if not tool_results:
        # No tools have completed yet
        return
    
    # Get expected tools for this scan level
    expected_tool_keys = set()
    try:
        from app.core.tool_matrix import get_tools_for_level
        from app.models.scan import ScanLevel
        
        scan_level_enum = ScanLevel(scan_job.scan_level.value if hasattr(scan_job.scan_level, 'value') else scan_job.scan_level)
        expected_tools = get_tools_for_level(scan_level_enum)
        expected_tool_keys = {tool_config["key"] for tool_config in expected_tools if tool_config.get("enabled", True)}
        
        # If AI plan exists, add tools from next_tools
        if scan_job.ai_plan and isinstance(scan_job.ai_plan, dict):
            next_tools = scan_job.ai_plan.get("next_tools", [])
            if isinstance(next_tools, list):
                for tool_rec in next_tools:
                    tool_key = tool_rec.get("key") if isinstance(tool_rec, dict) else tool_rec
                    if tool_key:
                        expected_tool_keys.add(tool_key)
    except Exception as e:
        logger.warning(f"Failed to get expected tools for scan level {scan_job.scan_level}: {e}")
        # Fallback: use tools that have actually started
        expected_tool_keys = {tr.tool_name for tr in tool_results}
    
    # If we couldn't determine expected tools, use tools that have started
    if not expected_tool_keys:
        expected_tool_keys = {tr.tool_name for tr in tool_results}
    else:
        # Brain may enqueue additional tools beyond the static tool matrix.
        # Include any tools that have started so we don't mark the scan COMPLETE while
        # a tool is still RUNNING.
        expected_tool_keys |= {tr.tool_name for tr in tool_results if tr.tool_name}
    
    # Get latest status for each tool (in case there are multiple runs)
    tool_statuses_dict = {}
    for tr in tool_results:
        tool_name = tr.tool_name
        if tool_name not in tool_statuses_dict or (
            tr.created_at and tool_statuses_dict[tool_name].created_at < tr.created_at
        ):
            tool_statuses_dict[tool_name] = tr
    
    # Check if all expected tools are in terminal states
    terminal_states = {
        ToolExecutionStatus.COMPLETED,
        ToolExecutionStatus.FAILED,
        ToolExecutionStatus.SKIPPED,
        ToolExecutionStatus.TIMED_OUT
    }
    
    all_tools_done = True
    for tool_key in expected_tool_keys:
        if tool_key not in tool_statuses_dict:
            # Tool hasn't started yet
            all_tools_done = False
            break
        tool_result = tool_statuses_dict[tool_key]
        if not tool_result.status or tool_result.status not in terminal_states:
            # Tool is not in a terminal state
            all_tools_done = False
            break
    
    # If all tools are done, update scan status to COMPLETED/FAILED depending on tool outcomes
    if all_tools_done:
        # Count completed vs failed tools
        completed_tools = []
        failed_tools = []
        for tool_key in expected_tool_keys:
            tr = tool_statuses_dict.get(tool_key)
            if tr:
                if tr.status == ToolExecutionStatus.COMPLETED:
                    completed_tools.append(tool_key)
                elif tr.status in {ToolExecutionStatus.FAILED, ToolExecutionStatus.TIMED_OUT}:
                    failed_tools.append(tool_key)

        logger.info(
            f"All {len(expected_tool_keys)} tools completed for scan {scan_job.id}",
            extra={
                "scan_id": scan_job.id,
                "expected_tools": list(expected_tool_keys),
                "completed_tools": completed_tools,
                "failed_tools": failed_tools,
            }
        )
        
        # Determine scan status based on tool results
        if len(completed_tools) == 0:
            # No tools completed - mark as FAILED
            scan_job.status = ScanStatus.FAILED
            if not scan_job.error_message:
                scan_job.error_message = f"All tools failed: {', '.join(failed_tools[:5])}"
                if len(failed_tools) > 5:
                    scan_job.error_message += f" and {len(failed_tools) - 5} more"
        elif len(failed_tools) > 0:
            # Some tools completed, some failed - mark as COMPLETED_WITH_ERRORS
            scan_job.status = ScanStatus.COMPLETED_WITH_ERRORS
            if not scan_job.error_message:
                scan_job.error_message = f"Some tools failed: {', '.join(failed_tools[:5])}"
                if len(failed_tools) > 5:
                    scan_job.error_message += f" and {len(failed_tools) - 5} more"
        else:
            # All tools completed successfully
            scan_job.status = ScanStatus.COMPLETED
            scan_job.error_message = None
        
        if not scan_job.completed_at:
            scan_job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Scan {scan_job.id} status updated to {scan_job.status.value.upper()} (completed: {len(completed_tools)}, failed: {len(failed_tools)})")

        # Best-effort: stop brain session to prevent further step enqueues after completion.
        if getattr(scan_job, "brain_session_id", None):
            try:
                from app.services.brain_client import get_brain_client
                brain_client = get_brain_client()
                # org_id is the tenant_id for scan jobs in this codebase
                org_id = getattr(scan_job, "tenant_id", None)
                if org_id:
                    import asyncio
                    asyncio.create_task(
                        brain_client.stop_session(
                            session_id=scan_job.brain_session_id,
                            org_id=org_id,
                            project_id=scan_job.project_id,
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to stop brain session after completion for scan {scan_job.id}: {e}")

