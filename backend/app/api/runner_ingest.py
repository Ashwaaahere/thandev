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
from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from datetime import datetime, timezone

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

# Callback router for async tool updates (e.g. dependency scanner)
callback_router = APIRouter(
    tags=["callback"],
    dependencies=[Depends(require_runner_service_auth)],
)

@callback_router.post("/callback")
async def handle_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle generic callbacks from runner service (e.g. for dependency scans).
    Accepts arbitrary JSON and saves it as a ScanArtifact.
    """
    try:
        payload = await request.json()
        logger.warning(f"[CALLBACK-DEBUG] Received callback request, payload keys: {list(payload.keys()) if isinstance(payload, dict) else 'not dict'}")
        
        scan_id = payload.get("scan_id")
        artifact_type = payload.get("artifact_type") or payload.get("job_type")
        data = payload.get("payload")
        
        logger.warning(f"[CALLBACK-DEBUG] Parsed: scan_id={scan_id}, artifact_type={artifact_type}, has_data={data is not None}")
        logger.info(f"Received runner callback: scan_id={scan_id}, type={artifact_type}")
        
        if not scan_id or not artifact_type or data is None:
            logger.warning(f"[CALLBACK-DEBUG] Invalid callback payload: scan_id={scan_id}, artifact_type={artifact_type}, data={data is not None}")
            logger.warning("Invalid callback payload: missing scan_id, artifact_type/job_type, or payload")
            # Log what keys we actually received to help debugging
            logger.warning(f"Received keys: {list(payload.keys())}")
            logger.warning(f"Full payload preview: {str(payload)[:500]}")
            return {"status": "ignored", "reason": "missing_fields"}
            
        # Verify scan exists
        from app.models.scan import ScanJob
        scan_job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
        if not scan_job:
            logger.warning(f"Callback for non-existent scan: {scan_id}")
            return {"status": "ignored", "reason": "scan_not_found"}

        # Save as ScanArtifact
        from app.models.scan_artifact import ScanArtifact
        
        # Check if artifact already exists to update it (avoid duplicates for same type)
        existing_artifact = db.query(ScanArtifact).filter(
            ScanArtifact.scan_id == scan_id,
            ScanArtifact.type == artifact_type
        ).first()

        if existing_artifact:
            # Update existing artifact
            # Note: For PostgreSQL JSONB, we accept dict/list directly. For SQLite JSON, likely same.
            existing_artifact.payload = data
            logger.info(f"Updated existing artifact {existing_artifact.id} type={artifact_type} for scan {scan_id}")
        else:
            # Create new artifact
            artifact = ScanArtifact(
                scan_id=scan_id,
                type=artifact_type,
                payload=data
            )
            db.add(artifact)
            logger.info(f"Created new artifact type={artifact_type} for scan {scan_id}")
        
        db.commit()
        
        logger.warning(f"[CALLBACK-DEBUG] Successfully processed callback, returning success response")
        return {"status": "received", "scan_id": scan_id, "type": artifact_type}
    except Exception as e:
        logger.error(f"[CALLBACK-DEBUG] Error processing callback: {e}", exc_info=True)
        logger.error(f"Error processing callback: {e}", exc_info=True)
        # Return 200 anyway to prevent retries/crashes in runner
        return {"status": "error", "error": str(e)}
logger = logging.getLogger(__name__)


@router.post("/{scan_id}/tool-results", response_model=ToolResultResponse, status_code=status.HTTP_201_CREATED)
async def create_tool_result(
    scan_id: str,
    request: Request,
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
        request: Raw request to inspect body
        
    Returns:
        ToolResultResponse with tool_result_id and findings_ingested count
    """
    # CRITICAL: Read raw request body to capture meta field before Pydantic deserialization
    # We need to read the body manually because FastAPI consumes it for Pydantic
    body_bytes = await request.body()
    raw_body = json.loads(body_bytes.decode('utf-8')) if body_bytes else {}
    
    # Log raw body for wappalyzer/retire to debug meta field
    if raw_body.get('tool_name') in ('wappalyzer', 'retire'):
        logger.error(f"[RAW-BODY-DEBUG] {raw_body.get('tool_name')} - Raw body meta: {raw_body.get('meta')}")
        logger.error(f"[RAW-BODY-DEBUG] {raw_body.get('tool_name')} - Raw body meta type: {type(raw_body.get('meta'))}")
        logger.error(f"[RAW-BODY-DEBUG] {raw_body.get('tool_name')} - Raw body keys: {list(raw_body.keys())}")
    
    # Parse with Pydantic using raw_body directly (bypass FastAPI's automatic deserialization)
    # This ensures we have full control over the parsing process
    try:
        tool_result = ToolResultCreate(**raw_body)
    except Exception as e:
        logger.error(f"[PARSE-ERROR] Failed to parse ToolResultCreate: {e}, raw_body keys: {list(raw_body.keys())}")
        raise
    
    # CRITICAL: Always use raw_body meta if it exists, even if Pydantic parsed it
    # This ensures we preserve the exact meta structure sent by the runner
    raw_meta = None
    if 'meta' in raw_body:
        raw_meta = raw_body.get('meta')
        if raw_meta is not None:
            # Always use raw_meta to ensure we preserve the exact structure
            if tool_result.meta != raw_meta:
                logger.error(f"[META-RESTORE] Restoring meta from raw_body for {tool_result.tool_name}: raw_meta={raw_meta}, parsed_meta={tool_result.meta}")
            tool_result.meta = raw_meta
    
    # CRITICAL DEBUG: Log incoming meta for wappalyzer/retire AFTER parsing
    logger.error(f"[META-DEBUG-ENTRY] Received tool_result for {tool_result.tool_name}, scan_id={scan_id}")
    if tool_result.tool_name in ('wappalyzer', 'retire'):
        meta_to_check = raw_meta if raw_meta is not None else tool_result.meta
        logger.error(f"[META-DEBUG] {tool_result.tool_name} - meta type: {type(meta_to_check)}, value: {meta_to_check}")
        if meta_to_check:
            logger.error(f"[META-DEBUG] {tool_result.tool_name} - meta keys: {list(meta_to_check.keys()) if isinstance(meta_to_check, dict) else 'not dict'}")
            if 'technologies' in (meta_to_check or {}):
                logger.error(f"[META-DEBUG] {tool_result.tool_name} - HAS TECHNOLOGIES: {len(meta_to_check.get('technologies', []))}")
            if 'client_dependencies' in (meta_to_check or {}):
                logger.error(f"[META-DEBUG] {tool_result.tool_name} - HAS CLIENT_DEPENDENCIES: {len(meta_to_check.get('client_dependencies', []))}")
            if 'findings' in (meta_to_check or {}):
                logger.error(f"[META-DEBUG] {tool_result.tool_name} - HAS FINDINGS: {len(meta_to_check.get('findings', []))}")
            if not any(k in (meta_to_check or {}) for k in ['technologies', 'client_dependencies', 'findings']):
                logger.error(f"[META-DEBUG] {tool_result.tool_name} - NO TECHNOLOGIES/CLIENT_DEPS/FINDINGS IN META!")
        else:
            logger.error(f"[META-DEBUG] {tool_result.tool_name} - META IS NONE!")
    
    # CRITICAL: Log incoming request to debug findings ingestion
    logger.info(
        f"[INGEST-DEBUG] Received tool result POST: scan_id={scan_id}, "
        f"tool_name={tool_result.tool_name}, tool_run_id={tool_result.tool_run_id}, "
        f"findings_count={len(tool_result.findings) if tool_result.findings else 0}, "
        f"findings_list_type={type(tool_result.findings).__name__}"
    )
    if tool_result.findings and len(tool_result.findings) > 0:
        logger.info(
            f"[INGEST-DEBUG] First finding sample: {tool_result.findings[0] if tool_result.findings else None}"
        )
    
    # Namespace UUID for deterministic UUIDv5 generation (legacy mode)
    TOOL_RUN_ID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # Standard namespace UUID
    
    # Verify scan exists
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
    if not scan_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan not found: {scan_id}"
        )
    
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
    
    # Check for existing tool result with same tool_run_id (idempotency)
    existing_result = None
    if tool_result.tool_run_id:
        existing_result = db.query(ToolResult).filter(
            and_(
                ToolResult.scan_job_id == scan_id,
                ToolResult.tool_run_id == tool_result.tool_run_id,
            )
        ).first()
    
    # If duplicate found, validate payload hash with version-aware strictness
    if existing_result:
        existing_meta = existing_result.meta or {}
        existing_hash_v2 = existing_meta.get("payload_hash_v2")
        existing_hash_v1 = existing_meta.get("payload_hash_v1") or existing_meta.get("payload_hash")  # legacy
        
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
    
    # CRITICAL FIX: Check if a PENDING record exists for this tool (created during scan initialization)
    # PENDING records are placeholders - we should update them with actual results, not skip ingestion
    pending_record = db.query(ToolResult).filter(
        and_(
            ToolResult.scan_job_id == scan_id,
            ToolResult.tool_name == tool_result.tool_name,
            ToolResult.status == ToolExecutionStatus.PENDING
        )
    ).first()
    
    if pending_record:
        logger.info(
            f"[PENDING-UPDATE] Found PENDING ToolResult {pending_record.id} for {tool_result.tool_name} "
            f"in scan {scan_id}. Updating with actual results."
        )
        # Update PENDING record with actual results (transforms placeholder into real result)
        pending_record.tool_run_id = tool_result.tool_run_id
        pending_record.output = tool_result.output[:10000] if tool_result.output else None
        pending_record.exit_code = tool_result.exit_code
        pending_record.execution_time = tool_result.execution_time
        pending_record.command = tool_result.command
        pending_record.error_message = tool_result.error_message
        pending_record.timed_out = 1 if tool_result.timed_out else 0
        pending_record.stdout_preview = tool_result.stdout_preview
        pending_record.stderr_preview = tool_result.stderr_preview
        pending_record.status = ToolExecutionStatus.COMPLETED if tool_result.success else ToolExecutionStatus.FAILED
        pending_record.parsed_findings_count = len(tool_result.findings)
        # Merge incoming meta with hash values (preserve technologies, dependencies, etc.)
        # CRITICAL: Use raw_meta if available (from raw_body), otherwise use tool_result.meta
        # This ensures we preserve client_dependencies and findings from RetireJS
        meta_to_merge = raw_meta if raw_meta is not None else (tool_result.meta or {})
        if tool_result.tool_run_id:
            pending_record.meta = {
                **(pending_record.meta or {}),  # Preserve existing meta
                **meta_to_merge,  # Merge incoming meta (e.g., technologies from wappalyzer, client_dependencies from retire)
                "payload_hash_v": PAYLOAD_HASH_VERSION,
                "payload_hash_v1": payload_hash_v1,
                "payload_hash_v2": payload_hash_v2,
                "payload_hash": payload_hash_v1,
            }
        else:
            pending_record.meta = meta_to_merge if meta_to_merge else None
        
        # Use the existing PENDING record
        tool_result_obj = pending_record
        tool_result_id = pending_record.id
        db.flush()  # Flush to ensure updated record is visible
    else:
        logger.info(
            f"[NEW-RESULT] No PENDING record found for {tool_result.tool_name} "
            f"in scan {scan_id}. Creating new ToolResult."
        )
    
    try:
        # Only create new ToolResult if no PENDING record was found
        if not pending_record:
            # Create ToolResult
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
                meta={
                    **(raw_meta if raw_meta is not None else (tool_result.meta or {})),  # Use raw_meta if available (preserves client_dependencies, findings)
                    "payload_hash_v": PAYLOAD_HASH_VERSION,
                    "payload_hash_v1": payload_hash_v1,
                    "payload_hash_v2": payload_hash_v2,
                    # Legacy field for backward compatibility
                    "payload_hash": payload_hash_v1,
                } if tool_result.tool_run_id else (raw_meta if raw_meta is not None else (tool_result.meta or None)),  # If no tool_run_id, use raw_meta or meta as-is
            )
            db.add(tool_result_obj)
            db.flush()  # Flush to get tool_result_id for findings
        
        # Ingest findings within the same transaction (ALWAYS - even when updating PENDING records)
        logger.info(
            f"[INGEST-DEBUG] Starting findings ingestion: scan_id={scan_id}, "
            f"tool={tool_result.tool_name}, findings_list_length={len(tool_result.findings) if tool_result.findings else 0}"
        )
        
        for idx, finding_data in enumerate(tool_result.findings or []):
            try:
                logger.debug(
                    f"[INGEST-DEBUG] Processing finding {idx+1}/{len(tool_result.findings)}: "
                    f"title={finding_data.get('title', 'N/A')[:50] if finding_data else 'None'}"
                )
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
                logger.debug(
                    f"[INGEST-DEBUG] Successfully ingested finding {idx+1}: finding_id={finding.id if finding else 'None'}"
                )
                
            except Exception as e:
                logger.warning(
                    f"[INGEST-DEBUG] Failed to ingest finding {idx+1}: {e}", exc_info=True
                )
                ingestion_error = str(e)
                # Continue processing other findings
                continue
        
        # Update tool result with created findings count
        tool_result_obj.created_findings_count = len(findings_created)
        
        # Commit entire transaction (ToolResult + findings)
        db.commit()
        logger.info(
            f"[INGEST-DEBUG] Created tool result {tool_result_id} for scan {scan_id}, "
            f"tool={tool_result.tool_name}, tool_run_id={tool_result.tool_run_id}, "
            f"findings_received={len(tool_result.findings) if tool_result.findings else 0}, "
            f"findings_created={len(findings_created)}"
        )
        
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
    # Only check if scan is currently RUNNING
    if scan_job.status != ScanStatus.RUNNING:
        return
    
    # Get all tool results for this scan
    tool_results = db.query(ToolResult).filter(
        ToolResult.scan_job_id == scan_job.id
    ).all()
    
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
    
    # If all tools are done, update scan status to COMPLETED
    if all_tools_done:
        logger.info(
            f"All {len(expected_tool_keys)} tools completed for scan {scan_job.id}, marking as COMPLETED",
            extra={
                "scan_id": scan_job.id,
                "expected_tools": list(expected_tool_keys),
                "completed_tools": list(tool_statuses_dict.keys()),
            }
        )
        scan_job.status = ScanStatus.COMPLETED
        if not scan_job.completed_at:
            scan_job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Scan {scan_job.id} status updated to COMPLETED")

