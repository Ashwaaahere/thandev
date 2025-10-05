#!/usr/bin/env python3
"""
Test script for the performance scan functionality
"""
import requests
import time
import json

# Backend URL
BACKEND_URL = "http://localhost:8000"

def test_performance_scan():
    """Test the complete performance scan flow"""
    print("🚀 Testing Performance Scan Flow")
    print("=" * 50)
    
    # Test URL
    test_url = "https://example.com"
    
    try:
        # 1. Start a performance scan
        print(f"1. Starting performance scan for {test_url}...")
        response = requests.post(f"{BACKEND_URL}/api/performance-scan/", json={
            "url": test_url,
            "device": "desktop",
            "timestamp": "2024-01-01T00:00:00Z"
        })
        
        if response.status_code != 200:
            print(f"❌ Failed to start scan: {response.status_code}")
            print(response.text)
            return
        
        scan_data = response.json()
        job_id = scan_data["jobId"]
        print(f"✅ Scan started with job ID: {job_id}")
        
        # 2. Poll for results
        print("2. Polling for results...")
        max_attempts = 30  # 30 attempts = 1 minute
        attempt = 0
        
        while attempt < max_attempts:
            time.sleep(2)  # Wait 2 seconds between polls
            attempt += 1
            
            print(f"   Attempt {attempt}/{max_attempts}...")
            
            status_response = requests.get(f"{BACKEND_URL}/api/performance-scan/{job_id}")
            
            if status_response.status_code != 200:
                print(f"❌ Failed to get status: {status_response.status_code}")
                return
            
            status_data = status_response.json()
            status = status_data["status"]
            
            print(f"   Status: {status}")
            
            if status == "completed":
                print("✅ Scan completed!")
                result = status_data.get("result", {})
                
                # Display results
                print("\n📊 Performance Results:")
                print("-" * 30)
                
                categories = result.get("categories", {})
                print(f"Performance Score: {categories.get('performance', 'N/A')}")
                print(f"Accessibility Score: {categories.get('accessibility', 'N/A')}")
                print(f"Best Practices Score: {categories.get('bestPractices', 'N/A')}")
                print(f"SEO Score: {categories.get('seo', 'N/A')}")
                
                metrics = result.get("metrics", {})
                print(f"\nCore Web Vitals:")
                print(f"  First Contentful Paint: {metrics.get('firstContentfulPaint', 'N/A')}ms")
                print(f"  Largest Contentful Paint: {metrics.get('largestContentfulPaint', 'N/A')}ms")
                print(f"  Cumulative Layout Shift: {metrics.get('cumulativeLayoutShift', 'N/A')}")
                
                opportunities = result.get("opportunities", [])
                print(f"\nOptimization Opportunities: {len(opportunities)}")
                for opp in opportunities[:3]:  # Show first 3
                    print(f"  - {opp.get('title', 'N/A')}: {opp.get('displayValue', 'N/A')}")
                
                diagnostics = result.get("diagnostics", [])
                print(f"\nDiagnostics: {len(diagnostics)}")
                for diag in diagnostics[:3]:  # Show first 3
                    print(f"  - {diag.get('title', 'N/A')}: {diag.get('displayValue', 'N/A')}")
                
                break
            elif status == "failed":
                print("❌ Scan failed!")
                print(f"Error: {status_data.get('result', {}).get('error', 'Unknown error')}")
                break
            elif status in ["pending", "running"]:
                continue
            else:
                print(f"❌ Unknown status: {status}")
                break
        else:
            print("❌ Scan timed out!")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to backend. Make sure it's running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_performance_scan()
