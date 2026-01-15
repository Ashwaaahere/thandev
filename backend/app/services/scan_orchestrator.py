"""
Scan orchestrator service
Handles queuing and coordination of security scans
"""
import logging
from typing import Optional, TYPE_CHECKING, Dict, Any, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import os
from pathlib import Path

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.scan import ScanJob
    from app.services.tools import ToolExecutor

logger = logging.getLogger(__name__)

# Maximum number of tools to run in parallel - now uses settings.MAX_PARALLEL_TOOLS


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
        logger.debug("Normalizing dalfox placeholder output to empty array")
        return "[]"
    
    # Try parsing as JSON to check for empty objects
    # This handles cases like "[\n{}\n]" where newlines are inside brackets
    try:
        import json
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
                logger.debug("Normalizing dalfox output: all items were empty dicts, returning []")
                return "[]"
            # Return filtered list as JSON
            return json.dumps(filtered)
        
        # If it's a single empty dict, return []
        if isinstance(parsed, dict) and not parsed:
            logger.debug("Normalizing dalfox output: empty dict, returning []")
            return "[]"
        
        # Valid output, return as-is (re-serialize to ensure clean formatting)
        return json.dumps(parsed) if not isinstance(parsed, str) else output_stripped
        
    except json.JSONDecodeError:
        # Not valid JSON, return as-is (might be error message or other text)
        logger.warning("Dalfox output is not valid JSON, returning as-is")
        return output_stripped


class ScanOrchestrator:
    """Orchestrates security scan execution"""
    
    # NOTE: queue_scan method removed - Celery has been removed.
    # Scans are now queued via Runner (Redis streams) or Brain service directly.
    
    # NOTE: get_scan_status method removed - Celery has been removed.
    # Scan status is now tracked via Runner (Redis streams) or Brain service.
    
    def run_basic_scan_for_job(self, job: "ScanJob") -> None:
        """
        Run the basic scan pipeline for this job.
        DEPRECATED: Use run_scan_for_job() instead.
        
        Args:
            job: ScanJob instance
        """
        logger.warning(f"run_basic_scan_for_job is deprecated, use run_scan_for_job instead")
        # Import here to avoid circular import
        from app.services.scan_orchestrator import run_scan_for_job
        return run_scan_for_job(job)


def _run_single_tool(
    db: Session,
    scan_job_id: str,
    executor: "ToolExecutor",
    tool_config: Dict[str, Any],
    target_url: str,
    job_dir: Path,
    loop: asyncio.AbstractEventLoop,
) -> str:
    """
    Execute a single tool, save results, and ingest findings.
    
    This is a helper function designed to run in parallel via ThreadPoolExecutor.
    Each tool execution is independent and can run concurrently with others.
    
    Args:
        db: Database session (thread-local, each thread gets its own)
        scan_job_id: ScanJob ID (will be loaded from this thread's DB session)
        executor: ToolExecutor instance
        tool_config: Tool configuration dict with "name" and "config" keys
        target_url: Target URL to scan
        job_dir: Directory for saving tool output files
        loop: Event loop for async tool execution
        
    Returns:
        Tool name (key) for tracking
        
    Raises:
        Exception: If tool execution fails (will be caught by caller)
    """
    from app.models.scan import ScanJob
    from app.models.finding import ToolResult, ToolExecutionStatus
    from app.core.scan_timeouts import get_tool_timeout
    from app.services.tool_run_recorder import start_tool_run, finish_tool_run, update_tool_run_counts
    from datetime import datetime
    
    # Load scan_job from this thread's DB session
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
    if not scan_job:
        raise ValueError(f"Scan job {scan_job_id} not found")
    
    # Support both old format (name/config) and new format (tool_id/mode_id)
    tool_name = tool_config.get("name")
    tool_id = tool_config.get("tool_id")
    mode_id = tool_config.get("mode_id")
    tool_config_dict = tool_config.get("config", {})
    
    # Determine tool name for tracking
    result_tool_name = tool_id or tool_name or "unknown"
    
    # Get timeout for this tool at this scan level
    timeout_seconds = get_tool_timeout(scan_job.scan_level.value, result_tool_name)
    tool_config_dict["timeout_seconds"] = timeout_seconds
    
    # Prepare meta for tool run (command, args, version, etc.)
    meta = {
        "tool_id": tool_id,
        "mode_id": mode_id,
        "tool_name": tool_name,
        "timeout_seconds": timeout_seconds,
    }
    
    # Start tool run using recorder helper
    tool_run_id = start_tool_run(db, scan_job.id, result_tool_name, meta=meta)
    
    # Get the ToolResult record for status updates
    tool_result = db.query(ToolResult).filter(ToolResult.id == tool_run_id).first()
    if not tool_result:
        raise ValueError(f"ToolResult {tool_run_id} not found after creation")
    
    # Update status to RUNNING
    tool_result.status = ToolExecutionStatus.RUNNING
    db.commit()
    db.refresh(tool_result)
    
    tool_start_time = datetime.now(timezone.utc)
    logger.info(
        "Starting tool execution",
        extra={
            "tool_name": result_tool_name,
            "scan_job_id": scan_job.id,
            "tool_run_id": tool_run_id,
            "timeout_seconds": timeout_seconds,
            "started_at": tool_start_time.isoformat(),
        }
    )
    
    # Initialize result dict for exception handling
    result = {}
    final_status = ToolExecutionStatus.FAILED
    stdout = ""
    stderr = ""
    
    # Execute tool
    try:
        # New format: tool_id/mode_id (from brain service plan)
        if tool_id and mode_id:
            logger.info(f"Running tool_id={tool_id}, mode_id={mode_id} for scan {scan_job.id}")
            try:
                params = tool_config_dict.copy()
                result = loop.run_until_complete(
                    executor.run_step(
                        tool_id=tool_id,
                        mode_id=mode_id,
                        target_url=target_url,
                        params=params,
                        scan_job_id=scan_job.id,
                        job_dir=job_dir,
                    )
                )
                # Ensure result has tool_name for backward compatibility
                if "tool_name" not in result:
                    result["tool_name"] = tool_id
            except ValueError as e:
                logger.error(f"Invalid tool_id/mode_id: {e}")
                raise
        # Legacy format: tool name (for backward compatibility during migration)
        elif tool_name:
            logger.info(f"Running {tool_name} for scan {scan_job.id} (legacy format)")
            # Pass scan_job_id and scan_job_dir to tools for better logging and output paths
            tool_config_dict["scan_job_id"] = scan_job.id
            tool_config_dict["scan_job_dir"] = job_dir
            result = loop.run_until_complete(
                executor.run_tool(tool_name, target_url, scan_job.scan_level.value, **tool_config_dict)
            )
        else:
            raise ValueError(f"Tool config must have either (tool_id, mode_id) or 'name': {tool_config}")
        
        # Capture stdout/stderr from result
        # Ensure result has required fields (defensive programming)
        if not isinstance(result, dict):
            logger.error(f"Tool {result_tool_name} returned non-dict result: {type(result)}")
            result = {"output": "", "error": "Invalid result format from tool execution"}
        
        stdout = result.get("output", "")
        stderr = result.get("error", "") or result.get("stderr", "")
        
        # Ensure success field exists (default to True if not present for backward compatibility)
        if "success" not in result:
            # Infer success from other fields
            result["success"] = (
                result.get("exit_code", 0) == 0 and
                not result.get("error") and
                not result.get("timed_out", False)
            )
        
        # Update ToolResult with execution results (for backward compatibility)
        tool_result.output = stdout or ""
        tool_result.exit_code = result.get("exit_code", 0)
        tool_result.execution_time = result.get("execution_time", 0)
        tool_result.command = result.get("command", "")
        tool_result.error_message = result.get("error")
        tool_result.timed_out = 1 if result.get("timed_out", False) else 0
        
        # Determine final status based on result
        # Use explicit success field if available, otherwise infer from other fields
        tool_success = result.get("success", True)
        if "success" not in result:
            # Infer success: no error, no timeout, exit code 0 or no exit code
            tool_success = (
                result.get("exit_code", 0) == 0 and
                not result.get("error") and
                not result.get("timed_out", False)
            )
        
        if result.get("timed_out", False):
            final_status = ToolExecutionStatus.TIMED_OUT
            tool_result.error_code = "timeout"
            if not tool_result.error_message:
                tool_result.error_message = f"Tool execution timed out after {timeout_seconds} seconds"
        elif not tool_success:
            final_status = ToolExecutionStatus.FAILED
            # Determine error code from error message
            error_msg = (result.get("error", "") or tool_result.error_message or "").lower()
            if "not found" in error_msg or "missing" in error_msg or "binary" in error_msg:
                tool_result.error_code = "missing_binary"
            elif "unreachable" in error_msg or "connection" in error_msg:
                tool_result.error_code = "target_unreachable"
            elif "timeout" in error_msg or "timed out" in error_msg:
                tool_result.error_code = "timeout"
            else:
                tool_result.error_code = "execution_error"
        else:
            final_status = ToolExecutionStatus.COMPLETED
            tool_result.error_code = None
        
        tool_end_time = datetime.now(timezone.utc)
        tool_duration = (tool_end_time - tool_start_time).total_seconds()
        logger.info(
            "Tool execution completed",
            extra={
                "tool_name": result_tool_name,
                "scan_job_id": scan_job.id,
                "tool_run_id": tool_run_id,
                "status": final_status.value,
                "exit_code": result.get("exit_code"),
                "duration_seconds": tool_duration,
                "completed_at": tool_end_time.isoformat(),
                "success": tool_success,
            }
        )
        
    except Exception as e:
        # Tool execution raised an exception
        logger.error(f"Tool {result_tool_name} execution failed for scan {scan_job.id}: {e}", exc_info=True)
        final_status = ToolExecutionStatus.FAILED
        tool_result.error_code = "execution_error"
        tool_result.error_message = str(e)
        stdout = ""
        stderr = str(e)
        # Don't re-raise - we want to continue with other tools
    
    # Compute duration_ms from execution_time if available
    duration_ms = None
    if tool_result.execution_time is not None:
        duration_ms = int(tool_result.execution_time * 1000)
    
    db.commit()
    db.refresh(tool_result)
    
    # Save tool output to file
    # CRITICAL: Always write output to file, even if tool doesn't write directly
    # This ensures repeatability and testability
    # Use canonical tool name for output file to ensure consistent naming
    from app.services.tool_name_utils import canonical_tool_name
    output_tool_name_raw = tool_name or tool_id or result_tool_name
    output_tool_name = canonical_tool_name(output_tool_name_raw)  # Normalize for consistent comparison
    output_file = job_dir / f"{output_tool_name}_output.json"
    output_path_str = str(output_file)
    
    # Track file write success for error reporting
    file_write_success = False
    
    # #region agent log
    import json
    with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scan_orchestrator.py:356","message":"BEFORE file write block","data":{"scan_job_id":scan_job_id,"output_tool_name":output_tool_name,"output_tool_name_raw":output_tool_name_raw,"stdout_length":len(stdout) if stdout else 0,"stdout_preview":repr(stdout[:50]) if stdout else ""},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
    # #endregion
    
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # For dalfox: Always write stdout to file (even if empty)
        # Normalize dalfox output: convert placeholder outputs to empty array
        # CRITICAL: output_tool_name is already canonical, so direct comparison works
        # #region agent log
        with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scan_orchestrator.py:372","message":"Tool name check","data":{"scan_job_id":scan_job_id,"output_tool_name":output_tool_name,"output_tool_name_raw":output_tool_name_raw,"is_dalfox":output_tool_name == "dalfox"},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
        # #endregion
        if output_tool_name == "dalfox":
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scan_orchestrator.py:365","message":"Dalfox output before normalization","data":{"scan_job_id":scan_job_id,"stdout_length":len(stdout) if stdout else 0,"stdout_preview":stdout[:300] if stdout else "","stdout_repr":repr(stdout[:100]) if stdout else ""},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
            # #endregion
            output_text = _normalize_dalfox_output(stdout)
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scan_orchestrator.py:370","message":"Dalfox output after normalization","data":{"scan_job_id":scan_job_id,"normalized_length":len(output_text),"normalized_preview":output_text[:300],"normalized_repr":repr(output_text[:100])},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
            # #endregion
        else:
            # For other tools, use stdout or empty string
            output_text = stdout or ""
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scan_orchestrator.py:376","message":"Non-dalfox tool output","data":{"scan_job_id":scan_job_id,"output_tool_name":output_tool_name},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
            # #endregion
        
        # Always write to file (ensures repeatability)
        # #region agent log
        with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"scan_orchestrator.py:392","message":"About to write output file","data":{"scan_job_id":scan_job_id,"output_file":str(output_file),"output_text_length":len(output_text),"output_text_preview":output_text[:100],"output_text_repr":repr(output_text[:100])},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
        # #endregion
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output_text)
        
        # Verify file was written successfully
        if output_file.exists():
            file_write_success = True
            file_size = os.path.getsize(output_file)
            logger.info(
                "Output file created successfully",
                extra={
                    "tool_name": output_tool_name,
                    "scan_job_id": scan_job_id,
                    "tool_run_id": tool_run_id,
                    "file_path": str(output_file),
                    "file_size_bytes": file_size,
                    "output_length": len(output_text),
                }
            )
        else:
            logger.error(
                "File write appeared to succeed but file does not exist",
                extra={
                    "tool_name": output_tool_name,
                    "scan_job_id": scan_job_id,
                    "tool_run_id": tool_run_id,
                    "file_path": str(output_file),
                }
            )
            file_write_success = False
        # #region agent log
        if output_tool_name == "dalfox":  # output_tool_name is already canonical
            file_size = os.path.getsize(output_file) if output_file.exists() else 0
            file_content = output_file.read_text() if output_file.exists() else ""
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"scan_orchestrator.py:399","message":"Dalfox output file written","data":{"scan_job_id":scan_job_id,"output_file":str(output_file),"file_size":file_size,"file_content_preview":file_content[:100],"file_content_repr":repr(file_content[:100])},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
        # #endregion
        # #region agent log
        if canonical_tool_name(output_tool_name) == "dalfox":
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"scan_orchestrator.py:363","message":"Dalfox output file written","data":{"scan_job_id":scan_job_id,"output_file":str(output_file),"file_size":os.path.getsize(output_file) if output_file.exists() else 0},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
        # #endregion
        # #region agent log
        with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"scan_orchestrator.py:363","message":"Dalfox output file written","data":{"scan_job_id":scan_job_id,"output_file":str(output_file),"file_size":os.path.getsize(output_file) if output_file.exists() else 0},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
        # #endregion
        
        # Don't finish tool run yet - wait until after ingestion to capture ingestion errors
        # We'll call finish_tool_run after ingestion completes (or fails)
        
        # Log file size after writing
        file_size = os.path.getsize(output_file)
        if output_tool_name == "nuclei":
            logger.info(
                "Nuclei output written for scan %s: %d bytes at %s",
                scan_job.id, file_size, output_file
            )
            # Log a preview of the output if it's not empty
            if file_size > 0:
                try:
                    with open(output_file, "r", encoding="utf-8") as preview_f:
                        first_line = preview_f.readline().strip()
                        if first_line:
                            logger.debug("Nuclei output first line preview: %s", first_line[:200])
                except Exception:
                    pass
            else:
                logger.info("Nuclei output file is empty (0 bytes) - no findings detected")
        elif output_tool_name == "dalfox":
            # Structured logging for dalfox output
            logger.info(
                "Dalfox output written",
                extra={
                    "scan_id": scan_job.id,
                    "file_path": str(output_file),
                    "file_size_bytes": file_size,
                    "tool_name": "dalfox",
                }
            )
            # Log a preview of the output if it's not empty
            if file_size > 0:
                try:
                    with open(output_file, "r", encoding="utf-8") as preview_f:
                        content = preview_f.read()
                        preview_truncated = content[:300]  # First 300 chars for preview
                        logger.debug(
                            "Dalfox output preview",
                            extra={
                                "scan_id": scan_job.id,
                                "preview": preview_truncated,
                                "is_empty_array": content.strip() == "[]",
                            }
                        )
                except Exception:
                    pass
            else:
                logger.info(
                    "Dalfox output file is empty - no findings detected",
                    extra={
                        "scan_id": scan_job.id,
                        "file_path": str(output_file),
                    }
                )
        else:
            logger.debug(f"Saved {output_tool_name} output to {output_file} ({file_size} bytes)")
    except Exception as e:
        file_write_success = False
        error_msg = f"Failed to save {output_tool_name} output to file {output_file}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if tool_result:
            existing_error = tool_result.error_message or ""
            if "File write error" not in existing_error:
                tool_result.error_message = f"{existing_error}; File write error: {str(e)}".strip("; ")
            tool_result.error_code = tool_result.error_code or "file_write_error"
        # Ensure output_path is still set even if file write failed (for debugging)
        if not output_path_str:
            output_path_str = str(output_file)
    
    # Ingest tool-specific findings immediately after file is written
    from app.services.findings_ingestor import (
        parse_nuclei_output,
        parse_nmap_output,
        parse_sqlmap_output,
        parse_sqlmap_stdout,
        ingest_sqlmap_findings,
        parse_sslscan_output,
        parse_httpx_output,
        parse_ffuf_output,
        parse_dalfox_output,
        parse_sqlmap_output,
        ingest_nuclei_findings,
        ingest_nmap_findings,
        ingest_sslscan_findings,
        ingest_httpx_findings,
        ingest_ffuf_findings,
        ingest_dalfox_findings,
        ingest_sqlmap_findings,
    )
    
    # Use canonical tool name for ingestion (tool_name already normalized in start_tool_run)
    from app.services.tool_name_utils import canonical_tool_name
    ingest_tool_name = canonical_tool_name(tool_id or tool_name or result_tool_name)
    
    # Track ingestion errors (initialize before ingestion)
    ingest_error = None
    
    # Ingest nuclei findings immediately (don't wait for end)
    # CRITICAL: Ingest findings even if tool timed out, as there might be partial results
    # Only skip if tool actually failed (not just timed out)
    should_ingest_nuclei = (
        ingest_tool_name == "nuclei" and 
        (result.get("success", True) or result.get("timed_out", False))
    )
    if should_ingest_nuclei:
        try:
            nuclei_results = parse_nuclei_output(output_file)
            parsed_count = len(nuclei_results)
            if parsed_count > 0:
                logger.info("Parsed %d nuclei findings for scan %s (even though tool may have timed out)", parsed_count, scan_job.id)
            else:
                logger.info("No nuclei findings parsed for scan %s (file may be empty or tool timed out before finding anything)", scan_job.id)
            findings = ingest_nuclei_findings(db, scan_job.id, nuclei_results, tool_result_id=tool_run_id)
            created_count_hint = len(findings)
            update_tool_run_counts(db, tool_run_id, parsed_count, created_count_hint)
        except Exception as e:
            error_msg = f"Failed to ingest nuclei findings: {str(e)}"
            logger.error("Failed to ingest nuclei findings for scan %s: %s", scan_job.id, e, exc_info=True)
            ingest_error = error_msg
            update_tool_run_counts(db, tool_run_id, 0, 0)
    
    elif ingest_tool_name == "nmap" and result.get("success", True):
        try:
            nmap_results = parse_nmap_output(output_file)
            parsed_count = len(nmap_results)
            logger.info("Parsed %d nmap findings for scan %s", parsed_count, scan_job.id)
            findings = ingest_nmap_findings(db, scan_job.id, nmap_results, tool_result_id=tool_run_id)
            created_count_hint = len(findings)
            update_tool_run_counts(db, tool_run_id, parsed_count, created_count_hint)
        except Exception as e:
            error_msg = f"Failed to ingest nmap findings: {str(e)}"
            logger.error("Failed to ingest nmap findings for scan %s: %s", scan_job.id, e, exc_info=True)
            ingest_error = error_msg
            update_tool_run_counts(db, tool_run_id, 0, 0)
    
    elif ingest_tool_name == "sslscan" and result.get("success", True):
        try:
            sslscan_results = parse_sslscan_output(output_file)
            parsed_count = len(sslscan_results)
            logger.info("Parsed %d sslscan findings for scan %s", parsed_count, scan_job.id)
            findings = ingest_sslscan_findings(db, scan_job.id, sslscan_results, tool_result_id=tool_run_id)
            created_count_hint = len(findings)
            update_tool_run_counts(db, tool_run_id, parsed_count, created_count_hint)
        except Exception as e:
            error_msg = f"Failed to ingest sslscan findings: {str(e)}"
            logger.error("Failed to ingest sslscan findings for scan %s: %s", scan_job.id, e, exc_info=True)
            ingest_error = error_msg
            update_tool_run_counts(db, tool_run_id, 0, 0)
    
    elif ingest_tool_name == "httpx" and result.get("success", True):
        try:
            httpx_results = parse_httpx_output(output_file)
            parsed_count = len(httpx_results)
            logger.info("Parsed %d httpx findings for scan %s", parsed_count, scan_job.id)
            findings = ingest_httpx_findings(db, scan_job.id, httpx_results, tool_result_id=tool_run_id)
            created_count_hint = len(findings)
            update_tool_run_counts(db, tool_run_id, parsed_count, created_count_hint)
        except Exception as e:
            error_msg = f"Failed to ingest httpx findings: {str(e)}"
            logger.error("Failed to ingest httpx findings for scan %s: %s", scan_job.id, e, exc_info=True)
            ingest_error = error_msg
            update_tool_run_counts(db, tool_run_id, 0, 0)
    
    elif ingest_tool_name == "ffuf" and result.get("success", True):
        try:
            # PR-4C: Extract baseline from result for filtering 404/wildcard responses
            baseline_filter = result.get("baseline")
            ffuf_results = parse_ffuf_output(output_file, baseline_filter=baseline_filter)
            parsed_count = len(ffuf_results)
            logger.info("Parsed %d ffuf findings for scan %s (baseline filter: %s)", 
                       parsed_count, scan_job.id, "enabled" if baseline_filter else "disabled")
            findings = ingest_ffuf_findings(db, scan_job.id, ffuf_results, tool_result_id=tool_run_id)
            created_count_hint = len(findings)
            update_tool_run_counts(db, tool_run_id, parsed_count, created_count_hint)
        except Exception as e:
            error_msg = f"Failed to ingest ffuf findings: {str(e)}"
            logger.error("Failed to ingest ffuf findings for scan %s: %s", scan_job.id, e, exc_info=True)
            ingest_error = error_msg
            update_tool_run_counts(db, tool_run_id, 0, 0)
    
    elif ingest_tool_name == "dalfox" and result.get("success", True):
        try:
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"scan_orchestrator.py:540","message":"Dalfox ingestion start","data":{"scan_job_id":scan_job.id,"tool_run_id":tool_run_id,"output_file":str(output_file)},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
            # #endregion
            # Parse from file (not stdout) - file is always created above
            dalfox_results = parse_dalfox_output(output_file)
            parsed_count = len(dalfox_results)
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"scan_orchestrator.py:543","message":"Dalfox parsing complete","data":{"parsed_count":parsed_count,"results_sample":dalfox_results[:1] if dalfox_results else []},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
            # #endregion
            
            if parsed_count > 0:
                logger.info("Parsed %d dalfox findings for scan %s", parsed_count, scan_job.id)
            else:
                logger.info("Dalfox completed successfully for scan %s but found no XSS vulnerabilities", scan_job.id)
            
            # Ingest findings (pass tool_result_id for v2 mapping)
            findings = ingest_dalfox_findings(db, scan_job.id, dalfox_results, tool_result_id=tool_run_id)
            # Note: created_count will be computed from DB in update_tool_run_counts (source of truth)
            # We pass len(findings) as a hint, but DB query will override it
            created_count_hint = len(findings)
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"scan_orchestrator.py:551","message":"Dalfox ingestion complete","data":{"findings_count":len(findings),"created_count_hint":created_count_hint},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
            # #endregion
            
            # Update tool run counts (DB query will compute actual count)
            update_tool_run_counts(db, tool_run_id, parsed_count, created_count_hint)
        except Exception as e:
            error_msg = f"Failed to ingest dalfox findings: {str(e)}"
            logger.error("Failed to ingest dalfox findings for scan %s: %s", scan_job.id, e, exc_info=True)
            ingest_error = error_msg
            # Update counts to 0 on error
            update_tool_run_counts(db, tool_run_id, 0, 0)
    
    elif ingest_tool_name == "sqlmap":
        # Always try to parse sqlmap output, even if success=False
        # sqlmap may find SQL injection but exit with non-zero or timeout
        try:
            logger.info("Processing sqlmap results for scan %s (success=%s, has_output=%s)", 
                       scan_job.id, result.get("success"), bool(result.get("output")))
            
            # Parse stdout FIRST (this is where sqlmap outputs detection results)
            sqlmap_results = []
            if result.get("output"):
                logger.info("Parsing sqlmap stdout for scan %s (output length: %d chars)", 
                           scan_job.id, len(result.get("output", "")))
                stdout_results = parse_sqlmap_stdout(result.get("output"), target_url)
                if stdout_results:
                    logger.info("Parsed %d sqlmap findings from stdout for scan %s", len(stdout_results), scan_job.id)
                    sqlmap_results.extend(stdout_results)
                else:
                    # Log a sample of stdout to debug why parsing failed
                    output_preview = result.get("output", "")[:500]
                    if "vulnerable" in output_preview.lower() or "injection" in output_preview.lower():
                        logger.warning("sqlmap output contains 'vulnerable' or 'injection' but parsing returned 0 findings. Full output length: %d", 
                                     len(result.get("output", "")))
            
            # Also try parsing output directory (for CSV/log files)
            output_dir = None
            possible_dirs = [
                result.get("output_dir"),  # From result dict
                job_dir / "sqlmap",  # Default location
            ]
            
            # Try to extract output directory from stdout
            if result.get("output"):
                import re
                output_dir_match = re.search(r"output directory:\s*['\"]?([^'\n\"]+)", result.get("output", ""), re.IGNORECASE)
                if output_dir_match:
                    possible_dirs.insert(0, Path(output_dir_match.group(1)))
                
                csv_match = re.search(r"CSV file '([^']+)'", result.get("output", ""))
                if csv_match:
                    csv_path = Path(csv_match.group(1))
                    if csv_path.exists():
                        possible_dirs.insert(0, csv_path.parent)
            
            # Find the first existing directory
            for dir_path in possible_dirs:
                if dir_path:
                    test_dir = Path(dir_path)
                    if test_dir.exists() and test_dir.is_dir():
                        output_dir = test_dir
                        break
            
            if output_dir and output_dir.exists():
                dir_results = parse_sqlmap_output(output_dir)
                logger.info("Parsed %d sqlmap findings from directory %s for scan %s", len(dir_results), output_dir, scan_job.id)
                # Merge results, avoiding duplicates (by parameter + technique)
                existing_params = {(r.get("url", ""), r.get("parameter", ""), r.get("technique", "")) for r in sqlmap_results}
                for dir_result in dir_results:
                    key = (dir_result.get("url", ""), dir_result.get("parameter", ""), dir_result.get("technique", ""))
                    if key not in existing_params:
                        sqlmap_results.append(dir_result)
                        existing_params.add(key)
            
            if sqlmap_results:
                logger.info("Ingesting %d sqlmap findings for scan %s", len(sqlmap_results), scan_job.id)
                ingested = ingest_sqlmap_findings(db, scan_job.id, sqlmap_results)
                logger.info("Successfully ingested %d sqlmap findings for scan %s", len(ingested), scan_job.id)
            else:
                # Log more details when no findings are detected
                logger.warning("No sqlmap findings detected for scan %s. Output length: %d, Output dir exists: %s", 
                             scan_job.id, 
                             len(result.get("output", "")),
                             output_dir.exists() if output_dir else False)
                # Log a sample of the output for debugging if it contains relevant keywords
                if result.get("output"):
                    output_sample = result.get("output", "")
                    if "vulnerable" in output_sample.lower() or "injection" in output_sample.lower():
                        logger.warning("sqlmap output contains 'vulnerable' or 'injection' keywords but no findings parsed. Sample: %s", 
                                     output_sample[:1000])
        except Exception as e:
            logger.error("Failed to ingest sqlmap findings for scan %s: %s", scan_job.id, e, exc_info=True)
    
    # Commit this tool's results (each thread manages its own transaction)
    db.commit()
    
    # PR-3: Ingest findings into brain RAG after DB commit
    try:
        from app.services.brain_client import get_brain_client
        from app.core.config import settings
        
        if settings.BRAIN_SERVICE_ENABLED:
            # Get org_id and project_id for RAG filtering
            org_id = None
            project_id = scan_job.project_id
            if scan_job.project and scan_job.project.tenant:
                org_id = scan_job.project.tenant.id
            
            # Query findings that were just created for this tool
            from app.models.finding import Finding
            recent_findings = db.query(Finding).filter(
                Finding.scan_job_id == scan_job.id,
                Finding.tool_name == output_tool_name
            ).order_by(Finding.created_at.desc()).limit(100).all()
            
            if recent_findings:
                # Convert Finding models to dict format for brain
                findings_data = []
                for finding in recent_findings:
                    finding_dict = {
                        "id": str(finding.id),
                        "title": finding.title,
                        "description": finding.description,
                        "severity": finding.severity.value if hasattr(finding.severity, 'value') else str(finding.severity),
                        "url": finding.url,
                        "tool_id": finding.tool_name,
                        "tool_name": finding.tool_name,  # For compatibility
                        "org_id": org_id,
                        "project_id": project_id,
                        "target": target_url,
                    }
                    
                    # Parse raw_data if available
                    if finding.raw_data:
                        try:
                            import json
                            raw_data = json.loads(finding.raw_data)
                            finding_dict["raw_data"] = raw_data
                            
                            # Extract CVE ID if present
                            if isinstance(raw_data, dict):
                                cve_id = raw_data.get("cve_id") or raw_data.get("cve")
                                if cve_id:
                                    finding_dict["cve_id"] = cve_id
                        except (json.JSONDecodeError, TypeError):
                            pass
                    
                    findings_data.append(finding_dict)
                
                # Ingest to brain RAG (async, but we're in a sync context)
                # Use the existing event loop
                try:
                    brain_client = get_brain_client()
                    loop.run_until_complete(
                        brain_client.ingest_documents(
                            findings=findings_data,
                            org_id=org_id,
                            project_id=project_id,
                        )
                    )
                    logger.info(f"Ingested {len(findings_data)} findings from {output_tool_name} into brain RAG for scan {scan_job.id}")
                except Exception as e:
                    # Don't fail the scan if RAG ingestion fails
                    logger.warning(f"Failed to ingest findings into brain RAG: {e}", exc_info=True)
    except Exception as e:
        # Don't fail the scan if RAG ingestion fails
        logger.warning(f"RAG ingestion error (non-fatal): {e}", exc_info=True)
    
    # Verify output file exists (critical for debugging and ingestion)
    if not file_write_success and output_file.exists():
        # File was created despite exception - mark as success
        file_write_success = True
        logger.info(f"Output file {output_file} exists despite earlier error - marking as successful")
    
    if not file_write_success:
        logger.warning(
            "Output file was not created",
            extra={
                "tool_name": output_tool_name,
                "scan_job_id": scan_job.id,
                "tool_run_id": tool_run_id,
                "file_path": str(output_file),
                "file_exists": output_file.exists(),
            }
        )
        # Update tool result to indicate file write issue
        if tool_result and not tool_result.error_message:
            tool_result.error_message = f"Output file not created: {output_file}"
    
    # Finish tool run after all ingestion is complete (capture ingestion errors)
    # CRITICAL: Always call finish_tool_run, even if file write failed
    try:
        finish_tool_run(
            db=db,
            tool_run_id=tool_run_id,
            status=final_status,
            exit_code=tool_result.exit_code,
            stdout=stdout,
            stderr=stderr,
            output_path=output_path_str if file_write_success and output_file.exists() else None,
            duration_ms=duration_ms,
            ingest_error=ingest_error,
        )
    except Exception as finish_error:
        # Log but don't fail - tool execution is already complete
        logger.error(f"Failed to finish tool run {tool_run_id}: {finish_error}", exc_info=True)
    
    return output_tool_name


def run_scan_for_job(job: "ScanJob") -> None:
    """
    Run the appropriate scan pipeline for this job based on job.scan_level.
    
    This function:
    1. Gets the scan profile for the job's scan level
    2. Runs each tool in the profile sequentially
    3. Parses findings from tool output
    4. Generates AI report
    
    Args:
        job: ScanJob instance with project relationship loaded
        
    Raises:
        ValueError: If scan level is invalid
        Exception: If scan execution fails
    """
    from app.core.database import SessionLocal
    from app.models.scan import ScanJob, ScanStatus
    from app.services.tools import ToolExecutor
    from app.models.finding import ToolResult
    from app.services.scan_profiles import get_profile
    from app.services.findings_ingestor import (
        parse_nuclei_output,
        ingest_nuclei_findings,
        parse_nmap_output,
        parse_sslscan_output,
        parse_httpx_output,
        parse_ffuf_output,
        parse_dalfox_output,
        parse_sqlmap_output,
        ingest_nmap_findings,
        ingest_sslscan_findings,
        ingest_http_header_findings,
        ingest_httpx_findings,
        ingest_ffuf_findings,
        ingest_dalfox_findings,
        ingest_sqlmap_findings,
    )
    from datetime import datetime
    import json
    import asyncio
    import os
    from pathlib import Path
    
    scan_start_time = datetime.now(timezone.utc)
    logger.info(
        "Starting scan execution",
        extra={
            "scan_job_id": job.id,
            "scan_level": job.scan_level.value,
            "started_at": scan_start_time.isoformat(),
        }
    )
    
    # Get database session (job might be from a different session)
    db = SessionLocal()
    
    try:
        # Reload job from database to ensure we have latest state
        scan_job = db.query(ScanJob).filter(ScanJob.id == job.id).first()
        if not scan_job:
            raise ValueError(f"Scan job {job.id} not found in database")
        
        # Get target URL from project
        if not scan_job.project:
            db.refresh(scan_job, ["project"])
        if not scan_job.project:
            raise ValueError(f"Project not found for scan job {scan_job.id}")
        
        target_url = scan_job.project.target_url
        logger.info(f"Scanning target: {target_url}")
        
        # Build stack_info for future AI planning
        # This MUST be set before any tool execution or early returns
        from typing import Any, Dict
        import requests
        
        stack_info: Dict[str, Any] = {
            "target_url": target_url,
            "scan_level": getattr(scan_job.scan_level, "value", str(scan_job.scan_level)),
        }
        
        # Try a cheap HTTP HEAD/GET to enrich stack_info
        try:
            # Try HEAD first (cheaper, no body)
            try:
                resp = requests.head(target_url, timeout=5, allow_redirects=True)
            except requests.exceptions.RequestException:
                # Fallback to GET if HEAD fails (some servers don't support HEAD)
                from app.core.config import settings
                resp = requests.get(target_url, timeout=settings.HTTP_PROBE_TIMEOUT_SECONDS, allow_redirects=True, stream=True)
            
            stack_info["http"] = {
                "status_code": resp.status_code,
                "headers": {
                    "server": resp.headers.get("Server"),
                    "content_type": resp.headers.get("Content-Type"),
                    "x_powered_by": resp.headers.get("X-Powered-By"),
                },
            }
            logger.debug(f"Collected HTTP stack info for {target_url}: status={resp.status_code}")
        except Exception as e:
            # If HTTP request fails, log warning and continue with minimal stack_info
            logger.warning(f"Failed to fetch HTTP info for stack_info on job {scan_job.id}: {e}")
            # stack_info already has target_url and scan_level, which is sufficient
        
        # Persist stack_info to DB BEFORE running tools
        scan_job.stack_info = stack_info
        db.add(scan_job)
        db.commit()
        db.refresh(scan_job)
        logger.info(f"Saved stack_info for scan {scan_job.id}: {stack_info}")
        
        # Initialize event loop for async operations (brain client calls)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # PR-3: Ingest tech fingerprint into brain RAG
        try:
            from app.services.brain_client import get_brain_client
            from app.core.config import settings
            
            if settings.BRAIN_SERVICE_ENABLED:
                org_id = None
                project_id = scan_job.project_id
                if scan_job.project and scan_job.project.tenant:
                    org_id = scan_job.project.tenant.id
                
                brain_client = get_brain_client()
                loop.run_until_complete(
                    brain_client.ingest_documents(
                        tech_fingerprints=[{
                            "target": target_url,
                            "stack_info": stack_info,
                            "org_id": org_id,
                            "project_id": project_id,
                        }],
                        org_id=org_id,
                        project_id=project_id,
                    )
                )
                logger.info(f"Ingested tech fingerprint into brain RAG for scan {scan_job.id}")
        except Exception as e:
            # Don't fail the scan if RAG ingestion fails
            logger.warning(f"Failed to ingest tech fingerprint into brain RAG: {e}", exc_info=True)
        
        # Plan scan using brain service (PR-1: brain-only planning)
        plan = None
        from app.core.config import settings
        from app.services.ai.plan_validation import PlanExecutionValidator, PlanValidationError
        import sys
        from pathlib import Path
        
        # Add packages to path
        # Go up from: backend/app/services/scan_orchestrator.py
        # To: backend/../packages
        packages_path = Path(__file__).parent.parent.parent.parent.parent / "packages"
        if str(packages_path) not in sys.path:
            sys.path.insert(0, str(packages_path))
        
        from thandev_schemas.planning import PlanScanResponse
        
        # PR-1: Core must NOT decide which tools to run
        # Brain service is the only planner (unless explicitly disabled)
        if settings.BRAIN_SERVICE_ENABLED:
            try:
                from app.services.brain_client import get_brain_client
                brain_client = get_brain_client()
                
                # Get org_id and project_id for RAG filtering
                org_id = None
                project_id = scan_job.project_id
                if scan_job.project and scan_job.project.tenant:
                    org_id = scan_job.project.tenant.id
                
                # Call brain service (using existing event loop)
                brain_plan_dict = loop.run_until_complete(
                    brain_client.create_plan(
                        target_url=target_url,
                        scan_level=scan_job.scan_level.value,
                        org_id=org_id,
                        project_id=project_id,
                        stack_info=stack_info,
                    )
                )
                
                # Validate plan using PlanExecutionValidator (PR-1 requirement)
                try:
                    brain_plan = PlanScanResponse(**brain_plan_dict)
                    validator = PlanExecutionValidator()
                    
                    # Determine target type from URL
                    target_type = "https" if target_url.startswith("https://") else "http"
                    
                    # Validate plan
                    validator.validate_plan(
                        brain_plan,
                        target_type=target_type,
                        max_steps=50,
                        max_parallelism=10,
                        max_total_runtime_sec=3600,
                    )
                    
                    logger.info(
                        f"Plan validated: {len(brain_plan.steps)} steps, "
                        f"{brain_plan.timeline.total_estimated_sec}s estimated"
                    )
                    
                except PlanValidationError as e:
                    logger.error(f"Plan validation failed: {e}")
                    raise ValueError(f"Invalid plan from brain service: {e}")
                
                # Log the complete brain plan for debugging
                logger.info(
                    f"Brain service plan for scan {scan_job.id}: "
                    f"{len(brain_plan.steps)} steps, "
                    f"tools=[{', '.join(set(s.tool_id for s in brain_plan.steps))}]"
                )
                for step in brain_plan.steps:
                    logger.info(
                        f"  Step {step.step_id}: tool={step.tool_id}, mode={step.mode_id}, "
                        f"params={step.params}, depends_on={step.depends_on}, reason={step.reason}"
                    )
                
                # Convert brain plan format to orchestrator format
                # Brain returns: {plan_id, steps: [{step_id, tool_id, mode_id, params, depends_on, reason, estimated_duration_sec}], timeline, metadata}
                # Orchestrator expects: {waves: [{phase, tools: [{tool_id, mode_id, params}]}]}
                
                # Group steps by phase based on dependencies (topological sort)
                steps_by_phase = {}
                step_phases = {}  # Map step_id -> phase number
                
                # Build dependency graph
                step_ids = {step.step_id for step in brain_plan.steps}
                graph: Dict[str, List[str]] = {step.step_id: [] for step in brain_plan.steps}
                in_degree: Dict[str, int] = {step_id: 0 for step_id in step_ids}
                
                for step in brain_plan.steps:
                    for dep in step.depends_on:
                        if dep in step_ids:
                            graph[step.step_id].append(dep)
                            in_degree[step.step_id] += 1
                
                # Topological sort to assign phases
                phase = 1
                queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
                
                while queue:
                    if phase not in steps_by_phase:
                        steps_by_phase[phase] = []
                    
                    next_queue = []
                    for node in queue:
                        step_phases[node] = phase
                        # Find step object
                        step_obj = next(s for s in brain_plan.steps if s.step_id == node)
                        
                        # Convert to orchestrator format (NEW: tool_id/mode_id format)
                        tool_config = {
                            "tool_id": step_obj.tool_id,
                            "mode_id": step_obj.mode_id,
                            "config": step_obj.params,  # Already validated params
                        }
                        steps_by_phase[phase].append(tool_config)
                        
                        # Update in_degree for dependent steps
                        for step in brain_plan.steps:
                            if node in step.depends_on:
                                in_degree[step.step_id] -= 1
                                if in_degree[step.step_id] == 0:
                                    next_queue.append(step.step_id)
                    
                    queue = next_queue
                    phase += 1
                
                # Build waves
                waves = []
                for phase_num in sorted(steps_by_phase.keys()):
                    waves.append({
                        "phase": f"phase_{phase_num}",
                        "tools": steps_by_phase[phase_num]
                    })
                
                plan = {"waves": waves}
                logger.info(
                    f"Generated scan plan from brain service: {len(waves)} wave(s), "
                    f"{len(brain_plan.steps)} step(s), validated and ready for execution"
                )
                
            except Exception as e:
                logger.error(f"Brain service planning failed: {e}", exc_info=True)
                
                # Graceful degradation: Use fallback planner if brain service is unavailable
                if settings.BRAIN_REQUIRED:
                    # Brain is required - fail the scan
                    scan_job.status = ScanStatus.FAILED
                    error_msg = f"Brain service planning failed: {str(e)}. Brain service is required (BRAIN_REQUIRED=true)."
                    scan_job.error_message = error_msg
                    db.commit()
                    raise ValueError(f"Brain service required but failed: {e}")
                else:
                    # Brain is optional - use catalog-based fallback planner
                    logger.warning(f"Brain service unavailable, using catalog-based fallback planner for scan {scan_job.id}")
                    try:
                        from app.services.tools import ToolExecutor
                        from app.models.scan import ScanLevel
                        
                        executor = ToolExecutor()
                        level_enum = ScanLevel(scan_job.scan_level.value)
                        
                        # Use catalog to get default tools for scan level
                        # Map scan level to default modes from catalog
                        level_to_default_modes = {
                            ScanLevel.BASIC: [
                                ("httpx", "low"),
                                ("nuclei", "basic_web"),
                                ("zap", "passive_spider"),
                            ],
                            ScanLevel.PRO: [
                                ("httpx", "medium"),
                                ("nuclei", "pro_web"),
                                ("nmap", "top_ports"),
                                ("sslscan", "standard"),
                                ("dalfox", "standard"),
                                ("zap", "active_scan"),
                            ],
                            ScanLevel.ADVANCED: [
                                ("httpx", "high"),
                                ("nuclei", "advanced_web"),
                                ("nmap", "full_ports_scripts"),
                                ("sslscan", "standard"),
                                ("dalfox", "standard"),
                                ("sqlmap", "sqli_light"),
                                ("zap", "ajax_spider"),  # AJAX spider first
                                ("zap", "active_scan"),  # Then active scan
                            ],
                        }
                        
                        default_tools = level_to_default_modes.get(level_enum, [])
                        tools = []
                        for tool_id, mode_id in default_tools:
                            # Verify tool/mode exists in catalog
                            if (tool_id, mode_id) in executor._tool_mode_map:
                                tools.append({
                                    "tool_id": tool_id,
                                    "mode_id": mode_id,
                                    "config": {}
                                })
                            else:
                                logger.warning(f"Tool {tool_id}/{mode_id} not found in catalog, skipping")
                        
                        if not tools:
                            raise ValueError(f"No valid tools found in catalog for scan level {level_enum.value}")
                        
                        plan = {
                            "waves": [{
                                "phase": "fallback",
                                "tools": tools
                            }]
                        }
                        logger.info(f"Catalog-based fallback plan generated: {len(tools)} tool(s) for scan {scan_job.id}")
                    except Exception as fallback_error:
                        logger.error(f"Catalog-based fallback planner failed: {fallback_error}", exc_info=True)
                        scan_job.status = ScanStatus.FAILED
                        scan_job.error_message = f"Both brain service and catalog-based fallback planner failed: {str(e)} / {str(fallback_error)}"
                        db.commit()
                        raise ValueError(f"All planning methods failed: {e} / {fallback_error}")
        
        # Ensure plan was generated (should never be None at this point)
        if plan is None:
            error_msg = "Failed to generate scan plan: Brain service did not return a plan."
            logger.error(error_msg)
            scan_job.status = ScanStatus.FAILED
            scan_job.error_message = error_msg
            db.commit()
            raise ValueError(error_msg)
        
        # Create job directory for artifacts
        job_dir = Path(f"data/jobs/{scan_job.id}")
        max_retries = 3
        dir_created = False
        for attempt in range(max_retries):
            try:
                job_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created job directory: {job_dir}")
                dir_created = True
                break
            except Exception as e:
                logger.warning(f"Failed to create job directory {job_dir} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(0.1)
        
        if not dir_created:
            logger.error(f"Failed to create job directory {job_dir} after {max_retries} attempts")
            # Continue anyway - file writes will handle directory creation as fallback
        
        # Initialize tool executor
        executor = ToolExecutor()
        
        # Pre-flight check: Verify all required tools are available
        # Extract tool_ids from plan
        required_tool_ids = []
        for wave in plan.get("waves", []):
            for tool_config in wave.get("tools", []):
                tool_id = tool_config.get("tool_id")
                tool_name = tool_config.get("name")  # Legacy format
                # Support both new (tool_id) and legacy (name) formats
                tool_identifier = tool_id or tool_name
                if tool_identifier and tool_identifier not in required_tool_ids:
                    required_tool_ids.append(tool_identifier)
        
        if required_tool_ids:
            all_available, missing_tools = executor.check_tool_dependencies(required_tool_ids)
            if not all_available:
                error_msg = (
                    f"Required tools are missing: {', '.join(missing_tools)}. "
                    f"Please install the missing tools before running scans. "
                    f"Installation instructions: "
                    f"nuclei: go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest, "
                    f"nmap: sudo apt-get install nmap (or brew install nmap), "
                    f"sslscan: sudo apt-get install sslscan, "
                    f"httpx: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest, "
                    f"ffuf: go install -v github.com/ffuf/ffuf/v2@latest, "
                    f"dalfox: go install github.com/hahwul/dalfox/v2@latest, "
                    f"sqlmap: pip install sqlmap"
                )
                logger.error(error_msg)
                scan_job.status = ScanStatus.FAILED
                scan_job.error_message = error_msg
                scan_job.completed_at = datetime.now(timezone.utc)
                db.commit()
                raise ValueError(error_msg)
            logger.info(f"Pre-flight check passed: All required tools are available ({', '.join(required_tool_ids)})")
        else:
            logger.warning(f"No tools found in plan for scan {scan_job.id} - scan may not execute any tools")
        
        tool_results = []
        
        # Event loop already initialized earlier (line 505-509)
        # Reuse the same loop for async tool execution
        
        # Run HTTP security header checks (for HTTP/HTTPS URLs only)
        # This runs before other tools to collect headers early
        from app.services.http_security import fetch_http_security, build_header_findings
        from app.services.findings_ingestor import ingest_http_header_findings
        
        logger.info(f"Starting HTTP header check for scan {scan_job.id} on {target_url}")
        try:
            http_result = loop.run_until_complete(
                fetch_http_security(target_url, timeout=10.0)
            )
            
            if http_result is not None:
                logger.info(f"HTTP header check successful for {target_url}: status={http_result.status_code}, headers={len(http_result.headers)}")
                header_findings = build_header_findings(http_result, scan_job)
                if header_findings:
                    ingest_http_header_findings(db, scan_job.id, header_findings)
                    logger.info(f"Created {len(header_findings)} HTTP header findings for scan {scan_job.id}")
                else:
                    logger.info(f"No missing headers detected for {target_url} (all security headers present)")
            else:
                logger.info(f"Skipping HTTP header checks for {target_url} (not HTTP/HTTPS or request failed)")
        except Exception as e:
            logger.error(f"HTTP header check failed for scan {scan_job.id}: {e}", exc_info=True)
            # Continue with scan - header checks are optional
        
        # Create PENDING ToolResult records for all planned tools (for status tracking)
        from app.models.finding import ToolResult, ToolExecutionStatus
        from app.core.scan_timeouts import get_max_parallelism
        
        all_planned_tools = []
        for wave in plan.get("waves", []):
            for tool_config in wave.get("tools", []):
                tool_name = tool_config.get("tool_id") or tool_config.get("name") or "unknown"
                all_planned_tools.append(tool_name)
        
        # Create PENDING records for tools that don't have one yet
        for tool_name in all_planned_tools:
            existing = db.query(ToolResult).filter(
                ToolResult.scan_job_id == scan_job.id,
                ToolResult.tool_name == tool_name
            ).first()
            if not existing:
                tool_result = ToolResult(
                    scan_job_id=scan_job.id,
                    tool_name=tool_name,
                    status=ToolExecutionStatus.PENDING,
                )
                db.add(tool_result)
        db.commit()
        logger.info(f"Created {len(all_planned_tools)} PENDING tool records for scan {scan_job.id}")
        
        # Log the final plan before execution
        logger.info(f"Executing scan plan for scan {scan_job.id}: {len(plan.get('waves', []))} wave(s)")
        for wave_idx, wave in enumerate(plan.get("waves", [])):
            logger.info(f"  Wave {wave_idx + 1} ({wave.get('phase', 'unknown')}): {len(wave.get('tools', []))} tool(s)")
            for tool_cfg in wave.get("tools", []):
                logger.info(
                    f"    - tool_id={tool_cfg.get('tool_id')}, mode_id={tool_cfg.get('mode_id')}, "
                    f"config={tool_cfg.get('config', {})}"
                )
        
        # Execute tools from all waves in the plan
        # We'll collect all Nuclei outputs and ingest them at the end for idempotency
        all_nuclei_outputs = []
        completed_tools: List[str] = []
        failed_tools: List[str] = []
        
        # Get scan-level parallelism
        max_parallelism = get_max_parallelism(scan_job.scan_level.value)
        
        # Filter tools if THANDEV_PIPELINE_TOOLS is set
        allowed_tools = os.getenv("THANDEV_PIPELINE_TOOLS")
        if allowed_tools:
            allowed_tool_list = [t.strip() for t in allowed_tools.split(",")]
            logger.info(f"Filtering tools to subset: {allowed_tool_list}")
            
            # Collect all tools that will be filtered out
            filtered_out_tools = []
            
            # Filter tools in each wave
            for wave in plan.get("waves", []):
                original_tools = wave.get("tools", [])
                filtered_tools = []
                for tool_config in original_tools:
                    tool_name = tool_config.get("tool_id") or tool_config.get("name") or "unknown"
                    if tool_name in allowed_tool_list:
                        filtered_tools.append(tool_config)
                    else:
                        # Track filtered-out tool
                        filtered_out_tools.append(tool_name)
                wave["tools"] = filtered_tools
            
            # CRITICAL: Create ToolResult rows for filtered-out tools with SKIPPED status
            # This prevents API from creating fake "pending" entries
            from app.models.finding import ToolResult, ToolExecutionStatus
            for tool_name in filtered_out_tools:
                existing = db.query(ToolResult).filter(
                    ToolResult.scan_job_id == scan_job.id,
                    ToolResult.tool_name == tool_name
                ).first()
                if not existing:
                    tool_result = ToolResult(
                        scan_job_id=scan_job.id,
                        tool_name=tool_name,
                        status=ToolExecutionStatus.SKIPPED,
                        error_code="filtered_out",
                        error_message=f"Tool filtered out by THANDEV_PIPELINE_TOOLS={allowed_tools}",
                    )
                    db.add(tool_result)
            
            db.commit()
            logger.info(f"Filtered {len(filtered_out_tools)} tool(s) out, created SKIPPED ToolResult records")
        
        for wave_idx, wave in enumerate(plan.get("waves", [])):
            phase = wave.get("phase", f"wave_{wave_idx}")
            tools = wave.get("tools", [])
            
            if not tools:
                logger.warning(f"Wave {phase} has no tools, skipping")
                continue
            
            logger.info(f"Executing {phase} wave ({wave_idx + 1}/{len(plan.get('waves', []))}) with {len(tools)} tool(s)")
            
            # Run tools in parallel using ThreadPoolExecutor
            # Use scan-level parallelism instead of global setting
            max_workers = min(len(tools), max_parallelism)
            logger.info(f"Running {len(tools)} tool(s) in parallel (max {max_workers} concurrent, scan_level={scan_job.scan_level.value})")
            
            # Create a new event loop for each thread (ThreadPoolExecutor requirement)
            # Each thread will create its own loop for async tool execution
            def run_tool_with_loop(tool_cfg: Dict[str, Any]) -> str:
                """Wrapper that creates a thread-local event loop"""
                # Create a new event loop for this thread
                thread_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(thread_loop)
                try:
                    # Create a new DB session for this thread
                    from app.core.database import SessionLocal
                    thread_db = SessionLocal()
                    try:
                        return _run_single_tool(
                            thread_db, scan_job.id, executor, tool_cfg,
                            target_url, job_dir, thread_loop
                        )
                    finally:
                        thread_db.close()
                finally:
                    thread_loop.close()
            
            # Execute tools in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_workers) as executor_pool:
                future_map = {
                    executor_pool.submit(run_tool_with_loop, tool_config): (
                        tool_config.get("tool_id") or tool_config.get("name") or "unknown"
                    )
                    for tool_config in tools
                }
                
                for future in as_completed(future_map):
                    tool_key = future_map[future]
                    try:
                        completed_tool = future.result()
                        completed_tools.append(completed_tool)
                        logger.info(
                            "Tool %s completed for scan_job %s",
                            completed_tool,
                            scan_job.id,
                        )
                    except Exception as exc:
                        failed_tools.append(tool_key)
                        logger.exception(
                            "Tool %s failed for scan_job %s: %s",
                            tool_key,
                            scan_job.id,
                            exc,
                        )
        
        # Collect Nuclei outputs from files (after all tools complete)
        nuclei_output_path = job_dir / "nuclei_output.json"
        if nuclei_output_path.exists():
            try:
                with open(nuclei_output_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content:
                        all_nuclei_outputs.append(content)
            except Exception as e:
                logger.warning(f"Failed to read Nuclei output file: {e}")
        
        logger.info(f"Completed {len(completed_tools)} tool(s), {len(failed_tools)} failed")
        
        # ===== UPDATE SCAN STATUS IMMEDIATELY AFTER TOOLS COMPLETE =====
        # This ensures each scan completes independently, even if post-processing fails
        # Scan 2 can complete before Scan 1 without waiting
        db.refresh(scan_job)
        from app.models.finding import ToolResult, ToolExecutionStatus
        from app.models.scan import ScanStatus
        from datetime import datetime, timezone
        
        # Query all tool results for this scan
        tool_results = db.query(ToolResult).filter(
            ToolResult.scan_job_id == scan_job.id
        ).all()
        
        # Count tools by status
        completed_count = sum(1 for tr in tool_results if tr.status == ToolExecutionStatus.COMPLETED)
        failed_count = sum(1 for tr in tool_results if tr.status in [ToolExecutionStatus.FAILED, ToolExecutionStatus.TIMED_OUT, ToolExecutionStatus.SKIPPED])
        pending_count = sum(1 for tr in tool_results if tr.status == ToolExecutionStatus.PENDING)
        running_count = sum(1 for tr in tool_results if tr.status == ToolExecutionStatus.RUNNING)
        total_tools = len(tool_results)
        
        logger.info(
            f"Scan {scan_job.id} tool status summary: {completed_count} completed, {failed_count} failed, "
            f"{pending_count} pending, {running_count} running (total: {total_tools})"
        )
        
        # If there are still pending/running tools, mark them as failed (they should have completed by now)
        if pending_count > 0 or running_count > 0:
            logger.warning(
                f"Scan {scan_job.id} has {pending_count} pending and {running_count} running tools after execution. "
                f"Marking them as failed."
            )
            for tr in tool_results:
                if tr.status in [ToolExecutionStatus.PENDING, ToolExecutionStatus.RUNNING]:
                    tr.status = ToolExecutionStatus.FAILED
                    tr.error_code = "timeout"
                    tr.error_message = tr.error_message or "Tool did not complete execution"
                    failed_count += 1
                    if tr.status == ToolExecutionStatus.PENDING:
                        pending_count -= 1
                    else:
                        running_count -= 1
        
        # Determine final scan status based on tool results
        # CRITICAL: Always update scan status, even if all tools failed
        # This ensures the scan appears in the frontend
        if total_tools == 0:
            # No tools were executed - mark as FAILED
            scan_job.status = ScanStatus.FAILED
            scan_job.error_message = "No tools were executed for this scan"
            logger.warning(f"Scan {scan_job.id} has no tool results - marking as FAILED")
        elif completed_count == 0 and failed_count > 0:
            # No tools completed, all failed - mark scan as FAILED
            scan_job.status = ScanStatus.FAILED
            failed_tool_names = [tr.tool_name for tr in tool_results if tr.status in [ToolExecutionStatus.FAILED, ToolExecutionStatus.TIMED_OUT, ToolExecutionStatus.SKIPPED]]
            scan_job.error_message = f"All tools failed: {', '.join(failed_tool_names[:5])}"  # Limit to first 5 for brevity
            if len(failed_tool_names) > 5:
                scan_job.error_message += f" and {len(failed_tool_names) - 5} more"
            logger.warning(f"Scan {scan_job.id} failed: all {failed_count} tool(s) failed")
        elif completed_count > 0:
            # At least one tool completed - mark as COMPLETED or COMPLETED_WITH_ERRORS
            if failed_count > 0:
                scan_job.status = ScanStatus.COMPLETED_WITH_ERRORS
                failed_tool_names = [tr.tool_name for tr in tool_results if tr.status in [ToolExecutionStatus.FAILED, ToolExecutionStatus.TIMED_OUT, ToolExecutionStatus.SKIPPED]]
                scan_job.error_message = f"Some tools failed: {', '.join(failed_tool_names[:5])}"  # Limit to first 5
                if len(failed_tool_names) > 5:
                    scan_job.error_message += f" and {len(failed_tool_names) - 5} more"
                logger.info(f"Scan {scan_job.id} completed with errors: {completed_count} succeeded, {failed_count} failed")
            else:
                scan_job.status = ScanStatus.COMPLETED
                scan_job.error_message = None
                logger.info(f"Scan {scan_job.id} completed successfully: {completed_count} tool(s) completed")
        else:
            # No tools completed or failed (should not happen after marking pending/running as failed)
            scan_job.status = ScanStatus.FAILED
            scan_job.error_message = "No tools completed execution"
            logger.error(f"Scan {scan_job.id} has no completed or failed tools - this should not happen")
        
        # Set completed_at timestamp
        scan_job.completed_at = datetime.now(timezone.utc)
        
        # Commit status update immediately - scan is now marked as complete
        # CRITICAL: This ensures the scan appears in the frontend even if post-processing fails
        try:
            db.commit()
            db.refresh(scan_job)
            logger.info(
                "Scan status updated after tool execution",
                extra={
                    "scan_job_id": scan_job.id,
                    "status": scan_job.status.value,
                    "completed_count": completed_count,
                    "failed_count": failed_count,
                    "total_tools": total_tools,
                    "completed_at": scan_job.completed_at.isoformat() if scan_job.completed_at else None,
                }
            )
        except Exception as commit_error:
            logger.error(f"Failed to commit scan status update for {scan_job.id}: {commit_error}", exc_info=True)
            db.rollback()
            # Try one more time
            try:
                scan_job.status = ScanStatus.COMPLETED_WITH_ERRORS  # Safe fallback
                scan_job.completed_at = datetime.now(timezone.utc)
                scan_job.error_message = f"Status update error: {str(commit_error)[:200]}"
                db.commit()
                logger.warning(f"Scan {scan_job.id} status updated to COMPLETED_WITH_ERRORS after commit retry")
            except Exception as retry_error:
                logger.error(f"Failed to commit scan status on retry for {scan_job.id}: {retry_error}", exc_info=True)
                db.rollback()
        # ===== END OF IMMEDIATE STATUS UPDATE =====
        
        # Note: We'll ingest all Nuclei findings at the end after follow-up waves
        
        # Legacy AI planner removed - brain service handles all planning
        # If follow-up planning is needed, it should be done via brain service
        # For now, we only do initial planning via brain service
        from app.models.scan import AIStatus
        
        # Set AI status to indicate planning was done via brain service
        scan_job.ai_status = AIStatus.PLANNED.value if scan_job.ai_plan else None
        db.commit()
        db.refresh(scan_job)
        
        logger.info(f"Scan planning completed for scan {scan_job.id} via brain service")
        
        # Load findings for adaptive refinement
        db.refresh(scan_job)
        findings_list = list(scan_job.findings)
        logger.info(f"Current findings count before refinement: {len(findings_list)}")
        
        # Execute second wave of tools from AI plan if available
        # PR-1: This section should also use tool_id/mode_id format
        # Note: Legacy AI planner returns tool "key" format, we convert to tool_id/mode_id
        ai_plan = scan_job.ai_plan or {}
        next_tools = ai_plan.get("next_tools", [])
        
        if next_tools and scan_job.ai_status == AIStatus.PLANNED.value:
            logger.info(f"Executing AI-planned second wave for scan {scan_job.id}")
            
            # PR-1: Filter tools using catalog validation instead of tool_matrix
            executor = ToolExecutor()
            
            tools_to_run = []
            for tool_rec in next_tools:
                tool_key = tool_rec.get("key")
                if not tool_key:
                    continue
                
                # Check if tool is supported
                if tool_key not in executor.supported_tools:
                    logger.warning(
                        f"AI planner recommended unsupported tool '{tool_key}' for scan {scan_job.id}, skipping"
                    )
                    continue
                
                # PR-1: Use catalog to determine default mode instead of tool_matrix
                # For now, use a default mode based on tool_key (legacy compatibility)
                # TODO: AI planner should return tool_id/mode_id pairs
                default_mode_map = {
                    "nuclei": "pro_web",
                    "httpx": "medium",
                    "ffuf": "standard",
                    "dalfox": "constrained",
                    "sqlmap": "sqli_light",
                }
                mode_id = default_mode_map.get(tool_key, "standard")
                
                # Use new format: tool_id/mode_id
                tools_to_run.append({
                    "tool_id": tool_key,
                    "mode_id": mode_id,
                    "config": {}  # AI planner doesn't provide params yet
                })
            
            if tools_to_run:
                logger.info(
                    f"Executing {len(tools_to_run)} AI-planned tool(s) for scan {scan_job.id}"
                )
                
                # Run tools in parallel using ThreadPoolExecutor
                max_workers = min(len(tools_to_run), settings.MAX_PARALLEL_TOOLS)
                
                def run_tool_with_loop(tool_cfg: Dict[str, Any]) -> str:
                    """Wrapper that creates a thread-local event loop"""
                    thread_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(thread_loop)
                    try:
                        from app.core.database import SessionLocal
                        thread_db = SessionLocal()
                        try:
                            return _run_single_tool(
                                thread_db, scan_job.id, executor, tool_cfg,
                                target_url, job_dir, thread_loop
                            )
                        finally:
                            thread_db.close()
                    finally:
                        thread_loop.close()
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor_pool:
                    future_map = {
                        executor_pool.submit(run_tool_with_loop, tool_config): (
                            tool_config.get("tool_id") or tool_config.get("name") or "unknown"
                        )
                        for tool_config in tools_to_run
                    }
                    
                    for future in as_completed(future_map):
                        tool_key = future_map[future]
                        try:
                            completed_tool = future.result()
                            completed_tools.append(completed_tool)
                            logger.info(
                                "AI-planned tool %s completed for scan_job %s",
                                completed_tool,
                                scan_job.id,
                            )
                        except Exception as exc:
                            failed_tools.append(tool_key)
                            logger.exception(
                                "AI-planned tool %s failed for scan_job %s: %s",
                                tool_key,
                                scan_job.id,
                                exc,
                            )
            else:
                logger.info(f"No valid tools to run from AI plan for scan {scan_job.id}")
        else:
            if not next_tools:
                logger.info(f"AI planner returned no tools for scan {scan_job.id}, skipping second wave")
            elif scan_job.ai_status != AIStatus.PLANNED.value:
                logger.info(f"AI planner status is {scan_job.ai_status} for scan {scan_job.id}, skipping second wave")
        
        # PR-1: Legacy adaptive refinement removed - brain service handles all planning
        # Follow-up planning should be done via brain service if needed
        # No follow-up waves from legacy planner
        
        # Ingest all Nuclei findings at once (after all waves complete)
        # Read from the output file (not stdout) to get clean JSONL
        nuclei_output_path = job_dir / "nuclei_output.json"
        
        try:
            # Parse Nuclei output file (handles non-JSON lines, empty files gracefully)
            logger.info("Parsing Nuclei findings from %s", nuclei_output_path)
            all_nuclei_results = parse_nuclei_output(nuclei_output_path)
            
            logger.info("Parsed %d nuclei findings from file for scan %s", len(all_nuclei_results), scan_job.id)
            
            # Ingest findings (this deletes old ones and creates new ones - idempotent)
            # Call ingest_nuclei_findings even if results is empty (to ensure DB is clean)
            ingested_findings = ingest_nuclei_findings(db, scan_job.id, all_nuclei_results)
            logger.info("Finished nuclei ingestion for scan %s", scan_job.id)
            
            # PR-3: Ingest all findings into brain RAG after nuclei ingestion
            try:
                from app.services.brain_client import get_brain_client
                from app.core.config import settings
                from app.models.finding import Finding
                
                if settings.BRAIN_SERVICE_ENABLED:
                    # Get org_id and project_id
                    org_id = None
                    project_id = scan_job.project_id
                    if scan_job.project and scan_job.project.tenant:
                        org_id = scan_job.project.tenant.id
                    
                    # Get all findings for this scan
                    db.refresh(scan_job)
                    all_findings = db.query(Finding).filter(
                        Finding.scan_job_id == scan_job.id
                    ).all()
                    
                    if all_findings:
                        # Convert to dict format
                        findings_data = []
                        for finding in all_findings:
                            finding_dict = {
                                "id": str(finding.id),
                                "title": finding.title,
                                "description": finding.description,
                                "severity": finding.severity.value if hasattr(finding.severity, 'value') else str(finding.severity),
                                "url": finding.url,
                                "tool_id": finding.tool_name or "unknown",
                                "tool_name": finding.tool_name or "unknown",
                                "org_id": org_id,
                                "project_id": project_id,
                                "target": target_url,
                            }
                            
                            # Parse raw_data and extract CVE
                            if finding.raw_data:
                                try:
                                    import json
                                    raw_data = json.loads(finding.raw_data)
                                    finding_dict["raw_data"] = raw_data
                                    if isinstance(raw_data, dict):
                                        cve_id = raw_data.get("cve_id") or raw_data.get("cve") or finding.cve_id
                                        if cve_id:
                                            finding_dict["cve_id"] = cve_id
                                except (json.JSONDecodeError, TypeError):
                                    pass
                            
                            if finding.cve_id:
                                finding_dict["cve_id"] = finding.cve_id
                            
                            findings_data.append(finding_dict)
                        
                        # Ingest to brain RAG
                        brain_client = get_brain_client()
                        loop.run_until_complete(
                            brain_client.ingest_documents(
                                findings=findings_data,
                                org_id=org_id,
                                project_id=project_id,
                            )
                        )
                        logger.info(f"Ingested {len(findings_data)} total findings into brain RAG for scan {scan_job.id}")
            except Exception as e:
                # Don't fail the scan if RAG ingestion fails
                logger.warning(f"Failed to ingest findings into brain RAG: {e}", exc_info=True)
            
            # Verify findings count in DB
            db.refresh(scan_job)
            db_findings_count = len(scan_job.findings) if scan_job.findings else 0
            logger.info("Verified: %d findings in database for scan %s", db_findings_count, scan_job.id)
        except Exception as e:
            logger.error(
                "Failed to ingest Nuclei findings from %s: %s",
                nuclei_output_path, e, exc_info=True
            )
            # Continue - scan should complete even if finding ingestion fails
            # The scan will have 0 findings but status will be "completed"
        
        # Generate AI report (after all waves complete)
        # Use brain service for report prompt, then OpenAI for generation
        db.refresh(scan_job)
        final_findings_list = list(scan_job.findings)
        
        try:
            from app.core.config import settings
            
            if settings.BRAIN_SERVICE_ENABLED and settings.OPENAI_API_KEY:
                # Use brain service + OpenAI for report generation
                try:
                    from app.services.brain_client import get_brain_client
                    from app.services.ai.openai_client import get_openai_client
                    import json
                    
                    brain_client = get_brain_client()
                    
                    # Get org_id and project_id
                    org_id = None
                    project_id = scan_job.project_id
                    if scan_job.project and scan_job.project.tenant:
                        org_id = scan_job.project.tenant.id
                    
                    # Get finding IDs
                    finding_ids = [f.id for f in final_findings_list]
                    
                    # Build artifact refs from tool results
                    artifact_refs = []
                    for tool_result in scan_job.tool_results:
                        artifact_refs.append({
                            "id": f"artifact_{tool_result.id}",
                            "tool_name": tool_result.tool_name,
                            "file_path": f"data/jobs/{scan_job.id}/{tool_result.tool_name}_output.json",
                            "scan_job_id": scan_job.id,
                            "summary": f"{tool_result.tool_name} scan results",
                        })
                    
                    # Get prompt package from brain (using existing event loop)
                    prompt_package = loop.run_until_complete(
                        brain_client.build_report_prompt(
                            scan_job_id=scan_job.id,
                            finding_ids=finding_ids,
                            artifact_refs=artifact_refs,
                            org_id=org_id,
                            project_id=project_id,
                        )
                    )
                    
                    # Call OpenAI with structured outputs (using existing event loop)
                    openai_client = get_openai_client()
                    response = loop.run_until_complete(
                        openai_client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": prompt_package["system_message"]},
                                {"role": "user", "content": json.dumps(prompt_package["user_content"])},
                            ],
                            response_format={
                                "type": "json_schema",
                                "json_schema": {
                                    "name": "security_report",
                                    "schema": prompt_package["report_json_schema"],
                                }
                            },
                            temperature=0.3,
                            timeout=60.0,
                        )
                    )
                    
                    # Parse report JSON
                    report_json = json.loads(response.choices[0].message.content)
                    
                    # Validate report structure
                    # TODO: Add JSON Schema validation
                    
                    scan_job.summary = report_json
                    logger.info(f"Generated AI report via brain service for scan {scan_job.id} with {len(final_findings_list)} findings")
                    
                except Exception as e:
                    logger.warning(f"Brain service report generation failed: {e}, falling back to basic report", exc_info=True)
                    # Fall through to basic report
                    raise
            else:
                # Fallback to basic report (rule-based, no LLM)
                raise ValueError("Brain service or OpenAI not configured")
                
        except Exception as e:
            # Fallback to basic report
            try:
                from app.services.ai.reporter import generate_basic_report
                ai_report = generate_basic_report(scan_job, final_findings_list)
                scan_job.summary = ai_report
                logger.info(f"Generated basic report for scan {scan_job.id} with {len(final_findings_list)} findings")
            except Exception as e2:
                logger.error(f"Failed to generate AI report: {e2}", exc_info=True)
                from collections import Counter
                from app.core.constants import (
                    CANON_FINDINGS_COUNT, CANON_SEV_BREAKDOWN, CANON_RISK_SCORE,
                    DEPRECATED_TOTAL_FINDINGS, DEPRECATED_FINDINGS_BY_SEVERITY
                )
                findings_list = list(scan_job.findings) if scan_job.findings else []
                
                # Build severity_breakdown with all 5 keys
                severity_breakdown = dict(Counter(f.severity.value for f in findings_list)) if findings_list else {}
                # Ensure all keys present
                for sev in ["critical", "high", "medium", "low", "info"]:
                    if sev not in severity_breakdown:
                        severity_breakdown[sev] = 0
                
                scan_job.summary = {
                    "executive_summary": f"Scan completed with {len(findings_list)} findings. AI report generation encountered an error.",
                    "top_risks": [],
                    "remediation_overview": "Review findings and apply security best practices.",
                    CANON_RISK_SCORE: 0.0,  # float
                    CANON_FINDINGS_COUNT: len(findings_list),  # canonical
                    DEPRECATED_TOTAL_FINDINGS: len(findings_list),  # deprecated alias
                    CANON_SEV_BREAKDOWN: severity_breakdown,  # canonical, all keys present
                    DEPRECATED_FINDINGS_BY_SEVERITY: severity_breakdown.copy(),  # deprecated alias
                    "error": f"AI report generation failed: {str(e2)}"
                }
                logger.warning(f"Using fallback summary format for scan {scan_job.id}")
        
        # Safety check: Verify scan status was updated (should already be set above)
        # This is a fallback in case something went wrong
        db.refresh(scan_job)
        from app.models.finding import ToolResult, ToolExecutionStatus
        
        if scan_job.status == ScanStatus.RUNNING:
            logger.warning(f"Scan {scan_job.id} status still RUNNING after post-processing, re-checking tool results (safety check)")
            
            # Query all tool results for this scan
            tool_results = db.query(ToolResult).filter(
                ToolResult.scan_job_id == scan_job.id
            ).all()
            
            # Count tools by status
            completed_count = sum(1 for tr in tool_results if tr.status == ToolExecutionStatus.COMPLETED)
            failed_count = sum(1 for tr in tool_results if tr.status in [ToolExecutionStatus.FAILED, ToolExecutionStatus.TIMED_OUT, ToolExecutionStatus.SKIPPED])
            pending_count = sum(1 for tr in tool_results if tr.status == ToolExecutionStatus.PENDING)
            running_count = sum(1 for tr in tool_results if tr.status == ToolExecutionStatus.RUNNING)
            
            logger.info(f"Scan {scan_job.id} tool status summary (safety check): {completed_count} completed, {failed_count} failed, {pending_count} pending, {running_count} running")
            
            # Determine final scan status
            if completed_count == 0 and failed_count > 0:
                # No tools completed, all failed - mark scan as FAILED
                scan_job.status = ScanStatus.FAILED
                failed_tool_names = [tr.tool_name for tr in tool_results if tr.status in [ToolExecutionStatus.FAILED, ToolExecutionStatus.TIMED_OUT, ToolExecutionStatus.SKIPPED]]
                scan_job.error_message = f"All tools failed: {', '.join(failed_tool_names)}"
            elif completed_count > 0:
                # At least one tool completed - mark as COMPLETED or COMPLETED_WITH_ERRORS
                if failed_count > 0:
                    scan_job.status = ScanStatus.COMPLETED_WITH_ERRORS
                    failed_tool_names = [tr.tool_name for tr in tool_results if tr.status in [ToolExecutionStatus.FAILED, ToolExecutionStatus.TIMED_OUT, ToolExecutionStatus.SKIPPED]]
                    scan_job.error_message = f"Some tools failed: {', '.join(failed_tool_names)}"
                else:
                    scan_job.status = ScanStatus.COMPLETED
                    scan_job.error_message = None
            else:
                # No tools completed or failed (all pending/running) - should not happen, but mark as FAILED
                scan_job.status = ScanStatus.FAILED
                scan_job.error_message = "No tools completed execution"
            
            scan_job.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Scan {scan_job.id} status updated via safety check to {scan_job.status.value}")
        else:
            logger.info(f"Scan {scan_job.id} status already set to {scan_job.status.value} (no safety check needed)")
        
        # CRITICAL: Always update findings_count in summary from database
        # Query findings count directly from database to ensure accuracy
        from app.models.finding import Finding
        final_findings_count = db.query(Finding).filter(Finding.scan_job_id == scan_job.id).count()
        
        # Ensure summary has findings_count set
        if scan_job.summary:
            if isinstance(scan_job.summary, dict):
                scan_job.summary["findings_count"] = final_findings_count
            else:
                # If summary is not a dict, create a new one
                scan_job.summary = {"findings_count": final_findings_count}
        else:
            # If summary doesn't exist, create a minimal one with findings_count
            scan_job.summary = {"findings_count": final_findings_count}
        
        db.commit()
        # Reload to get final findings count
        db.refresh(scan_job)
        scan_end_time = datetime.now(timezone.utc)
        scan_duration = (scan_end_time - scan_start_time).total_seconds() if 'scan_start_time' in locals() else None
        logger.info(
            "Scan execution completed",
            extra={
                "scan_job_id": scan_job.id,
                "status": scan_job.status.value,
                "findings_count": final_findings_count,
                "duration_seconds": scan_duration,
                "completed_at": scan_job.completed_at.isoformat() if scan_job.completed_at else None,
            }
        )
        
        # Update findings lifecycle: mark findings not seen in this scan
        try:
            update_findings_lifecycle_after_scan(db, scan_job.id, scan_job.project_id)
        except Exception as e:
            logger.warning(f"Failed to update findings lifecycle after scan completion: {e}", exc_info=True)
            # Don't fail the scan if lifecycle update fails
        
        # Log audit event: SCAN_COMPLETED
        try:
            from app.services.audit_logger import log_audit_event
            if scan_job.project:
                log_audit_event(
                    db=db,
                    action_type="SCAN_COMPLETED" if scan_job.status == ScanStatus.COMPLETED else "SCAN_COMPLETED_WITH_ERRORS",
                    user_id=scan_job.project.owner_id if scan_job.project else None,
                    tenant_id=scan_job.project.tenant_id if scan_job.project else None,
                    target_type="scan",
                    target_id=scan_job.id,
                    metadata={
                        "scan_level": scan_job.scan_level.value if hasattr(scan_job.scan_level, 'value') else str(scan_job.scan_level),
                        "findings_count": final_findings_count,
                        "status": scan_job.status.value if hasattr(scan_job.status, 'value') else str(scan_job.status),
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to log audit event for scan completion: {e}")
        
        # Create notification for scan completion
        try:
            create_scan_completed_notification(db, scan_job)
        except Exception as e:
            logger.warning(f"Failed to create scan completion notification: {e}", exc_info=True)
            # Don't fail the scan if notification creation fails
        
    except Exception as e:
        logger.error(f"Scan {job.id} failed: {str(e)}", exc_info=True)
        
        # Update scan job status to failed
        try:
            scan_job = db.query(ScanJob).filter(ScanJob.id == job.id).first()
            if scan_job:
                scan_job.status = ScanStatus.FAILED
                scan_job.error_message = str(e)
                scan_job.completed_at = datetime.now(timezone.utc)
                db.commit()
                
                # Log audit event: SCAN_FAILED
                try:
                    from app.services.audit_logger import log_audit_event
                    if scan_job.project:
                        log_audit_event(
                            db=db,
                            action_type="SCAN_FAILED",
                            user_id=scan_job.project.owner_id if scan_job.project else None,
                            tenant_id=scan_job.project.tenant_id if scan_job.project else None,
                            target_type="scan",
                            target_id=scan_job.id,
                            metadata={
                                "scan_level": scan_job.scan_level.value if hasattr(scan_job.scan_level, 'value') else str(scan_job.scan_level),
                                "error_message": str(e)[:500],  # Truncate long error messages
                            },
                        )
                except Exception as audit_error:
                    logger.warning(f"Failed to log audit event for scan failure: {audit_error}")
        except Exception as db_error:
            logger.error(f"Failed to update scan job status: {db_error}")
            db.rollback()
        
        raise
    
    finally:
        db.close()


def create_scan_completed_notification(db: Session, scan_job: "ScanJob") -> None:
    """
    Create a notification when a scan completes successfully.
    
    Args:
        db: Database session
        scan_job: Completed ScanJob instance (must have project relationship loaded)
    """
    from app.models.notification import Notification
    from app.models.project import Project
    from app.models.user import User
    from app.models.tenant import Tenant
    
    # Ensure project is loaded
    if not scan_job.project:
        db.refresh(scan_job, ["project"])
    
    if not scan_job.project:
        logger.warning(f"Cannot create notification: project not found for scan {scan_job.id}")
        return
    
    project = scan_job.project
    
    # Get tenant and user from project
    if not project.tenant:
        db.refresh(project, ["tenant"])
    if not project.owner:
        db.refresh(project, ["owner"])
    
    tenant = project.tenant
    user = project.owner
    
    if not tenant or not user:
        logger.warning(f"Cannot create notification: tenant or user not found for scan {scan_job.id}")
        return
    
    # Build notification title and message
    title = f"Scan completed for {project.name}"
    
    risk_score = None
    if scan_job.summary and isinstance(scan_job.summary, dict):
        risk_score = scan_job.summary.get("risk_score")
    
    message_parts = [
        f"Security scan for {project.target_url} ({scan_job.scan_level.value}) completed."
    ]
    if risk_score is not None:
        message_parts.append(f"Risk score: {risk_score:.1f}")
    
    message = " ".join(message_parts)
    
    # Build link URL
    link_url = f"/projects/{project.id}/scans/{scan_job.id}"
    
    # Create notification
    notification = Notification(
        tenant_id=tenant.id,
        owner_id=user.id,
        type="scan_completed",
        title=title,
        message=message,
        link_url=link_url,
        is_read=False,
    )
    
    db.add(notification)
    db.commit()
    logger.info(f"Created scan completion notification for scan {scan_job.id}")


def update_findings_lifecycle_after_scan(
    db: Session,
    current_scan_id: str,
    project_id: str,
) -> None:
    """
    Update findings lifecycle after a scan completes.
    
    For all findings in this project:
    - If last_seen_in_scan_id == current_scan_id: Mark as still present (no change)
    - If last_seen_in_scan_id != current_scan_id: Set not_seen_in_latest_scan = true
    
    This allows users to see which findings were not observed in the latest scan
    (potentially fixed, but user must confirm).
    
    Args:
        db: Database session
        current_scan_id: ID of the scan that just completed
        project_id: Project ID
    """
    from app.models.finding import Finding
    
    # Get all findings for this project
    findings = db.query(Finding).filter(
        Finding.project_id == project_id
    ).all()
    
    updated_count = 0
    for finding in findings:
        if finding.last_seen_in_scan_id == current_scan_id:
            # Still present in latest scan
            finding.not_seen_in_latest_scan = False
        else:
            # Not seen in latest scan
            finding.not_seen_in_latest_scan = True
        updated_count += 1
    
    if updated_count > 0:
        db.commit()
        logger.info(
            f"Updated lifecycle for {updated_count} findings after scan {current_scan_id} "
            f"(project {project_id})"
        )
