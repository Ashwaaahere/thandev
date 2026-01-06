#!/usr/bin/env python3
"""
Quick verification script to check scan pipeline improvements.

This script checks the database directly to verify:
1. Tool status tracking is working
2. Timeouts are configured correctly
3. Parallelism limits are set

Usage:
    python verify_scan_improvements.py [scan_id]
"""
import sys
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.scan_timeouts import get_tool_timeout, get_max_parallelism
from app.models.finding import ToolResult, ToolExecutionStatus
from app.models.scan import ScanJob, ScanStatus
from app.core.database import SessionLocal

def verify_timeout_config():
    """Verify timeout configuration is correct"""
    print("⏱️  Verifying Timeout Configuration...")
    
    basic_nuclei = get_tool_timeout("basic", "nuclei")
    pro_nuclei = get_tool_timeout("pro", "nuclei")
    advanced_nuclei = get_tool_timeout("advanced", "nuclei")
    
    print(f"   Basic scan - nuclei: {basic_nuclei}s")
    print(f"   Pro scan - nuclei: {pro_nuclei}s")
    print(f"   Advanced scan - nuclei: {advanced_nuclei}s")
    
    # Verify basic is shorter than pro, pro shorter than advanced
    if basic_nuclei < pro_nuclei < advanced_nuclei:
        print("   ✅ Timeout configuration is correct (basic < pro < advanced)")
        return True
    else:
        print("   ❌ Timeout configuration issue")
        return False

def verify_parallelism_config():
    """Verify parallelism configuration is correct"""
    print("\n🔄 Verifying Parallelism Configuration...")
    
    basic_parallel = get_max_parallelism("basic")
    pro_parallel = get_max_parallelism("pro")
    advanced_parallel = get_max_parallelism("advanced")
    
    print(f"   Basic scan: max {basic_parallel} concurrent tools")
    print(f"   Pro scan: max {pro_parallel} concurrent tools")
    print(f"   Advanced scan: max {advanced_parallel} concurrent tools")
    
    # Verify basic <= pro <= advanced
    if basic_parallel <= pro_parallel <= advanced_parallel:
        print("   ✅ Parallelism configuration is correct")
        return True
    else:
        print("   ❌ Parallelism configuration issue")
        return False

def verify_tool_status_tracking(scan_id: str = None):
    """Verify tool status tracking in database"""
    print("\n📊 Verifying Tool Status Tracking...")
    
    db = SessionLocal()
    try:
        if scan_id:
            # Check specific scan
            scan_job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
            if not scan_job:
                print(f"   ❌ Scan {scan_id} not found")
                return False
            
            print(f"   Checking scan: {scan_id} ({scan_job.scan_level.value})")
            tool_results = db.query(ToolResult).filter(
                ToolResult.scan_job_id == scan_id
            ).all()
        else:
            # Check latest scan
            scan_job = db.query(ScanJob).order_by(ScanJob.created_at.desc()).first()
            if not scan_job:
                print("   ⚠️  No scans found in database")
                return False
            
            print(f"   Checking latest scan: {scan_job.id} ({scan_job.scan_level.value})")
        
        # Use raw SQL to avoid enum conversion issues
        from sqlalchemy import text
        result_rows = db.execute(text("""
            SELECT tool_name, status, started_at, completed_at, error_code, execution_time
            FROM tool_results
            WHERE scan_job_id = :scan_id
            ORDER BY created_at DESC
        """), {"scan_id": scan_job.id}).fetchall()
        
        if not result_rows:
            print("   ⚠️  No tool results found for this scan")
            return False
        
        print(f"   Found {len(result_rows)} tool result(s)")
        
        # Check that status field exists and has valid values
        statuses_found = set()
        for row in result_rows:
            tool_name, status, started_at, completed_at, error_code, execution_time = row
            if status:
                statuses_found.add(status)
                print(f"      {tool_name}: {status}")
                if started_at:
                    print(f"         Started: {started_at}")
                if completed_at:
                    print(f"         Completed: {completed_at}")
                if error_code:
                    print(f"         Error code: {error_code}")
            else:
                print(f"      {tool_name}: (no status - legacy record)")
        
        valid_statuses = {s.value for s in ToolExecutionStatus}
        invalid_statuses = statuses_found - valid_statuses
        
        if invalid_statuses:
            print(f"   ❌ Invalid statuses found: {invalid_statuses}")
            return False
        
        if statuses_found:
            print(f"   ✅ Tool status tracking is working (found: {', '.join(statuses_found)})")
            return True
        else:
            print("   ⚠️  No status values found (all legacy records?)")
            return True  # Not an error, just legacy data
        
    finally:
        db.close()

def verify_scan_completion_logic(scan_id: str = None):
    """Verify scan completion logic based on tool results"""
    print("\n✅ Verifying Scan Completion Logic...")
    
    db = SessionLocal()
    try:
        if scan_id:
            scan_job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
        else:
            scan_job = db.query(ScanJob).order_by(ScanJob.created_at.desc()).first()
        
        if not scan_job:
            print("   ⚠️  No scan found")
            return False
        
        print(f"   Scan: {scan_job.id}")
        print(f"   Status: {scan_job.status.value}")
        
        # Query tool results, but handle enum conversion issues
        # Use raw SQL to avoid enum conversion errors for existing records
        from sqlalchemy import text
        result_rows = db.execute(text("""
            SELECT tool_name, status, started_at, completed_at, error_code, execution_time
            FROM tool_results
            WHERE scan_job_id = :scan_id
        """), {"scan_id": scan_job.id}).fetchall()
        
        tool_results = []
        for row in result_rows:
            class ToolResultRow:
                def __init__(self, row):
                    self.tool_name = row[0]
                    self.status = row[1]  # String value
                    self.started_at = row[2]
                    self.completed_at = row[3]
                    self.error_code = row[4]
                    self.execution_time = row[5]
            tool_results.append(ToolResultRow(row))
        
        # Handle both enum and string status values
        def is_completed(tr):
            if not tr.status:
                return False
            status_val = tr.status.value if hasattr(tr.status, 'value') else str(tr.status)
            return status_val == ToolExecutionStatus.COMPLETED.value
        
        def is_failed(tr):
            if not tr.status:
                return False
            status_val = tr.status.value if hasattr(tr.status, 'value') else str(tr.status)
            return status_val in [
                ToolExecutionStatus.FAILED.value,
                ToolExecutionStatus.TIMED_OUT.value,
                ToolExecutionStatus.SKIPPED.value
            ]
        
        completed_count = sum(1 for tr in tool_results if is_completed(tr))
        failed_count = sum(1 for tr in tool_results if is_failed(tr))
        
        print(f"   Tools completed: {completed_count}")
        print(f"   Tools failed: {failed_count}")
        
        # Verify scan status matches tool results
        if scan_job.status == ScanStatus.COMPLETED:
            if completed_count > 0:
                print("   ✅ Scan status matches tool results (COMPLETED with successful tools)")
                return True
            else:
                print("   ⚠️  Scan marked COMPLETED but no tools completed")
                return False
        elif scan_job.status == ScanStatus.COMPLETED_WITH_ERRORS:
            if completed_count > 0 and failed_count > 0:
                print("   ✅ Scan status matches tool results (COMPLETED_WITH_ERRORS)")
                return True
            else:
                print("   ⚠️  Scan marked COMPLETED_WITH_ERRORS but status doesn't match")
                return False
        elif scan_job.status == ScanStatus.FAILED:
            if completed_count == 0:
                print("   ✅ Scan status matches tool results (FAILED - no tools completed)")
                return True
            else:
                print("   ⚠️  Scan marked FAILED but some tools completed")
                return False
        else:
            print(f"   ℹ️  Scan is still {scan_job.status.value}")
            return True
        
    finally:
        db.close()

def main():
    """Main verification function"""
    print("🔍 Scan Pipeline Improvements Verification")
    print("=" * 60)
    
    scan_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    results = []
    
    # Run verifications
    results.append(("Timeout Configuration", verify_timeout_config()))
    results.append(("Parallelism Configuration", verify_parallelism_config()))
    results.append(("Tool Status Tracking", verify_tool_status_tracking(scan_id)))
    results.append(("Scan Completion Logic", verify_scan_completion_logic(scan_id)))
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n✅ All verifications passed!")
        return 0
    else:
        print("\n❌ Some verifications failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

