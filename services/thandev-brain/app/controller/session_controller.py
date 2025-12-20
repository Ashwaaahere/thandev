"""
Session controller worker - runs closed-loop scanning
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.session.state import (
    get_session,
    update_session,
    stop_session,
    acquire_session_lock,
    release_session_lock,
)
from app.queue.streams import (
    StepRequest,
    publish_step_request,
    read_step_results,
)
from app.models import SessionStatus, StopReasonCode
from app.core.config import settings
from app.planner.plan import generate_plan
from app.rag.ingestion import ingest_findings_batch
from app.rag.store import get_rag_store

logger = logging.getLogger(__name__)

# Background tasks for session loops
_active_loops: Dict[str, asyncio.Task] = {}


async def trigger_session_loop(session_id: str, org_id: Optional[str] = None, project_id: Optional[str] = None) -> None:
    """
    Trigger a session loop to start processing.
    
    This is called when a session is created. It starts a background task
    that runs the closed-loop scanning logic.
    
    Args:
        session_id: Session ID to process
        org_id: Organization ID (optional, will be loaded from session if not provided)
        project_id: Project ID (optional, will be loaded from session if not provided)
    """
    if session_id in _active_loops:
        logger.warning(f"Session {session_id} loop already running")
        return
    
    # Start background task
    loop = asyncio.get_event_loop()
    task = loop.create_task(run_session_loop(session_id, org_id, project_id))
    _active_loops[session_id] = task
    
    logger.info(f"Started session loop for {session_id}")


async def run_session_loop(session_id: str, org_id: Optional[str] = None, project_id: Optional[str] = None) -> None:
    """
    Main loop for a scan session.
    
    This implements the closed-loop scanning:
    1. Load session state
    2. Check stop conditions
    3. Retrieve RAG evidence
    4. Decide next steps
    5. Enqueue steps
    6. Wait for results
    7. Update state
    8. Ingest summaries to RAG
    9. Repeat
    
    Args:
        session_id: Session ID to process
        org_id: Organization ID (optional, will try to load from session if not provided)
        project_id: Project ID (optional, will try to load from session if not provided)
    """
    try:
        # Try to get session state
        # First try with provided org_id/project_id, then try without (for backward compatibility)
        session_state = None
        if org_id and project_id:
            session_state = await get_session(org_id, project_id, session_id)
        
        # If not found and org_id/project_id not provided, try to find it by scanning
        if not session_state:
            # Try with None (will use "default" key)
            session_state = await get_session(None, None, session_id)
        
        # If still not found, try to find by scanning Redis keys (fallback)
        if not session_state:
            from app.session.state import get_redis_client
            redis_client = get_redis_client()
            # Search for session key pattern
            pattern = f"session:*:*:{session_id}"
            keys = redis_client.keys(pattern)
            if keys:
                # Extract org_id and project_id from key
                key_parts = keys[0].split(":")
                if len(key_parts) >= 4:
                    found_org_id = key_parts[1] if key_parts[1] != "default" else None
                    found_project_id = key_parts[2] if key_parts[2] != "default" else None
                    session_state = await get_session(found_org_id, found_project_id, session_id)
        
        if not session_state:
            logger.error(f"Session {session_id} not found in Redis")
            return
        
        # Use org_id/project_id from session state if not provided
        org_id = org_id or session_state.org_id
        project_id = project_id or session_state.project_id
        
        logger.info(f"Starting session loop for {session_id} (scan_job: {session_state.scan_job_id})")
        
        iteration = 0
        MAX_ITERATIONS = 100  # Failsafe to prevent infinite loops
        while iteration < MAX_ITERATIONS:
            iteration += 1
            logger.info(f"Session {session_id} iteration {iteration}")
            
            # Acquire lock to prevent concurrent processing
            if not await acquire_session_lock(session_id, timeout=60):
                logger.warning(f"Could not acquire lock for session {session_id}, skipping iteration")
                await asyncio.sleep(5)
                continue
            
            try:
                # Reload session state
                session_state = await get_session(org_id, project_id, session_id)
                if not session_state:
                    logger.error(f"Session {session_id} not found or state is malformed")
                    # Mark session as ERROR if state cannot be loaded
                    try:
                        await stop_session(
                            org_id,
                            project_id,
                            session_id,
                            SessionStatus.FAILED,
                            StopReasonCode.ERROR,
                        )
                    except Exception as stop_error:
                        logger.error(f"Failed to stop session after state read failure: {stop_error}")
                    break
                
                # Check stop conditions
                should_stop, reason_code = await check_stop_conditions(session_state)
                if should_stop:
                    logger.info(f"Session {session_id} stopping: {reason_code}")
                    await stop_session(
                        org_id,
                        project_id,
                        session_id,
                        SessionStatus.COMPLETED if reason_code != StopReasonCode.ERROR else SessionStatus.FAILED,
                        reason_code,
                    )
                    break
                
                # Retrieve RAG evidence
                rag_evidence = await retrieve_rag_evidence(
                    session_state.target_url,
                    org_id,
                    project_id,
                    session_state.stack_info if hasattr(session_state, 'stack_info') else {},
                )
                
                # Decide next steps
                next_steps = await decide_next_steps(
                    session_state,
                    rag_evidence,
                )
                
                if not next_steps:
                    logger.info(f"Session {session_id} has no more steps, stopping")
                    await stop_session(
                        org_id,
                        project_id,
                        session_id,
                        SessionStatus.COMPLETED,
                        StopReasonCode.DIMINISHING_RETURNS,
                    )
                    break
                
                # Enqueue steps
                step_ids = []
                step_request_map = {}  # Map step_id -> StepRequest for later lookup
                for step in next_steps:
                    if await publish_step_request(step):
                        step_ids.append(step.step_id)
                        step_request_map[step.step_id] = step  # Store for later lookup
                        logger.info(f"Enqueued step {step.step_id} ({step.tool_id}/{step.mode_id}) for session {session_id}")
                
                if not step_ids:
                    logger.warning(f"No steps enqueued for session {session_id}")
                    await asyncio.sleep(5)
                    continue
                
                # Wait for results
                # Timeout to accommodate tool execution (max 5 minutes per tool, now 300s)
                # Add buffer: 5 min max tool time + 2 min buffer = 7 minutes (420 seconds)
                # This should be sufficient for 300s timeout tools
                logger.info(f"Waiting for {len(step_ids)} step results for session {session_id}")
                results = await read_step_results(session_id, step_ids, timeout_sec=420)
                
                # After reading results, check if session was stopped externally
                # (runner may have skipped steps if session was stopped)
                session_state = await get_session(org_id, project_id, session_id)
                if session_state and session_state.status != SessionStatus.RUNNING:
                    logger.info(f"Session {session_id} was stopped externally (status: {session_state.status}) during result wait")
                    # Create placeholder results for any missing steps
                    # Use stored step_request_map to preserve tool_id and mode_id
                    for step_id in step_ids:
                        if step_id not in results:
                            from app.queue.streams import StepResult
                            step_request = step_request_map.get(step_id)
                            # Preserve tool_id from original step request for proper tracking
                            tool_id = step_request.tool_id if step_request else None
                            results[step_id] = StepResult(
                                session_id=session_id,
                                step_id=step_id,
                                status="failed",
                                execution_time_sec=0.0,
                                findings_count=0,
                                error=f"Step cancelled - session was stopped ({session_state.status.value})",
                                tool_id=tool_id,  # Preserve tool_id for tracking
                            )
                    # Update session state with any results we got before the stop
                    await update_session_from_results(
                        org_id,
                        project_id,
                        session_id,
                        results,
                        step_request_map=step_request_map,  # Use our local map instead of Redis lookup
                    )
                    # Break out of the loop immediately since session is stopped
                    # The stop_reason_code should already be set correctly when the session was stopped
                    logger.info(f"Session {session_id} loop ending due to external stop (status: {session_state.status})")
                    break
                
                # Update session state
                # Pass step_request_map to avoid Redis lookup and ensure accurate tracking
                await update_session_from_results(
                    org_id,
                    project_id,
                    session_id,
                    results,
                    step_request_map=step_request_map,  # Use our local map instead of Redis lookup
                )
                
                # Ingest summaries to RAG
                await ingest_step_summaries(
                    org_id,
                    project_id,
                    session_state.scan_job_id,
                    results,
                )
                
            finally:
                await release_session_lock(session_id)
            
            # Small delay between iterations (reduced for faster processing)
            await asyncio.sleep(0.1)
        
        # If we exit the loop due to max iterations, stop the session
        if iteration >= MAX_ITERATIONS:
            logger.warning(f"Session {session_id} reached maximum iterations ({MAX_ITERATIONS}), stopping")
            try:
                await stop_session(
                    org_id,
                    project_id,
                    session_id,
                    SessionStatus.FAILED,
                    StopReasonCode.BUDGET_EXCEEDED,
                )
            except Exception as stop_error:
                logger.error(f"Failed to stop session after max iterations: {stop_error}")
    
    except Exception as e:
        logger.error(f"Session loop error for {session_id}: {e}", exc_info=True)
        try:
            await stop_session(
                org_id if 'org_id' in locals() else None,
                project_id if 'project_id' in locals() else None,
                session_id,
                SessionStatus.FAILED,
                StopReasonCode.ERROR,
            )
        except:
            pass
    finally:
        # Remove from active loops
        _active_loops.pop(session_id, None)
        logger.info(f"Session loop ended for {session_id}")


async def check_stop_conditions(
    session_state: "SessionState",
) -> tuple[bool, Optional[StopReasonCode]]:
    """
    Check if session should stop based on stop conditions.
    
    Returns:
        Tuple of (should_stop, reason_code)
    """
    # Check if session is already stopped FIRST - this takes priority over other conditions
    # to preserve the original stop reason (e.g., USER_STOPPED, external stop)
    if session_state.status != SessionStatus.RUNNING:
        return True, session_state.stop_reason_code
    
    # Check max steps
    if session_state.current_step_count >= settings.SESSION_MAX_STEPS:
        return True, StopReasonCode.BUDGET_EXCEEDED
    
    # Check max runtime
    if session_state.total_runtime_sec >= settings.SESSION_MAX_RUNTIME_SEC:
        return True, StopReasonCode.BUDGET_EXCEEDED
    
    # Check consecutive failures
    if session_state.consecutive_failures >= settings.SESSION_MAX_CONSECUTIVE_FAILURES:
        return True, StopReasonCode.ERROR
    
    # Check no new findings iterations
    if session_state.no_new_findings_iterations >= settings.SESSION_NO_NEW_FINDINGS_ITERATIONS:
        return True, StopReasonCode.DIMINISHING_RETURNS
    
    return False, None


async def retrieve_rag_evidence(
    target_url: str,
    org_id: Optional[str],
    project_id: Optional[str],
    stack_info: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Retrieve RAG evidence for planning.
    
    Uses the existing query_rag_lanes function from planner.
    """
    try:
        from app.rag.ingestion import query_rag_lanes
        from app.rag.store import get_rag_store
        
        rag_store = get_rag_store()
        query_text = f"security scan findings for {target_url}"
        
        evidence = await query_rag_lanes(
            rag_store=rag_store,
            query_text=query_text,
            org_id=org_id,
            project_id=project_id,
            target=target_url,
            top_k_per_lane=5,
        )
        
        # Add stack_info to evidence for compatibility
        evidence["stack_info"] = stack_info
        
        return evidence
    except Exception as e:
        logger.error(f"Failed to retrieve RAG evidence: {e}", exc_info=True)
        return {}


async def decide_next_steps(
    session_state: "SessionState",
    rag_evidence: Dict[str, Any],
) -> List[StepRequest]:
    """
    Decide next steps based on session state and RAG evidence.
    
    For now, uses the existing generate_plan function, but only generates
    steps that haven't been executed yet. In the future, this will be more
    adaptive based on results.
    """
    try:
        # Generate plan using existing planner
        plan = await generate_plan(
            target_url=session_state.target_url,
            scan_level=session_state.scan_level,
            org_id=session_state.org_id,
            project_id=session_state.project_id,
            stack_info=rag_evidence.get("stack_info", {}),
        )
        
        # Convert plan steps to StepRequest objects
        # Filter out steps that have already been executed using step signatures
        # Since StepRequest generates new UUID step_ids each time, we track by signature
        # (tool_id:mode_id:params_hash) instead
        import json
        import hashlib
        
        executed_signatures = set(session_state.executed_step_ids or [])
        steps = []
        
        for plan_step in plan.steps:
            # Create signature for this plan step based on tool_id, mode_id, and params
            params_json = json.dumps(plan_step.params, sort_keys=True) if plan_step.params else "{}"
            signature = f"{plan_step.tool_id}:{plan_step.mode_id}:{hashlib.md5(params_json.encode()).hexdigest()[:8]}"
            
            # Skip if this signature is already in executed_step_ids
            if signature in executed_signatures:
                logger.debug(f"Skipping already-executed step: {signature} ({plan_step.tool_id}/{plan_step.mode_id})")
                continue
            
            step_request = StepRequest(
                session_id=session_state.session_id,
                tool_id=plan_step.tool_id,
                mode_id=plan_step.mode_id,
                params=plan_step.params,
                target_ref=session_state.target_url,
                depends_on=plan_step.depends_on,
                reason=plan_step.reason,
                org_id=session_state.org_id,
                project_id=session_state.project_id,
                scan_job_id=session_state.scan_job_id,
            )
            steps.append(step_request)
        
        if not steps:
            logger.info(f"All steps have been executed for session {session_state.session_id}")
        
        return steps
        
    except Exception as e:
        logger.error(f"Failed to decide next steps: {e}", exc_info=True)
        return []


async def update_session_from_results(
    org_id: Optional[str],
    project_id: Optional[str],
    session_id: str,
    results: Dict[str, "StepResult"],
    step_request_map: Optional[Dict[str, StepRequest]] = None,
) -> None:
    """
    Update session state based on step results.
    
    Args:
        org_id: Organization ID
        project_id: Project ID
        session_id: Session ID
        results: Dictionary of step_id -> StepResult
        step_request_map: Optional map of step_id -> StepRequest. If provided, uses this
                         instead of looking up from Redis stream. This ensures accurate
                         tracking especially for cancelled steps.
    """
    if not results:
        return

    # Load current session state once so we can accumulate counters
    session_state = await get_session(org_id, project_id, session_id)
    if not session_state:
        logger.warning(f"Session {session_id} not found while updating from results")
        return

    updates: Dict[str, Any] = {}

    # Accumulate step count across iterations
    updates["current_step_count"] = session_state.current_step_count + len(results)

    # Accumulate total runtime across all iterations
    batch_runtime = sum(r.execution_time_sec for r in results.values())
    existing_runtime = float(getattr(session_state, "total_runtime_sec", 0.0) or 0.0)
    updates["total_runtime_sec"] = existing_runtime + float(batch_runtime)

    # Consecutive failures: count failed steps in this batch, accumulate if non‑zero, reset on full success
    failures = sum(1 for r in results.values() if r.status != "success")
    if failures > 0:
        updates["consecutive_failures"] = session_state.consecutive_failures + failures
    else:
        updates["consecutive_failures"] = 0

    # No‑new‑findings iterations: increment only when *all* steps produced zero findings
    total_findings = sum(r.findings_count for r in results.values())
    if total_findings == 0:
        updates["no_new_findings_iterations"] = session_state.no_new_findings_iterations + 1
    else:
        updates["no_new_findings_iterations"] = 0

    # Track executed step signatures for filtering in decide_next_steps()
    # Use step_request_map if provided, otherwise fall back to Redis lookup
    import json
    import hashlib
    from app.session.state import get_redis_client
    from app.queue.streams import STREAM_STEP_REQUESTS
    
    executed_signatures = list(session_state.executed_step_ids or [])
    
    # Build step request data map
    step_request_data_map = {}
    
    if step_request_map:
        # Use provided step_request_map (more reliable, especially for cancelled steps)
        for step_id, step_request in step_request_map.items():
            if step_id in results:
                step_request_data_map[step_id] = {
                    "mode_id": step_request.mode_id,
                    "params": step_request.params,
                    "tool_id": step_request.tool_id,
                }
    else:
        # Fallback: lookup from Redis stream
        redis_client = get_redis_client()
        step_ids_to_lookup = [step_result.step_id for step_result in results.values()]
        
        try:
            stream_data = redis_client.xrevrange(STREAM_STEP_REQUESTS, count=5000)
            for msg_id, msg_data in stream_data:
                step_id = msg_data.get("step_id")
                if step_id in step_ids_to_lookup and step_id not in step_request_data_map:
                    step_request_data_map[step_id] = msg_data
        except Exception as e:
            logger.warning(f"Failed to read step requests from stream: {e}", exc_info=True)
    
    for step_result in results.values():
        # Get step request data (mode_id and params) to create signature
        try:
            step_data = step_request_data_map.get(step_result.step_id)
            
            if step_data:
                # Extract mode_id and params
                if isinstance(step_data, dict) and "mode_id" in step_data:
                    # From step_request_map (StepRequest object converted to dict)
                    mode_id = step_data.get("mode_id")
                    params = step_data.get("params", {})
                    tool_id = step_data.get("tool_id") or step_result.tool_id
                else:
                    # From Redis stream (string format)
                    mode_id = step_data.get("mode_id")
                    params_str = step_data.get("params", "{}")
                    try:
                        params = json.loads(params_str) if params_str else {}
                    except json.JSONDecodeError:
                        params = {}
                    tool_id = step_result.tool_id
                
                # Create signature (same format as in decide_next_steps)
                if mode_id and tool_id:
                    params_json = json.dumps(params, sort_keys=True) if params else "{}"
                    signature = f"{tool_id}:{mode_id}:{hashlib.md5(params_json.encode()).hexdigest()[:8]}"
                    
                    # Add signature if not already in list
                    if signature not in executed_signatures:
                        executed_signatures.append(signature)
                        logger.info(f"Tracked executed step signature: {signature} (step_id: {step_result.step_id}, tool: {tool_id}, mode: {mode_id})")
                    else:
                        logger.debug(f"Signature already tracked: {signature} (step_id: {step_result.step_id})")
                else:
                    logger.warning(f"Missing tool_id or mode_id for step {step_result.step_id}: tool_id={tool_id}, mode_id={mode_id}")
            else:
                logger.warning(f"Original step request not found for step_id {step_result.step_id}. Cannot track signature precisely.")
                # Fallback: use tool_id only (less precise but prevents some duplicates)
                if step_result.tool_id:
                    # Use a generic signature that will prevent re-execution of the same tool
                    # This is a fallback, so we'll be more conservative
                    signature = f"{step_result.tool_id}:*:*"
                    if signature not in executed_signatures:
                        # Only add if we don't already have any signature for this tool
                        tool_has_signature = any(sig.startswith(f"{step_result.tool_id}:") for sig in executed_signatures)
                        if not tool_has_signature:
                            executed_signatures.append(signature)
                            logger.info(f"Tracked fallback signature: {signature} (step_id: {step_result.step_id})")
        except Exception as e:
            logger.warning(f"Failed to create signature for step {step_result.step_id}: {e}", exc_info=True)
    
    if executed_signatures != (session_state.executed_step_ids or []):
        updates["executed_step_ids"] = executed_signatures
        logger.info(f"Updated executed_step_ids: {len(executed_signatures)} signatures tracked for session {session_id}")

    await update_session(org_id, project_id, session_id, updates)


async def ingest_step_summaries(
    org_id: Optional[str],
    project_id: Optional[str],
    scan_job_id: str,
    results: Dict[str, "StepResult"],
) -> None:
    """
    Ingest step summaries into RAG.
    """
    try:
        rag_store = get_rag_store()
        
        # Create summaries from results
        findings = []
        for step_result in results.values():
            if step_result.findings_count > 0:
                # Create a summary finding
                findings.append({
                    "id": f"summary_{step_result.step_id}",
                    "title": f"Step {step_result.step_id} completed",
                    "description": f"Tool execution completed with {step_result.findings_count} findings",
                    "severity": "info",
                    "tool_id": step_result.tool_id or "summary",
                    "tool_name": step_result.tool_id or "summary",
                    "org_id": org_id,
                    "project_id": project_id,
                })
        
        if findings:
            await ingest_findings_batch(
                rag_store=rag_store,
                findings=findings,
            )
            logger.info(f"Ingested {len(findings)} step summaries into RAG for scan_job {scan_job_id}")
    except Exception as e:
        logger.error(f"Failed to ingest step summaries: {e}", exc_info=True)



