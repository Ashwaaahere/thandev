#!/usr/bin/env python3
"""
Test script for validating Juice Shop scan with dalfox and sqlmap.

This script:
1. Creates a scan against Juice Shop (or provided URL)
2. Waits for scan completion
3. Validates that dalfox and sqlmap tool runs appear with proper metadata
4. Checks targets_count, logs, and artifacts

Usage:
    python test_juice_shop_scan.py [--url https://demo.owasp-juice.shop]
"""
import argparse
import sys
import time
import requests
from typing import Dict, Any, Optional
from pathlib import Path


class JuiceShopScanValidator:
    """Validator for Juice Shop scan with dalfox and sqlmap"""
    
    def __init__(self, backend_url: str = "http://localhost:8000", api_token: Optional[str] = None):
        self.backend_url = backend_url.rstrip("/")
        self.api_token = api_token
        self.session = requests.Session()
        if api_token:
            self.session.headers.update({"Authorization": f"Bearer {api_token}"})
    
    def create_project(self, target_url: str) -> str:
        """Create a test project"""
        payload = {
            "name": f"Juice Shop Test {int(time.time())}",
            "target_url": target_url,
            "description": "Automated test project for Juice Shop scan validation",
        }
        
        response = self.session.post(f"{self.backend_url}/api/projects", json=payload)
        response.raise_for_status()
        
        project_data = response.json()
        project_id = project_data.get("id")
        print(f"✓ Created project: {project_id}")
        return project_id
    
    def create_scan(self, project_id: str, scan_level: str = "pro") -> str:
        """Create a scan for the project"""
        payload = {
            "project_id": project_id,
            "scan_level": scan_level,
            "target_url": None,  # Use project's target_url
        }
        
        response = self.session.post(f"{self.backend_url}/api/scans", json=payload)
        response.raise_for_status()
        
        scan_data = response.json()
        scan_id = scan_data.get("id")
        print(f"✓ Created scan: {scan_id} (level: {scan_level})")
        return scan_id
    
    def wait_for_scan_completion(self, scan_id: str, timeout: int = 3600) -> Dict[str, Any]:
        """Wait for scan to complete or timeout"""
        print(f"⏳ Waiting for scan {scan_id} to complete (timeout: {timeout}s)...")
        
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < timeout:
            response = self.session.get(f"{self.backend_url}/api/scans/{scan_id}")
            response.raise_for_status()
            
            scan_data = response.json()
            status = scan_data.get("status")
            
            if status != last_status:
                print(f"  Status: {status}")
                last_status = status
            
            if status in ["completed", "failed", "cancelled"]:
                elapsed = time.time() - start_time
                print(f"✓ Scan {status} after {elapsed:.1f}s")
                return scan_data
            
            time.sleep(10)  # Poll every 10 seconds
        
        raise TimeoutError(f"Scan {scan_id} did not complete within {timeout}s")
    
    def get_tool_results(self, scan_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all tool results for a scan"""
        response = self.session.get(f"{self.backend_url}/api/scans/{scan_id}/tool-results")
        response.raise_for_status()
        
        tool_results = response.json()
        
        # Index by tool_name
        tool_results_by_name = {}
        for tr in tool_results:
            tool_name = tr.get("tool_name")
            tool_results_by_name[tool_name] = tr
        
        return tool_results_by_name
    
    def validate_tool_run(self, tool_name: str, tool_result: Dict[str, Any]) -> bool:
        """Validate a tool run has proper metadata"""
        print(f"\n🔍 Validating {tool_name} tool run:")
        
        # Check required fields
        required_fields = ["id", "tool_name", "status", "exit_code", "execution_time", "targets_count"]
        missing_fields = [f for f in required_fields if f not in tool_result or tool_result[f] is None]
        
        if missing_fields:
            print(f"  ✗ Missing required fields: {missing_fields}")
            return False
        
        # Check targets_count
        targets_count = tool_result.get("targets_count", 0)
        if targets_count == 0:
            skip_reason = tool_result.get("skip_reason")
            if skip_reason:
                print(f"  ⚠ Tool was skipped: {skip_reason}")
            else:
                print(f"  ⚠ targets_count is 0 (no targets provided to tool)")
        else:
            print(f"  ✓ targets_count: {targets_count}")
        
        # Check meta
        meta = tool_result.get("meta")
        if meta:
            print(f"  ✓ meta: {meta}")
            
            # Check for harvester stats
            harvested_requests = meta.get("harvested_requests", 0)
            total_parameters = meta.get("total_parameters", 0)
            
            if harvested_requests > 0:
                print(f"    - harvested_requests: {harvested_requests}")
                print(f"    - total_parameters: {total_parameters}")
            else:
                print(f"    ⚠ No parameterized requests harvested")
        else:
            print(f"  ⚠ No meta field")
        
        # Check status
        status = tool_result.get("status")
        print(f"  ✓ status: {status}")
        
        # Check execution_time
        execution_time = tool_result.get("execution_time")
        print(f"  ✓ execution_time: {execution_time}s")
        
        # Check for output/logs
        output_preview = tool_result.get("stdout_preview") or tool_result.get("output")
        if output_preview:
            print(f"  ✓ output/logs available ({len(output_preview)} chars)")
        else:
            print(f"  ⚠ No output/logs")
        
        # Check error messages
        error_message = tool_result.get("error_message")
        if error_message:
            print(f"  ⚠ error_message: {error_message[:100]}...")
        
        return True
    
    def run_validation(self, target_url: str, scan_level: str = "pro") -> bool:
        """Run full validation workflow"""
        print(f"\n{'='*60}")
        print(f"Juice Shop Scan Validation")
        print(f"{'='*60}")
        print(f"Target URL: {target_url}")
        print(f"Scan Level: {scan_level}")
        print(f"Backend URL: {self.backend_url}")
        print(f"{'='*60}\n")
        
        try:
            # Step 1: Create project
            project_id = self.create_project(target_url)
            
            # Step 2: Create scan
            scan_id = self.create_scan(project_id, scan_level)
            
            # Step 3: Wait for completion
            scan_data = self.wait_for_scan_completion(scan_id, timeout=3600)
            
            # Step 4: Get tool results
            print(f"\n📊 Fetching tool results...")
            tool_results = self.get_tool_results(scan_id)
            
            print(f"✓ Found {len(tool_results)} tool results")
            print(f"  Tools: {', '.join(tool_results.keys())}")
            
            # Step 5: Validate dalfox and sqlmap
            validation_success = True
            
            for tool_name in ["dalfox", "sqlmap"]:
                if tool_name not in tool_results:
                    print(f"\n✗ {tool_name} not found in tool results!")
                    validation_success = False
                else:
                    if not self.validate_tool_run(tool_name, tool_results[tool_name]):
                        validation_success = False
            
            # Step 6: Summary
            print(f"\n{'='*60}")
            if validation_success:
                print("✓ VALIDATION PASSED")
                print(f"{'='*60}\n")
                return True
            else:
                print("✗ VALIDATION FAILED")
                print(f"{'='*60}\n")
                return False
            
        except Exception as e:
            print(f"\n✗ Error during validation: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Validate Juice Shop scan with dalfox and sqlmap")
    parser.add_argument(
        "--url",
        default="https://demo.owasp-juice.shop",
        help="Target URL (default: https://demo.owasp-juice.shop)"
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--api-token",
        help="API token for authentication (optional)"
    )
    parser.add_argument(
        "--scan-level",
        default="pro",
        choices=["basic", "pro", "advanced"],
        help="Scan level (default: pro)"
    )
    
    args = parser.parse_args()
    
    validator = JuiceShopScanValidator(
        backend_url=args.backend_url,
        api_token=args.api_token
    )
    
    success = validator.run_validation(args.url, args.scan_level)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
