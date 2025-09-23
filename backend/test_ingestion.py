#!/usr/bin/env python3
"""
Test script for CVE data ingestion
"""
import os
import sys
from real_data_ingestion import NVDAPIClient, CVEProcessor

def test_nvd_api():
    """Test NVD API connection"""
    print("Testing NVD API connection...")
    
    client = NVDAPIClient()
    
    # Test with a small request
    data = client.fetch_cves(start_index=0, results_per_page=5)
    
    if data and "vulnerabilities" in data:
        print(f"✅ NVD API connection successful")
        print(f"   Total results available: {data.get('totalResults', 0)}")
        print(f"   Results in this page: {len(data.get('vulnerabilities', []))}")
        return True
    else:
        print("❌ NVD API connection failed")
        return False

def test_ingestion():
    """Test the ingestion process"""
    print("\nTesting CVE data ingestion...")
    
    try:
        from real_data_ingestion import main
        main()
        print("✅ Ingestion test completed")
        return True
    except Exception as e:
        print(f"❌ Ingestion test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Starting CVE data ingestion tests...")
    
    # Test API connection
    api_ok = test_nvd_api()
    
    if api_ok:
        # Test ingestion
        ingestion_ok = test_ingestion()
        
        if ingestion_ok:
            print("\n🎉 All tests passed! Real-time data ingestion is working.")
        else:
            print("\n⚠️  API connection works but ingestion failed.")
    else:
        print("\n❌ API connection failed. Check your internet connection and NVD API status.")

if __name__ == "__main__":
    main()
