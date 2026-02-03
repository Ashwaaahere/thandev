#!/usr/bin/env python3
"""Check if scan steps are in Redis stream"""
import redis
import os
import sys

scan_id = sys.argv[1] if len(sys.argv) > 1 else '1b908a55-eca1-43a1-9b07-b899697616c6'

redis_url = os.getenv('REDIS_URL', 'redis://thandev-redis:6379')
print(f'Connecting to Redis: {redis_url}')

try:
    client = redis.from_url(redis_url, decode_responses=True)
    client.ping()
    print('✅ Redis connected')
    
    # Check stream length
    length = client.xlen('scan_step_requests')
    print(f'\nscan_step_requests stream length: {length}')
    
    # Get all messages and search for our scan
    print(f'\nSearching for scan: {scan_id}')
    messages = client.xrevrange('scan_step_requests', count=1000)
    print(f'Checking last {len(messages)} messages...')
    
    found_messages = []
    for msg_id, data in messages:
        if scan_id.lower() in str(data).lower():
            found_messages.append((msg_id, data))
    
    if found_messages:
        print(f'\n✅ Found {len(found_messages)} messages for this scan:')
        for msg_id, data in found_messages:
            print(f'\n  Message ID: {msg_id}')
            print(f'    scan_job_id: {data.get("scan_job_id", "N/A")}')
            print(f'    tool_id: {data.get("tool_id", "N/A")}')
            print(f'    session_id: {data.get("session_id", "N/A")}')
            print(f'    step_id: {data.get("step_id", "N/A")}')
    else:
        print(f'\n❌ Scan {scan_id} NOT found in Redis stream')
        print('   This means steps were never published to Redis')
    
    # Check consumer groups
    try:
        groups = client.xinfo_groups('scan_step_requests')
        print(f'\nConsumer groups: {len(groups)}')
        for group in groups:
            name = group.get('name', 'N/A')
            pending = group.get('pending', 0)
            consumers = group.get('consumers', 0)
            print(f'  Group: {name}, Pending: {pending}, Consumers: {consumers}')
            
            # Check pending messages
            if pending > 0:
                try:
                    pending_info = client.xpending('scan_step_requests', name, '-', '+', pending)
                    print(f'    Pending messages: {len(pending_info) if isinstance(pending_info, list) else pending}')
                except:
                    pass
    except Exception as e:
        print(f'\n⚠️  Could not check consumer groups: {e}')
        
except Exception as e:
    print(f'❌ Redis error: {e}')
    import traceback
    traceback.print_exc()

