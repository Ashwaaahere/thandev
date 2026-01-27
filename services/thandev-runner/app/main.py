"""
Main entry point for runner service
"""
import asyncio
import logging
from app.tasks import run_worker_loop
from app.backend_client import _flush_event_batch

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def run_services():
    """Run both the worker loop and event batch processor concurrently."""
    logger.info("Starting worker loop and event batch processor")
    await asyncio.gather(
        run_worker_loop(),
        _flush_event_batch(),
        return_exceptions=True
    )


if __name__ == "__main__":
    logger.info("Starting Thandev Runner Service")
    try:
        asyncio.run(run_services())
    except KeyboardInterrupt:
        logger.info("Runner service stopped by user")
    except Exception as e:
        logger.error(f"Runner service error: {e}", exc_info=True)
        raise



