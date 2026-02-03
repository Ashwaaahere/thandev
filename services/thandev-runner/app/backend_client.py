"""
Backend API client for runner service
Handles communication with backend API for tool results and findings
"""
import logging
import httpx
import uuid
import asyncio
import random
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import deque

from app.config import settings

logger = logging.getLogger(__name__)

# Event batching configuration
EVENT_BATCH_SIZE = 10  # Send events in batches of 10
EVENT_BATCH_INTERVAL = 3.0  # Or every 3 seconds
_event_queue: deque = deque()
_event_batch_task: Optional[asyncio.Task] = None

# Retry configuration
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 60.0  # seconds
RETRY_EXPONENT = 2.0
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}  # Rate limit, Bad Gateway, Service Unavailable, Gateway Timeout
REQUEST_TIMEOUT = 60.0  # seconds
# Connection timeout for initial connection (separate from request timeout)
CONNECT_TIMEOUT = 10.0  # seconds

# Shared HTTP client for connection pooling and keep-alive
_http_client: Optional[httpx.AsyncClient] = None
_client_lock = asyncio.Lock()

async def get_http_client() -> httpx.AsyncClient:
    """Get or create shared HTTP client with connection pooling"""
    global _http_client
    if _http_client is None:
        async with _client_lock:
            # Double-check after acquiring lock
            if _http_client is None:
                # Use connection pooling with keep-alive for better performance
                limits = httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=30.0)
                timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
                _http_client = httpx.AsyncClient(
                    timeout=timeout,
                    limits=limits,
                    http2=True,  # Use HTTP/2 for better performance
                )
    return _http_client

async def test_backend_connectivity() -> bool:
    """Test backend connectivity by calling health endpoint"""
    if not settings.BACKEND_URL:
        return False
    
    try:
        endpoint = f"{settings.BACKEND_URL}/health"
        client = await get_http_client()
        resp = await client.get(endpoint, timeout=5.0)
        resp.raise_for_status()
        logger.info(f"Backend connectivity test successful: {endpoint}")
        return True
    except Exception as e:
        logger.warning(f"Backend connectivity test failed: {e}")
        return False


async def get_scan_status(scan_job_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch scan status from backend using runner service auth.

    Uses /api/runner/scans/{scan_id} which is protected by RUNNER_API_TOKEN.
    Returns None if BACKEND_URL is not configured or request fails.
    """
    if not settings.BACKEND_URL:
        return None

    endpoint = f"{settings.BACKEND_URL}/api/runner/scans/{scan_job_id}"
    headers = {"Content-Type": "application/json"}
    if settings.RUNNER_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.RUNNER_API_TOKEN}"

    try:
        # Use longer timeout and explicit connect timeout for internal DNS
        timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(endpoint, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.debug(f"Scan {scan_job_id} not found in backend")
        else:
            logger.warning(f"Backend API returned error status {e.response.status_code} for scan status: {e.response.text}")
        return None
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        logger.warning(f"Network error fetching scan status for {scan_job_id}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch scan status from backend for scan {scan_job_id}: {e}")
        return None


async def mark_scan_started(scan_job_id: str) -> bool:
    """
    Tell backend that runner has started processing this scan.

    This transitions scan status QUEUED -> RUNNING immediately when the first step begins.
    """
    if not settings.BACKEND_URL:
        return False

    endpoint = f"{settings.BACKEND_URL}/api/runner/scans/{scan_job_id}/started"
    headers = {"Content-Type": "application/json"}
    if settings.RUNNER_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.RUNNER_API_TOKEN}"

    try:
        timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(endpoint, headers=headers)
            resp.raise_for_status()
            return True
    except Exception as e:
        logger.warning(f"Failed to mark scan started for {scan_job_id}: {e}")
        return False


async def post_tool_started(
    scan_job_id: str,
    tool_run_id: str,
    step_id: str,
    tool_name: str,
    tool_id: Optional[str] = None,
    command: Optional[str] = None,
) -> bool:
    """
    Notify backend that a tool has started (creates/updates ToolResult with status=RUNNING).
    
    This is called AFTER acquiring a concurrency slot, so the tool is actually starting execution.
    """
    if not settings.BACKEND_URL:
        logger.warning(f"Cannot post tool started for {tool_name}: BACKEND_URL not configured")
        return False

    endpoint = f"{settings.BACKEND_URL}/api/runner/scans/{scan_job_id}/tool-started"
    headers = {"Content-Type": "application/json"}
    if settings.RUNNER_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.RUNNER_API_TOKEN}"

    payload: Dict[str, Any] = {
        "tool_run_id": tool_run_id,
        "step_id": step_id,
        "tool_name": tool_name,
    }
    if tool_id:
        payload["tool_id"] = tool_id
    if command:
        payload["command"] = command

    try:
        timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            logger.info(f"Posted tool-started for {tool_name} (scan {scan_job_id}, step {step_id}) - status will change to RUNNING")
            return True
    except Exception as e:
        logger.error(f"Failed to post tool-started for {tool_name} (scan {scan_job_id}, step {step_id}): {e}")
        # This is non-critical - tool will still execute, but UI won't show RUNNING status immediately
        return False


def _calculate_retry_delay(attempt: int) -> float:
    """
    Calculate retry delay with exponential backoff and jitter.
    
    Args:
        attempt: Current retry attempt (0-indexed)
        
    Returns:
        Delay in seconds
    """
    # Exponential backoff: initial_delay * (exponent ^ attempt)
    delay = INITIAL_RETRY_DELAY * (RETRY_EXPONENT ** attempt)
    
    # Cap at max delay
    delay = min(delay, MAX_RETRY_DELAY)
    
    # Add jitter (random 0-20% of delay)
    jitter = delay * random.uniform(0, 0.2)
    delay = delay + jitter
    
    return delay


def _is_retryable_error(exception: Exception) -> bool:
    """
    Check if an exception is retryable.
    
    Args:
        exception: Exception to check
        
    Returns:
        True if retryable, False otherwise
    """
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRYABLE_STATUS_CODES
    
    if isinstance(exception, (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError)):
        return True
    
    return False


async def post_tool_result(
    scan_job_id: str,
    step_id: str,
    tool_name: str,
    tool_id: str,
    findings: List[Dict[str, Any]],
    execution_result: Optional[Dict[str, Any]] = None,
    tool_run_id: Optional[str] = None,
) -> bool:
    """
    POST tool result and findings to backend API with retry logic.
    
    This endpoint is idempotent - using tool_run_id as unique key prevents duplicates.
    
    Args:
        scan_job_id: Scan job ID
        step_id: Step ID (for reference, kept for backward compatibility)
        tool_name: Tool name (e.g., "nuclei", "httpx")
        tool_id: Tool ID (e.g., "tool-nuclei-v2")
        findings: List of normalized finding dicts
        execution_result: Optional execution result dict with exit_code, execution_time, etc.
        tool_run_id: Optional tool run ID (UUID). If not provided, generates a new one.
        
    Returns:
        True if successful, False otherwise
    """
    if not settings.BACKEND_URL:
        logger.warning("BACKEND_URL not configured, skipping tool result POST")
        return False
    
    # Generate tool_run_id if not provided
    if not tool_run_id:
        tool_run_id = str(uuid.uuid4())
    
    # Changed from /api/internal/... to /api/runner/... to avoid Fly.io proxy blocking
    endpoint = f"{settings.BACKEND_URL}/api/runner/scans/{scan_job_id}/tool-results"
    
    # Build payload
    payload = {
        "tool_run_id": tool_run_id,  # Required for idempotency
        "step_id": step_id,  # Kept for backward compatibility
        "tool_name": tool_name,
        "tool_id": tool_id,
        "findings": findings,
        "findings_count": len(findings),
    }
    
    # Add execution metadata if available
    if execution_result:
        # Default "success" should be False when missing (many tool wrappers omit it on failure/timeout)
        success_value = execution_result.get("success") if "success" in execution_result else False
        # Best-effort "timed_out" inference for legacy error strings
        err_text = (execution_result.get("error") or execution_result.get("error_message") or "")
        timed_out_value = bool(execution_result.get("timed_out", False)) or ("timed out" in str(err_text).lower())

        payload.update({
            "exit_code": execution_result.get("exit_code"),
            "execution_time": execution_result.get("execution_time"),
            "success": bool(success_value),
            "output": execution_result.get("output", "")[:50000] if execution_result.get("output") else None,  # Truncate to 50KB (was 10KB)
            "command": execution_result.get("command"),
            "error_message": execution_result.get("error") or execution_result.get("error_message"),
            "timed_out": timed_out_value,
            "stdout_preview": (execution_result.get("stdout") or "")[:1000] if execution_result.get("stdout") else None,
            "stderr_preview": (execution_result.get("stderr") or "")[:1000] if execution_result.get("stderr") else None,
            # Tool run tracking fields
            "targets_count": execution_result.get("targets_count", 0),
            "meta": execution_result.get("meta"),
        })
    
    # Debug: Log what we're sending for wappalyzer/retire
    if tool_name in ('wappalyzer', 'retire'):
        logger.error(f"[BACKEND-CLIENT-DEBUG] Sending {tool_name} payload with meta: {payload.get('meta')}")
    
    # Prepare headers
    headers = {"Content-Type": "application/json"}
    if settings.RUNNER_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.RUNNER_API_TOKEN}"
    
    # Calculate payload size for logging
    import json as json_module
    payload_size = len(json_module.dumps(payload))
    payload_size_mb = payload_size / (1024 * 1024)
    
    logger.info(
        f"[TOOL-RESULT-POST] Attempting to POST tool result: "
        f"scan={scan_job_id}, tool={tool_name}, findings={len(findings)}, "
        f"payload_size={payload_size_mb:.2f}MB, endpoint={endpoint}"
    )
    
    # Retry loop with exponential backoff + jitter
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            # Use longer timeout for large payloads (ZAP can have large results)
            timeout_seconds = REQUEST_TIMEOUT
            if payload_size_mb > 5:  # If payload > 5MB, use longer timeout
                timeout_seconds = REQUEST_TIMEOUT * 2  # Double timeout for large payloads
                logger.info(f"[TOOL-RESULT-POST] Large payload detected ({payload_size_mb:.2f}MB), using extended timeout: {timeout_seconds}s")
            
            # Use shared client with connection pooling for better reliability
            client = await get_http_client()
            custom_client = None
            # Update timeout for this specific request if needed
            if timeout_seconds != REQUEST_TIMEOUT:
                custom_client = httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=CONNECT_TIMEOUT))
                client = custom_client
            
            try:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                
                logger.info(
                    f"Posted tool result to backend (status code {response.status_code}): "
                    f"scan={scan_job_id}, step={step_id}, tool={tool_name}, tool_run_id={tool_run_id}, "
                    f"findings={len(findings)}, payload_size={payload_size_mb:.2f}MB"
                )
                
                return True
            finally:
                # Only close if we created a custom client for this request
                if custom_client:
                    await custom_client.aclose()
                
        except httpx.HTTPStatusError as e:
            last_exception = e
            # Check if retryable
            if e.response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                delay = _calculate_retry_delay(attempt)
                logger.warning(
                    f"Backend API returned retryable status {e.response.status_code} for tool result POST "
                    f"(attempt {attempt + 1}/{MAX_RETRIES}). Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
                continue
            else:
                # Non-retryable status code or max retries reached
                logger.error(
                    f"Backend API returned error status {e.response.status_code} for tool result POST: {e.response.text}"
                )
                return False
                
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
            last_exception = e
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "endpoint": endpoint,
                "backend_url": settings.BACKEND_URL,
                "payload_size_mb": f"{payload_size_mb:.2f}",
                "attempt": attempt + 1,
                "max_retries": MAX_RETRIES
            }
            
            if attempt < MAX_RETRIES - 1:
                delay = _calculate_retry_delay(attempt)
                logger.warning(
                    f"Network error during tool result POST (attempt {attempt + 1}/{MAX_RETRIES}): {type(e).__name__}: {e}. "
                    f"Endpoint: {endpoint}, BACKEND_URL: {settings.BACKEND_URL}, "
                    f"Payload size: {payload_size_mb:.2f}MB. Retrying in {delay:.2f}s...",
                    extra=error_details
                )
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(
                    f"Network error during tool result POST after {MAX_RETRIES} attempts: {e}. "
                    f"Payload size: {payload_size_mb:.2f}MB, Endpoint: {endpoint}",
                    exc_info=True,
                    extra=error_details
                )
                return False
                
        except Exception as e:
            # Non-retryable exception
            logger.error(f"Failed to POST tool result to backend: {e}", exc_info=True)
            return False
    
    # If we get here, all retries failed
    error_summary = {
        "scan_job_id": scan_job_id,
        "tool_name": tool_name,
        "step_id": step_id,
        "endpoint": endpoint,
        "backend_url": settings.BACKEND_URL,
        "payload_size_mb": f"{payload_size_mb:.2f}",
        "findings_count": len(findings),
        "last_error_type": type(last_exception).__name__ if last_exception else "Unknown",
        "last_error": str(last_exception) if last_exception else "Unknown error"
    }
    logger.error(
        f"Failed to POST tool result to backend after {MAX_RETRIES} attempts. "
        f"Last error: {last_exception}. Payload size: {payload_size_mb:.2f}MB",
        extra=error_summary,
        exc_info=True
    )
    return False


async def _flush_event_batch():
    """Background task to flush event batch periodically"""
    global _event_queue
    
    while True:
        try:
            await asyncio.sleep(EVENT_BATCH_INTERVAL)
            
            if _event_queue:
                await _send_event_batch()
        except asyncio.CancelledError:
            # Flush remaining events before exiting
            if _event_queue:
                await _send_event_batch()
            break
        except Exception as e:
            logger.error(f"Error in event batch flusher: {e}", exc_info=True)


async def _send_event_batch():
    """Send batched events to backend"""
    global _event_queue
    
    if not _event_queue:
        return
    
    # Extract events from queue
    events_to_send = []
    while _event_queue and len(events_to_send) < EVENT_BATCH_SIZE:
        events_to_send.append(_event_queue.popleft())
    
    if not events_to_send:
        return
    
    # Group events by scan_id
    events_by_scan = {}
    for event in events_to_send:
        scan_id = event.pop("scan_id")
        if scan_id not in events_by_scan:
            events_by_scan[scan_id] = []
        events_by_scan[scan_id].append(event)
    
    # Send batches
    for scan_id, events in events_by_scan.items():
        try:
            await post_scan_events(scan_id, events)
        except Exception as e:
            logger.error(f"Failed to send event batch for scan {scan_id}: {e}")


async def emit_scan_event(
    scan_id: str,
    phase: str,
    tool: Optional[str],
    stage: str,
    message: str,
    progress: Optional[float] = None,
    meta: Optional[Dict[str, Any]] = None,
):
    """
    Emit a scan event (batched for efficiency)
    
    Events are queued and sent in batches to minimize HTTP overhead.
    
    Args:
        scan_id: Scan job ID
        phase: Scan phase (prepare, enumerate, scan, correlate, finalize)
        tool: Tool name (httpx, nuclei, zap, katana, etc.)
        stage: Stage (queued, starting, running, parsing, uploading, completed, failed)
        message: Human-readable status message
        progress: Optional progress percentage (0.0 to 1.0)
        meta: Optional metadata dict
    """
    global _event_queue, _event_batch_task
    
    # Add event to queue
    _event_queue.append({
        "scan_id": scan_id,
        "phase": phase,
        "tool": tool,
        "stage": stage,
        "message": message,
        "progress": progress,
        "meta": meta,
    })
    
    # Start batch flusher if not running
    if _event_batch_task is None or _event_batch_task.done():
        _event_batch_task = asyncio.create_task(_flush_event_batch())
    
    # Flush immediately if batch is full
    if len(_event_queue) >= EVENT_BATCH_SIZE:
        await _send_event_batch()


async def post_scan_events(scan_id: str, events: List[Dict[str, Any]]) -> bool:
    """
    Post batch of scan events to backend
    
    Args:
        scan_id: Scan job ID
        events: List of event dicts
        
    Returns:
        True if successful, False otherwise
    """
    if not settings.BACKEND_URL or not events:
        return False
    
    endpoint = f"{settings.BACKEND_URL}/api/runner/scans/{scan_id}/events"
    headers = {"Content-Type": "application/json"}
    if settings.RUNNER_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.RUNNER_API_TOKEN}"
    
    payload = {"events": events}
    
    try:
        timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            logger.debug(f"Posted {len(events)} events for scan {scan_id}")
            return True
    except Exception as e:
        logger.warning(f"Failed to post scan events for {scan_id}: {e}")
        return False


async def post_scan_inventory(scan_id: str, inventory: Dict[str, Any]) -> bool:
    """
    Post scan asset inventory to backend with retry logic
    
    Args:
        scan_id: Scan job ID
        inventory: Asset inventory dict
        
    Returns:
        True if successful, False otherwise
    """
    if not settings.BACKEND_URL:
        logger.warning(f"Cannot post inventory for scan {scan_id}: BACKEND_URL not configured")
        return False
    
    endpoint = f"{settings.BACKEND_URL}/api/runner/scans/{scan_id}/inventory"
    headers = {"Content-Type": "application/json"}
    if settings.RUNNER_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.RUNNER_API_TOKEN}"
    
    payload = {"inventory": inventory}
    
    # Calculate payload size
    import json as json_module
    payload_size = len(json_module.dumps(payload))
    payload_size_mb = payload_size / (1024 * 1024)
    
    logger.info(
        f"[INVENTORY-POST] Posting inventory for scan {scan_id}: "
        f"payload_size={payload_size_mb:.2f}MB, endpoint={endpoint}"
    )
    
    # Use retry logic similar to tool results
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            timeout_seconds = REQUEST_TIMEOUT
            if payload_size_mb > 5:
                timeout_seconds = REQUEST_TIMEOUT * 2
                logger.info(f"[INVENTORY-POST] Large payload ({payload_size_mb:.2f}MB), using extended timeout: {timeout_seconds}s")
            
            # Use shared client with connection pooling
            client = await get_http_client()
            custom_client = None
            if timeout_seconds != REQUEST_TIMEOUT:
                custom_client = httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=CONNECT_TIMEOUT))
                client = custom_client
            
            try:
                resp = await client.post(endpoint, headers=headers, json=payload)
                resp.raise_for_status()
                logger.info(
                    f"Posted asset inventory for scan {scan_id}: "
                    f"payload_size={payload_size_mb:.2f}MB, status={resp.status_code}"
                )
                return True
            finally:
                if custom_client:
                    await custom_client.aclose()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                delay = _calculate_retry_delay(attempt)
                logger.warning(
                    f"Network error during inventory POST (attempt {attempt + 1}/{MAX_RETRIES}): "
                    f"{type(e).__name__}: {e}. Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(
                    f"Network error during inventory POST after {MAX_RETRIES} attempts: {e}. "
                    f"Payload size: {payload_size_mb:.2f}MB"
                )
                return False
        except httpx.HTTPStatusError as e:
            last_exception = e
            if e.response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                delay = _calculate_retry_delay(attempt)
                logger.warning(
                    f"Backend returned retryable status {e.response.status_code} for inventory POST "
                    f"(attempt {attempt + 1}/{MAX_RETRIES}). Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(
                    f"Backend returned error status {e.response.status_code} for inventory POST: {e.response.text}"
                )
                return False
        except Exception as e:
            last_exception = e
            logger.error(f"Failed to post scan inventory for {scan_id}: {e}", exc_info=True)
            if attempt < MAX_RETRIES - 1:
                delay = _calculate_retry_delay(attempt)
                await asyncio.sleep(delay)
                continue
            return False
    
    logger.error(
        f"Failed to post inventory after {MAX_RETRIES} attempts. Last error: {last_exception}"
    )
    return False


async def get_scan_artifact(scan_id: str, artifact_name: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a scan artifact from the backend
    
    Args:
        scan_id: Scan job ID
        artifact_name: Name of the artifact (e.g., "asset_inventory.json")
        
    Returns:
        Artifact data as dict if found, None otherwise
    """
    if not settings.BACKEND_URL:
        return None
    
    endpoint = f"{settings.BACKEND_URL}/api/scans/{scan_id}/artifacts"
    headers = {"Content-Type": "application/json"}
    if settings.RUNNER_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.RUNNER_API_TOKEN}"
    
    try:
        timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(endpoint, headers=headers)
            resp.raise_for_status()
            artifacts = resp.json()
            
            # Find the requested artifact
            for artifact in artifacts:
                if artifact.get("artifact_type") == artifact_name:
                    # Get the artifact data
                    artifact_data = artifact.get("data")
                    if artifact_data:
                        logger.debug(f"Retrieved artifact {artifact_name} for scan {scan_id}")
                        return artifact_data
            
            logger.debug(f"Artifact {artifact_name} not found for scan {scan_id}")
            return None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.debug(f"No artifacts found for scan {scan_id}")
        else:
            logger.warning(f"Failed to get scan artifact for {scan_id}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to get scan artifact for {scan_id}: {e}")
        return None


async def get_scan_inventory_with_retry(scan_id: str, max_retries: int = 10, retry_delay: float = 3.0) -> Optional[Dict[str, Any]]:
    """
    Retrieve scan inventory from backend with retry logic.
    Waits for enumeration to complete and inventory to be available.
    
    Args:
        scan_id: Scan job ID
        max_retries: Maximum number of retries (default 10 = 30 seconds)
        retry_delay: Delay between retries in seconds (default 3)
        
    Returns:
        Inventory dict if found, None otherwise
    """
    import asyncio
    
    if not settings.BACKEND_URL:
        return None
    
    # Use the runner inventory endpoint
    endpoint = f"{settings.BACKEND_URL}/api/runner/scans/{scan_id}/inventory"
    headers = {"Content-Type": "application/json"}
    if settings.RUNNER_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.RUNNER_API_TOKEN}"
    
    for attempt in range(max_retries):
        try:
            timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(endpoint, headers=headers)
                
                if resp.status_code == 200:
                    data = resp.json()
                    inventory = data.get("inventory")
                    if inventory:
                        logger.info(f"[INVENTORY-RETRY] Found inventory for scan {scan_id} on attempt {attempt + 1}")
                        return inventory
                    else:
                        logger.debug(f"[INVENTORY-RETRY] Inventory empty for scan {scan_id} on attempt {attempt + 1}")
                elif resp.status_code == 404:
                    logger.debug(f"[INVENTORY-RETRY] Inventory not found for scan {scan_id} on attempt {attempt + 1}")
                else:
                    logger.warning(f"[INVENTORY-RETRY] Unexpected status {resp.status_code} for scan {scan_id}")
                    
        except Exception as e:
            logger.debug(f"[INVENTORY-RETRY] Error fetching inventory for scan {scan_id} on attempt {attempt + 1}: {e}")
        
        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)
    
    logger.warning(f"[INVENTORY-RETRY] Failed to get inventory for scan {scan_id} after {max_retries} attempts")
    return None

