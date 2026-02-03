#!/usr/bin/env python3
"""
Direct method to retry publishing scan steps by calling the function directly
This works even if the API endpoint isn't available yet
"""
import sys
import os
import asyncio

# Set up environment
os.environ.setdefault('REDIS_URL', 'redis://thandev-redis:6379')

async def retry_scan_direct(scan_id: str):
    """Directly call the publish function"""
    sys.path.insert(0, '/app')
    
    from app.services.runner_client import publish_scan_steps_to_runner
    from app.models.scan import ScanJob
    from app.models.project import Project
    from app.models.tenant import Tenant
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        scan_job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
        if not scan_job:
            print(f"❌ Scan {scan_id} not found")
            return False
        
        print(f"✅ Scan found: {scan_job.url}, Level: {scan_job.scan_level}, Status: {scan_job.status}")
        
        project = db.query(Project).filter(Project.id == scan_job.project_id).first()
        if not project:
            print("❌ Project not found")
            return False
        
        tenant = db.query(Tenant).filter(Tenant.id == project.tenant_id).first()
        if not tenant:
            print("❌ Tenant not found")
            return False
        
        print(f"\n📤 Publishing tools...")
        success = await publish_scan_steps_to_runner(
            scan_job_id=scan_id,
            target_url=project.target_url,
            scan_level=scan_job.scan_level,
            org_id=tenant.id,
            project_id=project.id,
            background_tasks=None,  # No background tasks in direct call
        )
        
        if success:
            scan_job.status = scan_job.status  # Keep current status
            db.commit()
            print(f"\n✅ Successfully published tools for scan {scan_id}")
            return True
        else:
            print(f"\n❌ Failed to publish tools for scan {scan_id}")
            return False
    finally:
        db.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python retry_scan_direct.py <scan_id>")
        print("Example: python retry_scan_direct.py c7e26f8b-e950-45b5-8cda-891651a5c34b")
        sys.exit(1)
    
    scan_id = sys.argv[1]
    success = asyncio.run(retry_scan_direct(scan_id))
    sys.exit(0 if success else 1)

