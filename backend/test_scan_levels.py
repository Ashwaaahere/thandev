#!/usr/bin/env python3
"""
Test script for scan levels functionality
"""

import requests
import json
import time
import sys

# Configuration
BACKEND_URL = "http://localhost:8000"
TEST_URL = "https://httpbin.org"

def test_tier_validation():
    """Test tier validation"""
    print("Testing tier validation...")
    
    # Test valid tiers
    valid_tiers = ["level0", "level1", "level2"]
    for tier in valid_tiers:
        response = requests.post(f"{BACKEND_URL}/api/security-scan", json={
            "url": TEST_URL,
            "tier": tier,
            "user_id": "test_user"
        })
        if response.status_code == 200:
            print(f"✅ Valid tier {tier} accepted")
        else:
            print(f"❌ Valid tier {tier} rejected: {response.status_code}")
    
    # Test invalid tier
    response = requests.post(f"{BACKEND_URL}/api/security-scan", json={
        "url": TEST_URL,
        "tier": "invalid_tier",
        "user_id": "test_user"
    })
    if response.status_code == 400:
        print("✅ Invalid tier rejected")
    else:
        print(f"❌ Invalid tier accepted: {response.status_code}")

def test_rate_limiting():
    """Test rate limiting"""
    print("\nTesting rate limiting...")
    
    # Create 4 concurrent scans (limit is 3)
    responses = []
    for i in range(4):
        response = requests.post(f"{BACKEND_URL}/api/security-scan", json={
            "url": f"{TEST_URL}/test{i}",
            "tier": "level0",
            "user_id": "test_user"
        })
        responses.append(response)
        print(f"Scan {i+1}: {response.status_code}")
    
    # Check if the 4th scan was rate limited
    if responses[3].status_code == 429:
        print("✅ Rate limiting working correctly")
    else:
        print("❌ Rate limiting not working")

def test_scan_workflow():
    """Test complete scan workflow"""
    print("\nTesting scan workflow...")
    
    # Start a scan
    response = requests.post(f"{BACKEND_URL}/api/security-scan", json={
        "url": TEST_URL,
        "tier": "level0",
        "user_id": "test_user"
    })
    
    if response.status_code != 200:
        print(f"❌ Failed to start scan: {response.status_code}")
        return
    
    data = response.json()
    job_id = data["jobId"]
    print(f"✅ Scan started with job ID: {job_id}")
    
    # Check scan status
    response = requests.get(f"{BACKEND_URL}/api/security-scan/status/{job_id}")
    if response.status_code == 200:
        print("✅ Status endpoint working")
    else:
        print(f"❌ Status endpoint failed: {response.status_code}")
    
    # Wait a bit and check again
    time.sleep(2)
    response = requests.get(f"{BACKEND_URL}/api/security-scan/status/{job_id}")
    if response.status_code == 200:
        status_data = response.json()
        print(f"✅ Scan status: {status_data.get('status', 'unknown')}")
    else:
        print(f"❌ Status check failed: {response.status_code}")

def test_presets_loading():
    """Test preset loading"""
    print("\nTesting preset loading...")
    
    # This would test if presets are loaded correctly
    # For now, just check if the endpoint responds
    response = requests.get(f"{BACKEND_URL}/api/security-scan/list?user_id=test_user")
    if response.status_code == 200:
        print("✅ Presets and list endpoint working")
    else:
        print(f"❌ Presets/list endpoint failed: {response.status_code}")

def main():
    """Run all tests"""
    print("Starting scan levels tests...")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test URL: {TEST_URL}")
    
    try:
        test_tier_validation()
        test_rate_limiting()
        test_scan_workflow()
        test_presets_loading()
        
        print("\n✅ All tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to backend. Make sure it's running on", BACKEND_URL)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
