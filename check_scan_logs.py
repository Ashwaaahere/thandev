#!/usr/bin/env python3
"""
Script to check scan logs for a given scan ID
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Get database URL from environment
db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:6ySBsM6lRK8JSMQu@db.kooxcykmlwonxqdushgt.supabase.co:5432/postgres?sslmode=require')

def check_scan_logs(scan_id_partial: str):
    try:
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        # Try to find the scan (support partial IDs)
        if len(scan_id_partial) == 8:
            # Partial ID, search for matching scans
            result = db.execute(
                text('SELECT id, status, scan_level, url, created_at, started_at, completed_at, error_message, project_id FROM scan_jobs WHERE id LIKE :scan_id ORDER BY created_at DESC LIMIT 5'),
                {'scan_id': f'{scan_id_partial}%'}
            )
        else:
            # Full ID
            result = db.execute(
                text('SELECT id, status, scan_level, url, created_at, started_at, completed_at, error_message, project_id FROM scan_jobs WHERE id = :scan_id'),
                {'scan_id': scan_id_partial}
            )
        
        scans = result.fetchall()
        
        if not scans:
            print(f'❌ No scan found with ID matching "{scan_id_partial}"')
            db.close()
            return
        
        for scan in scans:
            scan_id = scan[0]
            print(f'\n{"="*80}')
            print(f'📊 Scan ID: {scan_id}')
            print(f'{"="*80}')
            print(f'Status: {scan[1]}')
            print(f'Level: {scan[2]}')
            print(f'URL: {scan[3]}')
            print(f'Created: {scan[4]}')
            print(f'Started: {scan[5]}')
            print(f'Completed: {scan[6]}')
            if scan[7]:
                print(f'❌ Error: {scan[7]}')
            print()
            
            # Get scan events (logs)
            events_result = db.execute(
                text('''
                    SELECT phase, tool, stage, message, progress, created_at, meta
                    FROM scan_events 
                    WHERE scan_id = :scan_id 
                    ORDER BY created_at ASC
                '''),
                {'scan_id': scan_id}
            )
            events = events_result.fetchall()
            
            print(f'📝 Scan Events ({len(events)} total):')
            print('-' * 80)
            if events:
                for event in events:
                    phase = event[0] or 'N/A'
                    tool = event[1] or 'N/A'
                    stage = event[2] or 'N/A'
                    message = event[3] or ''
                    progress = f" ({int(event[4]*100)}%)" if event[4] is not None else ""
                    timestamp = event[5]
                    meta = event[6]
                    
                    meta_str = ""
                    if meta:
                        meta_str = f" | Meta: {meta}"
                    
                    print(f'[{timestamp}] {phase}/{tool}: {stage}{progress}')
                    print(f'  → {message}{meta_str}')
            else:
                print('  No events found')
            print()
            
            # Get tool results
            tools_result = db.execute(
                text('''
                    SELECT tool_name, tool_id, status, execution_time, findings_count, error_message, created_at
                    FROM tool_results 
                    WHERE scan_job_id = :scan_id 
                    ORDER BY created_at ASC
                '''),
                {'scan_id': scan_id}
            )
            tools = tools_result.fetchall()
            
            print(f'🔧 Tool Results ({len(tools)} total):')
            print('-' * 80)
            if tools:
                for tool in tools:
                    tool_name = tool[0] or 'N/A'
                    tool_id = tool[1] or 'N/A'
                    status = tool[2] or 'N/A'
                    exec_time = tool[3] or 0
                    findings = tool[4] or 0
                    error = tool[5]
                    created = tool[6]
                    
                    status_icon = '✅' if status == 'completed' else '❌' if status == 'failed' else '⏳'
                    print(f'{status_icon} {tool_name} ({tool_id}): {status}')
                    print(f'   Time: {exec_time:.2f}s | Findings: {findings} | Created: {created}')
                    if error:
                        print(f'   ❌ Error: {error}')
            else:
                print('  No tool results found')
            print()
            
            # Get tool states
            states_result = db.execute(
                text('''
                    SELECT tool, phase, stage, message, progress, updated_at
                    FROM scan_tool_states 
                    WHERE scan_id = :scan_id 
                    ORDER BY updated_at DESC
                '''),
                {'scan_id': scan_id}
            )
            states = states_result.fetchall()
            
            if states:
                print(f'📊 Tool States ({len(states)} total):')
                print('-' * 80)
                for state in states:
                    tool = state[0] or 'N/A'
                    phase = state[1] or 'N/A'
                    stage = state[2] or 'N/A'
                    message = state[3] or ''
                    progress = f" ({int(state[4]*100)}%)" if state[4] is not None else ""
                    updated = state[5]
                    print(f'[{updated}] {tool}/{phase}: {stage}{progress} - {message}')
                print()
        
        db.close()
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    scan_id = sys.argv[1] if len(sys.argv) > 1 else '26ea012e'
    check_scan_logs(scan_id)


