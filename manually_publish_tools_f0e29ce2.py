#!/usr/bin/env python3
"""Manually publish tools for scan F0E29CE2 that's stuck in prepare stage"""
import os
import asyncio
import sys
sys.path.insert(0, '/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set up database
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres.kooxcykmlwonxqdushgt:6ySBsM6lRK8JSMQu@aws-0-us-west-2.pooler.supabase.com:6543/postgres')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# Import after setting up path
os.environ.setdefault('REDIS_URL', 'redis://thandev-redis:6379')

async def main():
    scan_id = 'f0e29ce2-d46a-4965-8df6-c79b5fe591cd'
    
    print(f'=== Manually Publishing Tools for Scan {scan_id} ===\n')
    
    # Import here to avoid issues
    from app.services.runner_client import publish_scan_steps_to_runner
    from app.core.tool_matrix import get_tools_for_level
    from app.models.scan import ScanLevel
    
    # Get scan details
    session = Session()
    try:
        from app.models.scan import ScanJob
        scan_job = session.query(ScanJob).filter(ScanJob.id == scan_id).first()
        
        if not scan_job:
            print(f'Scan {scan_id} not found')
            return
        
        print(f'Scan found:')
        print(f'  URL: {scan_job.url}')
        print(f'  Level: {scan_job.scan_level}')
        print(f'  Status: {scan_job.status}')
        
        # Get tools for this scan level
        scan_level = scan_job.scan_level
        tools = get_tools_for_level(scan_level)
        
        print(f'\nFound {len(tools)} tools for level {scan_level}')
        
        # Get project
        from app.models.project import Project
        project = session.query(Project).filter(Project.id == scan_job.project_id).first()
        
        if not project:
            print(f'Project not found for scan')
            return
        
        # Get tenant
        from app.models.tenant import Tenant
        tenant = session.query(Tenant).filter(Tenant.id == project.tenant_id).first()
        
        if not tenant:
            print(f'Tenant not found for project')
            return
        
        print(f'\nPublishing tools to Redis...')
        
        # Publish tools (this will check enumeration and publish accordingly)
        success = await publish_scan_steps_to_runner(
            scan_job_id=scan_id,
            target_url=project.target_url,
            scan_level=scan_level,
            org_id=tenant.id,
            project_id=project.id,
        )
        
        if success:
            print(f'\n✅ Successfully published tools for scan {scan_id}')
        else:
            print(f'\n❌ Failed to publish tools for scan {scan_id}')
            
    finally:
        session.close()

if __name__ == '__main__':
    asyncio.run(main())

