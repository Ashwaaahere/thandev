
import asyncio
import logging
import sys
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock settings if needed or setup path
sys.path.append("/app")

from app.core.database import SessionLocal
from app.services.dependency_scanner import enqueue_dependency_scan_job
from app.models.scan import ScanJob
from app.core.config import settings

async def trigger_scan(scan_id):
    db = SessionLocal()
    try:
        scan = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
        if not scan:
            logger.error(f"Scan {scan_id} not found")
            return
        
        logger.info(f"files found for scan {scan.id}, url={scan.url}")
        
        callback_url = "http://backend:8000/api/runner/callback"
        
        logger.info(f"Enqueuing dependency scan for {scan_id} to {callback_url}")
        
        result = await enqueue_dependency_scan_job(
            scan_id=scan.id,
            job_type="url_sca",
            target_url=scan.url,
            callback_url=callback_url
        )
        
        if result:
            logger.info("Successfully enqueued dependency scan job")
        else:
            logger.error("Failed to enqueue job")
            
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.path) < 2:
        print("Usage: python trigger.py <scan_id>")
        sys.exit(1)
        
    scan_id = "bcf23698-4de1-4f3f-ace0-10f75a2bb278" 
    asyncio.run(trigger_scan(scan_id))
