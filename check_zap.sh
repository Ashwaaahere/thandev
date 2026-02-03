#!/bin/bash
# Quick script to check if ZAP is running for a scan
# Usage: ./check_zap.sh [scan_id]

SCAN_ID="${1:-}"

if [ -z "$SCAN_ID" ]; then
    echo "Usage: ./check_zap.sh <scan_id>"
    echo "Example: ./check_zap.sh a8d4e2f4"
    echo ""
    echo "Checking most recent running scan..."
    SCAN_ID=""
fi

docker compose -f docker-compose.fly-local.yml exec -T backend python3 -c "
import sys
sys.path.insert(0, '/app')
from sqlalchemy import create_engine, text
import os
from datetime import datetime, timezone

db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:6ySBsM6lRK8JSMQu@db.kooxcykmlwonxqdushgt.supabase.co:5432/postgres?sslmode=require')
engine = create_engine(db_url)
with engine.connect() as conn:
    if '$SCAN_ID':
        # Find scan by ID (partial match)
        result = conn.execute(text('''
            SELECT id, status, scan_level, url, started_at, created_at
            FROM scan_jobs 
            WHERE id LIKE :scan_id
            ORDER BY created_at DESC 
            LIMIT 1
        '''), {'scan_id': f'$SCAN_ID%'})
    else:
        # Get most recent running scan
        result = conn.execute(text('''
            SELECT id, status, scan_level, url, started_at, created_at
            FROM scan_jobs 
            WHERE status IN ('running', 'queued')
            ORDER BY created_at DESC 
            LIMIT 1
        '''))
    
    scan = result.fetchone()
    if not scan:
        print('❌ No scan found')
        exit(1)
    
    scan_id = scan[0]
    status = scan[1]
    scan_level = scan[2]
    url = scan[3]
    started_at = scan[4]
    created_at = scan[5]
    
    print('=' * 80)
    print(f'📊 Scan ID: {scan_id}')
    print(f'Status: {status}')
    print(f'Level: {scan_level}')
    print(f'URL: {url}')
    print(f'Started: {started_at}')
    print('=' * 80)
    print()
    
    # Check ZAP tool states
    zap_result = conn.execute(text('''
        SELECT tool, phase, stage, message, progress, updated_at
        FROM scan_tool_states 
        WHERE scan_id = :scan_id AND tool ILIKE '%zap%'
        ORDER BY updated_at DESC
        LIMIT 5
    '''), {'scan_id': scan_id})
    zap_states = zap_result.fetchall()
    
    if zap_states:
        latest = zap_states[0]
        tool = latest[0]
        phase = latest[1]
        stage = latest[2]
        message = latest[3]
        progress = latest[4]
        updated = latest[5]
        
        print(f'🔍 ZAP Status:')
        print(f'   Tool: {tool}')
        print(f'   Phase: {phase}')
        print(f'   Stage: {stage}')
        print(f'   Message: {message}')
        if progress is not None:
            print(f'   Progress: {int(progress*100)}%')
        print(f'   Last Update: {updated}')
        
        # Calculate time since last update
        if updated:
            now = datetime.now(timezone.utc) if updated.tzinfo else datetime.now()
            if updated.tzinfo:
                time_diff = now - updated
            else:
                time_diff = now.replace(tzinfo=None) - updated
            seconds_ago = int(time_diff.total_seconds())
            if seconds_ago < 60:
                time_str = f'{seconds_ago}s ago'
            elif seconds_ago < 3600:
                time_str = f'{seconds_ago // 60}m ago'
            else:
                hours = seconds_ago // 3600
                mins = (seconds_ago % 3600) // 60
                time_str = f'{hours}h {mins}m ago'
            print(f'   Time Since Update: {time_str}')
        
        print()
        
        # Determine if ZAP is actively running
        is_running = (
            status in ('running', 'queued') and
            phase in ('execution', 'running', 'scan') and
            stage not in ('completed', 'failed', 'timeout', 'cancelled', 'queued')
        )
        
        if is_running:
            print('✅ ZAP is RUNNING')
        elif stage == 'queued':
            print('⏳ ZAP is QUEUED (waiting to start)')
        elif stage == 'completed':
            print('✅ ZAP has COMPLETED')
        elif stage == 'failed':
            print('❌ ZAP has FAILED')
        else:
            print(f'⏸️  ZAP status: {stage}')
        
        if len(zap_states) > 1:
            print()
            print('📝 Recent ZAP Activity:')
            for state in zap_states[1:]:
                phase = state[1]
                stage = state[2]
                message = state[3]
                progress = state[4]
                updated = state[5]
                progress_str = f' ({int(progress*100)}%)' if progress is not None else ''
                print(f'   [{updated}] {phase}/{stage}{progress_str}: {message[:60]}')
    else:
        print('❌ No ZAP tool states found')
        
        # Check tool results
        result_result = conn.execute(text('''
            SELECT tool_name, status, execution_time, findings_count, error_message, created_at
            FROM tool_results 
            WHERE scan_job_id = :scan_id AND tool_name ILIKE '%zap%'
            ORDER BY created_at DESC
            LIMIT 1
        '''), {'scan_id': scan_id})
        zap_result = result_result.fetchone()
        
        if zap_result:
            print()
            print('🔧 ZAP Tool Result:')
            tool_name = zap_result[0]
            tool_status = zap_result[1]
            exec_time = zap_result[2]
            findings = zap_result[3]
            error = zap_result[4]
            created = zap_result[5]
            
            status_icon = '✅' if tool_status == 'completed' else '❌' if tool_status == 'failed' else '⏳'
            print(f'   {status_icon} {tool_name}: {tool_status}')
            if exec_time:
                print(f'   Execution Time: {exec_time:.2f}s')
            if findings:
                print(f'   Findings: {findings}')
            if error:
                print(f'   Error: {error}')
            print(f'   Created: {created}')
"


