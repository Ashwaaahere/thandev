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
    
    Uses Redis to track step status:
    - "processing": Step is currently being processed (short TTL, prevents concurrent execution)
    - "completed": Step completed successfully (long TTL, prevents retries)
    
    Args:
        session_id: Session ID
        step_id: Step ID
        
    Returns:
        True if step was already completed, False if new or can retry
    """
    redis_client = get_redis_client()
    # Use composite key: session_id:step_id for uniqueness
    key = f"step:processed:{session_id}:{step_id}"
    
    try:
        # Check if step was already completed
        existing_status = redis_client.get(key)
        if existing_status:
            status = existing_status.decode('utf-8') if isinstance(existing_status, bytes) else existing_status
            if status == "completed":
                logger.warning(
                    f"Step {step_id} for session {session_id} was already completed, "
                    f"skipping duplicate"
                )
                return True
            elif status == "processing":
                # Step is currently processing - check if it's stale
                # TTL returns remaining seconds until expiration
                # If TTL is low (< 5 minutes), the key was set a while ago and might be stale
                ttl = redis_client.ttl(key)
                if ttl > 0 and ttl < 300:  # Less than 5 minutes remaining = processing for 25+ minutes
                    # Key is stale (been processing for 25+ minutes), allow retry
                    logger.warning(
                        f"Step {step_id} for session {session_id} was marked as processing but appears stale "
                        f"(TTL={ttl}s), allowing retry"
                    )
                    redis_client.delete(key)
                    return False
                else:
                    # Step is actively processing (recently set or still has significant TTL), skip
                    logger.info(
                        f"Step {step_id} for session {session_id} is currently processing "
                        f"(TTL={ttl}s), skipping duplicate"
                    )
                    return True
        
        # No existing key or stale processing key - mark as processing and allow execution
        # Use shorter TTL for processing (30 minutes) to allow retry if step crashes
        redis_client.set(key, "processing", ex=1800)  # 30 minute TTL
        logger.debug(f"Step {step_id} for session {session_id} is new, marking as processing")
        return False
            
    except RedisError as e:
        logger.error(
            f"Failed to check idempotency for step {step_id}: {e}", exc_info=True
        )
        # On error, allow execution (fail open, but log warning)
        return False


async def mark_step_completed(session_id: str, step_id: str) -> None:
    """
    Mark a step as completed successfully.
    
    This should be called after a step completes successfully to prevent retries.
    
    Args:
        session_id: Session ID
        step_id: Step ID
    """
    redis_client = get_redis_client()
    key = f"step:processed:{session_id}:{step_id}"
    
    try:
        # Update key to "completed" with longer TTL (24 hours)
        redis_client.set(key, "completed", ex=86400)  # 24 hour TTL
        logger.debug(f"Marked step {step_id} for session {session_id} as completed")
    except RedisError as e:
        logger.error(
            f"Failed to mark step {step_id} as completed: {e}", exc_info=True
        )
        # Non-fatal error, continue

