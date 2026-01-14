import requests
import time
import json

API_URL = "http://localhost:8000/api"

def create_project():
    print("Creating project...")
    r = requests.post(f"{API_URL}/projects", json={
        "name": "Local Vulnerable App",
        "description": "Test vulnerable flask app",
        "scope_domains": ["host.docker.internal", "localhost"]
    })
    if r.status_code == 201:
        pid = r.json()["id"]
        print(f"Project created: {pid}")
        return pid
    elif r.status_code == 400 and "already exists" in r.text:
        # Fetch existing
        r = requests.get(f"{API_URL}/projects")
        for p in r.json():
            if p["name"] == "Local Vulnerable App":
                print(f"Using existing project: {p['id']}")
                return p["id"]
    else:
        print(f"Error creating project: {r.text}")
        return None

def start_scan(project_id):
    print("Starting scan...")
    # Scan the vulnerable app hosted on the host machine (accessible via host.docker.internal from container)
    r = requests.post(f"{API_URL}/scans", json={
        "project_id": project_id,
        "name": "Full Test Scan",
        "targets": ["http://host.docker.internal:5000"], 
        "scan_level": "advanced", # Use advanced to trigger full crawling and deep scans
        "profile": "fast"
    })
    if r.status_code == 201:
        sid = r.json()["id"]
        print(f"Scan started: {sid}")
        return sid
    else:
        print(f"Error starting scan: {r.text}")
        return None

if __name__ == "__main__":
    pid = create_project()
    if pid:
        sid = start_scan(pid)
