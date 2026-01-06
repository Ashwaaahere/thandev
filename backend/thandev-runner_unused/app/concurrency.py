"""
Per-session concurrency control for runner workers
Prevents a single session from flooding the worker pool
"""
import logging
from typing import Optional
from redis import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.queue.streams import get_redis_client

logger = logging.getLogger(__name__)


def _session_inflight_key(session_id: str) -> str:
    """Generate Redis key for session inflight counter"""
    return f"session:inflight:{session_id}"


async def acquire_session_slot(session_id: str, max_inflight: Optional[int] = None) -> bool:
    """
    Try to acquire a concurrency slot for a session.
    
    Uses Redis counter to track how many steps are currently in-flight for a session.
    Returns True if slot acquired, False if session is at max capacity.
    
    Args:
        session_id: Session ID
        max_inflight: Maximum concurrent steps for this session (default: from settings)
        
    Returns:
        True if slot acquired, False if session is at capacity
    """
    if max_inflight is None:
        max_inflight = settings.MAX_INFLIGHT_PER_SESSION
    
    redis_client = get_redis_client()
    key = _session_inflight_key(session_id)
    
    try:
        # Use Redis INCR to atomically increment counter
        # If counter doesn't exist, it starts at 0, then INCR makes it 1
        current_count = redis_client.incr(key)
        
        # Set expiration on key (in case we crash, counter will reset)
        redis_client.expire(key, 3600)  # 1 hour TTL
        
        if current_count > max_inflight:
            # We exceeded the limit, decrement back
            redis_client.decr(key)
            logger.debug(
                f"Session {session_id} at capacity ({current_count-1}/{max_inflight}), "
                f"deferring step"
            )
            return False
        
        logger.debug(f"Acquired slot for session {session_id} ({current_count}/{max_inflight})")
        return True
        
    except RedisError as e:
        logger.error(f"Failed to acquire session slot for {session_id}: {e}", exc_info=True)
        # On error, allow execution (fail open)
        return True


async def release_session_slot(session_id: str) -> None:
    """
    Release a concurrency slot for a session.
    
    Args:
        session_id: Session ID
    """
    redis_client = get_redis_client()
    key = _session_inflight_key(session_id)
    
    try:
        current_count = redis_client.decr(key)
        if current_count <= 0:
            # Counter went negative or zero, delete the key
            redis_client.delete(key)
        logger.debug(f"Released slot for session {session_id} (remaining: {max(0, current_count)})")
    except RedisError as e:
        logger.error(f"Failed to release session slot for {session_id}: {e}", exc_info=True)
        # Non-fatal error, continue


async def check_step_idempotency(session_id: str, step_id: str) -> bool:
    """
    Check if a step has already been processed (idempotency check).
    
    Uses Redis SET with expiration to track processed steps.
    
    Args:
        session_id: Session ID
        step_id: Step ID
        
    Returns:
        True if step was already processed, False if new
    """
    redis_client = get_redis_client()
    # Use composite key: session_id:step_id for uniqueness
    key = f"step:processed:{session_id}:{step_id}"
    
    try:
        # Try to set key with NX (only if not exists)
        # Returns True if key was set (new step), False if already exists
        was_set = redis_client.set(key, "1", nx=True, ex=86400)  # 24 hour TTL
        
        if was_set:
            logger.debug(f"Step {step_id} for session {session_id} is new (not duplicate)")
            return False
        else:
            logger.warning(
                f"Step {step_id} for session {session_id} was already processed, "
                f"skipping duplicate"
            )
            return True
            
    except RedisError as e:
        logger.error(
            f"Failed to check idempotency for step {step_id}: {e}", exc_info=True
        )
        # On error, allow execution (fail open, but log warning)
        return False

