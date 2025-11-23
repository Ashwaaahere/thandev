#!/usr/bin/env python3
"""
Locust Cloud Run Job runner
Executes Locust tests and uploads results to GCS
"""
import os
import sys
import json
import time
import requests
import subprocess
from google.cloud import storage
from locust import HttpUser, task, between
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging

# Configuration from environment variables
DOMAIN = os.getenv('DOMAIN')
VUS = int(os.getenv('VUS', '50'))
DURATION = int(os.getenv('DURATION', '120'))
SPAWN = int(os.getenv('SPAWN', '10'))
SCAN_ID = os.getenv('SCAN_ID')
CALLBACK_URL = os.getenv('CALLBACK_URL')
GCS_BUCKET = os.getenv('GCS_BUCKET', 'thandev-reports')

def upload_to_gcs(file_path, gcs_path):
    """Upload a file to Google Cloud Storage"""
    try:
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(file_path)
        return f"https://storage.googleapis.com/{GCS_BUCKET}/{gcs_path}"
    except Exception as e:
        print(f"Error uploading to GCS: {e}")
        return None

def run_locust_test():
    """Run the Locust test and return results"""
    print(f"Starting Locust test for domain: {DOMAIN}")
    print(f"VUs: {VUS}, Duration: {DURATION}s, Spawn rate: {SPAWN}/s")
    
    # Set up Locust environment
    env = Environment(user_classes=[HttpUser])
    env.create_local_runner()
    
    # Set the host
    env.host = f"https://{DOMAIN}"
    
    # Start the test
    env.runner.start(VUS, spawn_rate=SPAWN)
    
    # Run for the specified duration
    time.sleep(DURATION)
    
    # Stop the test
    env.runner.quit()
    
    # Generate summary
    stats = env.stats
    total_requests = stats.total.num_requests
    total_failures = stats.total.num_failures
    error_rate = (total_failures / total_requests * 100) if total_requests > 0 else 0
    
    # Get response times
    response_times = stats.total.response_times
    avg_response_time = stats.total.avg_response_time
    p95_response_time = response_times.get_percentile(0.95) if response_times else 0
    
    # Calculate RPS
    duration = time.time() - stats.start_time if hasattr(stats, 'start_time') else DURATION
    avg_rps = total_requests / duration if duration > 0 else 0
    
    summary = {
        "p95LatencyMs": round(p95_response_time, 2),
        "avgRps": round(avg_rps, 2),
        "errorRatePct": round(error_rate, 2),
        "totalRequests": total_requests,
        "durationSec": round(duration, 2),
        "avgResponseTimeMs": round(avg_response_time, 2),
        "totalFailures": total_failures
    }
    
    print(f"Test completed. Summary: {json.dumps(summary, indent=2)}")
    return summary

def main():
    """Main execution function"""
    if not all([DOMAIN, SCAN_ID, CALLBACK_URL]):
        print("Error: Missing required environment variables")
        sys.exit(1)
    
    try:
        # Run the Locust test
        summary = run_locust_test()
        
        # Upload results to GCS (placeholder for now)
        gcs_prefix = f"locust/{SCAN_ID}"
        artifacts = {}
        
        # In a real implementation, you would:
        # 1. Export Locust results to CSV/JSON
        # 2. Upload to GCS
        # 3. Get public URLs
        
        # For now, we'll just use the summary
        summary_json = json.dumps(summary, indent=2)
        
        # Call back to the API
        callback_data = {
            "scanId": SCAN_ID,
            "status": "done",
            "summary": summary,
            "gcsPrefix": gcs_prefix
        }
        
        print(f"Calling back to: {CALLBACK_URL}")
        response = requests.post(CALLBACK_URL, json=callback_data, timeout=30)
        
        if response.status_code == 200:
            print("Callback successful")
        else:
            print(f"Callback failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Error during execution: {e}")
        
        # Try to call back with error status
        try:
            error_data = {
                "scanId": SCAN_ID,
                "status": "error",
                "error": str(e)
            }
            requests.post(CALLBACK_URL, json=error_data, timeout=30)
        except:
            pass
        
        sys.exit(1)

if __name__ == "__main__":
    main()


