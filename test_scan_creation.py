#!/usr/bin/env python3
"""Test scan creation locally"""
import requests
import json

# Test creating a quick scan
url = "http://localhost:8000/api/scans/quick"
headers = {
    "Content-Type": "application/json",
    "X-Thandev-Tenant-Id": "8b6a9a85-a892-4a26-a0fc-3f0a8c0d8468",
    "X-Thandev-User-Id": "d36da182-2f87-4c52-9ab2-b8a7dcd28bcf"
}

payload = {
    "project_id": "15551741-5c77-49c1-9f94-7b59c38e59af",
    "scan_level": "advanced"
}

print("Creating scan...")
response = requests.post(url, json=payload, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

if response.status_code == 201:
    scan_id = response.json().get("scan_id")
    print(f"\n✅ Scan created: {scan_id}")
    print(f"\nNow checking Redis for steps...")
    
    # Check Redis
    import redis
    redis_client = redis.from_url("redis://localhost:6380", decode_responses=True)
    messages = redis_client.xrevrange('scan_step_requests', count=10)
    
    found = False
    for msg_id, data in messages:
        if scan_id.lower() in str(data.get('scan_job_id', '')).lower():
            found = True
            print(f"✅ Found scan in Redis: {msg_id}")
            print(f"   Tool: {data.get('tool_id', 'N/A')}")
            break
    
    if not found:
        print(f"❌ Scan NOT found in Redis stream")
else:
    print(f"❌ Failed to create scan")

