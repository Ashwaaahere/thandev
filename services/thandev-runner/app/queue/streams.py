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
            """Convert to dictionary for Redis stream - ensures no None values"""
            # Ensure all values are not None before xadd
            return {
                "session_id": self.session_id or "",
                "step_id": self.step_id or "",
                "status": self.status or "",
                "execution_time_sec": str(self.execution_time_sec) if self.execution_time_sec is not None else "0.0",
                "findings_count": str(self.findings_count) if self.findings_count is not None else "0",
                "artifact_refs": json.dumps(self.artifact_refs) if self.artifact_refs else "[]",
                "error": self.error or "",
                "tool_output_summary": self.tool_output_summary or "",
                "tool_id": self.tool_id or "",  # Include tool_id
            }

logger = logging.getLogger(__name__)

# Reuse stream names from brain service
STREAM_STEP_REQUESTS = "scan_step_requests"
STREAM_STEP_RESULTS = "scan_step_results"

# Brain session-specific stream patterns
BRAIN_STREAM_PATTERN = "brain:steps:*"
BRAIN_RESULT_PATTERN = "brain:results:{session_id}"

# Redis client singleton
_redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    """Get or create Redis client singleton"""
    global _redis_client
    if _redis_client is None:
        import os
        from urllib.parse import urlparse
        parsed = urlparse(settings.REDIS_URL)
        use_tls = parsed.scheme == "rediss"
        redis_kwargs = {
            "decode_responses": True,
            "socket_connect_timeout": 10,  # Increased from 5 to 10 seconds
            "socket_timeout": 30,  # Increased from 5 to 30 seconds to prevent timeout errors
        }
        if use_tls:
            # redis-py 5.x handles SSL automatically based on rediss:// scheme
            # Only add SSL parameters if we need to disable certificate verification
            if os.getenv("REDIS_TLS_INSECURE", "").lower() in ("true", "1", "yes"):
                import ssl
                redis_kwargs["ssl_cert_reqs"] = ssl.CERT_NONE
                redis_kwargs["ssl_check_hostname"] = False
        _redis_client = Redis.from_url(settings.REDIS_URL, **redis_kwargs)
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
    
    # #region agent log
    try:
        debug_log_path = "/home/ashwath/thandev/.cursor/debug.log"
        with open(debug_log_path, "a") as f:
            import json as json_lib
            import time
            f.write(json_lib.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"streams.py:125","message":"About to consume from Redis stream","data":{"stream":STREAM_STEP_REQUESTS,"consumer_group":consumer_group,"consumer_name":consumer_name},"timestamp":int(time.time()*1000)})+"\n")
    except: pass
    # #endregion
    
    try:
        # Create consumer group if it doesn't exist
        try:
            redis_client.xgroup_create(
                STREAM_STEP_REQUESTS,
                consumer_group,
                id="0",  # Start from beginning
                mkstream=True,  # Create stream if it doesn't exist
            )
            # #region agent log
            try:
                debug_log_path = "/home/ashwath/thandev/.cursor/debug.log"
                with open(debug_log_path, "a") as f:
                    import json as json_lib
                    import time
                    f.write(json_lib.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"streams.py:135","message":"Created consumer group","data":{"stream":STREAM_STEP_REQUESTS,"consumer_group":consumer_group},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
        except RedisError:
            # Group already exists, ignore
            pass
        
        result = []
        
        # First, try to read and claim PENDING messages (if check_pending is True).
        # This handles messages that were delivered but never ACKed (e.g., from a previous crash or restart).
        #
        # Important: pending entries may belong to a DIFFERENT consumer name (from the crashed container).
        # In that case, filtering by consumer_name would miss them and they would be stuck forever.
        # So we intentionally look at the group pending list (no consumer filter) and XCLAIM old entries.
        if check_pending:
            try:
                # Never let pending-claiming starve new work.
                # Reserve capacity to read ">" entries so newly-triggered scans start immediately.
                pending_read_count = min(count, 5)

                # Get summary first to check if there are any pending messages
                # xpending(key, group) returns: {'pending': count, 'min': '...', 'max': '...', 'consumers': [...]}
                pending_summary = redis_client.xpending(STREAM_STEP_REQUESTS, consumer_group)
                
                # redis-py has returned different shapes across versions:
                # - dict: {"pending": int, "min": str, "max": str, "consumers": [...]}
                # - tuple/list: (pending_count, min_id, max_id, consumers)
                pending_count = 0
                if isinstance(pending_summary, dict):
                    pending_count = int(pending_summary.get("pending", 0) or 0)
                elif isinstance(pending_summary, (tuple, list)) and len(pending_summary) >= 1:
                    try:
                        pending_count = int(pending_summary[0] or 0)
                    except Exception:
                        pending_count = 0

                if pending_count > 0:
                    # Get pending message details for the group (do NOT filter by consumer).
                    # redis-py API differs by version:
                    # - Newer: xpending_range(...)
                    # - Older: xpending(...) with range args
                    pending_info = []
                    if hasattr(redis_client, "xpending_range"):
                        pending_info = redis_client.xpending_range(
                            STREAM_STEP_REQUESTS,
                            consumer_group,
                            min="-",
                            max="+",
                            count=pending_read_count,
                        )
                    else:
                        # Best-effort fallback (older clients)
                        try:
                            pending_info = redis_client.xpending(
                                STREAM_STEP_REQUESTS,
                                consumer_group,
                                min="-",
                                max="+",
                                count=pending_read_count,
                            )
                        except TypeError:
                            logger.debug("Skipping pending message range - unsupported xpending signature")
                            pending_info = []
                    
                    if pending_info and isinstance(pending_info, list):
                        # Claim pending messages that are older than 60 seconds
                        min_idle_time = 60000  # 60 seconds in milliseconds
                        message_ids: list[str] = []
                        for p in pending_info:
                            # Newer redis-py: list of dicts with message_id
                            if isinstance(p, dict) and p.get("message_id"):
                                message_ids.append(p.get("message_id"))
                                continue
                            # Older redis-py: list of tuples/lists like (message_id, consumer, idle_ms, deliveries)
                            if isinstance(p, (tuple, list)) and len(p) >= 1:
                                mid = p[0]
                                if isinstance(mid, bytes):
                                    mid = mid.decode("utf-8")
                                if isinstance(mid, str):
                                    message_ids.append(mid)
                        
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
                                logger.info(f"xclaim returned type: {type(claimed)}, length: {len(claimed) if claimed else 0}")
                                if claimed:
                                    logger.info(f"First item type: {type(claimed[0])}, first item: {str(claimed[0])[:200]}")
                                # Process claimed messages
                                # xclaim returns list of tuples: [(message_id, {field: value, ...}), ...]
                                processed_count = 0
                                for item in claimed:
                                    # Handle both tuple format (message_id, data) and dict format
                                    if isinstance(item, tuple) and len(item) >= 2:
                                        message_id, data = item[0], item[1]
                                    elif isinstance(item, dict):
                                        # Some redis-py versions return dicts directly
                                        message_id = item.get("message_id") or item.get("id")
                                        data = {k: v for k, v in item.items() if k not in ("message_id", "id")}
                                    else:
                                        logger.warning(f"Unexpected xclaim return format: {type(item)} - {item}")
                                        continue
                                    
                                    if isinstance(message_id, bytes):
                                        message_id = message_id.decode('utf-8')
                                    
                                    decoded_data = {}
                                    if isinstance(data, dict):
                                        for key, value in data.items():
                                            if isinstance(key, bytes):
                                                key = key.decode('utf-8')
                                            if isinstance(value, bytes):
                                                value = value.decode('utf-8')
                                            decoded_data[key] = value
                                    else:
                                        logger.warning(f"Expected dict for message data, got {type(data)}")
                                        continue
                                    
                                    result.append({
                                        "id": message_id,
                                        "data": decoded_data,
                                    })
                                    processed_count += 1
                                
                                logger.info(f"Processed {processed_count} claimed messages, result list now has {len(result)} items")
            except Exception as e:
                # Catch all errors and continue - pending message handling is optional
                logger.warning(f"Error checking pending messages (skipping): {e}", exc_info=True)
                # Continue to read new messages even if pending check fails
        
        # Read new messages (only if we don't have enough pending messages).
        # IMPORTANT: Do NOT return early when we claimed pending messages.
        # If we do, a single "stuck" pending message can starve the consumer group and prevent
        # new scans from starting (we would never read ">" entries).
        logger.debug(f"Before xreadgroup: result has {len(result)} items, count={count}")
        if len(result) < count:
            # #region agent log
            try:
                debug_log_path = "/home/ashwath/thandev/.cursor/debug.log"
                with open(debug_log_path, "a") as f:
                    import json as json_lib
                    import time
                    f.write(json_lib.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"streams.py:298","message":"About to xreadgroup from Redis","data":{"stream":STREAM_STEP_REQUESTS,"consumer_group":consumer_group,"consumer_name":consumer_name,"count":count - len(result),"block_ms":block_ms if len(result) == 0 else 0,"result_count":len(result)},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            try:
                messages = await asyncio.to_thread(
                    redis_client.xreadgroup,
                    consumer_group,
                    consumer_name,
                    {STREAM_STEP_REQUESTS: ">"},  # Read new messages
                    count=count - len(result),  # Read remaining slots
                    block=block_ms if len(result) == 0 else 0,  # Only block if no messages at all
                )
                # #region agent log
                try:
                    debug_log_path = "/home/ashwath/thandev/.cursor/debug.log"
                    with open(debug_log_path, "a") as f:
                        import json as json_lib
                        import time
                        message_count = len(messages[0][1]) if messages and len(messages) > 0 and len(messages[0]) > 1 else 0
                        f.write(json_lib.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"streams.py:310","message":"After xreadgroup","data":{"message_count":message_count,"messages_type":type(messages).__name__,"has_messages":bool(messages)},"timestamp":int(time.time()*1000)})+"\n")
                except: pass
                # #endregion
                logger.debug(f"xreadgroup returned {len(messages) if messages else 0} stream(s)")
            except Exception as e:
                logger.warning(f"Error reading new messages (continuing with claimed messages): {e}", exc_info=True)
                messages = []
            
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
        else:
            logger.debug("No messages consumed from stream")
        
        return result
        
    except RedisError as e:
        # Redis socket timeouts are expected when blocking reads return no data.
        # Treat them as empty reads, not fatal errors.
        if "Timeout reading from socket" in str(e):
            logger.debug(f"Timeout waiting for step requests (normal): {e}")
            return []
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


def discover_brain_sessions() -> List[str]:
    """
    Discover active Brain session streams by scanning Redis for brain:steps:* keys.
    
    Returns:
        List of session IDs (extracted from stream names)
    """
    redis_client = get_redis_client()
    
    try:
        # Scan for all brain:steps:* streams
        brain_streams = []
        for key in redis_client.scan_iter(match="brain:steps:*", count=100):
            # Extract session ID from stream name (brain:steps:{session_id})
            if key.startswith("brain:steps:"):
                session_id = key[len("brain:steps:"):]
                brain_streams.append(session_id)
        
        if brain_streams:
            logger.debug(f"Discovered {len(brain_streams)} active Brain session(s): {brain_streams[:5]}...")
        
        return brain_streams
    except RedisError as e:
        logger.error(f"Failed to discover Brain sessions: {e}")
        return []


async def consume_brain_session_steps(
    session_id: str,
    consumer_group: str,
    consumer_name: str,
    count: int = 10,
    block_ms: int = 0,  # Don't block on Brain streams, we poll multiple
) -> List[Dict[str, Any]]:
    """
    Consume steps from a specific Brain session stream.
    
    Args:
        session_id: Brain session ID
        consumer_group: Consumer group name
        consumer_name: Consumer name
        count: Max messages to read
        block_ms: Block time (default 0 for non-blocking)
        
    Returns:
        List of messages with session_id metadata
    """
    redis_client = get_redis_client()
    stream_name = f"brain:steps:{session_id}"
    
    try:
        # Create consumer group if it doesn't exist
        try:
            redis_client.xgroup_create(
                stream_name,
                consumer_group,
                id="0",
                mkstream=True,
            )
        except RedisError:
            # Group already exists
            pass
        
        # Read new messages
        messages = redis_client.xreadgroup(
            consumer_group,
            consumer_name,
            {stream_name: ">"},
            count=count,
            block=block_ms,
        )
        
        result = []
        if messages:
            for stream, msgs in messages:
                for msg_id, data in msgs:
                    # Add session_id to metadata
                    data["_session_id"] = session_id
                    data["_stream_name"] = stream_name
                    result.append({"id": msg_id, "data": data})
        
        return result
    except RedisError as e:
        logger.error(f"Failed to consume from Brain session {session_id}: {e}")
        return []


async def publish_step_result(step_result: StepResult) -> bool:
    """
    Publish a step result to the appropriate stream.
    
    If step_result has a session_id, publishes to Brain's result stream (brain:results:{session_id}).
    Otherwise, publishes to the global scan_step_results stream.
    
    Args:
        step_result: StepResult instance
        
    Returns:
        True if published successfully, False otherwise
    """
    redis_client = get_redis_client()
    
    # Determine target stream
    if step_result.session_id:
        # Brain session - use session-specific result stream
        target_stream = f"brain:results:{step_result.session_id}"
    else:
        # Global stream (backward compatibility)
        target_stream = STREAM_STEP_RESULTS
    
    try:
        message_id = redis_client.xadd(
            target_stream,
            step_result.to_dict(),
        )
        logger.info(
            f"Published step result {step_result.step_id} for session {step_result.session_id} "
            f"to {target_stream} (status: {step_result.status}, message_id: {message_id})"
        )
        return True
    except RedisError as e:
        logger.error(f"Failed to publish step result to {target_stream}: {e}", exc_info=True)
        return False
