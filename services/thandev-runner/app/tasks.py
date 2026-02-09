"""
Celery tasks for step execution
"""
import logging
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, List
import socket
from urllib.parse import urlparse

from app.config import settings
from app.executor import get_execution_adapter  # Keep for backward compatibility
from app.execution.selector import get_backend_for_tool
from app.queue import consume_step_requests, ack_step_request, publish_step_result, StepResult
from app.queue.streams import discover_brain_sessions, consume_brain_session_steps
import uuid
from app.backend_client import post_tool_result, get_scan_status, mark_scan_started, post_tool_started, emit_scan_event, post_scan_inventory
from app.enumeration import run_enumeration
from app.findings.parsers import parse_nuclei_output, parse_httpx_output, parse_sslscan_output, parse_dalfox_output, parse_nmap_output, parse_zap_output, parse_sqlmap_output
from app.concurrency import (
    acquire_session_slot,
    release_session_slot,
    check_step_idempotency,
    mark_step_completed,
    get_redis_client,
)

logger = logging.getLogger(__name__)

def _tcp_connectable(target_url: str, timeout_sec: float = 5.0) -> bool:
    """
    Fast preflight check: can we open a TCP connection to target host:port?
    Prevents long-running tools from hanging on unreachable targets.
    
    Note: This check may fail for targets that are reachable via HTTP but not via raw TCP
    (e.g., behind load balancers, firewalls, or CDNs). In such cases, tools should still
    be allowed to attempt the connection as they may use HTTP-level retries or different
    connection methods.
    """
    try:
        parsed = urlparse(target_url)
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except Exception as e:
        # Log the specific error for debugging, but don't fail the preflight check
        # Some targets may block raw TCP but allow HTTP connections
        logger.debug(f"TCP preflight check failed for {target_url}: {e}. Allowing tool to attempt connection anyway.")
        # Return True to allow tools to attempt the connection even if TCP preflight fails
        # Tools like httpx and nuclei have their own retry logic and may succeed where raw TCP fails
        return True


def _normalize_dalfox_output(output_text: str) -> str:
    """
    Normalize dalfox output to prevent placeholder outputs from creating fake findings.
    
    Converts:
    - "" -> "[]"
    - "{}" -> "[]"
    - "[{}]" -> "[]"
    - List of empty dicts -> "[]"
    
    Args:
        output_text: Raw dalfox stdout output
        
    Returns:
        Normalized JSON string (always a valid JSON array)
    """
    if not output_text or not output_text.strip():
        return "[]"
    
    output_stripped = output_text.strip()
    
    # Handle common placeholder patterns (exact matches)
    # Note: Also check normalized version (remove all whitespace) for cases like "[\n{}\n]"
    normalized_for_check = "".join(output_stripped.split())
    if normalized_for_check in ["{}", "[{}]", "[]"] or output_stripped in ["{}", "[{}]", "[]"]:
        return "[]"
    
    # Try parsing as JSON to check for empty objects
    # This handles cases like "[\n{}\n]" where newlines are inside brackets
    try:
        parsed = json.loads(output_stripped)
        
        # If it's a list, filter out empty dicts
        if isinstance(parsed, list):
            # Filter out empty dicts (dicts with no keys or all None/empty values)
            filtered = []
            for item in parsed:
                if isinstance(item, dict):
                    # Check if dict has any non-empty values
                    if item and any(v for v in item.values() if v is not None and str(v).strip()):
                        filtered.append(item)
                    # Empty dict {} is skipped
                else:
                    # Non-dict items are kept (shouldn't happen in Dalfox output, but be safe)
                    filtered.append(item)
            
            if not filtered:
                # All items were empty dicts or empty
                return "[]"
            # Return filtered list as JSON
            return json.dumps(filtered)
        
        # If it's a single empty dict, return []
        if isinstance(parsed, dict) and not parsed:
            return "[]"
        
        # Valid output, return as-is (re-serialize to ensure clean formatting)
        return json.dumps(parsed) if not isinstance(parsed, str) else output_stripped
        
    except json.JSONDecodeError:
        # Not valid JSON, return as-is (might be error message or other text)
        return output_stripped


async def process_step_request(message: Dict[str, Any]) -> None:
    """
    Process a single step request message.
    
    Args:
        message: Message dict with 'id' and 'data' keys
    """
    message_id = message["id"]
    data = message["data"]
    
    session_id = data.get("session_id")
    step_id = data.get("step_id")
    tool_id = data.get("tool_id")
    mode_id = data.get("mode_id")
    target_ref = data.get("target_ref")
    org_id = data.get("org_id") or None
    project_id = data.get("project_id") or None
    scan_job_id = data.get("scan_job_id") or None
    
    # #region agent log
    try:
        debug_log_path = "/home/ashwath/thandev/.cursor/debug.log"
        with open(debug_log_path, "a") as f:
            import json as json_lib
            f.write(json_lib.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"tasks.py:119","message":"Processing step request","data":{"message_id":message_id,"step_id":step_id,"tool_id":tool_id,"mode_id":mode_id,"scan_job_id":scan_job_id},"timestamp":int(time.time()*1000)})+"\n")
    except: pass
    # #endregion
    
    # Note: Scan status check removed - runner no longer depends on backend Python imports
    # Backend API will handle validation when we POST tool results
    
    # Idempotency check: skip if step was already processed
    if await check_step_idempotency(session_id, step_id):
        logger.info(f"Step {step_id} for session {session_id} already processed, skipping")
        await ack_step_request(settings.CONSUMER_GROUP, message_id)
        return
    
    # Per-session concurrency control: acquire slot
    if not await acquire_session_slot(session_id):
        logger.info(
            f"Session {session_id} at max concurrency, deferring step {step_id} (tool: {tool_id}). "
            f"Message will be re-delivered by Redis Streams when a slot becomes available."
        )
        # Don't ACK - let Redis Streams re-deliver this message later
        # This is normal behavior - tools will start automatically when slots open
        return
    
    # Parse params and depends_on from JSON strings
    try:
        params = json.loads(data.get("params", "{}"))
        depends_on = json.loads(data.get("depends_on", "[]"))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse params/depends_on for step {step_id}: {e}")
        # Publish error result
        await publish_step_result(StepResult(
            session_id=session_id,
            step_id=step_id,
            status="failed",
            execution_time_sec=0.0,
            error=f"Invalid request format: {e}",
        ))
        await ack_step_request(settings.CONSUMER_GROUP, message_id)
        return
    
    # Wrap main execution in try/finally for cleanup
    import time
    start_time = time.time()
    execution_time = 0.0
    
    # Track if enumeration completed (for proper ACK handling)
    enumeration_completed = False
    
    # Initialize result to None to prevent UnboundLocalError if enumeration fails
    # and publish_step_result raises an exception
    result = None
    
    try:
        logger.info(
            f"Processing step {step_id} (tool_id={tool_id}, mode_id={mode_id}, "
            f"session={session_id}, scan_job={scan_job_id})"
        )
        
        # If the scan has been cancelled/failed/completed in core, skip execution immediately.
        # This prevents wasting resources and ensures "stop" propagates end-to-end.
        if scan_job_id:
            status_payload = await get_scan_status(scan_job_id)
            status_str = (status_payload or {}).get("status")
            if status_str in {"cancelled", "failed", "completed"}:
                logger.info(
                    f"Skipping step {step_id} because scan {scan_job_id} is {status_str}"
                )
                await publish_step_result(
                    StepResult(
                        session_id=session_id,
                        step_id=step_id,
                        status="skipped",
                        execution_time_sec=0.0,
                        error=f"Scan {scan_job_id} is {status_str}; step skipped",
                    )
                )
                await ack_step_request(settings.CONSUMER_GROUP, message_id)
                return

            # Mark scan as RUNNING as soon as we begin processing (before tool results are posted).
            # Best-effort: failures here should not block tool execution.
            await mark_scan_started(scan_job_id)

            # Emit queued event
            try:
                await emit_scan_event(
                    scan_id=scan_job_id,
                    phase="scan",
                    tool=tool_id,
                    stage="queued",
                    message=f"{tool_id.upper()} queued for execution"
                )
            except Exception as e:
                logger.warning(f"Failed to emit queued event: {e}")

            # Generate a stable tool_run_id for this step and reuse it for both
            # the "started" signal and the final tool-results POST.
            tool_run_id = str(uuid.uuid4())
            await post_tool_started(
                scan_job_id=scan_job_id,
                tool_run_id=tool_run_id,
                step_id=step_id,
                tool_name=tool_id,
                tool_id=tool_id,
            )
            
            # Emit starting event
            try:
                await emit_scan_event(
                    scan_id=scan_job_id,
                    phase="scan",
                    tool=tool_id,
                    stage="starting",
                    message=f"Starting {tool_id.upper()} scan..."
                )
            except Exception as e:
                logger.warning(f"Failed to emit starting event: {e}")

        # Handle enumeration tool specially (Pro/Advanced scans only)
        if tool_id == "enumeration":
            logger.info(f"[ENUM] Starting enumeration for scan {scan_job_id}")
            try:
                scan_level = params.get("scan_level", "pro")
                
                # CRITICAL: Extra deduplication check for enumeration since it's expensive
                # Use a separate Redis key to prevent simultaneous enumeration executions
                redis_client = get_redis_client()
                enum_lock_key = f"enum:lock:{scan_job_id}"
                lock_acquired = redis_client.set(enum_lock_key, "locked", ex=900, nx=True)  # 15 min lock, NX = only set if doesn't exist
                
                if not lock_acquired:
                    logger.warning(
                        f"[ENUM] Enumeration already running for scan {scan_job_id} in another worker, "
                        f"skipping duplicate step {step_id}"
                    )
                    await mark_step_completed(session_id, step_id)
                    enumeration_completed = True
                    return
                
                try:
                    # Emit running event
                    if scan_job_id:
                        await emit_scan_event(scan_id=scan_job_id, phase="enumerate", tool="enumeration", stage="running", message=f"Running asset discovery for {scan_level} scan", progress=0.1)

                    # Run enumeration - callback receives phase, tool, stage, message, progress, meta
                    async def enum_cb(phase: str, tool: str, stage: str, message: str, progress: float = None, meta: dict = None):
                        if scan_job_id:
                            await emit_scan_event(scan_id=scan_job_id, phase=phase, tool=tool, stage=stage, message=message, progress=progress, meta=meta)

                    # Add overall timeout for enumeration (15 minutes)
                    logger.info(f"[ENUM] Running enumeration with 15 minute timeout for scan {scan_job_id}")
                    inventory = await asyncio.wait_for(
                        run_enumeration(target_url=target_ref, scan_level=scan_level, emit_event_callback=enum_cb),
                        timeout=900.0  # 15 minutes
                    )

                    # Upload inventory
                    if scan_job_id:
                        logger.info(f"[ENUM] Posting inventory for scan {scan_job_id} with 60s timeout...")
                        try:
                            inventory_posted = await asyncio.wait_for(
                                post_scan_inventory(scan_job_id, inventory),
                                timeout=60.0  # 60 second timeout for inventory POST
                            )
                        except asyncio.TimeoutError:
                            logger.error(f"[ENUM] Inventory POST timed out after 60s for scan {scan_job_id}")
                            inventory_posted = False

                        urls_found = inventory.get("discovery", {}).get("merged", {}).get("all_urls_count", 0)
                        if inventory_posted:
                            logger.info(f"[ENUM] Successfully posted inventory for scan {scan_job_id} ({urls_found} URLs)")
                        else:
                            logger.error(f"[ENUM] FAILED to post inventory for scan {scan_job_id} ({urls_found} URLs). Enumeration data will not be visible in UI.")
                        await emit_scan_event(scan_id=scan_job_id, phase="enumerate", tool="enumeration", stage="completed", message=f"Discovered {urls_found} URLs", progress=1.0, meta={"urls_found": urls_found, "inventory_posted": inventory_posted})

                    # Don't call publish_step_result for enumeration - it's not a NATS-based tool
                    logger.info(f"[ENUM] Enumeration completed successfully for scan {scan_job_id}")
                    # Mark step as completed to prevent retries
                    await mark_step_completed(session_id, step_id)
                    execution_time = time.time() - start_time
                    enumeration_completed = True
                    return
                finally:
                    # Always release the enumeration lock
                    try:
                        redis_client.delete(enum_lock_key)
                        logger.debug(f"[ENUM] Released enumeration lock for scan {scan_job_id}")
                    except Exception as lock_err:
                        logger.warning(f"[ENUM] Failed to release enumeration lock: {lock_err}")
                        
            except asyncio.TimeoutError:
                logger.error(f"[ENUM] Enumeration timed out after 15 minutes for scan {scan_job_id}")
                if scan_job_id:
                    try:
                        await emit_scan_event(scan_id=scan_job_id, phase="enumerate", tool="enumeration", stage="failed", message="Enumeration timed out after 15 minutes", progress=0.0)
                    except Exception as emit_err:
                        logger.warning(f"[ENUM] Failed to emit timeout event: {emit_err}")
                execution_time = time.time() - start_time
                enumeration_completed = True
                return
            except Exception as e:
                logger.error(f"[ENUM] Failed: {e}", exc_info=True)
                if scan_job_id:
                    try:
                        await emit_scan_event(scan_id=scan_job_id, phase="enumerate", tool="enumeration", stage="failed", message=f"Enumeration failed: {str(e)[:100]}", progress=0.0)
                    except Exception as emit_err:
                        logger.warning(f"[ENUM] Failed to emit failed event: {emit_err}")
                result = {"success": False, "error": str(e), "findings": []}
                try:
                    await publish_step_result(step_id, StepResult(success=False, result=result))
                except Exception as publish_err:
                    logger.error(f"[ENUM] Failed to publish step result: {publish_err}", exc_info=True)
                execution_time = time.time() - start_time
                enumeration_completed = True
                return

        # Preflight connectivity check for HTTP/TLS tools.
        # NOTE: We log warnings but don't fail tools based on TCP preflight,
        # as some targets may block raw TCP but allow HTTP connections.
        http_tools = {"httpx", "nuclei", "dalfox", "sslscan"}
        preflight_ok = True
        if tool_id in http_tools:
            preflight_ok = _tcp_connectable(target_ref, timeout_sec=5.0)
            if not preflight_ok:
                logger.warning(
                    f"TCP preflight check failed for {target_ref}, but allowing tool to attempt connection anyway",
                    extra={"scan_job_id": scan_job_id, "step_id": step_id, "tool_id": tool_id}
                )

        # Get execution backend (new system) or adapter (legacy)
        # Use new execution backend system if available, fallback to adapter
        use_new_backend = getattr(settings, "USE_EXECUTION_BACKEND", True)
        execution_result = None  # Will be set if using new backend
        
        # Always attempt tool execution, even if preflight check fails
        if use_new_backend:
            # Use new execution backend system
            backend = get_backend_for_tool(tool_id)
            
            # Execute step using new backend
            start_time = time.time()
            
            # Emit running event (before actual execution)
            if scan_job_id:
                try:
                    await emit_scan_event(
                        scan_id=scan_job_id,
                        phase="scan",
                        tool=tool_id,
                        stage="running",
                        message=f"Running {tool_id.upper()} against target...",
                        progress=0.3,
                        meta={"target": target_ref}
                    )
                except Exception as e:
                    logger.warning(f"Failed to emit running event: {e}")
            
            try:
                execution_result = await backend.execute(
                    tool_id=tool_id,
                    mode_id=mode_id,
                    params=params,
                    target=target_ref,
                    session_id=session_id,
                    step_id=step_id,
                    org_id=org_id,
                    project_id=project_id,
                    scan_job_id=scan_job_id,
                    scope={},  # Additional scope info if needed
                )
                
                execution_time = time.time() - start_time
                
                # Convert ExecutionResult to dict format for compatibility
                result = execution_result.to_dict()
                # Ensure execution_time is from result if available
                if execution_result.execution_time > 0:
                    execution_time = execution_result.execution_time
            except Exception as e:
                logger.error(f"Backend execution failed: {e}", exc_info=True)
                execution_time = time.time() - start_time
                result = {
                    "tool_name": tool_id,
                    "output": "",
                    "exit_code": -1,
                    "execution_time": execution_time,
                    "success": False,
                    "error": str(e),
                }
        else:
            # Legacy adapter system (for backward compatibility)
            # Create job directory - always use configured JOBS_DIR (container-local path)
            base_jobs_dir = Path(settings.JOBS_DIR) if settings.JOBS_DIR else Path("/app/data/jobs")
            if scan_job_id:
                job_dir = base_jobs_dir / scan_job_id
            else:
                job_dir = base_jobs_dir / session_id
            job_dir.mkdir(parents=True, exist_ok=True)
            
            # Get execution adapter
            adapter = get_execution_adapter(settings.EXECUTION_ADAPTER)
            
            # Execute step
            start_time = time.time()
            
            try:
                result = await adapter.execute_step(
                    tool_id=tool_id,
                    mode_id=mode_id,
                    params=params,
                    target_ref=target_ref,
                    job_dir=job_dir,
                    scan_job_id=scan_job_id,
                )
                
                execution_time = time.time() - start_time
            except Exception as e:
                logger.error(f"Adapter execution failed: {e}", exc_info=True)
                execution_time = time.time() - start_time
                result = {
                    "tool_name": tool_id,
                    "output": "",
                    "exit_code": -1,
                    "execution_time": execution_time,
                    "success": False,
                    "error": str(e),
                }
        
        # Parse findings and POST to backend API (always, even if tool failed)
        findings_count = 0
        findings = []
        
        # Initialize output_file outside scan_job_id block to ensure it's in scope for parsing
        output_file = None
        tool_name = result.get("tool_name", tool_id) if result else tool_id
        
        if scan_job_id:
            # Determine output file path (may be from artifact_refs for remote backend)
            # output_file is already initialized above
            if use_new_backend and execution_result and execution_result.artifact_refs:
                # Use artifact refs from remote backend
                output_file = Path(execution_result.artifact_refs[0]) if execution_result.artifact_refs else None
            else:
                # Use local job_dir (legacy adapter)
                # Use configured jobs directory from settings
                if scan_job_id:
                    job_dir = Path(settings.JOBS_DIR) / scan_job_id
                else:
                    job_dir = Path(settings.JOBS_DIR) / session_id
                job_dir.mkdir(parents=True, exist_ok=True)
                output_file = job_dir / f"{tool_name}_output.json"

            # If we have tool output but no file yet (e.g. remote backend without shared volume),
            # materialize the output to a file so parsers can operate on it.
            # CRITICAL: Materialize output even if tool "failed" - tools can produce useful output
            # even with non-zero exit codes (e.g., httpx, nuclei may exit non-zero but still have output)
            # Also materialize for tools like ZAP that return output in result dict
            # CRITICAL FIX: Always write full output to file if we have output (even if file exists)
            # This ensures parser gets complete data, not truncated content
            if output_file and result.get("output"):
                try:
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    output_text = result.get("output") or ""
                    
                    logger.info(
                        f"[MATERIALIZE-CHECK] Step {step_id} (tool={tool_id}, name={tool_name}): "
                        f"output_file={output_file}, output_len={len(output_text)}, "
                        f"output_preview={output_text[:100] if output_text else 'None'}"
                    )
                    
                    # Normalize Dalfox output: convert placeholder outputs to empty array
                    # This must happen BEFORE writing to file so parsers get normalized data
                    # Check both tool_name and tool_id to handle formats like "tool-dalfox-v2"
                    is_dalfox = (tool_name and "dalfox" in tool_name.lower()) or (tool_id and "dalfox" in tool_id.lower())
                    if is_dalfox:
                        output_text = _normalize_dalfox_output(output_text)
                    
                    # CRITICAL: For ZAP and Nuclei, ALWAYS write output (even if empty)
                    # ZAP output is a JSON string of findings array, so we must write it
                    # Nuclei may have empty stdout when no vulnerabilities found, but we need the file for parsing
                    is_zap = (tool_name and "zap" in tool_name.lower()) or (tool_id and "zap" in tool_id.lower())
                    is_nuclei = (tool_name and "nuclei" in tool_name.lower()) or (tool_id and "nuclei" in tool_id.lower())
                    should_write = output_text.strip() or is_zap or is_nuclei
                    
                    logger.info(
                        f"[MATERIALIZE-DECISION] Step {step_id} (tool={tool_id}): "
                        f"is_zap={is_zap}, output_text.strip()={bool(output_text.strip())}, should_write={should_write}"
                    )
                    
                    if should_write:
                        # CRITICAL: For nuclei with empty output, write empty JSON array to ensure file exists
                        if is_nuclei and not output_text.strip():
                            output_text = "[]"
                            logger.info(f"[NUCLEI-EMPTY-FIX] Writing empty array for nuclei (no vulnerabilities found)")
                        # For zap with empty output, ensure it's at least "[]"
                        if is_zap and not output_text.strip():
                            output_text = "[]"
                            logger.info(f"[ZAP-EMPTY-FIX] Writing empty array for zap")
                        output_file.write_text(output_text, encoding="utf-8")
                        logger.info(
                            "Materialized output for tool %s (step %s, scan_job %s) to %s (len=%d)",
                            tool_name,
                            step_id,
                            scan_job_id,
                            output_file,
                            len(output_text),
                        )
                        # CRITICAL: Log immediately after materialization to trace execution
                        logger.info(f"[AFTER-MATERIALIZE] Step {step_id} (tool={tool_id}): Just materialized, output_file={output_file}, exists={output_file.exists() if output_file else False}")
                    else:
                        logger.warning(
                            f"[MATERIALIZE-SKIP] Step {step_id} (tool={tool_id}): Skipping empty output file for {tool_name}",
                        )
                except Exception as write_err:
                    logger.error(
                        f"[MATERIALIZE-ERROR] Failed to materialize output file for {tool_name}: {write_err}",
                        exc_info=True,
                    )
            else:
                logger.warning(
                    f"[MATERIALIZE-SKIP] Step {step_id} (tool={tool_id}): Skipping materialization - "
                    f"output_file={output_file}, has_output={bool(result.get('output') if result else False)}"
                )
        
        # CRITICAL: This log MUST appear after materialization - if it doesn't, parsing section is being skipped
        # Using ERROR level to ensure it always appears in logs
        logger.error(f"[CRITICAL-PARSING-ENTRY] Step {step_id} (tool={tool_id}): ABOUT TO ENTER PARSING SECTION - scan_job_id={scan_job_id}, output_file={output_file}")
        print(f"[STDOUT-PARSING-ENTRY] Step {step_id} (tool={tool_id}): PARSING SECTION ENTRY POINT", flush=True)
        
        # Emit parsing event
        if scan_job_id:
            try:
                await emit_scan_event(
                    scan_id=scan_job_id,
                    phase="scan",
                    tool=tool_id,
                    stage="parsing",
                    message=f"Parsing {tool_id.upper()} results...",
                    progress=0.7
                )
            except Exception as e:
                logger.warning(f"Failed to emit parsing event: {e}")
        
        # CRITICAL DEBUG: Log before parsing section to trace execution
        logger.info(f"[DEBUG-BEFORE-PARSE] Step {step_id} (tool={tool_id}): Reached parsing section, scan_job_id={scan_job_id}, output_file={output_file}")
        
        # #region agent log
        try:
            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                import json as json_lib
                import time
                f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H1","location":"tasks.py:404","message":"Parsing section entry","data":{"step_id":step_id,"tool_id":tool_id,"scan_job_id":scan_job_id,"output_file":str(output_file) if output_file else None,"output_file_exists":output_file.exists() if output_file else False},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion
        
        # Parse findings using local parsers
        # CRITICAL: Parse findings even if tool "failed" - tools can produce useful findings
        # even with non-zero exit codes (e.g., httpx, nuclei may exit non-zero but still have output)
        logger.info(f"[BEFORE-PARSE] Step {step_id} (tool={tool_id}): About to start parsing section, output_file={output_file}")
        findings_count = 0
        findings = []
        
        # CRITICAL: Ensure output_file is set if we have output but no file path yet
        if not output_file and result and result.get("output") and scan_job_id:
            # Reconstruct output_file path
            job_dir = Path(settings.JOBS_DIR) / scan_job_id
            tool_name = result.get("tool_name", tool_id)
            output_file = job_dir / f"{tool_name}_output.json"
            logger.info(f"[PARSE-FIX] Reconstructed output_file: {output_file}")
        
        try:
            logger.error(f"[PARSE-START] Step {step_id} (tool={tool_id}): Starting parsing section")
            print(f"[STDOUT-PARSE-START] Step {step_id} (tool={tool_id}): Parsing section try block entered", flush=True)
            
            # Parse findings if we have an output file OR if we have output in the result
            # Don't require success=True - tools can produce findings even when they "fail"
            has_output_file = bool(output_file and output_file.exists())
            has_output_in_result = bool(result.get("output") and len(result.get("output", "").strip()) > 0)
            
            logger.error(
                f"[PARSE] Step {step_id} (tool={tool_id}): "
                f"scan_job_id={scan_job_id}, has_output_file={has_output_file}, "
                f"has_output_in_result={has_output_in_result}, output_file={output_file}"
            )
            print(f"[STDOUT-PARSE] Step {step_id}: has_output_file={has_output_file}, has_output_in_result={has_output_in_result}, output_file={output_file}", flush=True)
            
            # CRITICAL: Always try to parse if we have an output file, regardless of scan_job_id
            # This ensures findings are parsed even if scan_job_id is None or conditions aren't met
            if (has_output_file or has_output_in_result):
                # Ensure output_file is set up for parsing
                if not output_file or not output_file.exists():
                    if use_new_backend and execution_result and execution_result.artifact_refs:
                        # Use artifact refs from remote backend
                        output_file = Path(execution_result.artifact_refs[0]) if execution_result.artifact_refs else None
                    else:
                        # Use local job_dir (legacy adapter)
                        # Use configured jobs directory from settings
                        job_dir = Path(settings.JOBS_DIR) / (scan_job_id or session_id)
                        job_dir.mkdir(parents=True, exist_ok=True)
                        tool_name = result.get("tool_name", tool_id)
                        output_file = job_dir / f"{tool_name}_output.json"

                # If we have tool output but no file yet (e.g. remote backend without shared volume),
                # materialize the output to a file so existing parsers can operate on it.
                # CRITICAL: Always write if we have output, even if file exists (to ensure full content, not truncated)
                if output_file and result.get("output"):
                    try:
                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        output_text = result.get("output") or ""
                        
                        logger.info(
                            f"[MATERIALIZE2-CHECK] Step {step_id} (tool={tool_id}, name={tool_name}): "
                            f"output_file={output_file}, output_len={len(output_text)}"
                        )
                        
                        # Normalize Dalfox output to avoid fake findings
                        is_dalfox = (tool_name and "dalfox" in tool_name.lower()) or (tool_id and "dalfox" in tool_id.lower())
                        if is_dalfox:
                            output_text = _normalize_dalfox_output(output_text)
                        
                        # CRITICAL: For ZAP and Nuclei, ALWAYS write output (even if empty array "[]")
                        # ZAP output is a JSON string of findings array, so we must write it
                        # Nuclei may have empty stdout when no vulnerabilities found, but we need the file for parsing
                        # For other tools, write if we have any output (even if it's just whitespace)
                        # Tools like httpx, nmap, sslscan may have output that needs parsing
                        is_zap = (tool_name and "zap" in tool_name.lower()) or (tool_id and "zap" in tool_id.lower())
                        is_nuclei = (tool_name and "nuclei" in tool_name.lower()) or (tool_id and "nuclei" in tool_id.lower())
                        # Always write if we have output text OR if tool requires file (nuclei/zap)
                        # Only skip if output_text is None or completely missing AND tool doesn't require file
                        should_write = output_text is not None and (len(output_text) > 0 or is_zap or is_nuclei)
                        
                        if should_write:
                            # CRITICAL: For nuclei with empty output, write empty JSON array to ensure file exists
                            if is_nuclei and not output_text.strip():
                                output_text = "[]"
                                logger.info(f"[MATERIALIZE2-NUCLEI-EMPTY] Writing empty array for nuclei")
                            # For zap with empty output, ensure it's at least "[]"
                            if is_zap and not output_text.strip():
                                output_text = "[]"
                                logger.info(f"[MATERIALIZE2-ZAP-EMPTY] Writing empty array for zap")
                            output_file.write_text(output_text, encoding="utf-8")
                            # Verify file was written
                            if output_file.exists():
                                actual_size = output_file.stat().st_size
                                logger.info(
                                    "Materialized output for tool %s (step %s, scan_job %s) to %s (len=%d, verified_size=%d)",
                                    tool_name,
                                    step_id,
                                    scan_job_id,
                                    output_file,
                                    len(output_text),
                                    actual_size,
                                )
                            else:
                                logger.error(
                                    f"[MATERIALIZE2-ERROR] File was not created after write! {output_file}"
                                )
                        else:
                            logger.warning(
                                f"[MATERIALIZE2-SKIP] Skipping empty output file for {tool_name} (step {step_id})"
                            )
                    except Exception as write_err:
                        logger.error(
                            f"[MATERIALIZE2-ERROR] Failed to write tool output to file for {tool_name} (step {step_id}): {write_err}",
                            exc_info=True,
                        )
                else:
                    logger.warning(
                        f"[MATERIALIZE2-SKIP] Step {step_id} (tool={tool_id}): Skipping materialization - "
                        f"output_file={output_file}, has_output={bool(result.get('output') if result else False)}"
                    )

            # Parse findings if we have an output file
            # CRITICAL: Always try to parse if file exists, regardless of other conditions
            # Also try to parse if we have output in result but file doesn't exist yet (write it first)
            
            # CRITICAL FIX: If we have output in result but file doesn't exist, write it now before parsing
            # Also handle nuclei/zap which should always have a file even if output is empty
            is_nuclei_fallback = (tool_name and "nuclei" in tool_name.lower()) or (tool_id and "nuclei" in tool_id.lower())
            is_zap_fallback = (tool_name and "zap" in tool_name.lower()) or (tool_id and "zap" in tool_id.lower())
            should_have_file = is_nuclei_fallback or is_zap_fallback
            
            if result and output_file and not output_file.exists():
                # Write file if we have output OR if tool should always have a file (nuclei/zap)
                output_text = result.get("output") or ""
                if output_text or should_have_file:
                    try:
                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        # For nuclei with empty output, write empty JSON array
                        if is_nuclei_fallback and not output_text.strip():
                            output_text = "[]"
                            logger.info(f"[FALLBACK-NUCLEI-EMPTY] Writing empty array for nuclei")
                        # For zap with empty output, ensure it's at least "[]"
                        if is_zap_fallback and not output_text.strip():
                            output_text = "[]"
                            logger.info(f"[FALLBACK-ZAP-EMPTY] Writing empty array for zap")
                        output_file.write_text(output_text, encoding="utf-8")
                        logger.info(f"[FALLBACK-WRITE] Wrote output to {output_file} (size={len(output_text)}, should_have_file={should_have_file})")
                    except Exception as e:
                        logger.error(f"[FALLBACK-WRITE] Failed to write output file: {e}", exc_info=True)
            
            if output_file and output_file.exists():
                try:
                    logger.info(
                        f"[PARSE-FILE] About to parse findings for step {step_id} (tool={tool_name}): "
                        f"output_file={output_file}, exists={output_file.exists()}, size={output_file.stat().st_size}"
                    )
                    
                    # Parse findings using local parsers - SIMPLIFIED
                    if tool_name == "zap":
                        logger.info(f"[ZAP-PARSE-START] Parsing ZAP output from {output_file}")
                        # #region agent log
                        try:
                            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                                import json as json_lib
                                import time
                                f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H4","location":"tasks.py:520","message":"Before parse_zap_output call","data":{"step_id":step_id,"output_file":str(output_file),"file_size":output_file.stat().st_size if output_file.exists() else 0},"timestamp":int(time.time()*1000)})+"\n")
                        except: pass
                        # #endregion
                        findings = parse_zap_output(output_file)
                        # #region agent log
                        try:
                            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                                import json as json_lib
                                import time
                                f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H4","location":"tasks.py:521","message":"After parse_zap_output call","data":{"step_id":step_id,"findings_count":len(findings),"first_finding_title":findings[0].get("title","N/A")[:50] if len(findings)>0 else None},"timestamp":int(time.time()*1000)})+"\n")
                        except: pass
                        # #endregion
                        logger.info(f"[ZAP-PARSE-END] Parsed {len(findings)} findings from zap")
                        if len(findings) > 0:
                            logger.info(f"[ZAP-PARSE-SUCCESS] First finding: {findings[0].get('title', 'N/A')[:60]}")
                        else:
                            logger.warning(f"[ZAP-PARSE-EMPTY] No findings parsed from ZAP output file {output_file}")
                    elif tool_name == "nuclei":
                        findings = parse_nuclei_output(output_file)
                        logger.info(f"Parsed {len(findings)} findings from nuclei")
                    elif tool_name == "httpx":
                        findings = parse_httpx_output(output_file)
                        logger.info(f"Parsed {len(findings)} findings from httpx (file={output_file}, size={output_file.stat().st_size if output_file.exists() else 0})")
                        if len(findings) == 0 and output_file.exists() and output_file.stat().st_size > 0:
                            # Log first few lines of output for debugging
                            try:
                                with open(output_file, 'r') as f:
                                    first_lines = [f.readline().strip() for _ in range(3)]
                                logger.warning(f"[HTTPX-DEBUG] No findings parsed but file has content. First lines: {first_lines}")
                            except:
                                pass
                    elif tool_name == "sslscan":
                        findings = parse_sslscan_output(output_file)
                        logger.info(f"Parsed {len(findings)} findings from sslscan")
                    elif tool_name == "dalfox":
                        findings = parse_dalfox_output(output_file)
                        logger.info(f"Parsed {len(findings)} findings from dalfox")
                    elif tool_name == "nmap":
                        findings = parse_nmap_output(output_file)
                        logger.info(f"Parsed {len(findings)} findings from nmap (file={output_file}, size={output_file.stat().st_size if output_file.exists() else 0})")
                        if len(findings) == 0 and output_file.exists() and output_file.stat().st_size > 0:
                            # Log first few lines of output for debugging
                            try:
                                with open(output_file, 'r') as f:
                                    first_chars = f.read(200)
                                logger.warning(f"[NMAP-DEBUG] No findings parsed but file has content. First 200 chars: {first_chars}")
                            except:
                                pass
                    elif tool_name == "sqlmap":
                        findings = parse_sqlmap_output(output_file)
                        logger.info(f"Parsed {len(findings)} findings from sqlmap")
                    else:
                        # Other tools not yet implemented in local parsers
                        logger.debug(f"Parser not yet implemented for {tool_name}, skipping findings parsing")
                        findings = []
                    
                    findings_count = len(findings)
                    logger.info(f"[PARSE-COMPLETE] Step {step_id} (tool={tool_name}): Found {findings_count} findings")
                    # #region agent log
                    try:
                        with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                            import json as json_lib
                            import time
                            f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H5","location":"tasks.py:549","message":"After parsing, before POST","data":{"step_id":step_id,"tool_name":tool_name,"findings_count":findings_count,"findings_len":len(findings)},"timestamp":int(time.time()*1000)})+"\n")
                    except: pass
                    # #endregion
                    
                except Exception as e:
                    logger.error(f"[PARSE-ERROR] Failed to parse findings for step {step_id} (tool={tool_name}): {e}", exc_info=True)
                    # Continue - findings parsing failure shouldn't fail the step
                    findings = []
                    findings_count = 0
                    # #region agent log
                    try:
                        with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                            import json as json_lib
                            import time
                            f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H4","location":"tasks.py:554","message":"Parse exception caught","data":{"step_id":step_id,"tool_name":tool_name,"error":str(e)},"timestamp":int(time.time()*1000)})+"\n")
                    except: pass
                    # #endregion
            else:
                # FALLBACK: If we have output in result but no file, try to parse from result directly
                # This handles cases where file write failed or output wasn't written
                if result and result.get("output") and result.get("output").strip():
                    logger.warning(f"[PARSE-FALLBACK] Step {step_id} (tool={tool_name}): No output file, but have output in result. Attempting to parse from result output directly.")
                    try:
                        # Create a temporary file-like object or parse directly
                        # For now, try to write to file one more time and then parse
                        if output_file:
                            output_file.parent.mkdir(parents=True, exist_ok=True)
                            output_text = result.get("output")
                            output_file.write_text(output_text, encoding="utf-8")
                            logger.info(f"[PARSE-FALLBACK-WRITE] Wrote output to {output_file} for parsing")
                            
                            # Now try parsing again
                            if output_file.exists() and output_file.stat().st_size > 0:
                                if tool_name == "httpx":
                                    findings = parse_httpx_output(output_file)
                                elif tool_name == "nmap":
                                    findings = parse_nmap_output(output_file)
                                elif tool_name == "sslscan":
                                    findings = parse_sslscan_output(output_file)
                                elif tool_name == "nuclei":
                                    findings = parse_nuclei_output(output_file)
                                elif tool_name == "dalfox":
                                    findings = parse_dalfox_output(output_file)
                                elif tool_name == "sqlmap":
                                    findings = parse_sqlmap_output(output_file)
                                else:
                                    findings = []
                                findings_count = len(findings)
                                logger.info(f"[PARSE-FALLBACK-SUCCESS] Parsed {findings_count} findings from fallback write")
                            else:
                                logger.warning(f"[PARSE-FALLBACK-FAIL] File still doesn't exist or is empty after write")
                                findings = []
                                findings_count = 0
                        else:
                            logger.warning(f"[PARSE-FALLBACK-SKIP] No output_file path available for fallback")
                            findings = []
                            findings_count = 0
                    except Exception as fallback_err:
                        logger.error(f"[PARSE-FALLBACK-ERROR] Failed to parse from fallback: {fallback_err}", exc_info=True)
                        findings = []
                        findings_count = 0
                else:
                    logger.warning(f"[PARSE-SKIP] Step {step_id} (tool={tool_name}): No output file to parse - output_file={output_file}, exists={output_file.exists() if output_file else False}, has_output_in_result={bool(result.get('output') if result else False)}")
                # #region agent log
                try:
                    with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                        import json as json_lib
                        import time
                        f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H2,H3","location":"tasks.py:557","message":"Parse skipped - file check failed","data":{"step_id":step_id,"tool_name":tool_name,"output_file":str(output_file) if output_file else None,"output_file_exists":output_file.exists() if output_file else False},"timestamp":int(time.time()*1000)})+"\n")
                except: pass
                # #endregion
        except Exception as parse_section_error:
            logger.error(
                f"[CRITICAL-PARSE-EXCEPTION] Exception in parsing section for step {step_id} (tool={tool_id}): {parse_section_error}",
                exc_info=True
            )
            # Ensure findings are empty on error
            findings = []
            findings_count = 0
        else:
            # This else block runs if NO exception occurred in the try block
            logger.info(f"[PARSE-SECTION-COMPLETE] Parsing section completed without exception for step {step_id} (tool={tool_id}), findings_count={findings_count}")
        
        # CRITICAL: Log before POST to confirm we reached here
        logger.error(f"[CRITICAL-BEFORE-POST] Step {step_id} (tool={tool_id}): About to POST - findings_count={findings_count}, scan_job_id={scan_job_id}")
        
        # POST tool result and findings to backend API (always when scan_job_id is present).
        # This ensures backend progress is accurate even for failures/timeouts.
        if scan_job_id:
            try:
                tool_name = result.get("tool_name", tool_id)
                
                # Ensure tool_run_id is set for idempotency
                if not tool_run_id:
                    tool_run_id = str(uuid.uuid4())
                
                # Normalize legacy tool wrappers: if "success" is missing, treat as failure.
                if "success" not in result:
                    result["success"] = False
                # Best-effort timeout inference (some tools only set error text)
                if "timed_out" not in result:
                    err_text = (result.get("error") or result.get("error_message") or "")
                    result["timed_out"] = "timed out" in str(err_text).lower()
                
                # POST tool result and findings to backend API
                if settings.BACKEND_URL:
                    # Emit uploading event
                    try:
                        await emit_scan_event(
                            scan_id=scan_job_id,
                            phase="scan",
                            tool=tool_id,
                            stage="uploading",
                            message=f"Uploading {len(findings)} findings to backend...",
                            progress=0.9,
                            meta={"findings_count": len(findings)}
                        )
                    except Exception as e:
                        logger.warning(f"Failed to emit uploading event: {e}")
                    
                    # #region agent log
                    try:
                        with open("/app/data/debug.log", "a") as f:
                            import json as json_lib
                            import time
                            f.write(json_lib.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H7",
                                "location": "tasks.py:671",
                                "message": "Before post_tool_result call",
                                "data": {
                                    "scan_job_id": scan_job_id,
                                    "step_id": step_id,
                                    "tool_name": tool_name,
                                    "tool_id": tool_id,
                                    "findings_count": len(findings),
                                    "findings_sample": findings[0] if len(findings) > 0 else None
                                },
                                "timestamp": int(time.time() * 1000)
                            }) + '\n')
                    except: pass
                    # #endregion
                    # CRITICAL: Log findings before POST to debug why findings_count is 0
                    logger.info(
                        f"[BEFORE-POST] Step {step_id} (tool={tool_name}): "
                        f"findings_count={len(findings)}, "
                        f"findings_sample={findings[0] if len(findings) > 0 else None}, "
                        f"output_file={output_file}, "
                        f"output_file_exists={output_file.exists() if output_file else False}, "
                        f"result_has_output={bool(result.get('output') if result else False)}"
                    )
                    
                    success = await post_tool_result(
                        scan_job_id=scan_job_id,
                        step_id=step_id,
                        tool_name=tool_name,
                        tool_id=tool_id,
                        findings=findings,
                        execution_result=result,
                        tool_run_id=tool_run_id,
                    )
                    
                    logger.info(
                        f"[AFTER-POST] Step {step_id} (tool={tool_name}): "
                        f"POST success={success}, findings_count={len(findings)}"
                    )
                    # #region agent log
                    try:
                        with open("/app/data/debug.log", "a") as f:
                            import json as json_lib
                            import time
                            f.write(json_lib.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H7",
                                "location": "tasks.py:688",
                                "message": "After post_tool_result call",
                                "data": {
                                    "scan_job_id": scan_job_id,
                                    "step_id": step_id,
                                    "tool_name": tool_name,
                                    "success": success,
                                    "findings_count": len(findings)
                                },
                                "timestamp": int(time.time() * 1000)
                            }) + '\n')
                    except: pass
                    # #endregion
                    if success:
                        logger.info(
                            f"Posted tool result to backend (status code 201): "
                            f"scan={scan_job_id}, step={step_id}, tool={tool_name}, findings={findings_count}"
                        )
                        
                        # Emit completed event
                        try:
                            await emit_scan_event(
                                scan_id=scan_job_id,
                                phase="scan",
                                tool=tool_id,
                                stage="completed",
                                message=f"{tool_id.upper()} scan completed - found {len(findings)} findings",
                                progress=1.0,
                                meta={"findings_count": len(findings), "execution_time": execution_time}
                            )
                        except Exception as e:
                            logger.warning(f"Failed to emit completed event: {e}")
                    else:
                        logger.error(
                            f"Failed to POST tool result to backend for scan={scan_job_id}, step={step_id}, tool={tool_name}. "
                            f"Findings will not be saved. This is a critical error."
                        )
                        
                        # CRITICAL: If posting fails, we should retry or at least log the findings count
                        # For now, log detailed error information
                        logger.error(
                            f"[TOOL-RESULT-POST-FAILED] Scan={scan_job_id}, Tool={tool_name}, "
                            f"Findings={len(findings)}, Step={step_id}. "
                            f"Backend may be unreachable or payload too large."
                        )
                        
                        # Emit failed event with more context
                        try:
                            # Check if tool execution actually succeeded but POST failed
                            tool_execution_success = result.get("success", False) if result else False
                            tool_error = result.get("error") or result.get("error_message") if result else None
                            
                            if tool_execution_success and len(findings) > 0:
                                # Tool ran successfully but POST failed
                                error_msg = f"Tool execution succeeded ({len(findings)} findings) but failed to post results to backend"
                            elif tool_error:
                                # Tool execution failed
                                error_msg = f"Tool execution failed: {str(tool_error)[:100]}"
                            else:
                                # Unknown error
                                error_msg = "Failed to post results to backend (unknown error)"
                            
                            await emit_scan_event(
                                scan_id=scan_job_id,
                                phase="scan",
                                tool=tool_id,
                                stage="failed",
                                message=f"{tool_id.upper()} scan failed: {str(error_msg)[:100]}",
                                meta={
                                    "error": str(error_msg)[:500], 
                                    "post_failed": True, 
                                    "findings_count": len(findings),
                                    "tool_execution_success": tool_execution_success,
                                    "tool_error": str(tool_error)[:200] if tool_error else None
                                }
                            )
                        except Exception as e:
                            logger.warning(f"Failed to emit failed event: {e}")
                else:
                    logger.warning("BACKEND_URL not configured, skipping tool result POST")
            except Exception as e:
                logger.error(f"Failed to POST tool result to backend for step {step_id}: {e}", exc_info=True)
        
        # Publish result
        # Ensure execution_time is always defined (preflight failures may skip execution branches)
        if isinstance(result, dict):
            execution_time = float(result.get("execution_time") or execution_time or 0.0)

        # Get output_file path (may not exist if execution failed)
        output_file_path = None
        if result.get("success"):
            tool_name = result.get("tool_name", tool_id)
            if use_new_backend and execution_result and execution_result.artifact_refs:
                output_file_path = execution_result.artifact_refs[0]
            else:
                # Legacy: use configured JOBS_DIR (container-local path)
                base_jobs_dir = Path(settings.JOBS_DIR) if settings.JOBS_DIR else Path("/app/data/jobs")
                job_dir = base_jobs_dir / (scan_job_id or session_id)
                output_file = job_dir / f"{tool_name}_output.json"
                if output_file.exists():
                    output_file_path = str(output_file)
        
        step_result = StepResult(
            session_id=session_id,
            step_id=step_id,
            status="success" if result.get("success") else "failed",
            execution_time_sec=execution_time,
            findings_count=findings_count or 0,  # Ensure not None
            artifact_refs=[output_file_path] if output_file_path else [],
            error=result.get("error") or None,  # Convert empty string to None
            tool_output_summary=(result.get("output", "")[:500] if result.get("output") else None) or None,  # Ensure None if empty
            tool_id=tool_id or None,  # Include tool_id in result
        )
        
        await publish_step_result(step_result)
        logger.info(
            f"Step {step_id} completed: status={step_result.status}, "
            f"findings={findings_count}, time={execution_time:.2f}s"
        )
        
        # Mark step as completed if it succeeded to prevent retries
        if step_result.status == "success":
            await mark_step_completed(session_id, step_id)
    except Exception as e:
        logger.error(f"Step {step_id} execution failed: {e}", exc_info=True)
        execution_time = time.time() - start_time if 'start_time' in locals() else 0.0
        
        # Emit failed event for catastrophic failures
        if scan_job_id:
            try:
                await emit_scan_event(
                    scan_id=scan_job_id,
                    phase="scan",
                    tool=tool_id,
                    stage="failed",
                    message=f"{tool_id.upper()} execution failed: {str(e)[:100]}",
                    meta={"error": str(e)[:500], "error_type": type(e).__name__}
                )
            except Exception as emit_err:
                logger.warning(f"Failed to emit failed event: {emit_err}")
        
        # Publish error result
        await publish_step_result(StepResult(
            session_id=session_id,
            step_id=step_id,
            status="failed",
            execution_time_sec=execution_time,
            error=str(e),
        ))
    finally:
        # Always release session slot, even on error
        await release_session_slot(session_id)
        
        # Acknowledge message (even on error to avoid infinite retries)
        await ack_step_request(settings.CONSUMER_GROUP, message_id)


async def run_worker_loop() -> None:
    """
    Main worker loop - consumes step requests and processes them.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info(
        f"Starting runner worker (group={settings.CONSUMER_GROUP}, "
        f"name={settings.CONSUMER_NAME})"
    )
    
    # Test backend connectivity on startup
    try:
        from app.backend_client import test_backend_connectivity
        connectivity_ok = await test_backend_connectivity()
        if connectivity_ok:
            logger.info("✅ Backend connectivity test passed on startup")
        else:
            logger.warning("⚠️ Backend connectivity test failed on startup - tool result posting may fail")
    except Exception as e:
        logger.warning(f"Could not test backend connectivity on startup: {e}")
    
    # NOTE: Removed local debug.log instrumentation (was breaking tools in containers).
    
    # Track if this is the first iteration (to check for pending messages on startup)
    first_iteration = True
    
    # Track running tasks to allow concurrent processing without blocking the loop
    running_tasks: set[asyncio.Task] = set()
    
    def cleanup_completed_tasks():
        """Remove completed tasks from the running set"""
        completed = [t for t in running_tasks if t.done()]
        for task in completed:
            running_tasks.discard(task)
            # Log any exceptions
            try:
                task.result()
            except Exception as e:
                logger.error(f"Task completed with error: {e}", exc_info=True)
        return len(completed)
    
    logger.info("Entering main worker loop...")
    while True:
        try:
            # Clean up completed tasks before checking capacity
            completed_count = cleanup_completed_tasks()
            if completed_count > 0:
                logger.info(f"Cleaned up {completed_count} completed task(s), {len(running_tasks)} still running")
            
            # Check if we're at capacity
            available_slots = settings.MAX_CONCURRENT_STEPS - len(running_tasks)
            if available_slots <= 0:
                # At capacity, wait a bit before checking again
                logger.info(f"At capacity ({len(running_tasks)}/{settings.MAX_CONCURRENT_STEPS}), waiting...")
                await asyncio.sleep(1)
                continue
            
            # Consume step requests
            logger.info(f"Waiting for step requests from stream {settings.CONSUMER_GROUP}... (available slots: {available_slots})")
            
            # NOTE: Removed local debug.log instrumentation (was breaking tools in containers).
            
            # #region agent log
            try:
                debug_log_path = "/home/ashwath/thandev/.cursor/debug.log"
                with open(debug_log_path, "a") as f:
                    import json as json_lib
                    f.write(json_lib.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"tasks.py:778","message":"About to consume step requests","data":{"consumer_group":settings.CONSUMER_GROUP,"consumer_name":settings.CONSUMER_NAME,"count":settings.MAX_CONCURRENT_STEPS,"available_slots":available_slots},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            
            # Poll from both global stream (backward compat) and Brain session streams
            messages = []
            
            # 1. Check global stream (legacy scans not using Brain)
            # Limit consumption based on available slots
            consume_count = min(available_slots, settings.MAX_CONCURRENT_STEPS // 2)
            global_messages = await consume_step_requests(
                consumer_group=settings.CONSUMER_GROUP,
                consumer_name=settings.CONSUMER_NAME,
                count=consume_count,  # Use available slots instead of fixed half
                block_ms=500,  # Reduced block time
                check_pending=True,  # Always check pending messages to recover stuck scans
            )
            messages.extend(global_messages or [])
            
            # Update available slots after consuming
            available_slots = settings.MAX_CONCURRENT_STEPS - len(running_tasks) - len(messages)
            
            # 2. Check Brain session streams (new Brain-managed scans)
            brain_sessions = discover_brain_sessions()
            for session_id in brain_sessions:
                if available_slots <= 0:
                    break
                session_messages = await consume_brain_session_steps(
                    session_id=session_id,
                    consumer_group=settings.CONSUMER_GROUP,
                    consumer_name=settings.CONSUMER_NAME,
                    count=max(1, min(available_slots, settings.MAX_CONCURRENT_STEPS // max(len(brain_sessions), 1))),
                    block_ms=0,  # Non-blocking for Brain streams
                )
                messages.extend(session_messages or [])
                available_slots -= len(session_messages or [])
            
            first_iteration = False  # Kept for backwards compatibility with existing log flow
            
            # #region agent log
            try:
                debug_log_path = "/home/ashwath/thandev/.cursor/debug.log"
                with open(debug_log_path, "a") as f:
                    import json as json_lib
                    f.write(json_lib.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"tasks.py:787","message":"After consume_step_requests","data":{"message_count":len(messages) if messages else 0,"first_message_id":messages[0].get("id") if messages and len(messages) > 0 else None,"first_step_id":messages[0].get("data",{}).get("step_id") if messages and len(messages) > 0 else None},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            
            if not messages:
                # No messages, continue
                logger.debug("No messages received, continuing...")
                await asyncio.sleep(0.5)  # Small sleep to prevent tight loop
                continue
            
            logger.info(f"Received {len(messages)} step request(s) (running: {len(running_tasks)})")
            
            # #region agent log
            log_data = {
                "location": "tasks.py:872",
                "message": "Processing step requests",
                "data": {
                    "message_count": len(messages),
                    "first_message_id": messages[0].get("id") if messages else None,
                    "first_step_id": messages[0].get("data", {}).get("step_id") if messages else None,
                },
                "timestamp": int(time.time() * 1000),
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "D"
            }
            # NOTE: Removed local debug.log instrumentation (was breaking tools in containers).
            
            # Process messages in parallel (up to MAX_CONCURRENT_STEPS)
            # Each message is processed concurrently, but per-session concurrency is controlled
            # Start tasks without waiting - they run in background
            for message in messages:
                if len(running_tasks) >= settings.MAX_CONCURRENT_STEPS:
                    logger.warning(f"At capacity, deferring {len(messages) - messages.index(message)} remaining message(s)")
                    break
                
                task = asyncio.create_task(
                    process_step_request_with_error_handling(message)
                )
                running_tasks.add(task)
                # Add callback to remove task when done
                task.add_done_callback(lambda t: running_tasks.discard(t))
            
            # Don't wait for tasks - continue loop to consume more messages
            # Tasks run in background and clean themselves up
            # NOTE: Removed local debug.log instrumentation (was breaking tools in containers).
        
        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
            await asyncio.sleep(5)  # Wait before retrying


async def process_step_request_with_error_handling(message: Dict[str, Any]) -> None:
    """
    Wrapper around process_step_request with error handling.
    
    This ensures that even if process_step_request fails, we handle it gracefully.
    """
    try:
        await process_step_request(message)
    except Exception as e:
        logger.error(f"Failed to process message {message.get('id')}: {e}", exc_info=True)
        # process_step_request handles its own ACK in finally block, but if it fails
        # before that, we need to ACK here to prevent infinite retries
        try:
            await ack_step_request(settings.CONSUMER_GROUP, message.get("id", ""))
        except Exception as ack_error:
            logger.error(f"Failed to acknowledge message: {ack_error}", exc_info=True)


async def run_all_workers() -> None:
    """
    Run both step request worker and dependency scan worker in parallel.
    """
    logger.info("Starting both worker loops in parallel...")
    results = await asyncio.gather(
        run_worker_loop(),
        run_dependency_worker_loop(),
        return_exceptions=True,
    )
    # Log any exceptions that were caught
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            worker_name = "step_worker" if i == 0 else "dependency_worker"
            logger.error(f"{worker_name} failed with exception: {result}", exc_info=result)


if __name__ == "__main__":
    # Import dependency worker
    try:
        from app.dependency_worker import run_dependency_worker_loop
        # Run both workers in parallel
        asyncio.run(run_all_workers())
    except ImportError:
        logger.warning("Dependency worker not available, running step worker only")
        # Fallback to step worker only
        asyncio.run(run_worker_loop())

