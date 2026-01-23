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

from app.config import settings

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 60.0  # seconds
RETRY_EXPONENT = 2.0
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}  # Rate limit, Bad Gateway, Service Unavailable, Gateway Timeout
REQUEST_TIMEOUT = 60.0  # seconds
# Connection timeout for initial connection (separate from request timeout)
CONNECT_TIMEOUT = 10.0  # seconds


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
            "output": execution_result.get("output", "")[:10000] if execution_result.get("output") else None,  # Truncate
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
    
    # Retry loop with exponential backoff + jitter
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                
                logger.info(
                    f"Posted tool result to backend (status code {response.status_code}): "
                    f"scan={scan_job_id}, step={step_id}, tool={tool_name}, tool_run_id={tool_run_id}, findings={len(findings)}"
                )
                
                return True
                
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
            if attempt < MAX_RETRIES - 1:
                delay = _calculate_retry_delay(attempt)
                logger.warning(
                    f"Network error during tool result POST (attempt {attempt + 1}/{MAX_RETRIES}): {type(e).__name__}: {e}. "
                    f"Endpoint: {endpoint}, BACKEND_URL: {settings.BACKEND_URL}. Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(f"Network error during tool result POST after {MAX_RETRIES} attempts: {e}")
                return False
                
        except Exception as e:
            # Non-retryable exception
            logger.error(f"Failed to POST tool result to backend: {e}", exc_info=True)
            return False
    
    # If we get here, all retries failed
    logger.error(
        f"Failed to POST tool result to backend after {MAX_RETRIES} attempts. "
        f"Last error: {last_exception}"
    )
    return False

