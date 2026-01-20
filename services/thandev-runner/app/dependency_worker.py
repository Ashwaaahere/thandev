"""
Worker for processing dependency scan jobs from Redis stream
"""
import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
from redis import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.dependency_scanner import run_url_sca_job, run_repo_sca_job
from app.queue.streams import get_redis_client

logger = logging.getLogger(__name__)

# Redis stream name for dependency scan jobs
DEPENDENCY_SCAN_STREAM = "dependency_scan_jobs"
CONSUMER_GROUP = "dependency-workers"
CONSUMER_NAME = settings.CONSUMER_NAME


async def consume_dependency_jobs(
    consumer_group: str = CONSUMER_GROUP,
    consumer_name: str = CONSUMER_NAME,
    count: int = 5,
    block_ms: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Consume dependency scan jobs from Redis stream.
    
    Args:
        consumer_group: Consumer group name
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
                DEPENDENCY_SCAN_STREAM,
                consumer_group,
                id="0",  # Start from beginning
                mkstream=True,  # Create stream if it doesn't exist
            )
            logger.info(f"Created consumer group {consumer_group} for stream {DEPENDENCY_SCAN_STREAM}")
        except RedisError:
            # Group already exists, ignore
            pass
        
        # Read messages from stream
        messages = redis_client.xreadgroup(
            consumer_group,
            consumer_name,
            {DEPENDENCY_SCAN_STREAM: ">"},  # Read new messages
            count=count,
            block=block_ms,
        )
        
        result = []
        for stream_name, stream_messages in messages:
            for message_id, message_data in stream_messages:
                result.append({
                    "id": message_id,
                    "data": message_data,
                })
        
        return result
    except RedisError as e:
        logger.error(f"Error consuming dependency jobs: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Unexpected error consuming dependency jobs: {e}", exc_info=True)
        return []


async def ack_dependency_job(message_id: str) -> None:
    """Acknowledge a dependency scan job message."""
    redis_client = get_redis_client()
    try:
        redis_client.xack(DEPENDENCY_SCAN_STREAM, CONSUMER_GROUP, message_id)
    except Exception as e:
        logger.error(f"Failed to acknowledge dependency job {message_id}: {e}", exc_info=True)


async def process_dependency_job(message: Dict[str, Any]) -> None:
    """
    Process a single dependency scan job.
    
    Args:
        message: Message dict with 'id' and 'data' keys
    """
    message_id = message["id"]
    data = message["data"]
    
    job_type = data.get("job_type", "")
    scan_id = data.get("scan_id", "")
    target_url = data.get("target_url", "")
    callback_url = data.get("callback_url", "")
    backend_url = data.get("backend_url", settings.BACKEND_URL)
    repo_info_str = data.get("repo", "")
    
    logger.info(
        f"Processing dependency scan job: scan_id={scan_id}, job_type={job_type}, "
        f"target_url={target_url}"
    )
    
    try:
        # Parse repo_info if present
        repo_info = None
        if repo_info_str:
            try:
                repo_info = json.loads(repo_info_str)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse repo_info: {repo_info_str}")
        
        # Get runner callback secret from environment
        runner_callback_secret = getattr(settings, "RUNNER_CALLBACK_SECRET", None) or None
        
        # Execute job based on type
        if job_type == "url_sca":
            await run_url_sca_job(
                scan_id=scan_id,
                target_url=target_url,
                callback_url=callback_url,
                backend_url=backend_url,
                runner_callback_secret=runner_callback_secret,
            )
        elif job_type == "repo_sca":
            if not repo_info:
                raise ValueError("repo_info is required for repo_sca jobs")
            await run_repo_sca_job(
                scan_id=scan_id,
                repo_info=repo_info,
                callback_url=callback_url,
                backend_url=backend_url,
                runner_callback_secret=runner_callback_secret,
            )
        else:
            raise ValueError(f"Unknown job_type: {job_type}")
        
        # Acknowledge message
        await ack_dependency_job(message_id)
        logger.info(f"Successfully processed dependency scan job {scan_id} (job_type={job_type})")
        
    except Exception as e:
        logger.error(
            f"Failed to process dependency scan job {scan_id} (job_type={job_type}): {e}",
            exc_info=True
        )
        # Still acknowledge to prevent infinite retries
        await ack_dependency_job(message_id)


async def run_dependency_worker_loop() -> None:
    """
    Main worker loop for dependency scan jobs.
    """
    logger.info("Starting dependency scan worker loop...")
    
    while True:
        try:
            # Consume dependency jobs
            messages = await consume_dependency_jobs(
                consumer_group=CONSUMER_GROUP,
                consumer_name=CONSUMER_NAME,
                count=5,
                block_ms=1000,
            )
            
            if not messages:
                await asyncio.sleep(1)  # Brief pause if no messages
                continue
            
            logger.info(f"Received {len(messages)} dependency scan job(s)")
            
            # Process messages in parallel
            tasks = []
            for message in messages:
                task = asyncio.create_task(
                    process_dependency_job(message)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info(f"Completed processing {len(tasks)} dependency scan job(s)")
        
        except Exception as e:
            logger.error(f"Dependency worker loop error: {e}", exc_info=True)
            await asyncio.sleep(5)  # Wait before retrying
