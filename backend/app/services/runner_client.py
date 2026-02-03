"""
Runner client for publishing step requests to Redis streams
Used when brain is disabled to route scans through Runner service
"""
import logging
import json
import uuid
import time
from typing import Dict, Any, List, Optional
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.tool_matrix import get_tools_for_level
from app.core.scan_timeouts import get_tool_timeout
from app.models.scan import ScanLevel

logger = logging.getLogger(__name__)

# Stream name (must match runner's expected stream)
STREAM_STEP_REQUESTS = "scan_step_requests"

# Redis client singleton
_redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    """Get or create Redis client singleton"""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def _publish_tools_after_enumeration(
    scan_job_id: str,
    target_url: str,
    scan_level: "ScanLevel",
    tools: List[Dict[str, Any]],
    org_id: Optional[str],
    project_id: Optional[str],
    enumeration_step_id: str,
):
    # Convert scan_level to string for use in timeout lookup
    scan_level_str = scan_level.value if hasattr(scan_level, 'value') else str(scan_level)
    """
    Background task that waits for enumeration to complete, then publishes other tools.
    This ensures scanners can use the enumeration inventory.
    """
    import asyncio
    from app.models.scan_tool_state import ScanToolState
    from app.core.database import SessionLocal
    
    # Convert scan_level to string for use in timeout lookup
    scan_level_str = scan_level.value if hasattr(scan_level, 'value') else str(scan_level)
    
    logger.info(f"[ENUM-WAIT] Starting wait for enumeration completion for scan {scan_job_id}")
    
    max_wait = 180  # 3 minutes max wait
    check_interval = 3  # Check every 3 seconds
    waited = 0
    enumeration_completed = False
    
    try:
        while waited < max_wait:
            await asyncio.sleep(check_interval)
            waited += check_interval
            
            db = SessionLocal()
            try:
                tool_state = db.query(ScanToolState).filter(
                    ScanToolState.scan_id == scan_job_id,
                    ScanToolState.tool == "enumeration"
                ).order_by(ScanToolState.updated_at.desc()).first()
                
                if tool_state and tool_state.stage in ["completed", "failed"]:
                    logger.info(f"[ENUM-WAIT] Enumeration {tool_state.stage} for scan {scan_job_id} after {waited}s")
                    enumeration_completed = True
                    break
            except Exception as db_error:
                logger.warning(f"[ENUM-WAIT] Error checking enumeration status for scan {scan_job_id}: {db_error}")
            finally:
                db.close()
            
            if waited % 15 == 0:
                logger.info(f"[ENUM-WAIT] Still waiting for enumeration for scan {scan_job_id} ({waited}s elapsed)")
        
        if not enumeration_completed:
            logger.warning(f"[ENUM-WAIT] Enumeration did not complete within {max_wait}s for scan {scan_job_id}, publishing tools anyway")
        
        # Now publish all other tools
        logger.info(f"[ENUM-WAIT] Publishing {len(tools)} tools for scan {scan_job_id} after enumeration")
        
        published_count = 0
        failed_count = 0
        for tool_config in tools:
            if not tool_config.get("enabled", True):
                continue
            
            tool_id = tool_config.get("key") or tool_config.get("name")
            if not tool_id:
                logger.warning(f"[ENUM-WAIT] Skipping tool config without tool_id: {tool_config}")
                continue
            
            try:
                # Extract mode_id
                mode_id = None
                if "mode" in tool_config:
                    mode_id = tool_config["mode"]
                elif "profile" in tool_config:
                    mode_id = tool_config["profile"]
                elif "intensity" in tool_config:
                    mode_id = tool_config["intensity"]
                else:
                    default_modes = {
                        "sslscan": "standard",
                        "sqlmap": "sqli_light",
                        "dalfox": "standard",
                        "nmap": "top_ports",
                        "nuclei": "basic_web",
                        "httpx": "low",
                    }
                    mode_id = default_modes.get(tool_id, "standard")
                
                params = tool_config.get("params", {})
                # CRITICAL: Add scan_level to params so tools can use it (especially for inventory waiting)
                params["scan_level"] = scan_level_str
                # CRITICAL: Add timeout_seconds from scan_timeouts configuration
                timeout_seconds = get_tool_timeout(scan_level_str, tool_id)
                params["timeout_seconds"] = timeout_seconds
                logger.info(f"[ENUM-WAIT] Added timeout_seconds={timeout_seconds}s for {tool_id} in {scan_level_str} scan")
                reason = f"Scan level {scan_level.value} requires {tool_id}"
                
                tool_step_id = await publish_step_request(
                    session_id=scan_job_id,
                    tool_id=tool_id,
                    mode_id=mode_id,
                    params=params,
                    target_ref=target_url,
                    depends_on=[enumeration_step_id],
                    reason=reason,
                    org_id=org_id,
                    project_id=project_id,
                    scan_job_id=scan_job_id,
                )
                
                if tool_step_id:
                    published_count += 1
                    logger.info(f"[ENUM-WAIT] Published {tool_id} (step_id={tool_step_id}) for scan {scan_job_id}")
                else:
                    failed_count += 1
                    logger.error(f"[ENUM-WAIT] Failed to publish {tool_id} for scan {scan_job_id} (publish_step_request returned None)")
            except Exception as tool_error:
                failed_count += 1
                logger.error(
                    f"[ENUM-WAIT] Error publishing {tool_id} for scan {scan_job_id}: {tool_error}",
                    exc_info=True
                )
        
        logger.info(
            f"[ENUM-WAIT] Published {published_count} tools for scan {scan_job_id} after enumeration "
            f"(failed: {failed_count}, total: {len(tools)})"
        )
    except Exception as e:
        logger.error(
            f"[ENUM-WAIT] Fatal error in _publish_tools_after_enumeration for scan {scan_job_id}: {e}",
            exc_info=True
        )
        raise  # Re-raise to be caught by wrapper


async def publish_step_request(
    session_id: str,
    tool_id: str,
    mode_id: str,
    params: Dict[str, Any],
    target_ref: str,
    depends_on: List[str],
    reason: str,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    scan_job_id: Optional[str] = None,
) -> bool:
    """
    Publish a step request to the scan_step_requests stream.
    
    Args:
        session_id: Scan session ID (typically scan_job_id)
        tool_id: Tool identifier (e.g., "nuclei", "nmap")
        mode_id: Tool mode (e.g., "nuclei-fast", "nmap-basic")
        params: Tool parameters dict
        target_ref: Target URL
        depends_on: List of step_ids this step depends on
        reason: Why this tool is being run
        org_id: Organization ID (optional)
        project_id: Project ID (optional)
        scan_job_id: Scan job ID (optional)
        
    Returns:
        step_id if published successfully, None otherwise
    """
    redis_client = get_redis_client()
    
    step_id = str(uuid.uuid4())
    
    message = {
        "step_id": step_id,
        "session_id": session_id,
        "tool_id": tool_id,
        "mode_id": mode_id,
        "params": json.dumps(params),
        "target_ref": target_ref,
        "depends_on": json.dumps(depends_on),
        "reason": reason,
        "org_id": org_id or "",
        "project_id": project_id or "",
        "scan_job_id": scan_job_id or "",
    }
    
    try:
        # #region agent log
        import json as json_module
        log_data = {
            "location": "runner_client.py:82",
            "message": "About to publish step request to Redis",
            "data": {
                "step_id": step_id,
                "session_id": session_id,
                "tool_id": tool_id,
                "scan_job_id": scan_job_id or "",
                "stream": STREAM_STEP_REQUESTS,
            },
            "timestamp": int(time.time() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A"
        }
        try:
            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                f.write(json_module.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion
        
        message_id = redis_client.xadd(STREAM_STEP_REQUESTS, message)
        logger.info(
            f"Published step request {step_id} for session {session_id} "
            f"(tool: {tool_id}, message_id: {message_id})"
        )
        
        return step_id  # Return step_id for dependency tracking
        
        # #region agent log
        log_data = {
            "location": "runner_client.py:87",
            "message": "Successfully published step request to Redis",
            "data": {
                "step_id": step_id,
                "session_id": session_id,
                "tool_id": tool_id,
                "message_id": str(message_id),
                "scan_job_id": scan_job_id or "",
            },
            "timestamp": int(time.time() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A"
        }
        try:
            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                f.write(json_module.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion
    except RedisError as e:
        logger.error(f"Failed to publish step request: {e}", exc_info=True)
        
        # #region agent log
        log_data = {
            "location": "runner_client.py:89",
            "message": "Failed to publish step request to Redis",
            "data": {
                "step_id": step_id,
                "session_id": session_id,
                "tool_id": tool_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            "timestamp": int(time.time() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "B"
        }
        try:
            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                f.write(json_module.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion
        
        return None


async def publish_scan_steps_to_runner(
    scan_job_id: str,
    target_url: str,
    scan_level: ScanLevel,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    background_tasks: Optional["BackgroundTasks"] = None,
) -> bool:
    """
    Publish all scan steps to Runner via Redis streams.
    Uses tool_matrix to determine which tools to run for the scan level.
    
    Args:
        scan_job_id: Scan job ID (used as session_id)
        target_url: Target URL to scan
        scan_level: Scan level (basic, pro, advanced)
        org_id: Organization ID (optional)
        project_id: Project ID (optional)
        
    Returns:
        True if all steps published successfully, False otherwise
    """
    logger.info(
        f"[PUBLISH-STEPS] Starting to publish scan steps: "
        f"scan_job_id={scan_job_id}, target_url={target_url}, scan_level={scan_level}, "
        f"org_id={org_id}, project_id={project_id}"
    )
    
    # Test Redis connectivity first
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        logger.info(f"[PUBLISH-STEPS] Redis connectivity test passed for scan {scan_job_id}")
    except Exception as redis_error:
        logger.error(
            f"[PUBLISH-STEPS] Redis connectivity test FAILED for scan {scan_job_id}: {redis_error}",
            exc_info=True
        )
        return False
    
    try:
        # #region agent log
        log_data = {
            "location": "runner_client.py:115",
            "message": "About to publish scan steps to runner",
            "data": {
                "scan_job_id": scan_job_id,
                "target_url": target_url,
                "scan_level": scan_level.value if hasattr(scan_level, 'value') else str(scan_level),
            },
            "timestamp": int(time.time() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A"
        }
        try:
            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion
        
        # Get tools for this scan level
        tools = get_tools_for_level(scan_level)
        
        if not tools:
            logger.warning(f"No tools configured for scan level {scan_level.value}")
            # #region agent log
            log_data = {
                "location": "runner_client.py:119",
                "message": "No tools configured for scan level",
                "data": {
                    "scan_job_id": scan_job_id,
                    "scan_level": scan_level.value if hasattr(scan_level, 'value') else str(scan_level),
                },
                "timestamp": int(time.time() * 1000),
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "A"
            }
            try:
                with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            return False
        
        # Add enumeration step for Pro/Advanced scans (before other tools)
        # Note: enumeration_step_id is used for dependency tracking but runner doesn't
        # check dependencies yet, so we keep this for future use
        enumeration_step_id = None
        scan_level_str = scan_level.value if hasattr(scan_level, 'value') else str(scan_level)
        logger.info(f"[ENUM-CHECK] scan_job_id={scan_job_id}, scan_level={scan_level}, scan_level_str={scan_level_str}, type={type(scan_level)}")
        
        # Check if enumeration is already completed - if so, skip enumeration and publish tools directly
        enumeration_already_complete = False
        if scan_level_str in ['pro', 'advanced']:
            from app.models.scan_tool_state import ScanToolState
            from app.core.database import SessionLocal
            db_check = SessionLocal()
            try:
                enum_state = db_check.query(ScanToolState).filter(
                    ScanToolState.scan_id == scan_job_id,
                    ScanToolState.tool == "enumeration"
                ).order_by(ScanToolState.updated_at.desc()).first()
                
                if enum_state and enum_state.stage == "completed":
                    logger.info(f"[ENUM-CHECK] Enumeration already completed for scan {scan_job_id}, skipping enumeration step and publishing tools directly")
                    enumeration_already_complete = True
            except Exception as check_error:
                logger.warning(f"[ENUM-CHECK] Error checking enumeration status: {check_error}")
            finally:
                db_check.close()
        
        if scan_level_str in ['pro', 'advanced'] and not enumeration_already_complete:
            logger.info(f"Publishing enumeration step for {scan_level_str} scan {scan_job_id}")
            enumeration_step_id = await publish_step_request(
                session_id=scan_job_id,
                tool_id="enumeration",
                mode_id="full",
                params={"scan_level": scan_level_str, "block_other_tools": True},
                target_ref=target_url,
                depends_on=[],  # First step, no dependencies
                reason=f"Asset discovery for {scan_level_str} scan (Katana + GAU + Arjun)",
                org_id=org_id,
                project_id=project_id,
                scan_job_id=scan_job_id,
            )
            if enumeration_step_id:
                logger.info(f"Published enumeration step {enumeration_step_id} for scan {scan_job_id}")
                # Schedule background task to publish other tools after enumeration completes
                import asyncio
                
                async def _publish_tools_wrapper():
                    """Wrapper to ensure background task errors are logged"""
                    try:
                        await _publish_tools_after_enumeration(
                            scan_job_id=scan_job_id,
                            target_url=target_url,
                            scan_level=scan_level,
                            tools=tools,
                            org_id=org_id,
                            project_id=project_id,
                            enumeration_step_id=enumeration_step_id,
                        )
                    except Exception as e:
                        logger.error(
                            f"[ENUM-WAIT] Background task failed for scan {scan_job_id}: {e}",
                            exc_info=True
                        )
                        # Try to publish tools anyway (fallback)
                        try:
                            logger.warning(f"[ENUM-WAIT] Attempting to publish tools without waiting for enumeration for scan {scan_job_id}")
                            from app.services.runner_client import publish_scan_steps_to_runner
                            # Publish tools directly (without enumeration dependency)
                            await publish_scan_steps_to_runner(
                                scan_job_id=scan_job_id,
                                target_url=target_url,
                                scan_level=scan_level,
                                org_id=org_id,
                                project_id=project_id,
                            )
                        except Exception as fallback_error:
                            logger.error(
                                f"[ENUM-WAIT] Fallback publishing also failed for scan {scan_job_id}: {fallback_error}",
                                exc_info=True
                            )
                
                # Use background_tasks if provided (FastAPI), otherwise use asyncio.create_task
                if background_tasks is not None:
                    # FastAPI BackgroundTasks - more reliable
                    background_tasks.add_task(_publish_tools_wrapper)
                    logger.info(f"[PUBLISH-STEPS] Scheduled FastAPI background task to publish tools after enumeration for scan {scan_job_id}")
                else:
                    # Fallback to asyncio.create_task
                    try:
                        task = asyncio.create_task(_publish_tools_wrapper())
                        logger.info(f"[PUBLISH-STEPS] Scheduled asyncio background task to publish tools after enumeration for scan {scan_job_id} (task={task})")
                    except Exception as task_error:
                    logger.error(f"Failed to create background task for scan {scan_job_id}: {task_error}", exc_info=True)
                    # Fallback: Check if enumeration is already complete and publish tools immediately
                    try:
                        from app.models.scan_tool_state import ScanToolState
                        from app.core.database import SessionLocal
                        db = SessionLocal()
                        try:
                            tool_state = db.query(ScanToolState).filter(
                                ScanToolState.scan_id == scan_job_id,
                                ScanToolState.tool == "enumeration"
                            ).order_by(ScanToolState.updated_at.desc()).first()
                            
                            if tool_state and tool_state.stage in ["completed", "failed"]:
                                logger.info(f"[ENUM-WAIT] Enumeration already {tool_state.stage} for scan {scan_job_id}, publishing tools immediately")
                                # Publish tools immediately since enumeration is done
                                await _publish_tools_after_enumeration(
                                    scan_job_id=scan_job_id,
                                    target_url=target_url,
                                    scan_level=scan_level,
                                    tools=tools,
                                    org_id=org_id,
                                    project_id=project_id,
                                    enumeration_step_id=enumeration_step_id,
                                )
                            else:
                                logger.warning(f"[ENUM-WAIT] Enumeration not complete yet for scan {scan_job_id}, will wait in background task")
                        finally:
                            db.close()
                    except Exception as fallback_error:
                        logger.error(f"[ENUM-WAIT] Fallback publishing failed for scan {scan_job_id}: {fallback_error}", exc_info=True)
                
                logger.info(f"[PUBLISH-STEPS] Enumeration step published for scan {scan_job_id}, tools will be published by background task after enumeration completes")
                # Return True to indicate enumeration step was published successfully
                # Tools will be published by background task after enumeration completes
                return True  # Return early - tools will be published by background task
            else:
                logger.warning(f"Failed to publish enumeration step for scan {scan_job_id}, continuing with regular tools")
        elif enumeration_already_complete:
            # Enumeration is already complete, publish tools immediately without waiting
            logger.info(f"[ENUM-CHECK] Enumeration already complete for scan {scan_job_id}, publishing tools immediately")
            try:
                await _publish_tools_after_enumeration(
                    scan_job_id=scan_job_id,
                    target_url=target_url,
                    scan_level=scan_level,
                    tools=tools,
                    org_id=org_id,
                    project_id=project_id,
                    enumeration_step_id="already-complete",  # Dummy ID since enumeration is done
                )
                return True
            except Exception as immediate_error:
                logger.error(f"[ENUM-CHECK] Failed to publish tools immediately for scan {scan_job_id}: {immediate_error}", exc_info=True)
                # Fall through to regular tool publishing
        
        # Publish step request for each enabled tool (only for basic scans or if enumeration failed)
        logger.info(f"[PUBLISH-STEPS] Publishing {len(tools)} tools for scan {scan_job_id} (basic scan or enumeration skipped)")
        published_count = 0
        failed_count = 0
        for tool_config in tools:
            if not tool_config.get("enabled", True):
                continue
            
            tool_id = tool_config.get("key") or tool_config.get("name")
            
            # Extract mode_id from tool_config based on tool-specific fields
            # Different tools use different field names for their mode:
            # - nuclei/nmap: uses "profile" field  
            # - httpx: uses "intensity" field
            # - zap/dalfox: uses "mode" field
            # - sslscan/sqlmap: use default modes
            mode_id = None
            if "mode" in tool_config:
                # ZAP and some tools use explicit "mode" field
                mode_id = tool_config["mode"]
            elif "profile" in tool_config:
                # Nuclei and nmap use "profile" field
                mode_id = tool_config["profile"]
            elif "intensity" in tool_config:
                # Httpx uses "intensity" field
                mode_id = tool_config["intensity"]
            else:
                # Default mode_id for tools without explicit mode
                # Map tool to its standard/default mode based on runner expectations
                default_modes = {
                    "sslscan": "standard",
                    "sqlmap": "sqli_light",
                    "dalfox": "standard",
                    "nmap": "top_ports",
                    "nuclei": "basic_web",
                    "httpx": "low",
                }
                mode_id = default_modes.get(tool_id, "standard")
            
            params = tool_config.get("params", {})
            # CRITICAL: Add scan_level to params so tools can use it (especially for inventory waiting)
            params["scan_level"] = scan_level_str
            # CRITICAL: Add timeout_seconds from scan_timeouts configuration
            timeout_seconds = get_tool_timeout(scan_level_str, tool_id)
            params["timeout_seconds"] = timeout_seconds
            logger.info(f"Added timeout_seconds={timeout_seconds}s for {tool_id} in {scan_level_str} scan")
            reason = f"Scan level {scan_level.value} requires {tool_id}"
            
            # For Pro/Advanced scans, tools depend on enumeration completing first
            depends_on = [enumeration_step_id] if enumeration_step_id else []
            
            tool_step_id = await publish_step_request(
                session_id=scan_job_id,
                tool_id=tool_id,
                mode_id=mode_id,
                params=params,
                target_ref=target_url,
                depends_on=depends_on,
                reason=reason,
                org_id=org_id,
                project_id=project_id,
                scan_job_id=scan_job_id,
            )
            
            if tool_step_id:
                published_count += 1
                if enumeration_step_id:
                    logger.info(f"[PUBLISH-STEPS] Published {tool_id} step {tool_step_id} with dependency on enumeration {enumeration_step_id}")
                else:
                    logger.info(f"[PUBLISH-STEPS] Published {tool_id} step {tool_step_id} for scan {scan_job_id}")
            else:
                failed_count += 1
                logger.error(f"[PUBLISH-STEPS] Failed to publish {tool_id} for scan {scan_job_id} (publish_step_request returned None)")
        
        total_attempted = published_count + failed_count
        logger.info(
            f"[PUBLISH-STEPS] Completed publishing tools for scan {scan_job_id}: "
            f"published={published_count}, failed={failed_count}, total={total_attempted}, "
            f"enumeration={enumeration_step_id or 'skipped'}"
        )
        
        if failed_count > 0:
            logger.warning(
                f"[PUBLISH-STEPS] Some tools failed to publish for scan {scan_job_id}: "
                f"{failed_count} failed out of {total_attempted} total"
        )
        
        # #region agent log
        log_data = {
            "location": "runner_client.py:149",
            "message": "Completed publishing scan steps to runner",
            "data": {
                "scan_job_id": scan_job_id,
                "published_count": published_count,
                "total_tools": len(tools),
            },
            "timestamp": int(time.time() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A"
        }
        try:
            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion
        
        total_attempted = published_count + failed_count if 'failed_count' in locals() else published_count
        failed_count = failed_count if 'failed_count' in locals() else 0
        
        logger.info(
            f"[PUBLISH-STEPS] Completed publishing tools for scan {scan_job_id}: "
            f"published={published_count}, failed={failed_count}, total={total_attempted}, "
            f"enumeration={enumeration_step_id or 'skipped'}"
        )
        
        if failed_count > 0:
            logger.warning(
                f"[PUBLISH-STEPS] Some tools failed to publish for scan {scan_job_id}: "
                f"{failed_count} failed out of {total_attempted} total"
            )
        
        return published_count > 0
        
    except Exception as e:
        logger.error(
            f"[PUBLISH-STEPS] Exception publishing scan steps to Runner for scan {scan_job_id}: {e}",
            exc_info=True
        )
        
        # #region agent log
        log_data = {
            "location": "runner_client.py:155",
            "message": "Exception publishing scan steps to runner",
            "data": {
                "scan_job_id": scan_job_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            "timestamp": int(time.time() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A"
        }
        try:
            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion
        
        return False

