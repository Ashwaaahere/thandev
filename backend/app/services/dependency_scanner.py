"""
Service for orchestrating dependency scanning jobs
"""
import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis stream name for dependency scan jobs
DEPENDENCY_SCAN_STREAM = "dependency_scan_jobs"


def get_redis_client():
    """Get Redis client for publishing dependency scan jobs."""
    try:
        from redis import Redis
        from urllib.parse import urlparse
        import os
        
        redis_url = getattr(settings, "REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        parsed = urlparse(redis_url)
        use_tls = parsed.scheme == "rediss"
        
        redis_kwargs = {
            "decode_responses": True,
            "socket_connect_timeout": 10,
            "socket_timeout": 30,
        }
        if use_tls:
            redis_kwargs["ssl"] = True
            if os.getenv("REDIS_TLS_INSECURE", "").lower() in ("true", "1", "yes"):
                import ssl
                redis_kwargs["ssl_cert_reqs"] = ssl.CERT_NONE
                redis_kwargs["ssl_check_hostname"] = False
        
        return Redis.from_url(redis_url, **redis_kwargs)
    except ImportError:
        logger.error("Redis not installed. Install with: pip install redis")
        return None
    except Exception as e:
        logger.error(f"Failed to create Redis client: {e}", exc_info=True)
        return None


async def enqueue_dependency_scan_job(
    scan_id: str,
    job_type: str,  # 'url_sca' or 'repo_sca'
    target_url: str,
    repo_info: Optional[Dict[str, Any]] = None,
    callback_url: Optional[str] = None,
) -> bool:
    """
    Enqueue a dependency scanning job to the runner via Redis stream.
    
    Args:
        scan_id: Scan job ID
        job_type: 'url_sca' or 'repo_sca'
        target_url: Target URL to scan
        repo_info: Optional repo information for repo_sca
        callback_url: Optional callback URL for runner to post results
    
    Returns:
        True if job was enqueued successfully, False otherwise
    """
    logger.info(
        f"Enqueuing dependency scan job: scan_id={scan_id}, job_type={job_type}, "
        f"target_url={target_url}, repo_info={repo_info is not None}"
    )
    
    try:
        redis_client = get_redis_client()
        if not redis_client:
            logger.error("Redis client not available, cannot enqueue dependency scan job")
            return False
        
        # Test connection
        redis_client.ping()
        logger.debug(f"Redis connection verified for dependency scan job {scan_id}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis for dependency scan job: {e}", exc_info=True)
        return False
    
    # Use backend service name for Docker, fallback to localhost for local dev
    backend_url = getattr(settings, "BACKEND_URL", None)
    if not backend_url:
        # Try to detect if we're in Docker by checking environment
        import os
        if os.getenv("DOCKER_CONTAINER") or os.path.exists("/.dockerenv"):
            backend_url = "http://backend:8000"  # Docker service name
        else:
            backend_url = "http://localhost:8000"  # Local development
    
    job_payload = {
        "job_type": job_type,
        "scan_id": scan_id,
        "target_url": target_url,
        "repo": json.dumps(repo_info) if repo_info else None,
        "callback_url": callback_url or f"{backend_url}/api/runner/callback",
        "backend_url": backend_url,
    }
    
    try:
        # Remove None values for Redis stream
        stream_data = {k: str(v) if v is not None else "" for k, v in job_payload.items()}
        
        message_id = redis_client.xadd(
            DEPENDENCY_SCAN_STREAM,
            stream_data,
            maxlen=10000,  # Keep last 10k jobs
        )
        
        logger.info(
            f"Successfully enqueued dependency scan job {scan_id} (job_type={job_type}) "
            f"to Redis stream {DEPENDENCY_SCAN_STREAM} (message_id={message_id})"
        )
        return True
    except Exception as e:
        logger.error(f"Error enqueuing dependency scan job to Redis: {e}", exc_info=True)
        return False
