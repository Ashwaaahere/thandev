#!/usr/bin/env python3
"""
Monitor the most recent scan automatically
"""
import os
import sys
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
except ImportError:
    print("❌ sqlalchemy not installed. Install with: pip install sqlalchemy psycopg2-binary")
    sys.exit(1)

# Get database URL from environment
db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:6ySBsM6lRK8JSMQu@db.kooxcykmlwonxqdushgt.supabase.co:5432/postgres?sslmode=require')

def find_latest_scan():
    """Find the most recent scan"""
    try:
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        result = db.execute(
            text('''
                SELECT id, status, scan_level, url, created_at 
                FROM scan_jobs 
                ORDER BY created_at DESC 
                LIMIT 5
            ''')
        )
        scans = result.fetchall()
        
        if not scans:
            print('❌ No scans found')
            db.close()
            return None
        
        print('📊 Recent Scans:')
        print('-' * 80)
        for i, scan in enumerate(scans, 1):
            scan_id = scan[0]
            status = scan[1]
            level = scan[2]
            url = scan[3]
            created = scan[4]
            print(f'{i}. {scan_id[:8]}... | {status.upper():<20} | {level:<10} | {url[:50]}')
            print(f'   Created: {created}')
        
        db.close()
        
        # Return the most recent scan
        return scans[0][0] if scans else None
        
    except Exception as e:
        print(f'❌ Error finding latest scan: {e}')
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    latest_scan_id = find_latest_scan()
    
    if latest_scan_id:
        print(f'\n🎯 Monitoring most recent scan: {latest_scan_id[:8]}...')
        print('   Starting monitor...\n')
        
        # Run the monitor script
        script_path = os.path.join(os.path.dirname(__file__), 'monitor_scan.py')
        subprocess.run([sys.executable, script_path, latest_scan_id, '5'])
    else:
        print('\n❌ Could not find a scan to monitor')

