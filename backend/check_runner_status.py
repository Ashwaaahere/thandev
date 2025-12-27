#!/usr/bin/env python3
"""
Quick script to check if runner service is processing messages from Redis streams.
"""
import redis
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def check_runner_status():
    """Check if runner service is active by checking Redis streams"""
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        
        # Check step requests stream
        step_requests_stream = "scan_step_requests"
        step_results_stream = "scan_step_results"
        
        # Get stream info
        requests_info = client.xinfo_stream(step_requests_stream)
        results_info = client.xinfo_stream(step_results_stream)
        
        print("=== Runner Service Status Check ===")
        print(f"\nStep Requests Stream ({step_requests_stream}):")
        print(f"  Length: {requests_info.get('length', 0)} messages")
        print(f"  Last ID: {requests_info.get('last-generated-id', 'N/A')}")
        
        print(f"\nStep Results Stream ({step_results_stream}):")
        print(f"  Length: {results_info.get('length', 0)} messages")
        print(f"  Last ID: {results_info.get('last-generated-id', 'N/A')}")
        
        # Check consumer groups
        try:
            groups = client.xinfo_groups(step_requests_stream)
            print(f"\nConsumer Groups:")
            for group in groups:
                print(f"  Group: {group.get('name', 'N/A')}")
                print(f"    Pending: {group.get('pending', 0)}")
                print(f"    Consumers: {group.get('consumers', 0)}")
                
                # Get consumer info
                consumers = client.xinfo_consumers(step_requests_stream, group.get('name', ''))
                for consumer in consumers:
                    print(f"      Consumer: {consumer.get('name', 'N/A')}")
                    print(f"        Pending: {consumer.get('pending', 0)}")
                    print(f"        Idle: {consumer.get('idle', 0)}ms")
        except redis.exceptions.ResponseError as e:
            if "no such key" in str(e).lower():
                print("\n⚠️  No consumer groups found - runner may not be running")
            else:
                print(f"\n⚠️  Error checking consumer groups: {e}")
        
        # Check for pending messages (indicates runner might not be processing)
        pending_count = requests_info.get('length', 0)
        if pending_count > 10:
            print(f"\n⚠️  WARNING: {pending_count} messages in requests stream")
            print("   Runner service may not be processing messages fast enough")
        elif pending_count > 0:
            print(f"\n✓ {pending_count} messages in queue (normal)")
        else:
            print("\n✓ No pending messages")
        
        print("\n=== Status ===")
        if pending_count == 0:
            print("✓ Runner service appears to be processing messages")
        else:
            print("⚠️  Runner service may have issues - check runner logs")
            
    except redis.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to Redis")
        print(f"   Redis URL: {REDIS_URL}")
        print("   Make sure Redis is running")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_runner_status()


