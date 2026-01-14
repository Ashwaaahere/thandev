#!/usr/bin/env python3
"""
Test script to verify basic scan works and findings are parsed correctly
"""
import requests
import time
import json
import sys
import uuid

API_URL = "http://localhost:8000/api"

# Generate test user and tenant IDs (UUIDs)
TEST_USER_ID = str(uuid.uuid4())
TEST_TENANT_ID = str(uuid.uuid4())

def check_backend():
    """Check if backend is running"""
    try:
        r = requests.get(f"{API_URL.replace('/api', '')}/health", timeout=5)
        if r.status_code == 200:
            print("✅ Backend is running")
            return True
        else:
            print(f"❌ Backend health check failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend not reachable: {e}")
        return False

def create_project():
    """Create or get existing test project"""
    print("\n📦 Creating/getting test project...")
    headers = {
        "X-Thandev-User-Id": TEST_USER_ID,
        "X-Thandev-Tenant-Id": TEST_TENANT_ID,
        "Content-Type": "application/json"
    }
    try:
        # Try to get existing projects first
        r = requests.get(f"{API_URL}/projects", headers=headers, timeout=10)
        if r.status_code == 200:
            projects = r.json().get("items", [])
            for p in projects:
                if "test" in p.get("name", "").lower():
                    print(f"✅ Using existing project: {p['id']} - {p['name']}")
                    return p["id"]
        
        # Create new project (use httpbin.org as a test target)
        r = requests.post(f"{API_URL}/projects", headers=headers, json={
            "name": "Test Project - Basic Scan",
            "target_url": "https://httpbin.org",
            "description": "Test project for basic scan verification"
        }, timeout=10)
        
        if r.status_code == 201:
            pid = r.json()["id"]
            print(f"✅ Project created: {pid}")
            return pid
        else:
            print(f"❌ Failed to create project: {r.status_code} - {r.text}")
            return None
    except Exception as e:
        print(f"❌ Error creating project: {e}")
        return None

def start_basic_scan(project_id):
    """Start a basic scan"""
    print(f"\n🔍 Starting basic scan for project {project_id}...")
    headers = {
        "X-Thandev-User-Id": TEST_USER_ID,
        "X-Thandev-Tenant-Id": TEST_TENANT_ID,
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(f"{API_URL}/scans", headers=headers, json={
            "project_id": project_id,
            "scan_level": "basic"
        }, timeout=10)
        
        if r.status_code == 201:
            scan_data = r.json()
            scan_id = scan_data["id"]
            print(f"✅ Scan created: {scan_id}")
            print(f"   Status: {scan_data.get('status', 'unknown')}")
            return scan_id
        else:
            print(f"❌ Failed to create scan: {r.status_code} - {r.text}")
            return None
    except Exception as e:
        print(f"❌ Error starting scan: {e}")
        return None

def monitor_scan(scan_id, max_wait=300):
    """Monitor scan until completion"""
    print(f"\n⏳ Monitoring scan {scan_id} (max {max_wait}s)...")
    start_time = time.time()
    headers = {
        "X-Thandev-User-Id": TEST_USER_ID,
        "X-Thandev-Tenant-Id": TEST_TENANT_ID
    }
    
    while time.time() - start_time < max_wait:
        try:
            r = requests.get(f"{API_URL}/scans/{scan_id}", headers=headers, timeout=10)
            if r.status_code == 200:
                scan_data = r.json()
                status = scan_data.get("status", "unknown")
                findings_count = scan_data.get("findings_count", 0)
                
                print(f"   Status: {status}, Findings: {findings_count}")
                
                if status in ["completed", "completed_with_errors", "failed", "cancelled"]:
                    print(f"\n✅ Scan finished with status: {status}")
                    return scan_data
            else:
                print(f"   ⚠️  Failed to get scan status: {r.status_code}")
            
            time.sleep(5)
        except Exception as e:
            print(f"   ⚠️  Error checking status: {e}")
            time.sleep(5)
    
    print(f"\n⏱️  Timeout waiting for scan to complete")
    return None

def get_tool_results(scan_id):
    """Get tool execution results"""
    print(f"\n🔧 Checking tool execution results...")
    headers = {
        "X-Thandev-User-Id": TEST_USER_ID,
        "X-Thandev-Tenant-Id": TEST_TENANT_ID
    }
    try:
        r = requests.get(f"{API_URL}/scans/{scan_id}/tools", headers=headers, timeout=10)
        if r.status_code == 200:
            tools_data = r.json()
            tools = tools_data.get("items", [])
            
            print(f"\n📊 Tool Execution Results:")
            print(f"{'Tool':<15} {'Status':<15} {'Findings':<10} {'Duration':<12} {'Exit':<8}")
            print("-" * 70)
            
            for tool in tools:
                tool_name = tool.get("tool_name", "unknown")
                status = tool.get("status", "unknown")
                findings = tool.get("findings_count", 0)
                duration = tool.get("execution_time", 0)
                exit_code = tool.get("exit_code", "N/A")
                
                status_icon = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
                print(f"{tool_name:<15} {status_icon} {status:<12} {findings:<10} {duration:<12.2f} {exit_code}")
            
            return tools
        else:
            print(f"❌ Failed to get tool results: {r.status_code} - {r.text}")
            return []
    except Exception as e:
        print(f"❌ Error getting tool results: {e}")
        return []

def get_findings(scan_id):
    """Get findings from scan"""
    print(f"\n🔎 Getting findings from scan {scan_id}...")
    headers = {
        "X-Thandev-User-Id": TEST_USER_ID,
        "X-Thandev-Tenant-Id": TEST_TENANT_ID
    }
    try:
        r = requests.get(f"{API_URL}/scans/{scan_id}/findings", headers=headers, timeout=10)
        if r.status_code == 200:
            findings_data = r.json()
            findings = findings_data.get("findings", [])
            total = findings_data.get("total", 0)
            
            print(f"\n📋 Findings Summary:")
            print(f"   Total findings: {total}")
            
            # Group by severity
            severity_counts = {}
            tool_counts = {}
            
            for finding in findings:
                severity = finding.get("severity", "unknown")
                tool = finding.get("tool_name", "unknown")
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                tool_counts[tool] = tool_counts.get(tool, 0) + 1
            
            print(f"\n   By Severity:")
            for sev in ["critical", "high", "medium", "low", "info"]:
                count = severity_counts.get(sev, 0)
                if count > 0:
                    print(f"     {sev.capitalize()}: {count}")
            
            print(f"\n   By Tool:")
            for tool, count in sorted(tool_counts.items()):
                print(f"     {tool}: {count}")
            
            # Show first few findings
            if findings:
                print(f"\n   Sample Findings (first 5):")
                for i, finding in enumerate(findings[:5], 1):
                    print(f"     {i}. [{finding.get('severity', 'unknown').upper()}] {finding.get('title', 'No title')[:60]}")
                    print(f"        Tool: {finding.get('tool_name', 'unknown')}, URL: {finding.get('url', 'N/A')[:50]}")
            
            return findings
        else:
            print(f"❌ Failed to get findings: {r.status_code} - {r.text}")
            return []
    except Exception as e:
        print(f"❌ Error getting findings: {e}")
        return []

def main():
    print("=" * 70)
    print("🧪 Basic Scan Test - Verifying Fixes")
    print("=" * 70)
    
    # Check backend
    if not check_backend():
        print("\n❌ Backend is not running. Please start it first.")
        sys.exit(1)
    
    # Create/get project
    project_id = create_project()
    if not project_id:
        print("\n❌ Failed to create/get project")
        sys.exit(1)
    
    # Start scan
    scan_id = start_basic_scan(project_id)
    if not scan_id:
        print("\n❌ Failed to start scan")
        sys.exit(1)
    
    # Monitor scan
    scan_data = monitor_scan(scan_id)
    if not scan_data:
        print("\n⚠️  Scan did not complete in time, but checking results anyway...")
    
    # Get tool results
    tools = get_tool_results(scan_id)
    
    # Get findings
    findings = get_findings(scan_id)
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary")
    print("=" * 70)
    
    if scan_data:
        print(f"✅ Scan Status: {scan_data.get('status', 'unknown')}")
        print(f"✅ Findings Count: {scan_data.get('findings_count', 0)}")
    
    # Check if tools succeeded
    failed_tools = [t for t in tools if t.get("status") == "failed"]
    if failed_tools:
        print(f"\n⚠️  {len(failed_tools)} tool(s) failed:")
        for tool in failed_tools:
            print(f"   - {tool.get('tool_name')}: {tool.get('error_message', 'Unknown error')}")
    else:
        print(f"\n✅ All tools executed successfully")
    
    # Check if we have findings
    if findings:
        info_findings = [f for f in findings if f.get("severity") == "info"]
        print(f"\n✅ Found {len(findings)} total findings")
        print(f"✅ Found {len(info_findings)} info severity findings")
        
        if len(info_findings) > 0:
            print("\n🎉 SUCCESS: Info severity findings are being detected!")
        else:
            print("\n⚠️  No info severity findings found (may be normal for this target)")
    else:
        print(f"\n⚠️  No findings detected (may be normal for this target)")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()

