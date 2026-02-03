#!/usr/bin/env python3
"""Manually publish steps for scan 1B908A55"""
import asyncio
import sys
import os
sys.path.insert(0, '/app')

os.environ.setdefault('REDIS_URL', 'redis://thandev-redis:6379')

async def main():
    scan_id = '1b908a55-eca1-43a1-9b07-b899697616c6'
    
    from app.services.runner_client import publish_scan_steps_to_runner
    from app.models.scan import ScanJob, ScanLevel
    from app.models.project import Project
    from app.models.tenant import Tenant
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        scan_job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
        if not scan_job:
            print(f'Scan {scan_id} not found')
            return
        
        print(f'Scan found: {scan_job.url}, Level: {scan_job.scan_level}, Status: {scan_job.status}')
        
        project = db.query(Project).filter(Project.id == scan_job.project_id).first()
        if not project:
            print('Project not found')
            return
        
        tenant = db.query(Tenant).filter(Tenant.id == project.tenant_id).first()
        if not tenant:
            print('Tenant not found')
            return
        
        print(f'\nPublishing tools...')
        success = await publish_scan_steps_to_runner(
            scan_job_id=scan_id,
            target_url=project.target_url,
            scan_level=scan_job.scan_level,
            org_id=tenant.id,
            project_id=project.id,
            background_tasks=None,  # No background tasks in manual call
        )
        
        if success:
            print(f'\n✅ Successfully published tools')
        else:
            print(f'\n❌ Failed to publish tools')
    finally:
        db.close()

if __name__ == '__main__':
    asyncio.run(main())

