#!/usr/bin/env python3
"""Check tool execution status for a scan"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres.kooxcykmlwonxqdushgt:6ySBsM6lRK8JSMQu@aws-0-us-west-2.pooler.supabase.com:6543/postgres')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

scan_id = '0a414e59'

# Find scan
query = text('''
    SELECT id FROM scan_jobs WHERE LOWER(id) LIKE :sid ORDER BY created_at DESC LIMIT 1
''')
result = session.execute(query, {'sid': f'%{scan_id}%'}).fetchone()

if result:
    exact_scan_id = result[0]
    print(f'=== TOOL EXECUTION STATUS FOR SCAN {exact_scan_id} ===\n')
    
    # Get all tool results
    tool_query = text('''
        SELECT tool_name, status, error_message, created_at
        FROM tool_results
        WHERE scan_job_id = :sid
        ORDER BY created_at
    ''')
    tools = session.execute(tool_query, {'sid': exact_scan_id}).fetchall()
    
    print(f'Total Tools: {len(tools)}\n')
    
    status_counts = {}
    for tool in tools:
        tool_name = tool[0]
        status = tool[1]
        error = tool[2]
        created = tool[3]
        status_counts[status] = status_counts.get(status, 0) + 1
        
        status_str = f'{tool_name:20s} | {status:15s}'
        if error:
            status_str += f' | ERROR: {error[:60]}'
        print(status_str)
    
    print(f'\n=== STATUS SUMMARY ===')
    for status, count in sorted(status_counts.items()):
        print(f'{status}: {count}')
    
    # Get findings count
    findings_query = text('''
        SELECT COUNT(*) FROM findings WHERE scan_job_id = :sid
    ''')
    findings_count = session.execute(findings_query, {'sid': exact_scan_id}).fetchone()[0]
    print(f'\nTotal Findings: {findings_count}')
else:
    print(f'Scan {scan_id} not found')

session.close()

