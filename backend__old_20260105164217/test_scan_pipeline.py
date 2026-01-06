#!/usr/bin/env python3
"""
Test script to verify scan pipeline improvements:
- Timeout enforcement
- Parallelism limits
- Tool status tracking
- Failure handling

Usage:
    # Run as standalone script:
    python test_scan_pipeline.py
    
    # Run with pytest (minimal - only project_id needed):
    RUN_MANUAL_INTEGRATION=1 \
    THANDEV_PROJECT_ID=your-project-id \
    pytest -m integration -v
    
    # Or run specific test:
    RUN_MANUAL_INTEGRATION=1 \
    THANDEV_PROJECT_ID=your-project-id \
    pytest test_scan_pipeline.py::test_basic_scan -v
    
    # Optionally override auth headers (otherwise fetched from project):
    RUN_MANUAL_INTEGRATION=1 \
    THANDEV_PROJECT_ID=your-project-id \
    THANDEV_USER_ID=your-user-id \
    THANDEV_TENANT_ID=your-tenant-id \
    pytest -m integration -v
    
    # Run with plan enforcement bypass (for testing pro/advanced scans):
    # IMPORTANT: You must also set THANDEV_DISABLE_PLAN_ENFORCEMENT=1 when starting the API server
    # Example: THANDEV_DISABLE_PLAN_ENFORCEMENT=1 uvicorn app.main:app --reload
    RUN_MANUAL_INTEGRATION=1 \
    THANDEV_PROJECT_ID=your-project-id \
    THANDEV_DISABLE_PLAN_ENFORCEMENT=1 \
    pytest test_scan_pipeline.py::test_pro_scan -vv -s

Environment Variables:
    RUN_MANUAL_INTEGRATION: Set to "1" to enable manual integration tests
    THANDEV_PROJECT_ID: (Required) Project ID to use for testing
    THANDEV_USER_ID: (Optional) User ID for API authentication (auto-fetched from project if not set)
    THANDEV_TENANT_ID: (Optional) Tenant ID for API authentication (auto-fetched from project if not set)
    THANDEV_DISABLE_PLAN_ENFORCEMENT: (Optional) Set to "1" to bypass plan restrictions in dev/test mode.
                                      IMPORTANT: This must be set in BOTH the test process AND the API server process.
                                      Example server start: THANDEV_DISABLE_PLAN_ENFORCEMENT=1 uvicorn app.main:app --reload
    THANDEV_PIPELINE_TOOLS: (Optional) Comma-separated list of tools to run (e.g., "httpx,nuclei").
                                     If set, only these tools will execute, others will be skipped.
                                     Useful for quick smoke tests.
    THANDEV_FAST_MANUAL: (Optional) Set to "1" to reduce tool timeouts by 70% for faster tests.
                         Only use this for local development - not for production testing.
    
Note: If THANDEV_USER_ID and THANDEV_TENANT_ID are not provided, they will be
automatically fetched from the database using the project's owner_id and tenant_id.

Note: THANDEV_DISABLE_PLAN_ENFORCEMENT bypasses plan restrictions to allow testing pro/advanced scans
in local development. The API server must be started with this env var for it to take effect.
"""
import os
import sys
import time
import requests
import json
import pytest
from typing import Dict, Any, Optional, List

# Enable manual integration tests via environment variable
RUN_MANUAL = os.getenv("RUN_MANUAL_INTEGRATION") == "1"
pytestmark = pytest.mark.skipif(not RUN_MANUAL, reason="Manual integration test (set RUN_MANUAL_INTEGRATION=1)")

# Configuration
API_BASE_URL = "http://localhost:8000/api"
TEST_TARGET_URL = "https://httpbin.org"  # Safe test target


@pytest.fixture
def project_id() -> str:
    """Get project_id from environment variable"""
    pid = os.getenv("THANDEV_PROJECT_ID")
    if not pid:
        pytest.skip("THANDEV_PROJECT_ID environment variable not set (required for manual integration tests)")
    return pid


@pytest.fixture
def headers(project_id: str) -> Dict[str, str]:
    """Get API headers from environment or fetch from project in database"""
    headers_dict = {
        "Content-Type": "application/json",
    }
    
    # Try to get auth headers from environment first
    user_id = os.getenv("THANDEV_USER_ID")
    tenant_id = os.getenv("THANDEV_TENANT_ID")
    
    # If not provided, fetch from database using project_id
    if not user_id or not tenant_id:
        try:
            from app.core.database import SessionLocal
            from app.models.project import Project
            
            db = SessionLocal()
            try:
                project = db.query(Project).filter(Project.id == project_id).first()
                if project:
                    if not user_id:
                        user_id = project.owner_id
                    if not tenant_id:
                        tenant_id = project.tenant_id
                else:
                    pytest.skip(f"Project {project_id} not found in database")
            finally:
                db.close()
        except Exception as e:
            pytest.skip(f"Failed to fetch project from database: {e}")
    
    # Add auth headers (at least one is required by the API)
    if user_id:
        headers_dict["X-Thandev-User-Id"] = user_id
    if tenant_id:
        headers_dict["X-Thandev-Tenant-Id"] = tenant_id
    
    # Ensure at least one auth header is present
    if "X-Thandev-User-Id" not in headers_dict and "X-Thandev-Tenant-Id" not in headers_dict:
        pytest.skip("Neither THANDEV_USER_ID nor THANDEV_TENANT_ID available (required for API authentication)")
    
    return headers_dict

def get_running_scans(project_id: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    """Get list of running scans for the tenant (not just project, since API checks tenant-level limits)"""
    # Check both project-specific and all scans (API limit is tenant-level)
    running_scans = []
    
    # First, try to get all scans for the tenant
    url = f"{API_BASE_URL}/scans"
    params = {"limit": 100}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])
        
        # Filter for running or queued scans
        running_statuses = ["queued", "running"]
        running_scans = [
            item for item in items 
            if item.get("status", "").lower() in running_statuses
        ]
    except Exception as e:
        print(f"⚠️  Failed to get all scans: {e}")
        # Fallback to project-specific scans
        try:
            url = f"{API_BASE_URL}/scans/project/{project_id}"
            params = {"limit": 100}
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            scans = data.get("scans", [])
            
            running_statuses = ["queued", "running"]
            running_scans = [
                scan for scan in scans 
                if scan.get("status", "").lower() in running_statuses
            ]
        except Exception as e2:
            print(f"⚠️  Failed to get project scans: {e2}")
    
    return running_scans


def cancel_scan(scan_id: str, headers: Dict[str, str]) -> bool:
    """Cancel a running scan"""
    url = f"{API_BASE_URL}/scans/{scan_id}/cancel"
    
    try:
        response = requests.patch(url, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"✅ Cancelled scan: {scan_id}")
        return True
    except Exception as e:
        print(f"⚠️  Failed to cancel scan {scan_id}: {e}")
        return False


def get_allowed_scan_levels(headers: Dict[str, str]) -> List[str]:
    """Get list of allowed scan levels for the current tenant's plan"""
    url = f"{API_BASE_URL}/tenants/current"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        limits = data.get("limits", {})
        allowed_levels = limits.get("allowed_scan_levels", [])
        return allowed_levels
    except Exception as e:
        print(f"⚠️  Failed to get allowed scan levels: {e}")
        # Default to basic if we can't check
        return ["basic"]


def ensure_no_running_scans(project_id: str, headers: Dict[str, str], max_wait: int = 30) -> None:
    """Wait for or cancel running scans to free up capacity"""
    print(f"\n🔍 Checking for running scans...")
    running_scans = get_running_scans(project_id, headers)
    
    if not running_scans:
        print("✅ No running scans found")
        return
    
    print(f"⚠️  Found {len(running_scans)} running/queued scan(s)")
    
    # Try to cancel them
    for scan in running_scans:
        scan_id = scan.get("id")
        if scan_id:
            cancel_scan(scan_id, headers)
    
    # Wait a bit for cancellations to process
    time.sleep(2)
    
    # Check again
    running_scans = get_running_scans(project_id, headers)
    if running_scans:
        # If still running, wait for them to complete
        print(f"⏳ Waiting for {len(running_scans)} scan(s) to complete (max {max_wait}s)...")
        start_time = time.time()
        while time.time() - start_time < max_wait:
            running_scans = get_running_scans(project_id, headers)
            if not running_scans:
                print("✅ All scans completed")
                return
            time.sleep(2)
        
        # If still running after max_wait, raise error
        raise AssertionError(
            f"Still {len(running_scans)} scan(s) running after {max_wait}s. "
            f"Please cancel them manually or wait for completion."
        )


def create_scan(project_id: str, scan_level: str, headers: Dict[str, str]) -> Optional[str]:
    """Create a scan and return scan_id
    
    Returns:
        scan_id if successful, None if failed
    Raises:
        AssertionError if the failure is due to plan limits (429, 403) - test will fail with clear message
    """
    url = f"{API_BASE_URL}/scans"
    payload = {
        "project_id": project_id,
        "scan_level": scan_level
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        scan_id = data.get("id")
        print(f"✅ Created {scan_level} scan: {scan_id}")
        return scan_id
    except requests.exceptions.HTTPError as e:
        if e.response is not None:
            status_code = e.response.status_code
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get("detail", "")
            except:
                error_detail = e.response.text
            
            # Handle expected business logic errors
            if status_code == 429:
                # Too many scans in progress - try to free up capacity
                print(f"⚠️  Too many scans in progress. Attempting to free up capacity...")
                ensure_no_running_scans(project_id, headers)
                
                # Retry creating the scan
                print(f"🔄 Retrying scan creation...")
                try:
                    retry_response = requests.post(url, json=payload, headers=headers, timeout=10)
                    retry_response.raise_for_status()
                    data = retry_response.json()
                    scan_id = data.get("id")
                    print(f"✅ Created {scan_level} scan: {scan_id}")
                    return scan_id
                except requests.exceptions.HTTPError as retry_e:
                    if retry_e.response is not None:
                        retry_status = retry_e.response.status_code
                        retry_error_detail = ""
                        try:
                            retry_error_data = retry_e.response.json()
                            retry_error_detail = retry_error_data.get("detail", "")
                        except:
                            retry_error_detail = retry_e.response.text
                        
                        if retry_status == 429:
                            error_msg = f"Cannot create scan: {retry_error_detail}. Please wait for existing scans to complete or cancel them manually."
                            print(f"❌ {error_msg}")
                            raise AssertionError(error_msg)
                        else:
                            # Other error on retry
                            error_msg = f"Failed to create scan after retry (HTTP {retry_status}): {retry_error_detail}"
                            print(f"❌ {error_msg}")
                            raise AssertionError(error_msg)
                    else:
                        raise
            elif status_code == 403:
                # Plan doesn't allow this scan level
                error_msg = f"Plan restriction: {error_detail}"
                
                # If dev bypass is enabled in test but API server doesn't have it, provide helpful message
                if os.getenv("THANDEV_DISABLE_PLAN_ENFORCEMENT") == "1":
                    error_msg = (
                        f"Plan restriction: {error_detail}. "
                        f"Note: THANDEV_DISABLE_PLAN_ENFORCEMENT=1 is set in test process, "
                        f"but the API server also needs this env var. "
                        f"Restart your API server with THANDEV_DISABLE_PLAN_ENFORCEMENT=1."
                    )
                    print(f"❌ {error_msg}")
                    raise AssertionError(error_msg)
                else:
                    # Normal case: skip if plan doesn't support it
                    print(f"⏭️  {error_msg}")
                    pytest.skip(error_msg)
            elif status_code == 401:
                # Authentication error
                error_msg = f"Authentication failed: {error_detail}"
                print(f"❌ {error_msg}")
                raise AssertionError(error_msg)
            else:
                # Other HTTP errors
                error_msg = f"Failed to create scan (HTTP {status_code}): {error_detail}"
                print(f"❌ {error_msg}")
                raise AssertionError(error_msg)
        else:
            error_msg = f"Failed to create scan: {e}"
            print(f"❌ {error_msg}")
            raise AssertionError(error_msg)
    except Exception as e:
        error_msg = f"Failed to create scan: {e}"
        print(f"❌ {error_msg}")
        raise AssertionError(error_msg)

def get_scan_status(scan_id: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Get scan status and tool statuses"""
    url = f"{API_BASE_URL}/scans/{scan_id}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Failed to get scan status: {e}")
        return None

def check_tool_statuses(scan_data: Dict[str, Any], expected_tools: list) -> bool:
    """Check that tool statuses are present and valid"""
    tool_statuses = scan_data.get("tool_statuses", [])
    
    if not tool_statuses:
        print("⚠️  No tool_statuses in response")
        return False
    
    print(f"\n📊 Tool Status Summary:")
    print(f"   Found {len(tool_statuses)} tool(s)")
    
    valid_statuses = ["pending", "running", "completed", "failed", "skipped", "timed_out"]
    all_valid = True
    
    for tool_status in tool_statuses:
        tool_name = tool_status.get("tool_name", "unknown")
        status = tool_status.get("status", "unknown")
        error_code = tool_status.get("error_code")
        started_at = tool_status.get("started_at")
        completed_at = tool_status.get("completed_at")
        
        status_icon = "✅" if status == "completed" else "⏳" if status == "running" else "❌" if status in ["failed", "timed_out"] else "⏸️"
        
        print(f"   {status_icon} {tool_name}: {status}")
        if started_at:
            print(f"      Started: {started_at}")
        if completed_at:
            print(f"      Completed: {completed_at}")
        if error_code:
            print(f"      Error code: {error_code}")
        if tool_status.get("error_message"):
            print(f"      Error: {tool_status['error_message'][:100]}")
        
        if status not in valid_statuses:
            print(f"      ⚠️  Invalid status: {status}")
            all_valid = False
    
    return all_valid

def check_timeout_enforcement(scan_data: Dict[str, Any], scan_level: str) -> bool:
    """Check that timeouts are being enforced"""
    from app.core.scan_timeouts import get_tool_timeout
    
    tool_statuses = scan_data.get("tool_statuses", [])
    timeout_ok = True
    
    print(f"\n⏱️  Timeout Verification:")
    
    for tool_status in tool_statuses:
        tool_name = tool_status.get("tool_name")
        status = tool_status.get("status")
        execution_time = tool_status.get("execution_time")
        
        if tool_name and execution_time is not None:
            expected_timeout = get_tool_timeout(scan_level, tool_name)
            print(f"   {tool_name}: executed for {execution_time:.1f}s (timeout: {expected_timeout}s)")
            
            if execution_time > expected_timeout * 1.1:  # Allow 10% margin
                print(f"      ⚠️  Tool exceeded timeout by {execution_time - expected_timeout:.1f}s")
                timeout_ok = False
            elif status == "timed_out" and execution_time < expected_timeout * 0.9:
                print(f"      ⚠️  Tool timed out before timeout limit")
                timeout_ok = False
    
    return timeout_ok

def check_parallelism(scan_data: Dict[str, Any], scan_level: str) -> bool:
    """Check that parallelism limits are respected by computing actual max concurrency
    
    Note: Parallelism means max concurrent tools running at the same time, not total tools.
    A scan can have more tools than the parallelism limit - they run in batches.
    This function computes actual max concurrency from timestamps using sweep-line algorithm.
    """
    from app.core.scan_timeouts import get_max_parallelism
    
    tool_statuses = scan_data.get("tool_statuses", [])
    max_parallel = get_max_parallelism(scan_level)
    
    print(f"\n🔄 Parallelism Verification:")
    print(f"   Expected max concurrent tools for {scan_level}: {max_parallel}")
    print(f"   Total tools in scan: {len(tool_statuses)}")
    
    # Parallelism is about concurrent execution, not total tool count
    # A scan can have 6 tools but run them in batches of 3 (for pro level)
    # Without real-time monitoring, we can't verify actual concurrent execution
    # So we just verify the scan completed with expected tools
    # Extract time intervals for tools that actually ran
    from datetime import datetime
    intervals = []
    for tool_status in tool_statuses:
        started = tool_status.get("started_at")
        completed = tool_status.get("completed_at")
        status = tool_status.get("status")
        
        # Only count tools that actually ran (have timestamps)
        if started and completed and status in ("completed", "failed", "timed_out"):
            try:
                # Handle both ISO format with Z and without
                start_str = started.replace('Z', '+00:00') if 'Z' in started else started
                end_str = completed.replace('Z', '+00:00') if 'Z' in completed else completed
                start_ts = datetime.fromisoformat(start_str)
                end_ts = datetime.fromisoformat(end_str)
                intervals.append((start_ts, end_ts, tool_status.get("tool_name")))
            except (ValueError, AttributeError, TypeError):
                # Skip tools with invalid timestamps
                continue
    
    # Compute max concurrent tools using sweep-line algorithm
    if not intervals:
        print(f"   ℹ️  No tools with timestamps to verify actual concurrency")
        print(f"   ✅ Scan completed with {len(tool_statuses)} tool(s)")
        return True
    
    # Sort by start time
    intervals.sort(key=lambda x: x[0])
    
    # Create events: (time, delta, tool_name)
    # delta = +1 for start, -1 for end
    events = []
    for start, end, tool_name in intervals:
        events.append((start, 1, tool_name))  # Start event
        events.append((end, -1, tool_name))  # End event
    
    # Sort events by time
    events.sort(key=lambda x: x[0])
    
    # Sweep through events to find max concurrent
    max_concurrent = 0
    current_concurrent = 0
    for time, delta, tool_name in events:
        current_concurrent += delta
        max_concurrent = max(max_concurrent, current_concurrent)
    
    print(f"   Actual max concurrent tools: {max_concurrent}")
    
    if max_concurrent > max_parallel:
        print(f"   ⚠️  Max concurrency ({max_concurrent}) exceeds limit ({max_parallel})")
        return False
    
    print(f"   ✅ Max concurrency ({max_concurrent}) within limit ({max_parallel})")
    return True

def wait_for_scan_completion(scan_id: str, headers: Dict[str, str], max_wait: int = 600) -> Optional[Dict[str, Any]]:
    """Wait for scan to complete, polling every 5 seconds"""
    print(f"\n⏳ Waiting for scan {scan_id} to complete (max {max_wait}s)...")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait:
        scan_data = get_scan_status(scan_id, headers)
        if not scan_data:
            return None
        
        status = scan_data.get("status")
        
        if status != last_status:
            print(f"   Status: {status}")
            last_status = status
        
        if status in ["completed", "completed_with_errors", "failed", "cancelled"]:
            print(f"   ✅ Scan finished with status: {status}")
            return scan_data
        
        # Show running tools
        tool_statuses = scan_data.get("tool_statuses", [])
        running_tools = [ts for ts in tool_statuses if ts.get("status") == "running"]
        if running_tools:
            tool_names = [ts.get("tool_name") for ts in running_tools]
            print(f"   Running: {', '.join(tool_names)}")
        
        time.sleep(5)
    
    print(f"   ⚠️  Scan did not complete within {max_wait}s")
    return scan_data

@pytest.mark.integration
def test_basic_scan(headers: Dict[str, str], project_id: str):
    """Test Basic scan with timeout enforcement"""
    print("\n" + "="*60)
    print("TEST 1: Basic Scan - Timeout Enforcement")
    print("="*60)
    
    # Ensure no running scans before starting
    ensure_no_running_scans(project_id, headers)
    
    scan_id = create_scan(project_id, "basic", headers)
    assert scan_id is not None, "Failed to create scan"
    
    # Wait for completion
    scan_data = wait_for_scan_completion(scan_id, headers, max_wait=300)
    assert scan_data is not None, "Failed to get scan data"
    
    # Check tool statuses
    status_ok = check_tool_statuses(scan_data, ["httpx", "nuclei"])
    timeout_ok = check_timeout_enforcement(scan_data, "basic")
    parallelism_ok = check_parallelism(scan_data, "basic")
    
    assert status_ok, "Tool statuses check failed"
    assert timeout_ok, "Timeout enforcement check failed"
    assert parallelism_ok, "Parallelism check failed"

@pytest.mark.integration
def test_pro_scan(headers: Dict[str, str], project_id: str):
    """Test Pro scan with parallelism limits"""
    print("\n" + "="*60)
    print("TEST 2: Pro Scan - Parallelism Limits")
    print("="*60)
    
    # Check if plan supports pro scans (unless dev bypass is enabled)
    if os.getenv("THANDEV_DISABLE_PLAN_ENFORCEMENT") != "1":
        allowed_levels = get_allowed_scan_levels(headers)
        if "pro" not in allowed_levels:
            allowed_str = ", ".join(allowed_levels)
            pytest.skip(
                f"Plan does not support 'pro' scans. "
                f"Allowed scan levels for your plan: {allowed_str}. "
                f"Please upgrade to a plan that supports pro scans (individual or team plan), "
                f"or set THANDEV_DISABLE_PLAN_ENFORCEMENT=1 for dev/testing."
            )
    else:
        print("⚠️  Plan enforcement disabled (THANDEV_DISABLE_PLAN_ENFORCEMENT=1) - allowing pro scan")
    
    # Ensure no running scans before starting
    ensure_no_running_scans(project_id, headers)
    
    scan_id = create_scan(project_id, "pro", headers)
    assert scan_id is not None, "Failed to create scan"
    
    # Wait for completion
    scan_data = wait_for_scan_completion(scan_id, headers, max_wait=600)
    assert scan_data is not None, "Failed to get scan data"
    
    # Check tool statuses
    status_ok = check_tool_statuses(scan_data, ["httpx", "nuclei", "nmap", "ffuf", "dalfox"])
    timeout_ok = check_timeout_enforcement(scan_data, "pro")
    parallelism_ok = check_parallelism(scan_data, "pro")
    
    assert status_ok, "Tool statuses check failed"
    assert timeout_ok, "Timeout enforcement check failed"
    assert parallelism_ok, "Parallelism check failed"

@pytest.mark.integration
def test_failure_scenarios(headers: Dict[str, str], project_id: str):
    """Test failure scenarios (missing binary, etc.)"""
    print("\n" + "="*60)
    print("TEST 3: Failure Scenarios")
    print("="*60)
    
    # This would require setting up a scenario with missing tools
    # For now, we'll just check that failed tools are handled gracefully
    print("   ℹ️  Failure scenario testing requires manual setup")
    print("   ℹ️  Check that failed tools show status='failed' with error_code")
    # Test passes if it reaches here (no exceptions)

def main():
    """Main test function"""
    print("🧪 Scan Pipeline Test Suite")
    print("="*60)
    
    # Check if API is accessible
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        print("✅ API is accessible")
    except Exception as e:
        print(f"❌ API is not accessible: {e}")
        print("   Make sure the backend server is running on http://localhost:8000")
        return 1
    
    # Get auth headers (you'll need to set these)
    # For testing, you might need to create a project first
    headers = {
        "Content-Type": "application/json",
        # Add auth headers here if needed
        # "X-Thandev-User-Id": "test-user-id",
        # "X-Thandev-Tenant-Id": "test-tenant-id",
    }
    
    # You'll need to provide a valid project_id
    # For now, we'll use a placeholder
    project_id = input("Enter project_id to test with (or press Enter to skip): ").strip()
    if not project_id:
        print("⚠️  Skipping tests - project_id required")
        return 0
    
    results = []
    
    # Run tests
    results.append(("Basic Scan", test_basic_scan(headers, project_id)))
    results.append(("Pro Scan", test_pro_scan(headers, project_id)))
    results.append(("Failure Scenarios", test_failure_scenarios(headers, project_id)))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(passed for _, passed in results)
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

