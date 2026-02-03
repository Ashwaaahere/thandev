#!/usr/bin/env python3
"""
Real-time scan monitoring script
Monitors scan progress, tool execution, and findings in real-time
"""
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
except ImportError:
    print("❌ sqlalchemy not installed. Install with: pip install sqlalchemy psycopg2-binary")
    sys.exit(1)

# Get database URL from environment
db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:6ySBsM6lRK8JSMQu@db.kooxcykmlwonxqdushgt.supabase.co:5432/postgres?sslmode=require')

def format_duration(seconds):
    """Format seconds into human-readable duration"""
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"

def get_status_icon(status):
    """Get icon for status"""
    icons = {
        'completed': '✅',
        'failed': '❌',
        'running': '🔄',
        'pending': '⏳',
        'timed_out': '⏱️',
        'skipped': '⏭️',
    }
    return icons.get(status, '❓')

def monitor_scan(scan_id_partial: str, refresh_interval: int = 5):
    """Monitor a scan in real-time"""
    try:
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        # Find the scan
        if len(scan_id_partial) < 36:
            result = db.execute(
                text('SELECT id, status, scan_level, url, created_at, started_at, completed_at, error_message FROM scan_jobs WHERE id LIKE :scan_id ORDER BY created_at DESC LIMIT 1'),
                {'scan_id': f'{scan_id_partial}%'}
            )
        else:
            result = db.execute(
                text('SELECT id, status, scan_level, url, created_at, started_at, completed_at, error_message FROM scan_jobs WHERE id = :scan_id'),
                {'scan_id': scan_id_partial}
            )
        
        scan = result.fetchone()
        
        if not scan:
            print(f'❌ No scan found with ID matching "{scan_id_partial}"')
            db.close()
            return
        
        scan_id = scan[0]
        print(f'\n{"="*80}')
        print(f'📊 Monitoring Scan: {scan_id}')
        print(f'{"="*80}')
        print(f'URL: {scan[3]}')
        print(f'Level: {scan[2]}')
        print(f'Created: {scan[4]}')
        print(f'Refresh interval: {refresh_interval}s')
        print(f'Press Ctrl+C to stop monitoring\n')
        
        last_tool_count = 0
        last_finding_count = 0
        start_time = time.time()
        
        try:
            while True:
                # Clear screen (works on most terminals)
                os.system('clear' if os.name != 'nt' else 'cls')
                
                # Get current scan status
                scan_result = db.execute(
                    text('SELECT id, status, scan_level, url, created_at, started_at, completed_at, error_message FROM scan_jobs WHERE id = :scan_id'),
                    {'scan_id': scan_id}
                )
                current_scan = scan_result.fetchone()
                
                if not current_scan:
                    print(f'❌ Scan {scan_id} not found!')
                    break
                
                scan_status = current_scan[1]
                scan_url = current_scan[3]
                scan_level = current_scan[2]
                created_at = current_scan[4]
                started_at = current_scan[5]
                completed_at = current_scan[6]
                error_message = current_scan[7]
                
                # Calculate elapsed time
                if started_at:
                    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
                else:
                    elapsed = (datetime.now(timezone.utc) - created_at).total_seconds()
                
                # Print header
                print(f'\n{"="*80}')
                print(f'📊 Scan: {scan_id[:8]}... | Status: {scan_status.upper()} | Elapsed: {format_duration(elapsed)}')
                print(f'{"="*80}')
                print(f'URL: {scan_url}')
                print(f'Level: {scan_level}')
                if error_message:
                    print(f'⚠️  Error: {error_message}')
                print()
                
                # Get tool results
                tools_result = db.execute(
                    text('''
                        SELECT 
                            tool_name, 
                            status, 
                            execution_time,
                            exit_code,
                            error_code,
                            error_message,
                            created_findings_count,
                            parsed_findings_count,
                            started_at,
                            completed_at
                        FROM tool_results 
                        WHERE scan_job_id = :scan_id 
                        ORDER BY created_at ASC
                    '''),
                    {'scan_id': scan_id}
                )
                tools = tools_result.fetchall()
                
                # Count tool statuses
                tool_counts = {
                    'completed': 0,
                    'failed': 0,
                    'running': 0,
                    'pending': 0,
                    'timed_out': 0,
                    'skipped': 0,
                }
                
                for tool in tools:
                    status = tool[1] or 'pending'
                    if status in tool_counts:
                        tool_counts[status] += 1
                
                total_tools = len(tools)
                done_tools = tool_counts['completed'] + tool_counts['failed'] + tool_counts['timed_out'] + tool_counts['skipped']
                
                # Print tool summary
                print(f'🔧 Tools: {done_tools}/{total_tools} done')
                print(f'   ✅ Completed: {tool_counts["completed"]} | ❌ Failed: {tool_counts["failed"]} | 🔄 Running: {tool_counts["running"]} | ⏳ Pending: {tool_counts["pending"]}')
                print()
                
                # Print tool details
                if tools:
                    print(f'{"Tool":<15} {"Status":<12} {"Time":<10} {"Findings":<10} {"Exit":<6} {"Error":<30}')
                    print('-' * 80)
                    for tool in tools:
                        tool_name = tool[0] or 'N/A'
                        status = tool[1] or 'pending'
                        exec_time = tool[2]
                        exit_code = tool[3]
                        error_code = tool[4]
                        error_msg = tool[5]
                        findings = tool[6] or 0
                        parsed_findings = tool[7] or 0
                        
                        icon = get_status_icon(status)
                        time_str = format_duration(exec_time) if exec_time else '-'
                        exit_str = str(exit_code) if exit_code is not None else '-'
                        findings_str = f"{findings}" if findings > 0 else "0"
                        if parsed_findings > 0 and findings == 0:
                            findings_str += f" ({parsed_findings} parsed)"
                        
                        error_display = (error_code or error_msg or '')[:28]
                        
                        print(f'{icon} {tool_name:<13} {status:<12} {time_str:<10} {findings_str:<10} {exit_str:<6} {error_display:<30}')
                else:
                    print('⏳ No tools started yet...')
                
                print()
                
                # Get findings count
                findings_result = db.execute(
                    text('''
                        SELECT 
                            COUNT(*) as total,
                            COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical,
                            COUNT(CASE WHEN severity = 'high' THEN 1 END) as high,
                            COUNT(CASE WHEN severity = 'medium' THEN 1 END) as medium,
                            COUNT(CASE WHEN severity = 'low' THEN 1 END) as low,
                            COUNT(CASE WHEN severity = 'info' THEN 1 END) as info
                        FROM findings 
                        WHERE scan_job_id = :scan_id
                    '''),
                    {'scan_id': scan_id}
                )
                findings_stats = findings_result.fetchone()
                
                total_findings = findings_stats[0] if findings_stats else 0
                critical = findings_stats[1] if findings_stats else 0
                high = findings_stats[2] if findings_stats else 0
                medium = findings_stats[3] if findings_stats else 0
                low = findings_stats[4] if findings_stats else 0
                info = findings_stats[5] if findings_stats else 0
                
                # Print findings summary
                print(f'📋 Findings: {total_findings} total')
                if total_findings > 0:
                    print(f'   🔴 Critical: {critical} | 🟠 High: {high} | 🟡 Medium: {medium} | 🔵 Low: {low} | ⚪ Info: {info}')
                
                # Check for changes
                if total_tools != last_tool_count:
                    print(f'\n🆕 New tool detected! (Total: {last_tool_count} → {total_tools})')
                    last_tool_count = total_tools
                
                if total_findings != last_finding_count:
                    new_findings = total_findings - last_finding_count
                    print(f'\n🆕 {new_findings} new finding(s) detected! (Total: {last_finding_count} → {total_findings})')
                    last_finding_count = total_findings
                
                # Check if scan is complete
                if scan_status in ('completed', 'completed_with_errors', 'failed'):
                    print(f'\n✅ Scan {scan_status.upper()}!')
                    if completed_at:
                        total_time = (completed_at - started_at).total_seconds() if started_at else 0
                        print(f'   Total duration: {format_duration(total_time)}')
                    print(f'\nPress Ctrl+C to exit')
                    time.sleep(refresh_interval)
                    break
                
                print(f'\n⏱️  Next update in {refresh_interval}s... (Press Ctrl+C to stop)')
                time.sleep(refresh_interval)
                
        except KeyboardInterrupt:
            print(f'\n\n👋 Monitoring stopped.')
            print(f'   Final status: {scan_status}')
            print(f'   Tools: {done_tools}/{total_tools} done')
            print(f'   Findings: {total_findings}')
        
        db.close()
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    from datetime import timezone
    
    if len(sys.argv) < 2:
        print('Usage: python3 monitor_scan.py <scan_id> [refresh_interval]')
        print('Example: python3 monitor_scan.py DF3C109E 5')
        print('         python3 monitor_scan.py DF3C109E 10  # Update every 10 seconds')
        sys.exit(1)
    
    scan_id = sys.argv[1]
    refresh = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    monitor_scan(scan_id, refresh)

