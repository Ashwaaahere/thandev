"""
Runner client for publishing step requests to Redis streams
Used when brain is disabled to route scans through Runner service
"""
import logging
import json
import uuid
from typing import Dict, Any, List, Optional
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.tool_matrix import get_tools_for_level
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
        True if published successfully, False otherwise
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
            import time
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
        
        return True
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
        
        return False


async def publish_scan_steps_to_runner(
    scan_job_id: str,
    target_url: str,
    scan_level: ScanLevel,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
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
        
        # Publish step request for each enabled tool
        published_count = 0
        for tool_config in tools:
            if not tool_config.get("enabled", True):
                continue
            
            tool_id = tool_config.get("key") or tool_config.get("name")
            mode_id = tool_config.get("mode", f"{tool_id}-default")
            params = tool_config.get("params", {})
            reason = f"Scan level {scan_level.value} requires {tool_id}"
            
            success = await publish_step_request(
                session_id=scan_job_id,
                tool_id=tool_id,
                mode_id=mode_id,
                params=params,
                target_ref=target_url,
                depends_on=[],  # No dependencies for simple tool matrix
                reason=reason,
                org_id=org_id,
                project_id=project_id,
                scan_job_id=scan_job_id,
            )
            
            if success:
                published_count += 1
        
        logger.info(
            f"Published {published_count} step requests to Runner for scan {scan_job_id}"
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
        
        return published_count > 0
        
    except Exception as e:
        logger.error(f"Failed to publish scan steps to Runner: {e}", exc_info=True)
        
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

