"""
Session state management using Redis
"""
import logging
import json
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.models import SessionState, SessionStatus, StopReasonCode

logger = logging.getLogger(__name__)

# Redis client singleton
_redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    """Get or create Redis client singleton"""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _redis_client


def _session_key(org_id: Optional[str], project_id: Optional[str], session_id: str) -> str:
    """Generate Redis key for session state"""
    # Use placeholder if org_id/project_id not provided
    org_part = org_id or "default"
    project_part = project_id or "default"
    return f"session:{org_part}:{project_part}:{session_id}"


def _lock_key(session_id: str) -> str:
    """Generate Redis key for session lock"""
    return f"lock:session:{session_id}"


async def create_session(
    scan_job_id: str,
    target_url: str,
    scan_level: str,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    stack_info: Optional[Dict[str, Any]] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> SessionState:
    """
    Create a new scan session and store state in Redis.
    
    Args:
        scan_job_id: Scan job ID from core
        target_url: Target URL to scan
        scan_level: Scan level (basic, pro, advanced)
        org_id: Organization ID
        project_id: Project ID
        stack_info: Target stack information
        policy: Scan policy (max_steps, max_runtime, etc.)
        
    Returns:
        SessionState instance
        
    Raises:
        RedisError: If Redis operation fails
    """
    session_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    # Extract policy limits
    max_steps = (policy or {}).get("max_steps", settings.SESSION_MAX_STEPS)
    max_runtime = (policy or {}).get("max_runtime_sec", settings.SESSION_MAX_RUNTIME_SEC)
    
    state = SessionState(
        session_id=session_id,
        scan_job_id=scan_job_id,
        org_id=org_id,
        project_id=project_id,
        target_url=target_url,
        scan_level=scan_level,
        status=SessionStatus.RUNNING,
        current_step_count=0,
        total_runtime_sec=0.0,
        consecutive_failures=0,
        no_new_findings_iterations=0,
        created_at=now,
        last_updated=now,
    )
    
    # Store in Redis with TTL
    redis_client = get_redis_client()
    key = _session_key(org_id, project_id, session_id)
    
    try:
        # Serialize state to JSON
        state_dict = state.model_dump(mode="json")
        # Convert datetime to ISO format strings
        state_dict["created_at"] = state.created_at.isoformat()
        state_dict["last_updated"] = state.last_updated.isoformat()
        state_dict["status"] = state.status.value
        if state.stop_reason_code:
            state_dict["stop_reason_code"] = state.stop_reason_code.value
        
        redis_client.setex(
            key,
            settings.REDIS_SESSION_TTL_SEC,
            json.dumps(state_dict),
        )
        
        logger.info(f"Created session {session_id} for scan_job {scan_job_id}")
        return state
        
    except RedisError as e:
        logger.error(f"Failed to create session in Redis: {e}", exc_info=True)
        raise


async def get_session(
    org_id: Optional[str],
    project_id: Optional[str],
    session_id: str,
) -> Optional[SessionState]:
    """
    Get session state from Redis.
    
    Args:
        org_id: Organization ID
        project_id: Project ID
        session_id: Session ID
        
    Returns:
        SessionState if found, None otherwise
    """
    redis_client = get_redis_client()
    key = _session_key(org_id, project_id, session_id)
    
    try:
        data = redis_client.get(key)
        if not data:
            return None
        
        state_dict = json.loads(data)
        
        # Parse datetime strings
        state_dict["created_at"] = datetime.fromisoformat(state_dict["created_at"])
        state_dict["last_updated"] = datetime.fromisoformat(state_dict["last_updated"])
        state_dict["status"] = SessionStatus(state_dict["status"])
        if state_dict.get("stop_reason_code"):
            state_dict["stop_reason_code"] = StopReasonCode(state_dict["stop_reason_code"])
        
        return SessionState(**state_dict)
        
    except (RedisError, json.JSONDecodeError, KeyError, ValueError) as e:
        # Log validation errors with more detail
        if "ValidationError" in str(type(e)) or "validation" in str(e).lower():
            logger.error(
                f"Session state validation failed for {session_id}: {e}. "
                f"This may indicate a schema mismatch. State dict keys: {list(state_dict.keys()) if 'state_dict' in locals() else 'N/A'}"
            )
        else:
            logger.error(f"Failed to get session from Redis: {e}", exc_info=True)
        return None
    except Exception as e:
        # Catch any other exceptions (including Pydantic ValidationError)
        logger.error(f"Unexpected error loading session {session_id}: {e}", exc_info=True)
        return None


async def update_session(
    org_id: Optional[str],
    project_id: Optional[str],
    session_id: str,
    updates: Dict[str, Any],
) -> bool:
    """
    Update session state in Redis.
    
    Args:
        org_id: Organization ID
        project_id: Project ID
        session_id: Session ID
        updates: Dictionary of fields to update
        
    Returns:
        True if updated successfully, False otherwise
    """
    redis_client = get_redis_client()
    key = _session_key(org_id, project_id, session_id)
    
    try:
        # Get current state
        data = redis_client.get(key)
        if not data:
            logger.warning(f"Session {session_id} not found for update")
            return False
        
        state_dict = json.loads(data)
        
        # Apply updates
        state_dict.update(updates)
        state_dict["last_updated"] = datetime.utcnow().isoformat()
        
        # Preserve TTL
        ttl = redis_client.ttl(key)
        if ttl > 0:
            redis_client.setex(key, ttl, json.dumps(state_dict))
        else:
            redis_client.setex(key, settings.REDIS_SESSION_TTL_SEC, json.dumps(state_dict))
        
        logger.debug(f"Updated session {session_id}")
        return True
        
    except (RedisError, json.JSONDecodeError) as e:
        logger.error(f"Failed to update session in Redis: {e}", exc_info=True)
        return False


async def stop_session(
    org_id: Optional[str],
    project_id: Optional[str],
    session_id: str,
    status: SessionStatus,
    stop_reason_code: Optional[StopReasonCode] = None,
    error_message: Optional[str] = None,
) -> bool:
    """
    Stop a session and update its status.
    
    Args:
        org_id: Organization ID
        project_id: Project ID
        session_id: Session ID
        status: Final status (COMPLETED, FAILED, or STOPPED)
        stop_reason_code: Reason for stopping
        error_message: Error message if session failed
        
    Returns:
        True if stopped successfully, False otherwise
    """
    updates = {
        "status": status.value,
        "last_updated": datetime.utcnow().isoformat(),
    }
    if stop_reason_code:
        updates["stop_reason_code"] = stop_reason_code.value
    if error_message:
        updates["error_message"] = error_message
    
    return await update_session(org_id, project_id, session_id, updates)


async def acquire_session_lock(session_id: str, timeout: int = 30) -> bool:
    """
    Acquire a lock for a session to prevent concurrent processing.
    
    Args:
        session_id: Session ID
        timeout: Lock timeout in seconds
        
    Returns:
        True if lock acquired, False otherwise
    """
    redis_client = get_redis_client()
    lock_key = _lock_key(session_id)
    
    try:
        # Try to acquire lock (SETNX with expiration)
        acquired = redis_client.set(lock_key, "locked", nx=True, ex=timeout)
        return bool(acquired)
    except RedisError as e:
        logger.error(f"Failed to acquire lock for session {session_id}: {e}", exc_info=True)
        return False


async def release_session_lock(session_id: str) -> bool:
    """
    Release a session lock.
    
    Args:
        session_id: Session ID
        
    Returns:
        True if released successfully, False otherwise
    """
    redis_client = get_redis_client()
    lock_key = _lock_key(session_id)
    
    try:
        redis_client.delete(lock_key)
        return True
    except RedisError as e:
        logger.error(f"Failed to release lock for session {session_id}: {e}", exc_info=True)
        return False



