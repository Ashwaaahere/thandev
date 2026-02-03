#!/usr/bin/env python3
"""
Script to debug scan results - check why tools appear failed or no results are showing
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Get database URL from environment
db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:6ySBsM6lRK8JSMQu@db.kooxcykmlwonxqdushgt.supabase.co:5432/postgres?sslmode=require')

def debug_scan_results(scan_id_partial: str):
    try:
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        # Try to find the scan (support partial IDs)
        if len(scan_id_partial) < 36:
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
            
            # Get tool results with detailed status
            tools_result = db.execute(
                text('''
                    SELECT 
                        tool_name, 
                        tool_id, 
                        status, 
                        execution_time, 
                        exit_code,
                        timed_out,
                        error_message,
                        error_code,
                        created_findings_count,
                        output,
                        created_at,
                        started_at,
                        completed_at
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
                    exit_code = tool[4]
                    timed_out = tool[5] or 0
                    error = tool[6]
                    error_code = tool[7]
                    findings_count = tool[8] or 0
                    output = tool[9]
                    created = tool[10]
                    started = tool[11]
                    completed = tool[12]
                    
                    # Determine status icon
                    if status == 'completed':
                        status_icon = '✅'
                    elif status == 'failed':
                        status_icon = '❌'
                    elif status == 'timed_out':
                        status_icon = '⏱️'
                    elif status == 'running':
                        status_icon = '🔄'
                    elif status == 'pending':
                        status_icon = '⏳'
                    elif status == 'skipped':
                        status_icon = '⏭️'
                    else:
                        status_icon = '❓'
                    
                    print(f'{status_icon} {tool_name} ({tool_id})')
                    print(f'   Status: {status}')
                    print(f'   Time: {exec_time:.2f}s' if exec_time else '   Time: N/A')
                    print(f'   Exit Code: {exit_code}' if exit_code is not None else '   Exit Code: N/A')
                    print(f'   Timed Out: {"Yes" if timed_out else "No"}')
                    print(f'   Findings Created: {findings_count}')
                    print(f'   Created: {created}')
                    if started:
                        print(f'   Started: {started}')
                    if completed:
                        print(f'   Completed: {completed}')
                    if error_code:
                        print(f'   Error Code: {error_code}')
                    if error:
                        print(f'   ❌ Error: {error}')
                    if output:
                        output_preview = output[:200] if len(output) > 200 else output
                        print(f'   Output Preview: {output_preview}...' if len(output) > 200 else f'   Output: {output_preview}')
                    print()
            else:
                print('  ⚠️  No tool results found - tools may not have been executed')
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
                        COUNT(CASE WHEN severity = 'info' THEN 1 END) as info,
                        COUNT(DISTINCT tool_name) as tools_with_findings
                    FROM findings 
                    WHERE scan_job_id = :scan_id
                '''),
                {'scan_id': scan_id}
            )
            findings_stats = findings_result.fetchone()
            
            print(f'📋 Findings Summary:')
            print('-' * 80)
            if findings_stats and findings_stats[0] > 0:
                print(f'   Total Findings: {findings_stats[0]}')
                print(f'   Critical: {findings_stats[1]}')
                print(f'   High: {findings_stats[2]}')
                print(f'   Medium: {findings_stats[3]}')
                print(f'   Low: {findings_stats[4]}')
                print(f'   Info: {findings_stats[5]}')
                print(f'   Tools with Findings: {findings_stats[6]}')
            else:
                print('   ⚠️  No findings found in database')
            print()
            
            # Get findings by tool
            findings_by_tool_result = db.execute(
                text('''
                    SELECT 
                        tool_name,
                        COUNT(*) as count,
                        COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical,
                        COUNT(CASE WHEN severity = 'high' THEN 1 END) as high,
                        COUNT(CASE WHEN severity = 'medium' THEN 1 END) as medium
                    FROM findings 
                    WHERE scan_job_id = :scan_id
                    GROUP BY tool_name
                    ORDER BY count DESC
                '''),
                {'scan_id': scan_id}
            )
            findings_by_tool = findings_by_tool_result.fetchall()
            
            if findings_by_tool:
                print(f'📊 Findings by Tool:')
                print('-' * 80)
                for tool_finding in findings_by_tool:
                    tool_name = tool_finding[0]
                    count = tool_finding[1]
                    critical = tool_finding[2]
                    high = tool_finding[3]
                    medium = tool_finding[4]
                    print(f'   {tool_name}: {count} total (C:{critical} H:{high} M:{medium})')
                print()
            
            # Check for common issues
            print(f'🔍 Diagnostic Checks:')
            print('-' * 80)
            
            issues_found = []
            
            # Check if scan is completed but no findings
            if scan[1] == 'completed' and (not findings_stats or findings_stats[0] == 0):
                issues_found.append('⚠️  Scan marked as COMPLETED but no findings found')
            
            # Check for tools with failed status
            failed_tools = [t for t in tools if t[2] == 'failed']
            if failed_tools:
                issues_found.append(f'⚠️  {len(failed_tools)} tool(s) marked as FAILED: {", ".join([t[0] for t in failed_tools])}')
            
            # Check for tools with no findings but completed status
            completed_no_findings = [t for t in tools if t[2] == 'completed' and (not t[8] or t[8] == 0)]
            if completed_no_findings:
                tool_names = [t[0] for t in completed_no_findings]
                issues_found.append(f'⚠️  {len(completed_no_findings)} tool(s) completed but created 0 findings: {", ".join(tool_names)}')
            
            # Check for tools that timed out
            timed_out_tools = [t for t in tools if t[5] and t[5] == 1]
            if timed_out_tools:
                issues_found.append(f'⚠️  {len(timed_out_tools)} tool(s) timed out: {", ".join([t[0] for t in timed_out_tools])}')
            
            # Check for tools with non-zero exit codes
            non_zero_exit = [t for t in tools if t[4] is not None and t[4] != 0]
            if non_zero_exit:
                issues_found.append(f'⚠️  {len(non_zero_exit)} tool(s) with non-zero exit codes: {", ".join([f"{t[0]}({t[4]})" for t in non_zero_exit])}')
            
            # Check for missing Zap
            zap_tools = [t for t in tools if 'zap' in (t[0] or '').lower()]
            if not zap_tools:
                issues_found.append('⚠️  No ZAP tool results found (ZAP may not have been executed)')
            
            if issues_found:
                for issue in issues_found:
                    print(f'   {issue}')
            else:
                print('   ✅ No obvious issues detected')
            print()
        
        db.close()
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    scan_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not scan_id:
        print('Usage: python debug_scan_results.py <scan_id>')
        print('Example: python debug_scan_results.py DF3C109E')
        sys.exit(1)
    debug_scan_results(scan_id)

