#!/usr/bin/env python3
"""
Entry point for dependency worker
"""
import asyncio
import logging
import sys

# Set up logging before any other imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

async def main():
    """Main entry point for dependency worker"""
    logger.info("=== Starting Dependency Scan Worker ===")
    
    from app.dependency_worker import run_dependency_worker_loop
    
    try:
        await run_dependency_worker_loop()
    except KeyboardInterrupt:
        logger.info("Dependency worker interrupted by user")
    except Exception as e:
        logger.error(f"Dependency worker failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main())
