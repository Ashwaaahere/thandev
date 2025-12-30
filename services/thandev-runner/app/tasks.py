"""
Celery tasks for step execution
"""
import logging
import asyncio
import json
import time
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
    
    # Check if scan is still active (skip if cancelled or completed)
    if scan_job_id:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            import os
            from pathlib import Path
            
            # Create a database connection to check scan status
            # Fix SQLite relative paths
            database_url = settings.DATABASE_URL
            if database_url.startswith("sqlite:///./"):
                repo_root = Path(__file__).parent.parent.parent.parent
                db_file = database_url.replace("sqlite:///./", "")
                absolute_path = repo_root / db_file
                database_url = f"sqlite:///{absolute_path}"
            elif database_url.startswith("sqlite:///") and not os.path.isabs(database_url.replace("sqlite:///", "")):
                repo_root = Path(__file__).parent.parent.parent.parent
                db_path = database_url.replace("sqlite:///", "")
                absolute_path = repo_root / db_path
                database_url = f"sqlite:///{absolute_path}"
            
            connect_args = {}
            if database_url.startswith("sqlite"):
                connect_args = {"check_same_thread": False}
            
            engine = create_engine(database_url, connect_args=connect_args)
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            
            try:
                # Import ScanJob model (need to add backend to path)
                import sys
                import os
                from pathlib import Path
                
                # Get backend path - runner is in services/thandev-runner, backend is at repo root
                runner_path = Path(__file__).parent.parent.parent.parent
                backend_path = runner_path / "backend"
                
                # Ensure backend is in path and change to backend directory for imports
                if str(backend_path) not in sys.path:
                    sys.path.insert(0, str(backend_path))
                
                # Change working directory to backend for relative imports (only if it exists)
                original_cwd = os.getcwd()
                backend_path_str = str(backend_path)
                try:
                    if os.path.exists(backend_path_str) and os.path.isdir(backend_path_str):
                        os.chdir(backend_path_str)
                    else:
                        logger.warning(f"Backend path {backend_path_str} does not exist. Skipping chdir. Proceeding with imports from sys.path.")

                    from app.models.scan import ScanJob, ScanStatus

                    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
                    if scan_job and scan_job.status in (
                        ScanStatus.CANCELLED,
                        ScanStatus.COMPLETED,
                        ScanStatus.FAILED,
                    ):
                        logger.info(
                            f"Skipping step {step_id} for scan {scan_job_id} - scan status is {scan_job.status.value}"
                        )
                        await ack_step_request(settings.CONSUMER_GROUP, message_id)
                        return

                except Exception as e:
                    logger.warning(
                        f"Failed to check scan status for {scan_job_id}: {e}. Proceeding anyway.",
                        exc_info=True,
                    )
                finally:
                    os.chdir(original_cwd)
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to check scan status for {scan_job_id}: {e}. Proceeding anyway.", exc_info=True)
    
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
            # Create job directory - use backend's data/jobs directory
            repo_root = Path(__file__).parent.parent.parent.parent
            if scan_job_id:
                job_dir = repo_root / "backend" / "data" / "jobs" / scan_job_id
            else:
                job_dir = repo_root / "backend" / "data" / "jobs" / session_id
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
        
        # Save ToolResult to database (always, even if tool failed)
        # and ingest findings if successful
        findings_count = 0
        if scan_job_id:
            # #region agent log
            log_data = {
                "location": "tasks.py:310",
                "message": "About to create ToolResult record",
                "data": {
                    "scan_job_id": scan_job_id,
                    "tool_id": tool_id,
                    "tool_name": result.get("tool_name"),
                    "success": result.get("success"),
                    "exit_code": result.get("exit_code"),
                },
                "timestamp": int(time.time() * 1000),
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "C"
            }
            try:
                with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            try:
                # Get database session
                from app.database import get_db_session
                db = get_db_session()
                
                # #region agent log
                log_data = {
                    "location": "tasks.py:315",
                    "message": "Got database session",
                    "data": {
                        "scan_job_id": scan_job_id,
                        "db_session_exists": db is not None,
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "C"
                }
                try:
                    with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                        f.write(json.dumps(log_data) + "\n")
                except Exception:
                    pass
                # #endregion
                
                try:
                    # Import ToolResult model from backend
                    from app.backend_imports import ensure_backend_in_path
                    ensure_backend_in_path()
                    from app.models.finding import ToolResult
                    
                    # Parse tool output to get findings
                    tool_name = result.get("tool_name", tool_id)
                    
                    # Create ToolResult record (always save, even if tool failed)
                    # Use actual exit_code from result, default based on success
                    actual_exit_code = result.get("exit_code")
                    if actual_exit_code is None:
                        actual_exit_code = 0 if result.get("success", False) else -1
                    
                    # #region agent log
                    log_data = {
                        "location": "tasks.py:330",
                        "message": "Creating ToolResult object",
                        "data": {
                            "scan_job_id": scan_job_id,
                            "tool_name": tool_name,
                            "exit_code": actual_exit_code,
                            "execution_time": result.get("execution_time", execution_time),
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "C"
                    }
                    try:
                        with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                            f.write(json.dumps(log_data) + "\n")
                    except Exception:
                        pass
                    # #endregion
                    
                    skip_reason = result.get("skip_reason") if result else None
                    # Dalfox-specific skip reasons
                    if not skip_reason and tool_name and "dalfox" in tool_name.lower():
                        meta = result.get("meta") if result else {}
                        if meta:
                            if meta.get("skip_reason"):
                                skip_reason = meta.get("skip_reason")
                            elif meta.get("no_injection_points"):
                                skip_reason = "no_injection_points"
                            elif meta.get("blocked"):
                                skip_reason = "blocked"
                        if not skip_reason and actual_exit_code == 429:
                            skip_reason = "rate_limited"
                        if not skip_reason and not result.get("output"):
                            skip_reason = "no_output"
                    tool_result = ToolResult(
                        scan_job_id=scan_job_id,
                        tool_name=tool_name,
                        output=result.get("output", "")[:10000] if result.get("output") else "",  # Truncate large outputs
                        exit_code=actual_exit_code,
                        execution_time=result.get("execution_time", execution_time),
                        command=result.get("command", ""),
                        error_message=result.get("error"),
                        timed_out=1 if result.get("timed_out", False) else 0,
                        stdout_preview=(result.get("stdout") or "")[:1000] if result else None,
                        stderr_preview=(result.get("stderr") or "")[:1000] if result else None,
                        raw_stdout=result.get("stdout") if result else None,
                        raw_stderr=result.get("stderr") if result else None,
                        skip_reason=skip_reason,
                    )
                    db.add(tool_result)
                    
                    # #region agent log
                    log_data = {
                        "location": "tasks.py:341",
                        "message": "Added ToolResult to session, about to commit",
                        "data": {
                            "scan_job_id": scan_job_id,
                            "tool_name": tool_name,
                            "tool_result_id": tool_result.id,
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "C"
                    }
                    try:
                        with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                            f.write(json.dumps(log_data) + "\n")
                    except Exception:
                        pass
                    # #endregion
                    
                    db.commit()
                    
                    # #region agent log
                    log_data = {
                        "location": "tasks.py:342",
                        "message": "ToolResult committed successfully",
                        "data": {
                            "scan_job_id": scan_job_id,
                            "tool_name": tool_name,
                            "tool_result_id": tool_result.id,
                            "exit_code": tool_result.exit_code,
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "C"
                    }
                    try:
                        with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                            f.write(json.dumps(log_data) + "\n")
                    except Exception:
                        pass
                    # #endregion
                    
                    logger.info(f"Saved ToolResult for {tool_name} (scan {scan_job_id}, exit_code={tool_result.exit_code})")
                    
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
                    # materialize the output to a file so existing parsers can operate on it.
                    if output_file and not output_file.exists() and result.get("output"):
                        try:
                            output_file.parent.mkdir(parents=True, exist_ok=True)
                            output_text = result.get("output") or ""
                            
                            # Normalize Dalfox output: convert placeholder outputs to empty array
                            # This must happen BEFORE writing to file so parsers get normalized data
                            # Check both tool_name and tool_id to handle formats like "tool-dalfox-v2"
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
                                f"Failed to materialize output file for {tool_name}: {write_err}",
                                exc_info=True,
                            )
                    
                except Exception as tool_result_error:
                    # #region agent log
                    log_data = {
                        "location": "tasks.py:315",
                        "message": "Exception creating ToolResult",
                        "data": {
                            "scan_job_id": scan_job_id,
                            "tool_name": tool_name if 'tool_name' in locals() else "unknown",
                            "error_type": type(tool_result_error).__name__,
                            "error_message": str(tool_result_error),
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "C"
                    }
                    try:
                        with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                            f.write(json.dumps(log_data) + "\n")
                    except Exception:
                        pass
                    # #endregion
                    logger.error(f"Failed to create ToolResult for {tool_name}: {tool_result_error}", exc_info=True)
                finally:
                    db.close()
            except Exception as db_error:
                # #region agent log
                log_data = {
                    "location": "tasks.py:312",
                    "message": "Exception getting database session",
                    "data": {
                        "scan_job_id": scan_job_id,
                        "error_type": type(db_error).__name__,
                        "error_message": str(db_error),
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "C"
                }
                try:
                    with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                        f.write(json.dumps(log_data) + "\n")
                except Exception:
                    pass
                # #endregion
                logger.error(f"Failed to get database session for ToolResult: {db_error}", exc_info=True)
        
        # Determine output file path (may be from artifact_refs for remote backend)
        output_file = None
        if scan_job_id:
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

            # Import parsers from backend
            from app.backend_imports import ensure_backend_in_path
            ensure_backend_in_path()
            
            from app.services.findings_ingestor import (
                parse_nuclei_output,
                parse_nmap_output,
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
            
            baseline_filter = result.get("baseline")  # For ffuf
        
        # Only ingest findings if tool was successful
        if scan_job_id and result.get("success") and output_file and output_file.exists():
            try:
                # Get database session for findings ingestion
                from app.database import get_db_session
                db = get_db_session()
                
                tool_name = result.get("tool_name", tool_id)
                if tool_name == "nuclei":
                    findings = parse_nuclei_output(output_file)
                    ingested = ingest_nuclei_findings(db, scan_job_id, findings)
                    findings_count = len(ingested or [])
                elif tool_name == "nmap":
                    findings = parse_nmap_output(output_file)
                    ingested = ingest_nmap_findings(db, scan_job_id, findings)
                    findings_count = len(ingested or [])
                elif tool_name == "sslscan":
                    findings = parse_sslscan_output(output_file)
                    ingested = ingest_sslscan_findings(db, scan_job_id, findings)
                    findings_count = len(ingested or [])
                elif tool_name == "httpx":
                    findings = parse_httpx_output(output_file)
                    ingested = ingest_httpx_findings(db, scan_job_id, findings)
                    findings_count = len(ingested or [])
                elif tool_name == "ffuf":
                    findings = parse_ffuf_output(output_file, baseline_filter=baseline_filter)
                    ingested = ingest_ffuf_findings(db, scan_job_id, findings)
                    findings_count = len(ingested or [])
                elif tool_name == "dalfox":
                    findings = parse_dalfox_output(output_file)
                    ingested = ingest_dalfox_findings(db, scan_job_id, findings)
                    findings_count = len(ingested or [])
                elif tool_name == "sqlmap":
                    # sqlmap outputs to a directory, not a single file
                    # Also parse stdout for detection results (sqlmap outputs to stdout)
                    from app.services.findings_ingestor import parse_sqlmap_stdout
                    
                    sqlmap_findings = []
                    
                    # Determine sqlmap output directory - use same job_dir as other tools
                    # SQLMap creates: job_dir/sqlmap/
                    sqlmap_output_dir = output_file.parent / "sqlmap"
                    
                    logger.info(
                        f"SQLMap ingestion for step {step_id}: "
                        f"sqlmap_output_dir={sqlmap_output_dir}, "
                        f"exists={sqlmap_output_dir.exists()}, "
                        f"stdout_length={len(result.get('output', ''))}"
                    )
                    
                    # First, try to parse filesystem artifacts (most reliable)
                    artifacts_found = False
                    if sqlmap_output_dir.exists() and sqlmap_output_dir.is_dir():
                        dir_findings = parse_sqlmap_output(sqlmap_output_dir)
                        if dir_findings:
                            logger.info(f"Parsed {len(dir_findings)} sqlmap findings from output directory for step {step_id}")
                            sqlmap_findings.extend(dir_findings)
                            artifacts_found = True
                        else:
                            # Check if directory has any files (for logging)
                            any_files = list(sqlmap_output_dir.rglob("*"))
                            logger.debug(f"SQLMap output directory exists but no findings parsed. Files found: {len(any_files)}")
                    
                    # Fallback: parse stdout if no artifacts found or artifacts had no findings
                    if not artifacts_found or not sqlmap_findings:
                        if result.get("output"):
                            stdout_findings = parse_sqlmap_stdout(result.get("output"), target_ref or "")
                            if stdout_findings:
                                logger.info(f"Parsed {len(stdout_findings)} sqlmap findings from stdout for step {step_id}")
                                # Deduplicate: only add findings not already in artifacts
                                existing_params = {(f.get("parameter", ""), f.get("technique", "")) for f in sqlmap_findings}
                                for finding in stdout_findings:
                                    key = (finding.get("parameter", ""), finding.get("technique", ""))
                                    if key not in existing_params:
                                        sqlmap_findings.append(finding)
                                        existing_params.add(key)
                    
                    # Ingest findings (always call, even if empty list)
                    ingested = ingest_sqlmap_findings(db, scan_job_id, sqlmap_findings)
                    findings_count = len(ingested or [])
                    
                    if findings_count > 0:
                        logger.info(
                            f"Ingested {findings_count} sqlmap findings for step {step_id} "
                            f"(from artifacts: {artifacts_found}, from stdout: {len(result.get('output', '')) > 0})"
                        )
                    else:
                                logger.info(
                                    f"No sqlmap findings for step {step_id} "
                                    f"(output_dir exists: {sqlmap_output_dir.exists()}, "
                                    f"stdout length: {len(result.get('output', ''))})"
                                )
            except Exception as e:
                logger.error(f"Failed to ingest findings for step {step_id}: {e}", exc_info=True)
                # Continue - findings ingestion failure shouldn't fail the step
            finally:
                db.close()
        
        # Publish result
        # Get output_file path (may not exist if execution failed)
        output_file_path = None
        if result.get("success"):
            tool_name = result.get("tool_name", tool_id)
            if use_new_backend and execution_result and execution_result.artifact_refs:
                output_file_path = execution_result.artifact_refs[0]
            else:
                # Legacy: use local job_dir - use backend's data/jobs directory
                repo_root = Path(__file__).parent.parent.parent.parent
                if scan_job_id:
                    job_dir = repo_root / "backend" / "data" / "jobs" / scan_job_id
                else:
                    job_dir = repo_root / "backend" / "data" / "jobs" / session_id
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
    
    # #region agent log
    log_data = {
        "location": "tasks.py:785",
        "message": "Runner worker loop started",
        "data": {
            "consumer_group": settings.CONSUMER_GROUP,
            "consumer_name": settings.CONSUMER_NAME,
            "redis_url": getattr(settings, 'REDIS_URL', 'not_set'),
        },
        "timestamp": int(time.time() * 1000),
        "sessionId": "debug-session",
        "runId": "run1",
        "hypothesisId": "C"
    }
    try:
        with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
            f.write(json.dumps(log_data) + "\n")
    except Exception:
        pass
    # #endregion
    
    # Track if this is the first iteration (to check for pending messages on startup)
    first_iteration = True
    
    while True:
        try:
            # Consume step requests
            logger.debug(f"Waiting for step requests from stream {settings.CONSUMER_GROUP}...")
            
            # #region agent log
            log_data = {
                "location": "tasks.py:815",
                "message": "About to consume step requests from Redis",
                "data": {
                    "consumer_group": settings.CONSUMER_GROUP,
                    "consumer_name": settings.CONSUMER_NAME,
                    "block_ms": 1000,
                },
                "timestamp": int(time.time() * 1000),
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "C"
            }
            try:
                with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            
            messages = await consume_step_requests(
                consumer_group=settings.CONSUMER_GROUP,
                consumer_name=settings.CONSUMER_NAME,
                count=settings.MAX_CONCURRENT_STEPS,
                block_ms=1000,
                check_pending=first_iteration,  # Only check pending on first iteration (startup)
            )
            first_iteration = False  # After first iteration, don't check pending anymore
            
            # #region agent log
            log_data = {
                "location": "tasks.py:801",
                "message": "Received messages from Redis",
                "data": {
                    "message_count": len(messages) if messages else 0,
                    "has_messages": bool(messages),
                },
                "timestamp": int(time.time() * 1000),
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "C"
            }
            try:
                with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            
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
            try:
                with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            
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
                
                # #region agent log
                log_data = {
                    "location": "tasks.py:886",
                    "message": "Completed processing step requests",
                    "data": {
                        "task_count": len(tasks),
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "D"
                }
                try:
                    with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                        f.write(json.dumps(log_data) + "\n")
                except Exception:
                    pass
                # #endregion
        
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

