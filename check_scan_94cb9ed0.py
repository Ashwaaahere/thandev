#!/usr/bin/env python3
"""Check scan 94CB9ED0 status in Azure database"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres.kooxcykmlwonxqdushgt:6ySBsM6lRK8JSMQu@aws-0-us-west-2.pooler.supabase.com:6543/postgres')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

scan_id = '94cb9ed0'

# Find scan
query = text('''
    SELECT id, scan_level, status, url, created_at, started_at, completed_at, error_message, tier, project_id
    FROM scan_jobs
    WHERE LOWER(id) LIKE :scan_id_pattern
    ORDER BY created_at DESC
    LIMIT 5
''')
scans = session.execute(query, {'scan_id_pattern': f'%{scan_id}%'}).fetchall()

print('=== SCANS MATCHING 94CB9ED0 ===')
for scan in scans:
    print(f'\nScan ID: {scan[0]}')
    print(f'  Level: {scan[1]}')
    print(f'  Status: {scan[2]}')
    print(f'  URL: {scan[3]}')
    print(f'  Created: {scan[4]}')
    print(f'  Started: {scan[5]}')
    print(f'  Completed: {scan[6]}')
    print(f'  Error: {scan[7]}')
    print(f'  Tier: {scan[8]}')
    print(f'  Project ID: {scan[9]}')
    
    exact_scan_id = scan[0]
    
    # Get tool results
    tool_query = text('''
        SELECT tool_name, status, error_message, created_at
        FROM tool_results
        WHERE scan_job_id = :sid
        ORDER BY created_at
    ''')
    tools = session.execute(tool_query, {'sid': exact_scan_id}).fetchall()
    
    print(f'\n  Tool Results ({len(tools)} total):')
    status_counts = {}
    for tool in tools:
        tool_name = tool[0]
        status = tool[1]
        error = tool[2]
        created = tool[3]
        status_counts[status] = status_counts.get(status, 0) + 1
        status_str = f'  - {tool_name}: {status} (created: {created})'
        if error:
            status_str += f' - ERROR: {error[:80]}'
        print(status_str)
    
    print(f'\n  Tool Status Summary:')
    for status, count in status_counts.items():
        print(f'    {status}: {count}')
    
    # Get findings count
    findings_query = text('''
        SELECT COUNT(*) FROM findings WHERE scan_job_id = :sid
    ''')
    findings_count = session.execute(findings_query, {'sid': exact_scan_id}).fetchone()[0]
    print(f'\n  Total Findings: {findings_count}')
    
    # Get findings by severity
    severity_query = text('''
        SELECT severity, COUNT(*) as count
        FROM findings
        WHERE scan_job_id = :sid
        GROUP BY severity
        ORDER BY 
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                WHEN 'info' THEN 5
                ELSE 6
            END
    ''')
    severity_counts = session.execute(severity_query, {'sid': exact_scan_id}).fetchall()
    if severity_counts:
        print(f'\n  Findings by Severity:')
        for sev, count in severity_counts:
            print(f'    {sev}: {count}')

session.close()

