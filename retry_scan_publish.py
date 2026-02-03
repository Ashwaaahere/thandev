#!/usr/bin/env python3
"""
Script to retry publishing scan steps for a stuck scan
Usage: python retry_scan_publish.py <scan_id> [backend_url] [auth_token]
"""
import sys
import requests
import json

def retry_scan_publish(scan_id: str, backend_url: str = None, tenant_id: str = None, user_id: str = None):
    """Retry publishing scan steps for a stuck scan"""
    
    # Default backend URL (Azure Container App)
    if not backend_url:
        backend_url = "https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io"
    
    # Construct the endpoint URL
    endpoint = f"{backend_url}/api/scans/{scan_id}/retry-publish"
    
    print(f"Retrying scan step publishing for scan: {scan_id}")
    print(f"Endpoint: {endpoint}")
    
    # Prepare headers - API requires X-Thandev-Tenant-Id or X-Thandev-User-Id
    headers = {
        "Content-Type": "application/json",
    }
    
    # Add tenant/user headers if provided
    if tenant_id:
        headers["X-Thandev-Tenant-Id"] = tenant_id
    if user_id:
        headers["X-Thandev-User-Id"] = user_id
    
    if not tenant_id and not user_id:
        print("⚠️  Warning: No tenant_id or user_id provided. The request may fail with 400/401.")
        print("   You can get these from the scan's project or user.")
    
    try:
        # Make the POST request
        response = requests.post(endpoint, headers=headers, timeout=30)
        
        print(f"\nResponse Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success: {result.get('message', 'Scan steps published successfully')}")
            print(f"   Scan ID: {result.get('scan_id', scan_id)}")
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"   Detail: {error_detail}")
            except:
                print(f"   Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python retry_scan_publish.py <scan_id> [backend_url] [tenant_id] [user_id]")
        print("\nExample:")
        print("  python retry_scan_publish.py C7E26F8B")
        print("  python retry_scan_publish.py C7E26F8B <backend_url> <tenant_id>")
        print("\nNote: You need either tenant_id or user_id for authentication")
        sys.exit(1)
    
    scan_id = sys.argv[1]
    backend_url = sys.argv[2] if len(sys.argv) > 2 else None
    tenant_id = sys.argv[3] if len(sys.argv) > 3 else None
    user_id = sys.argv[4] if len(sys.argv) > 4 else None
    
    success = retry_scan_publish(scan_id, backend_url, tenant_id, user_id)
    sys.exit(0 if success else 1)

