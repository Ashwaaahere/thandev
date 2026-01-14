#!/usr/bin/env python3
"""
Fix queued scans by publishing them to Runner instead of waiting for Celery worker.
"""
import asyncio
import sys
from app.core.database import SessionLocal
from app.models.scan import ScanJob, ScanStatus
from app.services.runner_client import publish_scan_steps_to_runner
from datetime import datetime, timezone

def fix_queued_scans():
    """Fix all queued scans by publishing them to Runner"""
    db = SessionLocal()
    try:
        queued_scans = db.query(ScanJob).filter(ScanJob.status == ScanStatus.QUEUED).all()
        
        if not queued_scans:
            print("No queued scans found")
            return
        
        print(f"Found {len(queued_scans)} queued scan(s)")
        
        for scan_job in queued_scans:
            print(f"\nProcessing scan: {scan_job.id}")
            print(f"  Level: {scan_job.scan_level}")
            print(f"  Celery Task ID: {scan_job.celery_task_id}")
            print(f"  Created: {scan_job.created_at}")
            
            # Get project
            project = scan_job.project
            if not project:
                print(f"  ❌ Project not found, skipping")
                continue
            
            print(f"  Publishing to Runner...")
            
            async def publish_scan():
                return await publish_scan_steps_to_runner(
                    scan_job_id=scan_job.id,
                    target_url=project.target_url,
                    scan_level=scan_job.scan_level,
                    org_id=project.tenant_id,
                    project_id=project.id,
                )
            
            success = asyncio.run(publish_scan())
            
            if success:
                scan_job.status = ScanStatus.RUNNING
                scan_job.started_at = datetime.now(timezone.utc)
                scan_job.celery_task_id = None  # Clear Celery task ID
                db.commit()
                print(f"  ✅ Fixed! Status set to RUNNING")
            else:
                print(f"  ❌ Failed to publish steps to Runner")
                scan_job.status = ScanStatus.FAILED
                scan_job.error_message = "Failed to publish steps to Runner (was stuck in QUEUED)"
                db.commit()
        
        print(f"\n✅ Processed {len(queued_scans)} scan(s)")
    finally:
        db.close()

if __name__ == "__main__":
    fix_queued_scans()


