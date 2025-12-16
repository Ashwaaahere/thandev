"""
Celery tasks for step execution
"""
import logging
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List

from app.config import settings
from app.executor import get_execution_adapter  # Keep for backward compatibility
from app.execution.selector import get_backend_for_tool
from app.ingestion import ingest_findings_direct_db
from app.queue import consume_step_requests, ack_step_request, publish_step_result, StepResult
from app.concurrency import (
    acquire_session_slot,
    release_session_slot,
    check_step_idempotency,
)

logger = logging.getLogger(__name__)


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
    
    try:
        logger.info(
            f"Processing step {step_id} (tool_id={tool_id}, mode_id={mode_id}, "
            f"session={session_id}, scan_job={scan_job_id})"
        )
        
        # Get execution backend (new system) or adapter (legacy)
        # Use new execution backend system if available, fallback to adapter
        use_new_backend = getattr(settings, "USE_EXECUTION_BACKEND", True)
        execution_result = None  # Will be set if using new backend
        
        if use_new_backend:
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
            # Create job directory
            if scan_job_id:
                job_dir = Path(settings.TOOLS_BASE_DIR) / "data" / "jobs" / scan_job_id
            else:
                job_dir = Path(settings.TOOLS_BASE_DIR) / "data" / "jobs" / session_id
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
        
        # Ingest findings if successful
        findings_count = 0
        if result.get("success") and scan_job_id:
            try:
                # Get database session
                from app.database import get_db_session
                db = get_db_session()
                try:
                    # Parse tool output to get findings
                    tool_name = result.get("tool_name", tool_id)
                    
                    # Determine output file path (may be from artifact_refs for remote backend)
                    output_file = None
                    if use_new_backend and execution_result and execution_result.artifact_refs:
                        # Use artifact refs from remote backend
                        output_file = Path(execution_result.artifact_refs[0]) if execution_result.artifact_refs else None
                    else:
                        # Use local job_dir (legacy adapter)
                        if scan_job_id:
                            job_dir = Path(settings.TOOLS_BASE_DIR) / "data" / "jobs" / scan_job_id
                        else:
                            job_dir = Path(settings.TOOLS_BASE_DIR) / "data" / "jobs" / session_id
                        output_file = job_dir / f"{tool_name}_output.json"

                    # If we have tool output but no file yet (e.g. remote backend without shared volume),
                    # materialize the output to a file so existing parsers can operate on it.
                    if output_file and not output_file.exists() and result.get("output"):
                        try:
                            output_file.parent.mkdir(parents=True, exist_ok=True)
                            output_text = result.get("output") or ""
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
                    
                    # Import parsers from backend
                    from app.backend_imports import ensure_backend_in_path
                    ensure_backend_in_path()
                    
                    from app.services.findings_ingestor import (
                        parse_nuclei_output,
                        parse_nmap_output,
                        parse_httpx_output,
                        parse_ffuf_output,
                        parse_dalfox_output,
                        ingest_nuclei_findings,
                        ingest_nmap_findings,
                        ingest_httpx_findings,
                        ingest_ffuf_findings,
                        ingest_dalfox_findings,
                    )
                    
                    baseline_filter = result.get("baseline")  # For ffuf
                    
                    if output_file and output_file.exists():
                        if tool_name == "nuclei":
                            findings = parse_nuclei_output(output_file)
                            ingested = ingest_nuclei_findings(db, scan_job_id, findings)
                            findings_count = len(ingested)
                        elif tool_name == "nmap":
                            findings = parse_nmap_output(output_file)
                            ingested = ingest_nmap_findings(db, scan_job_id, findings)
                            findings_count = len(ingested)
                        elif tool_name == "httpx":
                            findings = parse_httpx_output(output_file)
                            ingested = ingest_httpx_findings(db, scan_job_id, findings)
                            findings_count = len(ingested)
                        elif tool_name == "ffuf":
                            findings = parse_ffuf_output(output_file, baseline_filter=baseline_filter)
                            ingested = ingest_ffuf_findings(db, scan_job_id, findings)
                            findings_count = len(ingested)
                        elif tool_name == "dalfox":
                            findings = parse_dalfox_output(output_file)
                            ingested = ingest_dalfox_findings(db, scan_job_id, findings)
                            findings_count = len(ingested)
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Failed to ingest findings for step {step_id}: {e}", exc_info=True)
                # Continue - findings ingestion failure shouldn't fail the step
        
        # Publish result
        # Get output_file path (may not exist if execution failed)
        output_file_path = None
        if result.get("success"):
            tool_name = result.get("tool_name", tool_id)
            if use_new_backend and execution_result and execution_result.artifact_refs:
                output_file_path = execution_result.artifact_refs[0]
            else:
                # Legacy: use local job_dir
                if scan_job_id:
                    job_dir = Path(settings.TOOLS_BASE_DIR) / "data" / "jobs" / scan_job_id
                else:
                    job_dir = Path(settings.TOOLS_BASE_DIR) / "data" / "jobs" / session_id
                output_file = job_dir / f"{tool_name}_output.json"
                if output_file.exists():
                    output_file_path = str(output_file)
        
        step_result = StepResult(
            session_id=session_id,
            step_id=step_id,
            status="success" if result.get("success") else "failed",
            execution_time_sec=execution_time,
            findings_count=findings_count,
            artifact_refs=[output_file_path] if output_file_path else [],
            error=result.get("error"),
            tool_output_summary=result.get("output", "")[:500] if result.get("output") else None,
            tool_id=tool_id,  # Include tool_id in result
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
    
    while True:
        try:
            # Consume step requests
            logger.debug(f"Waiting for step requests from stream {settings.CONSUMER_GROUP}...")
            messages = await consume_step_requests(
                consumer_group=settings.CONSUMER_GROUP,
                consumer_name=settings.CONSUMER_NAME,
                count=settings.MAX_CONCURRENT_STEPS,
                block_ms=1000,
            )
            
            if not messages:
                # No messages, continue
                logger.debug("No messages received, continuing...")
                continue
            
            logger.info(f"Received {len(messages)} step request(s)")
            
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

