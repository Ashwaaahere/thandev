#!/usr/bin/env python3
"""
Fix stale scans that are marked as RUNNING but should be COMPLETED.

This script:
1. Finds scans with status=RUNNING that have brain_session_id
2. Checks brain session status
3. If brain session is completed, updates scan status
4. If all tools are done, marks scan as completed (fallback)
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Change to backend directory so relative database paths work
import os
os.chdir(backend_path)

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models.scan import ScanJob, ScanStatus
from app.models.finding import ToolResult, ToolExecutionStatus
from datetime import datetime
import asyncio
from app.services.brain_client import get_brain_client
from app.core.config import settings

# Ensure database tables exist
from app.models.scan import Base as ScanBase
from app.models.finding import Base as FindingBase
ScanBase.metadata.create_all(bind=engine)
FindingBase.metadata.create_all(bind=engine)

async def check_and_fix_scan(scan_job: ScanJob, db: Session) -> bool:
    """Check a single scan and fix if needed. Returns True if fixed."""
    print(f"\nChecking scan {scan_job.id} (status: {scan_job.status.value})")
    
    # Check if scan has brain session
    if not scan_job.brain_session_id:
        print(f"  No brain_session_id, skipping")
        return False
    
    # Check brain session status
    if settings.BRAIN_SERVICE_ENABLED:
        try:
            brain_client = get_brain_client()
            session_status = await brain_client.get_session(
                session_id=scan_job.brain_session_id,
                org_id=scan_job.project.tenant_id if scan_job.project else None,
                project_id=scan_job.project_id,
            )
            
            brain_status = session_status.get("status", "running")
            print(f"  Brain session status: {brain_status}")
            
            if brain_status == "completed":
                if scan_job.status != ScanStatus.COMPLETED:
                    print(f"  ✅ Fixing: Brain session is completed, updating scan status")
                    scan_job.status = ScanStatus.COMPLETED
                    if not scan_job.completed_at:
                        scan_job.completed_at = datetime.utcnow()
                    db.commit()
                    return True
            elif brain_status in ["failed", "cancelled", "stopped"]:
                if scan_job.status == ScanStatus.RUNNING:
                    print(f"  ✅ Fixing: Brain session is {brain_status}, updating scan status")
                    if brain_status == "failed":
                        scan_job.status = ScanStatus.FAILED
                    else:
                        scan_job.status = ScanStatus.CANCELLED
                    if not scan_job.completed_at:
                        scan_job.completed_at = datetime.utcnow()
                    db.commit()
                    return True
        except Exception as e:
            print(f"  ⚠️  Error checking brain session: {e}")
    
    # Fallback: Check if all tools are done
    tool_results = db.query(ToolResult).filter(
        ToolResult.scan_job_id == scan_job.id
    ).all()
    
    if tool_results:
        # Get latest status for each tool
        tool_statuses = {}
        for tr in tool_results:
            tool_name = tr.tool_name
            if tool_name not in tool_statuses or (tr.created_at and tool_statuses[tool_name].created_at < tr.created_at):
                tool_statuses[tool_name] = tr
        
        # Check if all tools are in terminal states
        all_tools_done = True
        for tool_name, tr in tool_statuses.items():
            if tr.status and tr.status not in [
                ToolExecutionStatus.COMPLETED,
                ToolExecutionStatus.FAILED,
                ToolExecutionStatus.SKIPPED,
                ToolExecutionStatus.TIMED_OUT
            ]:
                all_tools_done = False
                break
        
        if all_tools_done and scan_job.status == ScanStatus.RUNNING:
            print(f"  ✅ Fixing: All {len(tool_statuses)} tools are done, marking scan as completed")
            scan_job.status = ScanStatus.COMPLETED
            if not scan_job.completed_at:
                scan_job.completed_at = datetime.utcnow()
            db.commit()
            return True
        else:
            print(f"  ℹ️  Tools status: {len(tool_statuses)} tools, all_done={all_tools_done}")
            for tool_name, tr in tool_statuses.items():
                status_val = tr.status.value if tr.status and hasattr(tr.status, 'value') else str(tr.status)
                print(f"    - {tool_name}: {status_val}")
    else:
        print(f"  ℹ️  No tool results found")
    
    return False

async def main():
    """Main function"""
    db = SessionLocal()
    try:
        # First, list all scans to see what we have
        all_scans = db.query(ScanJob).order_by(ScanJob.created_at.desc()).limit(10).all()
        print(f"\nRecent scans (last 10):")
        for scan in all_scans:
            print(f"  - {scan.id[:8]}... | status={scan.status.value} | brain_session_id={scan.brain_session_id[:8] if scan.brain_session_id else 'None'}... | created={scan.created_at}")
        
        # Find all scans with status=RUNNING that have brain_session_id
        stale_scans = db.query(ScanJob).filter(
            ScanJob.status == ScanStatus.RUNNING,
            ScanJob.brain_session_id.isnot(None)
        ).all()
        
        print(f"\nFound {len(stale_scans)} scans with status=RUNNING and brain_session_id")
        
        # Also check scans that are RUNNING without brain_session_id (might be Celery-based)
        running_no_brain = db.query(ScanJob).filter(
            ScanJob.status == ScanStatus.RUNNING,
            ScanJob.brain_session_id.is_(None)
        ).all()
        print(f"Found {len(running_no_brain)} scans with status=RUNNING but no brain_session_id")
        
        if not stale_scans:
            if running_no_brain:
                print(f"\n⚠️  Found {len(running_no_brain)} scans running without brain_session_id - these might be Celery-based")
            else:
                print("\n✅ No stale scans found! All scans are properly completed or not running.")
            return
        
        fixed_count = 0
        for scan_job in stale_scans:
            try:
                if await check_and_fix_scan(scan_job, db):
                    fixed_count += 1
            except Exception as e:
                print(f"  ❌ Error processing scan {scan_job.id}: {e}")
                db.rollback()
        
        print(f"\n✅ Fixed {fixed_count} out of {len(stale_scans)} scans")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())

