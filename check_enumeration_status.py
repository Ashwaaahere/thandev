#!/usr/bin/env python3
"""Check enumeration status for scan 94CB9ED0"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres.kooxcykmlwonxqdushgt:6ySBsM6lRK8JSMQu@aws-0-us-west-2.pooler.supabase.com:6543/postgres')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

scan_id = '94cb9ed0-f95a-4423-9369-596a0f89388f'

print(f'=== Checking Enumeration Status for Scan {scan_id} ===\n')

# Check ScanToolState for enumeration
tool_state_query = text('''
    SELECT tool, stage, created_at, updated_at
    FROM scan_tool_states
    WHERE scan_id = :sid AND tool = 'enumeration'
    ORDER BY updated_at DESC
    LIMIT 5
''')
tool_states = session.execute(tool_state_query, {'sid': scan_id}).fetchall()

if tool_states:
    print('ScanToolState records for enumeration:')
    for state in tool_states:
        print(f'  Tool: {state[0]}, Stage: {state[1]}, Updated: {state[3]}')
else:
    print('No ScanToolState records found for enumeration')

# Check ToolResult for enumeration
tool_result_query = text('''
    SELECT tool_name, status, error_message, created_at
    FROM tool_results
    WHERE scan_job_id = :sid AND tool_name = 'enumeration'
    ORDER BY created_at DESC
    LIMIT 5
''')
tool_results = session.execute(tool_result_query, {'sid': scan_id}).fetchall()

print('\nToolResult records for enumeration:')
if tool_results:
    for result in tool_results:
        print(f'  Tool: {result[0]}, Status: {result[1]}, Error: {result[2]}, Created: {result[3]}')
else:
    print('  No ToolResult records found for enumeration')

# Check all tool results
all_tools_query = text('''
    SELECT tool_name, status, error_message, created_at
    FROM tool_results
    WHERE scan_job_id = :sid
    ORDER BY created_at
''')
all_tools = session.execute(all_tools_query, {'sid': scan_id}).fetchall()

print(f'\nAll Tool Results ({len(all_tools)} total):')
for tool in all_tools:
    print(f'  {tool[0]}: {tool[1]}' + (f' - {tool[2][:60]}' if tool[2] else ''))

session.close()

