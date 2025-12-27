"""
Redis Streams for scan step requests and results
"""
import logging
import json
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from redis import Redis
from redis.exceptions import RedisError

from app.session.state import get_redis_client

logger = logging.getLogger(__name__)

# Stream names
STREAM_STEP_REQUESTS = "scan_step_requests"
STREAM_STEP_RESULTS = "scan_step_results"


class StepRequest:
    """Step request message"""
    def __init__(
        self,
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
    ):
        self.step_id = str(uuid.uuid4())
        self.session_id = session_id
        self.tool_id = tool_id
        self.mode_id = mode_id
        self.params = params
        self.target_ref = target_ref
        self.depends_on = depends_on
        self.reason = reason
        self.org_id = org_id
        self.project_id = project_id
        self.scan_job_id = scan_job_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis stream"""
        return {
            "step_id": self.step_id,
            "session_id": self.session_id,
            "tool_id": self.tool_id,
            "mode_id": self.mode_id,
            "params": json.dumps(self.params),
            "target_ref": self.target_ref,
            "depends_on": json.dumps(self.depends_on),
            "reason": self.reason,
            "org_id": self.org_id or "",
            "project_id": self.project_id or "",
            "scan_job_id": self.scan_job_id or "",
        }


class StepResult:
    """Step result message"""
    def __init__(
        self,
        session_id: str,
        step_id: str,
        status: str,  # "success", "failed", "timeout"
        execution_time_sec: float,
        findings_count: int = 0,
        artifact_refs: Optional[List[str]] = None,
        error: Optional[str] = None,
        tool_output_summary: Optional[str] = None,
        tool_id: Optional[str] = None,  # Add tool_id field
    ):
        self.session_id = session_id
        self.step_id = step_id
        self.status = status
        self.execution_time_sec = execution_time_sec
        self.findings_count = findings_count
        self.artifact_refs = artifact_refs or []
        self.error = error
        self.tool_output_summary = tool_output_summary
        self.tool_id = tool_id  # Store tool_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis stream"""
        return {
            "session_id": self.session_id,
            "step_id": self.step_id,
            "status": self.status,
            "execution_time_sec": str(self.execution_time_sec),
            "findings_count": str(self.findings_count),
            "artifact_refs": json.dumps(self.artifact_refs),
            "error": self.error or "",
            "tool_output_summary": self.tool_output_summary or "",
            "tool_id": self.tool_id or "",  # Include tool_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepResult":
        """Create StepResult from Redis stream data"""
        return cls(
            session_id=data["session_id"],
            step_id=data["step_id"],
            status=data["status"],
            execution_time_sec=float(data.get("execution_time_sec", "0")),
            findings_count=int(data.get("findings_count", "0")),
            artifact_refs=json.loads(data.get("artifact_refs", "[]")),
            error=data.get("error") or None,
            tool_output_summary=data.get("tool_output_summary") or None,
            tool_id=data.get("tool_id") or None,  # Parse tool_id
        )


async def publish_step_request(step_request: StepRequest) -> bool:
    """
    Publish a step request to the scan_step_requests stream.
    
    Args:
        step_request: StepRequest instance
        
    Returns:
        True if published successfully, False otherwise
    """
    redis_client = get_redis_client()
    
    try:
        message_id = redis_client.xadd(
            STREAM_STEP_REQUESTS,
            step_request.to_dict(),
        )
        logger.info(
            f"Published step request {step_request.step_id} for session {step_request.session_id} "
            f"(message_id: {message_id})"
        )
        return True
    except RedisError as e:
        logger.error(f"Failed to publish step request: {e}", exc_info=True)
        return False


async def publish_step_result(step_result: StepResult) -> bool:
    """
    Publish a step result to the scan_step_results stream.
    
    Args:
        step_result: StepResult instance
        
    Returns:
        True if published successfully, False otherwise
    """
    redis_client = get_redis_client()
    
    try:
        message_id = redis_client.xadd(
            STREAM_STEP_RESULTS,
            step_result.to_dict(),
        )
        logger.info(
            f"Published step result {step_result.step_id} for session {step_result.session_id} "
            f"(status: {step_result.status}, message_id: {message_id})"
        )
        return True
    except RedisError as e:
        logger.error(f"Failed to publish step result: {e}", exc_info=True)
        return False


async def consume_step_requests(
    consumer_group: str,
    consumer_name: str,
    count: int = 10,
    block_ms: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Consume step requests from the stream using a consumer group.
    
    Args:
        consumer_group: Consumer group name (e.g., "runner-workers")
        consumer_name: Consumer name (unique per worker)
        count: Maximum number of messages to read
        block_ms: Block for this many milliseconds if no messages
        
    Returns:
        List of messages with format: [{"id": "...", "data": {...}}, ...]
    """
    redis_client = get_redis_client()
    
    try:
        # Create consumer group if it doesn't exist
        try:
            redis_client.xgroup_create(
                STREAM_STEP_REQUESTS,
                consumer_group,
                id="0",  # Start from beginning
                mkstream=True,  # Create stream if it doesn't exist
            )
        except RedisError:
            # Group already exists, ignore
            pass
        
        # Read messages
        messages = redis_client.xreadgroup(
            consumer_group,
            consumer_name,
            {STREAM_STEP_REQUESTS: ">"},  # Read new messages
            count=count,
            block=block_ms,
        )
        
        # Format: [(stream_name, [(message_id, {data})])]
        result = []
        for stream_name, stream_messages in messages:
            for message_id, data in stream_messages:
                result.append({
                    "id": message_id,
                    "data": data,
                })
        
        return result
        
    except RedisError as e:
        logger.error(f"Failed to consume step requests: {e}", exc_info=True)
        return []


async def ack_step_request(consumer_group: str, message_id: str) -> bool:
    """
    Acknowledge a step request message (mark as processed).
    
    Args:
        consumer_group: Consumer group name
        message_id: Message ID to acknowledge
        
    Returns:
        True if acknowledged successfully, False otherwise
    """
    redis_client = get_redis_client()
    
    try:
        redis_client.xack(STREAM_STEP_REQUESTS, consumer_group, message_id)
        return True
    except RedisError as e:
        logger.error(f"Failed to acknowledge step request: {e}", exc_info=True)
        return False


async def read_step_results(
    session_id: str,
    step_ids: List[str],
    timeout_sec: int = 300,
) -> Dict[str, StepResult]:
    """
    Read step results from the stream for specific steps.
    
    This is a blocking read that waits for results up to timeout_sec.
    
    Args:
        session_id: Session ID to filter results
        step_ids: List of step IDs to wait for
        timeout_sec: Maximum time to wait in seconds
        
    Returns:
        Dictionary mapping step_id to StepResult
    """
    redis_client = get_redis_client()
    
    step_ids_set = set(step_ids)
    results: Dict[str, StepResult] = {}
    start_time = datetime.utcnow()
    
    # Start reading from the beginning of the stream
    last_id = "0"
    
    # Check if we have partial results and timeout is approaching
    timeout_warning_sec = timeout_sec * 0.8  # Warn at 80% of timeout
    
    while len(results) < len(step_ids) and (datetime.utcnow() - start_time).total_seconds() < timeout_sec:
        try:
            # Calculate remaining time
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            remaining = timeout_sec - elapsed
            if remaining <= 0:
                break
            
            # Read new messages with appropriate timeout
            # Use a shorter block time to avoid socket timeouts, but retry
            block_ms = min(5000, int(remaining * 1000))
            
            # Create a new Redis client with longer socket timeout for blocking reads
            from redis import Redis
            from app.core.config import settings as brain_settings
            blocking_client = Redis.from_url(
                brain_settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=10,
                socket_timeout=block_ms + 1000,  # Add buffer for socket timeout
            )
            
            # Use asyncio.to_thread to run blocking Redis call in thread pool
            messages = await asyncio.to_thread(
                blocking_client.xread,
                {STREAM_STEP_RESULTS: last_id},
                count=100,
                block=block_ms,
            )
            
            # Close the blocking client
            blocking_client.close()
            
            # Handle empty result (timeout)
            if not messages:
                # No new messages, check if we're approaching timeout
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed > timeout_warning_sec and len(results) == 0:
                    logger.warning(
                        f"Waiting for {len(step_ids)} step results for session {session_id}, "
                        f"no results after {elapsed:.1f}s (timeout: {timeout_sec}s). "
                        f"Runner service may not be processing requests."
                    )
                continue
            
            for stream_name, stream_messages in messages:
                for message_id, data in stream_messages:
                    last_id = message_id
                    
                    # Check if this result is for our session and step
                    if data.get("session_id") == session_id and data.get("step_id") in step_ids_set:
                        step_result = StepResult.from_dict(data)
                        results[step_result.step_id] = step_result
                        
                        if len(results) >= len(step_ids):
                            # Got all results
                            break
        except TimeoutError as e:
            # Socket timeout is expected when no messages arrive
            logger.debug(f"Timeout waiting for step results (this is normal): {e}")
            continue
        except RedisError as e:
            logger.error(f"Failed to read step results: {e}", exc_info=True)
            import time
            time.sleep(1)  # Brief pause before retrying
            continue
        except Exception as e:
            logger.error(f"Unexpected error reading step results: {e}", exc_info=True)
            import time
            time.sleep(1)
            continue
    
    # Check if we got all results or timed out
    if len(results) < len(step_ids):
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        missing_steps = [step_id for step_id in step_ids if step_id not in results]
        logger.warning(
            f"Timeout waiting for step results for session {session_id}. "
            f"Got {len(results)}/{len(step_ids)} results after {elapsed:.1f}s. "
            f"Missing steps: {missing_steps}. Runner service may not be processing requests."
        )
    
    return results



