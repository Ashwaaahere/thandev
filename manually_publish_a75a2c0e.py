#!/usr/bin/env python3
"""Manually publish steps for scan A75A2C0E"""
import asyncio
import sys
import os
sys.path.insert(0, '/app')

os.environ.setdefault('REDIS_URL', 'redis://thandev-redis:6379')

async def main():
    scan_id = 'A75A2C0E'
    
    from app.services.runner_client import publish_scan_steps_to_runner
    from app.models.scan import ScanJob
    from app.models.project import Project
    from app.models.tenant import Tenant
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        # Find scan by partial ID
        from sqlalchemy import text
        query = text('SELECT id FROM scan_jobs WHERE UPPER(id) LIKE :sid ORDER BY created_at DESC LIMIT 1')
        result = db.execute(query, {'sid': f'%{scan_id}%'}).fetchone()
        if not result:
            print(f'Scan {scan_id} not found')
            return
        
        exact_id = result[0]
        print(f'Found scan: {exact_id}')
        
        scan_job = db.query(ScanJob).filter(ScanJob.id == exact_id).first()
        if not scan_job:
            print('Scan job not found')
            return
        
        print(f'Scan: {scan_job.url}, Level: {scan_job.scan_level}, Status: {scan_job.status}')
        
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
            scan_job_id=exact_id,
            target_url=project.target_url,
            scan_level=scan_job.scan_level,
            org_id=tenant.id,
            project_id=project.id,
            background_tasks=None,
        )
        
        if success:
            print(f'\n✅ Successfully published tools')
        else:
            print(f'\n❌ Failed to publish tools')
    finally:
        db.close()

if __name__ == '__main__':
    asyncio.run(main())

