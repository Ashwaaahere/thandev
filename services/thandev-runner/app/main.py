"""
Main entry point for runner service
"""
import asyncio
import logging
from app.tasks import run_worker_loop

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("Starting Thandev Runner Service")
    try:
        asyncio.run(run_worker_loop())
    except KeyboardInterrupt:
        logger.info("Runner service stopped by user")
    except Exception as e:
        logger.error(f"Runner service error: {e}", exc_info=True)
        raise



