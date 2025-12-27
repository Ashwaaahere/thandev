"""
Redis Streams client for runner service
Reuses stream definitions from brain service
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional
from redis import Redis
from redis.exceptions import RedisError

from app.config import settings

# Import StepResult from brain service (shared definition)
# We need to add brain service to path and import it properly
import sys
from pathlib import Path
brain_path = Path(__file__).parent.parent.parent.parent / "thandev-brain"
brain_app_path = brain_path / "app"
if str(brain_app_path) not in sys.path:
    sys.path.insert(0, str(brain_app_path))
if str(brain_path) not in sys.path:
    sys.path.insert(0, str(brain_path))

# Import StepResult from brain's queue.streams module
try:
    from app.queue.streams import StepResult as BrainStepResult
    StepResult = BrainStepResult
except ImportError:
    # Fallback: define StepResult locally if import fails
    import json
    from datetime import datetime
    
    class StepResult:
        """Step result message (local definition if brain import fails)"""
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

logger = logging.getLogger(__name__)

# Reuse stream names from brain service
STREAM_STEP_REQUESTS = "scan_step_requests"
STREAM_STEP_RESULTS = "scan_step_results"

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


async def consume_step_requests(
    consumer_group: str,
    consumer_name: str,
    count: int = 10,
    block_ms: int = 1000,
    check_pending: bool = False,
) -> List[Dict[str, Any]]:
    """
    Consume step requests from the stream using a consumer group.
    
    Args:
        consumer_group: Consumer group name (e.g., "runner-workers")
        consumer_name: Consumer name (unique per worker)
        count: Maximum number of messages to read
        block_ms: Block for this many milliseconds if no messages
        check_pending: If True, check for PENDING messages first (on startup)
        
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
        
        result = []
        
        # First, try to read PENDING messages for this consumer (if check_pending is True)
        # This handles messages that were delivered but never ACKed (e.g., from a previous crash)
        # Note: Pending message handling is optional - the main fix is checking scan status before processing
        if check_pending:
            try:
                # Get summary first to check if there are any pending messages
                # xpending(key, group) returns: {'pending': count, 'min': '...', 'max': '...', 'consumers': [...]}
                pending_summary = redis_client.xpending(STREAM_STEP_REQUESTS, consumer_group)
                
                if pending_summary and isinstance(pending_summary, dict) and pending_summary.get("pending", 0) > 0:
                    # Try to get pending messages for this consumer
                    # Note: Different redis-py versions may have different signatures
                    # We'll try the most common pattern
                    try:
                        # Try with keyword arguments (redis-py >= 4.0)
                        pending_info = redis_client.xpending(
                            STREAM_STEP_REQUESTS,
                            consumer_group,
                            min="-",
                            max="+",
                            count=count,
                            consumername=consumer_name
                        )
                    except TypeError:
                        # Fallback: try without consumername filter (older redis-py or different signature)
                        try:
                            pending_info = redis_client.xpending(
                                STREAM_STEP_REQUESTS,
                                consumer_group,
                                min="-",
                                max="+",
                                count=count
                            )
                            # Filter for this consumer manually
                            if pending_info:
                                pending_info = [
                                    p for p in pending_info 
                                    if isinstance(p, dict) and p.get("consumer") == consumer_name
                                ]
                        except TypeError:
                            # If that also fails, skip pending message handling
                            logger.debug("Skipping pending message check - unsupported xpending signature")
                            pending_info = []
                    
                    if pending_info and isinstance(pending_info, list):
                        # Claim pending messages that are older than 60 seconds
                        min_idle_time = 60000  # 60 seconds in milliseconds
                        message_ids = [p.get("message_id") for p in pending_info if isinstance(p, dict) and p.get("message_id")]
                        
                        if message_ids:
                            claimed = await asyncio.to_thread(
                                redis_client.xclaim,
                                STREAM_STEP_REQUESTS,
                                consumer_group,
                                consumer_name,
                                min_idle_time,
                                message_ids,
                            )
                            
                            if claimed:
                                logger.info(f"Claimed {len(claimed)} pending message(s) for consumer {consumer_name}")
                                # Process claimed messages
                                for message_id, data in claimed:
                                    if isinstance(message_id, bytes):
                                        message_id = message_id.decode('utf-8')
                                    
                                    decoded_data = {}
                                    for key, value in data.items():
                                        if isinstance(key, bytes):
                                            key = key.decode('utf-8')
                                        if isinstance(value, bytes):
                                            value = value.decode('utf-8')
                                        decoded_data[key] = value
                                    
                                    result.append({
                                        "id": message_id,
                                        "data": decoded_data,
                                    })
            except Exception as e:
                # Catch all errors and continue - pending message handling is optional
                logger.debug(f"Error checking pending messages (skipping): {e}")
                # Continue to read new messages even if pending check fails
        
        # Read new messages (only if we don't have enough pending messages)
        if len(result) < count:
            messages = await asyncio.to_thread(
                redis_client.xreadgroup,
                consumer_group,
                consumer_name,
                {STREAM_STEP_REQUESTS: ">"},  # Read new messages
                count=count - len(result),  # Read remaining slots
                block=block_ms if len(result) == 0 else 0,  # Only block if no messages at all
            )
            
            # Format: [(stream_name, [(message_id, {data})])]
            for stream_name, stream_messages in messages:
                for message_id, data in stream_messages:
                    # Decode message_id if it's bytes
                    if isinstance(message_id, bytes):
                        message_id = message_id.decode('utf-8')
                    
                    # Decode data values if they're bytes (shouldn't happen with decode_responses=True, but be safe)
                    decoded_data = {}
                    for key, value in data.items():
                        if isinstance(key, bytes):
                            key = key.decode('utf-8')
                        if isinstance(value, bytes):
                            value = value.decode('utf-8')
                        decoded_data[key] = value
                    
                    result.append({
                        "id": message_id,
                        "data": decoded_data,
                    })
        
        if result:
            logger.info(f"Consumed {len(result)} step request(s) from stream")
        
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
