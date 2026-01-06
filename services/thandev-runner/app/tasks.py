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
import uuid
from app.backend_client import post_tool_result, get_scan_status, mark_scan_started, post_tool_started
from app.findings.parsers import parse_nuclei_output, parse_httpx_output, parse_sslscan_output, parse_ffuf_output
from app.concurrency import (
    acquire_session_slot,
    release_session_slot,
    check_step_idempotency,
)

logger = logging.getLogger(__name__)

def _tcp_connectable(target_url: str, timeout_sec: float = 5.0) -> bool:
    """
    Fast preflight check: can we open a TCP connection to target host:port?
    Prevents long-running tools from hanging on unreachable targets.
    """
    try:
        parsed = urlparse(target_url)
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except Exception:
        return False


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
            f"Session {session_id} at max concurrency, deferring step {step_id}. "
            f"Message will be re-delivered by Redis Streams."
        )
        # Don't ACK - let Redis Streams re-deliver this message later
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

        # Preflight connectivity check for HTTP/TLS tools.
        # If the target is unreachable, fail fast (instead of hanging for minutes).
        http_tools = {"httpx", "nuclei", "ffuf", "dalfox", "sslscan"}
        preflight_ok = True
        if tool_id in http_tools:
            preflight_ok = _tcp_connectable(target_ref, timeout_sec=5.0)

        # Get execution backend (new system) or adapter (legacy)
        # Use new execution backend system if available, fallback to adapter
        use_new_backend = getattr(settings, "USE_EXECUTION_BACKEND", True)
        execution_result = None  # Will be set if using new backend

        if not preflight_ok:
            err = f"Target unreachable (TCP connect failed): {target_ref}"
            logger.warning(err, extra={"scan_job_id": scan_job_id, "step_id": step_id, "tool_id": tool_id})
            result = {
                "tool_name": tool_id,
                "output": "",
                "exit_code": -1,
                "execution_time": 0.0,
                "success": False,
                "error": err,
                "timed_out": False,
            }
        elif use_new_backend:
            # Use new execution backend system
            backend = get_backend_for_tool(tool_id)
            
            # Execute step using new backend
            start_time = time.time()
            
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
        
        if scan_job_id:
            # NOTE: Removed local debug.log instrumentation (was breaking tools in containers).
            # Initialize tool_name early
            tool_name = result.get("tool_name", tool_id) if result else tool_id
            
            # Determine output file path (may be from artifact_refs for remote backend)
            output_file = None
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
            # Always create the file (even if empty) so POST logic can run
            if output_file and not output_file.exists():
                try:
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    output_text = result.get("output") or ""
                    
                    # Normalize Dalfox output: convert placeholder outputs to empty array
                    # This must happen BEFORE writing to file so parsers get normalized data
                    # Check both tool_name and tool_id to handle formats like "tool-dalfox-v2"
                    is_dalfox = (tool_name and "dalfox" in tool_name.lower()) or (tool_id and "dalfox" in tool_id.lower())
                    if is_dalfox:
                        output_text = _normalize_dalfox_output(output_text)
                    
                    # Always create file (even if empty) to ensure POST logic runs
                    output_file.write_text(output_text, encoding="utf-8")
                    logger.info(
                        "Materialized output for tool %s (step %s, scan_job %s) to %s (len=%d)",
                        tool_name,
                        step_id,
                        scan_job_id,
                        output_file,
                        len(output_text),
                    )
                except Exception as write_err:
                    logger.warning(
                        f"Failed to materialize output file for {tool_name}: {write_err}",
                        exc_info=True,
                    )
        
        # Parse findings using local parsers
        # Always run POST logic for successful executions, even if no output file or no findings
        findings_count = 0
        findings = []
        
        if scan_job_id and result.get("success") and output_file and output_file.exists():
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
                if output_file and not output_file.exists() and result.get("output"):
                    try:
                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        output_text = result.get("output") or ""
                        
                        # Normalize Dalfox output to avoid fake findings
                        is_dalfox = (tool_name and "dalfox" in tool_name.lower()) or (tool_id and "dalfox" in tool_id.lower())
                        if is_dalfox:
                            output_text = _normalize_dalfox_output(output_text)
                        
                        output_file.write_text(output_text, encoding="utf-8")
                        logger.info(
                            "Materialized output for tool %s (step %s, scan_job %s) to %s (len=%d)",
                            tool_name,
                            step_id,
                            scan_job_id,
                            output_file,
                            len(output_text),
                        )
                    except Exception as write_err:
                        logger.warning(
                            "Failed to write tool output to file for %s (step %s, scan_job %s): %s",
                            tool_name,
                            step_id,
                            scan_job_id,
                            write_err,
                        )

            try:
                tool_name = result.get("tool_name", tool_id)
                
                # Parse findings using local parsers
                if tool_name == "nuclei":
                    findings = parse_nuclei_output(output_file)
                    logger.info(f"Parsed {len(findings)} findings from nuclei")
                elif tool_name == "httpx":
                    findings = parse_httpx_output(output_file)
                    logger.info(f"Parsed {len(findings)} findings from httpx")
                elif tool_name == "sslscan":
                    findings = parse_sslscan_output(output_file)
                    logger.info(f"Parsed {len(findings)} findings from sslscan")
                elif tool_name == "ffuf":
                    findings = parse_ffuf_output(output_file)
                    logger.info(f"Parsed {len(findings)} findings from ffuf")
                else:
                    # Other tools (nmap, ffuf, dalfox, sqlmap) not yet implemented in local parsers
                    # For now, skip parsing - can be added later
                    logger.debug(f"Parser not yet implemented for {tool_name}, skipping findings parsing")
                    findings = []
                
                findings_count = len(findings)
                
            except Exception as e:
                logger.error(f"Failed to parse findings for step {step_id}: {e}", exc_info=True)
                # Continue - findings parsing failure shouldn't fail the step
                findings = []
                findings_count = 0
        
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
                    success = await post_tool_result(
                        scan_job_id=scan_job_id,
                        step_id=step_id,
                        tool_name=tool_name,
                        tool_id=tool_id,
                        findings=findings,
                        execution_result=result,
                        tool_run_id=tool_run_id,
                    )
                    if success:
                        logger.info(
                            f"Posted tool result to backend (status code 201): "
                            f"scan={scan_job_id}, step={step_id}, tool={tool_name}, findings={findings_count}"
                        )
                    else:
                        logger.warning(
                            f"Failed to POST tool result to backend for scan={scan_job_id}, step={step_id}, tool={tool_name}"
                        )
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
    except Exception as e:
        logger.error(f"Step {step_id} execution failed: {e}", exc_info=True)
        execution_time = time.time() - start_time if 'start_time' in locals() else 0.0
        
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
    
    # NOTE: Removed local debug.log instrumentation (was breaking tools in containers).
    
    # Track if this is the first iteration (to check for pending messages on startup)
    first_iteration = True
    
    while True:
        try:
            # Consume step requests
            logger.debug(f"Waiting for step requests from stream {settings.CONSUMER_GROUP}...")
            
            # NOTE: Removed local debug.log instrumentation (was breaking tools in containers).
            
            messages = await consume_step_requests(
                consumer_group=settings.CONSUMER_GROUP,
                consumer_name=settings.CONSUMER_NAME,
                count=settings.MAX_CONCURRENT_STEPS,
                block_ms=1000,
                # Always check/claim pending messages to avoid stuck scans after restarts.
                # This is low overhead (quick XPENDING summary) and prevents orphaned work.
                check_pending=True,
            )
            first_iteration = False  # Kept for backwards compatibility with existing log flow
            
            # NOTE: Removed local debug.log instrumentation (was breaking tools in containers).
            
            if not messages:
                # No messages, continue
                logger.debug("No messages received, continuing...")
                continue
            
            logger.info(f"Received {len(messages)} step request(s)")
            
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
            tasks = []
            for message in messages:
                task = asyncio.create_task(
                    process_step_request_with_error_handling(message)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info(f"Completed processing {len(tasks)} step request(s)")
                
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
        
        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
            await asyncio.sleep(5)  # Wait before retrying


if __name__ == "__main__":
    # Run worker loop
    asyncio.run(run_worker_loop())

