#!/usr/bin/env python3
"""
Investigate scan A032D30F - why all tools failed or where results are lost
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Try both local and remote database
db_url_local = 'postgresql://postgres:postgres@localhost:5432/thandev'
db_url_remote = os.getenv('DATABASE_URL', 'postgresql://postgres:6ySBsM6lRK8JSMQu@db.kooxcykmlwonxqdushgt.supabase.co:5432/postgres?sslmode=require')

def investigate_scan(scan_id_partial: str):
    """Investigate scan in both local and remote databases"""
    
    print(f"\n{'='*80}")
    print(f"Investigating Scan: {scan_id_partial}")
    print(f"{'='*80}\n")
    
    # Try local database first
    print("📊 Checking LOCAL database...")
    try:
        engine = create_engine(db_url_local)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        # Find scan
        result = db.execute(
            text('SELECT id, status, scan_level, url, created_at, started_at, completed_at, error_message FROM scan_jobs WHERE id LIKE :scan_id ORDER BY created_at DESC LIMIT 1'),
            {'scan_id': f'{scan_id_partial}%'}
        )
        scan = result.fetchone()
        
        if scan:
            print(f"✅ Found scan in LOCAL database: {scan[0]}")
            print(f"   Status: {scan[1]}")
            print(f"   URL: {scan[3]}")
            print(f"   Created: {scan[4]}")
            
            # Get tool results
            tools_result = db.execute(
                text('''
                    SELECT 
                        tool_name, status, exit_code, error_code, error_message,
                        execution_time, created_findings_count, parsed_findings_count,
                        created_at, started_at, completed_at
                    FROM tool_results 
                    WHERE scan_job_id = :scan_id 
                    ORDER BY created_at ASC
                '''),
                {'scan_id': scan[0]}
            )
            tools = tools_result.fetchall()
            
            print(f"\n🔧 Tool Results ({len(tools)} total):")
            if tools:
                for tool in tools:
                    print(f"   {tool[0]}: {tool[1]} | Exit: {tool[2]} | Findings: {tool[6]}")
                    if tool[4]:
                        print(f"      Error: {tool[4]}")
            else:
                print("   ⚠️  NO TOOL RESULTS FOUND!")
            
            # Get scan events
            events_result = db.execute(
                text('''
                    SELECT phase, tool, stage, message, created_at
                    FROM scan_events 
                    WHERE scan_id = :scan_id 
                    ORDER BY created_at DESC
                    LIMIT 20
                '''),
                {'scan_id': scan[0]}
            )
            events = events_result.fetchall()
            
            print(f"\n📝 Recent Scan Events ({len(events)}):")
            for event in events[:10]:
                print(f"   [{event[4]}] {event[0]}/{event[1]}: {event[2]} - {event[3]}")
        else:
            print("   ❌ Scan not found in LOCAL database")
        
        db.close()
    except Exception as e:
        print(f"   ❌ Error checking local database: {e}")
    
    # Try remote database
    print(f"\n📊 Checking REMOTE database (Supabase)...")
    try:
        engine = create_engine(db_url_remote)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        # Find scan
        result = db.execute(
            text('SELECT id, status, scan_level, url, created_at, started_at, completed_at, error_message FROM scan_jobs WHERE id LIKE :scan_id ORDER BY created_at DESC LIMIT 1'),
            {'scan_id': f'{scan_id_partial}%'}
        )
        scan = result.fetchone()
        
        if scan:
            print(f"✅ Found scan in REMOTE database: {scan[0]}")
            print(f"   Status: {scan[1]}")
            print(f"   URL: {scan[3]}")
            print(f"   Created: {scan[4]}")
            
            # Get tool results
            tools_result = db.execute(
                text('''
                    SELECT 
                        tool_name, status, exit_code, error_code, error_message,
                        execution_time, created_findings_count, parsed_findings_count,
                        created_at, started_at, completed_at
                    FROM tool_results 
                    WHERE scan_job_id = :scan_id 
                    ORDER BY created_at ASC
                '''),
                {'scan_id': scan[0]}
            )
            tools = tools_result.fetchall()
            
            print(f"\n🔧 Tool Results ({len(tools)} total):")
            if tools:
                failed_count = 0
                completed_count = 0
                for tool in tools:
                    status_icon = "✅" if tool[1] == "completed" else "❌" if tool[1] == "failed" else "⏳"
                    print(f"   {status_icon} {tool[0]}: {tool[1]} | Exit: {tool[2]} | Findings: {tool[6]}")
                    if tool[4]:
                        print(f"      Error: {tool[4]}")
                    if tool[1] == "failed":
                        failed_count += 1
                    elif tool[1] == "completed":
                        completed_count += 1
                
                print(f"\n📊 Summary:")
                print(f"   ✅ Completed: {completed_count}")
                print(f"   ❌ Failed: {failed_count}")
                print(f"   ⏳ Other: {len(tools) - completed_count - failed_count}")
            else:
                print("   ⚠️  NO TOOL RESULTS FOUND!")
                print("\n🔍 This means:")
                print("   1. Tools may have executed but failed to POST results to backend")
                print("   2. BACKEND_URL may not have been configured in runner")
                print("   3. POST requests may have failed due to network/auth errors")
                print("   4. Backend endpoint may have rejected requests (validation errors)")
            
            # Get scan events
            events_result = db.execute(
                text('''
                    SELECT phase, tool, stage, message, created_at, meta
                    FROM scan_events 
                    WHERE scan_id = :scan_id 
                    ORDER BY created_at DESC
                    LIMIT 30
                '''),
                {'scan_id': scan[0]}
            )
            events = events_result.fetchall()
            
            print(f"\n📝 Recent Scan Events ({len(events)}):")
            for event in events[:15]:
                stage_icon = "✅" if event[2] == "completed" else "❌" if event[2] == "failed" else "⏳"
                print(f"   {stage_icon} [{event[4]}] {event[0]}/{event[1]}: {event[2]} - {event[3]}")
                if event[5] and isinstance(event[5], dict) and 'error' in event[5]:
                    print(f"      Error details: {event[5].get('error', '')[:100]}")
        else:
            print("   ❌ Scan not found in REMOTE database")
        
        db.close()
    except Exception as e:
        print(f"   ❌ Error checking remote database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    scan_id = sys.argv[1] if len(sys.argv) > 1 else 'A032D30F'
    investigate_scan(scan_id)

