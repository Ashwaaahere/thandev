#!/usr/bin/env python3
"""
Quick script to check if ZAP is running for a scan
"""
import os
import sys
import psycopg2
from datetime import datetime

# Get database URL from environment
db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:6ySBsM6lRK8JSMQu@db.kooxcykmlwonxqdushgt.supabase.co:5432/postgres?sslmode=require')

def check_zap_status(scan_id_partial: str):
    """Check if ZAP is running for a scan"""
    try:
        # Parse database URL
        if db_url.startswith('postgresql://'):
            # Extract connection details
            url_parts = db_url.replace('postgresql://', '').split('@')
            if len(url_parts) == 2:
                auth, host_port_db = url_parts
                user, password = auth.split(':')
                host_port, db_name = host_port_db.split('/')
                if '?' in db_name:
                    db_name = db_name.split('?')[0]
                if ':' in host_port:
                    host, port = host_port.split(':')
                else:
                    host = host_port
                    port = '5432'
            else:
                print("❌ Could not parse database URL")
                return
        
        # Connect to database
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=db_name,
            user=user,
            password=password,
            sslmode='require'
        )
        cur = conn.cursor()
        
        # Find the scan
        if len(scan_id_partial) == 8:
            cur.execute(
                "SELECT id, status, scan_level, url, created_at, started_at FROM scan_jobs WHERE id LIKE %s ORDER BY created_at DESC LIMIT 5",
                (f'{scan_id_partial}%',)
            )
        else:
            cur.execute(
                "SELECT id, status, scan_level, url, created_at, started_at FROM scan_jobs WHERE id = %s",
                (scan_id_partial,)
            )
        
        scans = cur.fetchall()
        
        if not scans:
            print(f'❌ No scan found with ID matching "{scan_id_partial}"')
            cur.close()
            conn.close()
            return
        
        for scan in scans:
            scan_id = scan[0]
            status = scan[1]
            scan_level = scan[2]
            url = scan[3]
            created_at = scan[4]
            started_at = scan[5]
            
            print(f'\n{"="*80}')
            print(f'📊 Scan ID: {scan_id}')
            print(f'{"="*80}')
            print(f'Status: {status}')
            print(f'Level: {scan_level}')
            print(f'URL: {url}')
            print(f'Created: {created_at}')
            print(f'Started: {started_at}')
            print()
            
            # Check tool states for ZAP
            cur.execute(
                """
                SELECT tool, phase, stage, message, progress, updated_at
                FROM scan_tool_states 
                WHERE scan_id = %s AND tool ILIKE %s
                ORDER BY updated_at DESC
                LIMIT 10
                """,
                (scan_id, '%zap%')
            )
            zap_states = cur.fetchall()
            
            if zap_states:
                print(f'🔍 ZAP Tool States ({len(zap_states)} recent):')
                print('-' * 80)
                latest_state = zap_states[0]
                tool = latest_state[0]
                phase = latest_state[1]
                stage = latest_state[2]
                message = latest_state[3]
                progress = latest_state[4]
                updated = latest_state[5]
                
                progress_str = f" ({int(progress*100)}%)" if progress is not None else ""
                time_ago = ""
                if updated:
                    time_diff = datetime.now(updated.tzinfo) - updated if updated.tzinfo else datetime.now() - updated.replace(tzinfo=None)
                    minutes_ago = int(time_diff.total_seconds() / 60)
                    if minutes_ago < 1:
                        time_ago = " (just now)"
                    elif minutes_ago < 60:
                        time_ago = f" ({minutes_ago}m ago)"
                    else:
                        hours_ago = minutes_ago // 60
                        time_ago = f" ({hours_ago}h {minutes_ago % 60}m ago)"
                
                print(f'[{updated}]{time_ago} {tool}/{phase}: {stage}{progress_str}')
                print(f'  → {message}')
                
                # Determine if ZAP is running
                is_running = (
                    status in ('running', 'queued') and
                    phase in ('execution', 'running') and
                    stage not in ('completed', 'failed', 'timeout', 'cancelled')
                )
                
                if is_running:
                    print(f'\n✅ ZAP appears to be RUNNING')
                    if progress is not None:
                        print(f'   Progress: {int(progress*100)}%')
                else:
                    print(f'\n⏸️  ZAP is NOT currently running')
                    if status == 'completed':
                        print(f'   Scan is completed')
                    elif status == 'failed':
                        print(f'   Scan has failed')
                    else:
                        print(f'   Last update: {updated}')
                
                if len(zap_states) > 1:
                    print(f'\n📝 Recent ZAP activity:')
                    for state in zap_states[1:4]:  # Show next 3
                        tool = state[0]
                        phase = state[1]
                        stage = state[2]
                        message = state[3]
                        progress = state[4]
                        updated = state[5]
                        progress_str = f" ({int(progress*100)}%)" if progress is not None else ""
                        print(f'  [{updated}] {phase}: {stage}{progress_str} - {message[:60]}')
            else:
                print('❌ No ZAP tool states found')
                
                # Check tool results instead
                cur.execute(
                    """
                    SELECT tool_name, status, execution_time, findings_count, error_message, created_at
                    FROM tool_results 
                    WHERE scan_job_id = %s AND tool_name ILIKE %s
                    ORDER BY created_at DESC
                    LIMIT 5
                    """,
                    (scan_id, '%zap%')
                )
                zap_results = cur.fetchall()
                
                if zap_results:
                    print(f'\n🔧 ZAP Tool Results:')
                    print('-' * 80)
                    for result in zap_results:
                        tool_name = result[0]
                        tool_status = result[1]
                        exec_time = result[2]
                        findings = result[3]
                        error = result[4]
                        created = result[5]
                        
                        status_icon = '✅' if tool_status == 'completed' else '❌' if tool_status == 'failed' else '⏳'
                        print(f'{status_icon} {tool_name}: {tool_status}')
                        if exec_time:
                            print(f'   Time: {exec_time:.2f}s | Findings: {findings}')
                        if error:
                            print(f'   ❌ Error: {error}')
                else:
                    print('   No ZAP tool results found either')
            
            # Check scan events for ZAP
            cur.execute(
                """
                SELECT phase, tool, stage, message, progress, created_at
                FROM scan_events 
                WHERE scan_id = %s AND tool ILIKE %s
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (scan_id, '%zap%')
            )
            zap_events = cur.fetchall()
            
            if zap_events:
                print(f'\n📝 Recent ZAP Events:')
                print('-' * 80)
                for event in zap_events:
                    phase = event[0] or 'N/A'
                    tool = event[1] or 'N/A'
                    stage = event[2] or 'N/A'
                    message = event[3] or ''
                    progress = f" ({int(event[4]*100)}%)" if event[4] is not None else ""
                    timestamp = event[5]
                    print(f'  [{timestamp}] {phase}/{tool}: {stage}{progress}')
                    if message:
                        print(f'    → {message[:80]}')
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    scan_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not scan_id:
        print("Usage: python3 check_zap_status.py <scan_id>")
        print("Example: python3 check_zap_status.py 26ea012e")
        sys.exit(1)
    check_zap_status(scan_id)



