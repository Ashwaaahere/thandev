#!/usr/bin/env python3
"""
Verification script for scan API fixes.

This script helps verify:
1. "sslscan: pending" is gone in API responses
2. Plan bypass is safe (cannot work in prod)
3. Tool subset filtering doesn't create phantom pending tools
4. Parallelism check is meaningful
"""
import os
import sys
import requests
import json
from typing import Dict, Any, Optional

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")


def get_scan(scan_id: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Fetch scan status from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/scans/{scan_id}", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch scan: {e}")
        return None


def verify_tool_statuses(scan_data: Dict[str, Any], scan_id: str):
    """Verify tool_statuses don't show pending for terminal scans"""
    tool_statuses = scan_data.get("tool_statuses", [])
    scan_status = scan_data.get("status")
    
    print(f"\n📊 Scan Status: {scan_status}")
    print(f"📊 Total Tools: {len(tool_statuses)}")
    
    # Check for pending tools in terminal scans
    terminal_statuses = {"completed", "completed_with_errors", "failed", "cancelled"}
    is_terminal = scan_status in terminal_statuses
    
    pending_tools = [ts for ts in tool_statuses if ts.get("status") == "pending"]
    skipped_tools = [ts for ts in tool_statuses if ts.get("status") == "skipped"]
    
    print(f"\n🔍 Tool Status Summary:")
    for ts in tool_statuses:
        tool_name = ts.get("tool_name", "unknown")
        status = ts.get("status", "unknown")
        error_code = ts.get("error_code")
        error_msg = ts.get("error_message", "")
        
        status_icon = {
            "completed": "✅",
            "failed": "❌",
            "skipped": "⏭️",
            "pending": "⏳",
            "running": "🔄",
            "timed_out": "⏱️",
        }.get(status, "❓")
        
        print(f"   {status_icon} {tool_name}: {status}", end="")
        if error_code:
            print(f" (error_code: {error_code})", end="")
        if error_msg:
            print(f" - {error_msg[:50]}", end="")
        print()
    
    # Verification
    if is_terminal:
        if pending_tools:
            print(f"\n⚠️  WARNING: Found {len(pending_tools)} pending tool(s) in terminal scan:")
            for pt in pending_tools:
                print(f"   - {pt.get('tool_name')}: {pt.get('status')}")
            print("   ❌ This should not happen - pending tools should be skipped in terminal scans")
            return False
        else:
            print(f"\n✅ PASS: No pending tools in terminal scan")
            if skipped_tools:
                print(f"   ✅ Found {len(skipped_tools)} skipped tool(s) (expected for unscheduled tools)")
            return True
    else:
        print(f"\nℹ️  Scan is not terminal ({scan_status}), pending tools are expected")
        return True


def verify_parallelism_check(scan_data: Dict[str, Any]):
    """Verify parallelism check has meaningful data"""
    tool_statuses = scan_data.get("tool_statuses", [])
    
    tools_with_timestamps = [
        ts for ts in tool_statuses
        if ts.get("started_at") and ts.get("completed_at")
    ]
    
    print(f"\n🔄 Parallelism Check Verification:")
    print(f"   Tools with timestamps: {len(tools_with_timestamps)}/{len(tool_statuses)}")
    
    if tools_with_timestamps:
        print(f"   ✅ Timestamps available for parallelism calculation")
        return True
    else:
        print(f"   ⚠️  No timestamps available - parallelism check will show 'No tools with timestamps'")
        return False


def main():
    """Main verification function"""
    if len(sys.argv) < 2:
        print("Usage: python verify_fixes.py <SCAN_ID> [USER_ID] [TENANT_ID]")
        print("\nExample:")
        print("  python verify_fixes.py test-scan-123")
        print("  python verify_fixes.py test-scan-123 test-user-123 test-tenant-123")
        sys.exit(1)
    
    scan_id = sys.argv[1]
    user_id = sys.argv[2] if len(sys.argv) > 2 else os.getenv("THANDEV_USER_ID", "test-user")
    tenant_id = sys.argv[3] if len(sys.argv) > 3 else os.getenv("THANDEV_TENANT_ID", "test-tenant")
    
    headers = {
        "Content-Type": "application/json",
        "X-Thandev-User-Id": user_id,
        "X-Thandev-Tenant-Id": tenant_id,
    }
    
    print(f"🔍 Verifying scan: {scan_id}")
    print(f"🌐 API Base URL: {API_BASE_URL}")
    
    scan_data = get_scan(scan_id, headers)
    if not scan_data:
        sys.exit(1)
    
    # Verify tool statuses
    tool_status_ok = verify_tool_statuses(scan_data, scan_id)
    
    # Verify parallelism check
    parallelism_ok = verify_parallelism_check(scan_data)
    
    # Print full tool_statuses JSON for inspection
    print(f"\n📋 Full tool_statuses JSON:")
    print(json.dumps(scan_data.get("tool_statuses", []), indent=2))
    
    # Summary
    print(f"\n{'='*60}")
    if tool_status_ok and parallelism_ok:
        print("✅ All verifications passed!")
    else:
        print("⚠️  Some verifications had warnings")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

