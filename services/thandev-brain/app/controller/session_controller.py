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
        while True:
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
                for step in next_steps:
                    if await publish_step_request(step):
                        step_ids.append(step.step_id)
                        logger.info(f"Enqueued step {step.step_id} ({step.tool_id}/{step.mode_id}) for session {session_id}")
                
                if not step_ids:
                    logger.warning(f"No steps enqueued for session {session_id}")
                    await asyncio.sleep(5)
                    continue
                
                # Wait for results
                logger.info(f"Waiting for {len(step_ids)} step results for session {session_id}")
                try:
                    # IMPORTANT:
                    # A busy/queued runner can legitimately take >10 minutes before it starts consuming
                    # newly enqueued steps (especially with a single runner worker).
                    #
                    # Do NOT mark the session as failed just because no results arrived quickly.
                    # Instead, wait up to the session max runtime budget.
                    results = await read_step_results(
                        session_id,
                        step_ids,
                        timeout_sec=settings.SESSION_MAX_RUNTIME_SEC,
                    )
                except Exception as e:
                    logger.error(f"Failed to read step results for session {session_id}: {e}", exc_info=True)
                    # If we can't read results, mark steps as failed
                    results = {}
                    for step_id in step_ids:
                        from app.queue.streams import StepResult
                        results[step_id] = StepResult(
                            session_id=session_id,
                            step_id=step_id,
                            status="failed",
                            execution_time_sec=0.0,
                            error=f"Failed to read step results: {str(e)}",
                        )
                
                # Check if we got any results
                #
                # If we waited the full session runtime budget and still got nothing, treat as runner down.
                # Otherwise, the scan should remain queued/running elsewhere.
                if not results:
                    error_msg = (
                        f"No step results received for session {session_id} after waiting. "
                        f"Runner service may not be processing requests."
                    )
                    logger.error(error_msg)
                    await stop_session(
                        org_id,
                        project_id,
                        session_id,
                        SessionStatus.FAILED,
                        StopReasonCode.ERROR,
                        error_message=error_msg,
                    )
                    break
                
                # Check if all steps failed (runner might be down)
                all_failed = all(r.status == "failed" for r in results.values())
                if all_failed and len(results) == len(step_ids):
                    # Check if errors indicate runner is down
                    runner_errors = [
                        r.error for r in results.values() 
                        if r.error and ("runner" in r.error.lower() or "timeout" in r.error.lower() or "connection" in r.error.lower())
                    ]
                    if runner_errors:
                        logger.error(
                            f"All steps failed for session {session_id}, runner service appears unavailable. "
                            f"Errors: {runner_errors[:3]}"
                        )
                        # Don't stop immediately - might be temporary, but log the issue
                
                # Update session state (this may stop the session if too many failures)
                session_stopped = False
                try:
                    await update_session_from_results(
                        org_id,
                        project_id,
                        session_id,
                        results,
                    )
                    # Reload session to check if it was stopped
                    updated_session = await get_session(org_id, project_id, session_id)
                    if updated_session and updated_session.status != SessionStatus.RUNNING:
                        session_stopped = True
                        logger.info(f"Session {session_id} was stopped during update (status: {updated_session.status})")
                except Exception as e:
                    logger.error(f"Failed to update session from results: {e}", exc_info=True)
                    # Continue anyway - don't break the loop
                
                if session_stopped:
                    break
                
                # Ingest summaries to RAG
                try:
                    await ingest_step_summaries(
                        org_id,
                        project_id,
                        session_state.scan_job_id,
                        results,
                    )
                except Exception as e:
                    logger.warning(f"Failed to ingest step summaries: {e}", exc_info=True)
                    # Don't break - ingestion failure shouldn't stop the scan
                
            finally:
                await release_session_lock(session_id)
            
            # Small delay between iterations
            await asyncio.sleep(1)
    
    except Exception as e:
        error_msg = f"Session loop error for {session_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        try:
            await stop_session(
                org_id if 'org_id' in locals() else None,
                project_id if 'project_id' in locals() else None,
                session_id,
                SessionStatus.FAILED,
                StopReasonCode.ERROR,
                error_message=error_msg,
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
    # Check max steps
    if session_state.current_step_count >= settings.SESSION_MAX_STEPS:
        return True, StopReasonCode.BUDGET_EXCEEDED
    
    # Check max runtime
    if session_state.total_runtime_sec >= settings.SESSION_MAX_RUNTIME_SEC:
        return True, StopReasonCode.BUDGET_EXCEEDED
    
    # Check no new findings iterations
    if session_state.no_new_findings_iterations >= settings.SESSION_NO_NEW_FINDINGS_ITERATIONS:
        return True, StopReasonCode.DIMINISHING_RETURNS
    
    # Check if session is already stopped
    if session_state.status != SessionStatus.RUNNING:
        return True, session_state.stop_reason_code
    
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
        
        # Convert plan steps to StepRequest objects.
        #
        # IMPORTANT: Do NOT re-enqueue the same tool/mode repeatedly.
        # The StepRequest.step_id is a random UUID, so we track executed tools via
        # session_state.executed_tool_keys (tool_id/mode_id) instead of step ids.
        steps = []
        for plan_step in plan.steps:
            # Prefer tool_id/mode_id, but fall back to tool_id only (runner StepResult includes tool_id today).
            tool_key = f"{plan_step.tool_id}/{plan_step.mode_id}"
            executed_keys = (session_state.executed_tool_keys or [])
            already_executed = (tool_key in executed_keys) or (plan_step.tool_id in executed_keys)
            if already_executed:
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
        
        return steps
        
    except Exception as e:
        logger.error(f"Failed to decide next steps: {e}", exc_info=True)
        return []


async def update_session_from_results(
    org_id: Optional[str],
    project_id: Optional[str],
    session_id: str,
    results: Dict[str, "StepResult"],
) -> None:
    """
    Update session state based on step results.
    """
    if not results:
        return

    # Load current session state once so we can accumulate counters
    session_state = await get_session(org_id, project_id, session_id)
    if not session_state:
        logger.warning(f"Session {session_id} not found while updating from results")
        return

    updates: Dict[str, Any] = {}

    # Track executed step ids and tool keys to avoid re-enqueue loops.
    executed_ids = list(getattr(session_state, "executed_step_ids", []) or [])
    executed_ids.extend([sid for sid in results.keys() if sid])
    updates["executed_step_ids"] = executed_ids

    executed_tool_keys = list(getattr(session_state, "executed_tool_keys", []) or [])
    for r in results.values():
        tool_id = getattr(r, "tool_id", None) or None
        mode_id = getattr(r, "mode_id", None) or None
        if tool_id and mode_id:
            executed_tool_keys.append(f"{tool_id}/{mode_id}")
        elif tool_id:
            executed_tool_keys.append(tool_id)
    # Deduplicate while preserving order
    deduped = []
    seen = set()
    for k in executed_tool_keys:
        if k in seen:
            continue
        seen.add(k)
        deduped.append(k)
    updates["executed_tool_keys"] = deduped

    # Accumulate step count across iterations
    updates["current_step_count"] = session_state.current_step_count + len(results)

    # Accumulate total runtime across all iterations
    batch_runtime = sum(r.execution_time_sec for r in results.values())
    existing_runtime = float(getattr(session_state, "total_runtime_sec", 0.0) or 0.0)
    updates["total_runtime_sec"] = existing_runtime + float(batch_runtime)

    # Consecutive failures: count failed steps in this batch, accumulate if non‑zero, reset on full success.
    # IMPORTANT: Do NOT stop the whole session due to consecutive failures. Runner/tools/network can be flaky,
    # and scan lifecycle is managed by core backend (it can mark the scan FAILED/CANCELLED).
    failures = sum(1 for r in results.values() if r.status != "success")
    if failures > 0:
        new_consecutive_failures = session_state.consecutive_failures + failures
        updates["consecutive_failures"] = new_consecutive_failures
    else:
        updates["consecutive_failures"] = 0

    # No‑new‑findings iterations: increment only when *all* steps succeeded AND produced zero findings.
    # If any step failed, do not treat it as "diminishing returns" (it is likely a transient/tool/network issue).
    total_findings = sum(r.findings_count for r in results.values())
    all_success = all(r.status == "success" for r in results.values())
    if all_success and total_findings == 0:
        updates["no_new_findings_iterations"] = session_state.no_new_findings_iterations + 1
    else:
        updates["no_new_findings_iterations"] = 0

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



