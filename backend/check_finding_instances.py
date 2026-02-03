#!/usr/bin/env python3
"""
Check how many FindingInstance records exist in the database for a specific finding.
This helps diagnose why only 1 URL is shown when 182 are expected.
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Get database URL from environment or use default
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Try to get from docker-compose or use local default
    DATABASE_URL = "postgresql://thandev:thandev@localhost:5432/thandev"

def check_finding_instances(finding_id: str = None, scan_id: str = None):
    """Check finding instances in database"""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        if finding_id:
            # Check specific finding
            print(f"\n🔍 Checking finding: {finding_id}\n")
            
            # Get finding details
            finding_query = text("""
                SELECT id, title, affected_count, tool_name, scan_job_id
                FROM findings
                WHERE id = :finding_id
            """)
            finding = session.execute(finding_query, {"finding_id": finding_id}).fetchone()
            
            if not finding:
                print(f"❌ Finding {finding_id} not found in database")
                return
            
            print(f"Finding Details:")
            print(f"  ID: {finding[0]}")
            print(f"  Title: {finding[1]}")
            print(f"  Affected Count: {finding[2]}")
            print(f"  Tool: {finding[3]}")
            print(f"  Scan ID: {finding[4]}")
            
            # Count instances in database
            instance_count_query = text("""
                SELECT COUNT(*) as count
                FROM finding_instances
                WHERE finding_id = :finding_id
            """)
            instance_count = session.execute(instance_count_query, {"finding_id": finding_id}).fetchone()[0]
            
            print(f"\n📊 Instance Count in Database: {instance_count}")
            print(f"📊 Affected Count on Finding: {finding[2]}")
            
            if instance_count < finding[2]:
                print(f"\n⚠️  WARNING: Only {instance_count} instances stored, but affected_count is {finding[2]}")
                print(f"   Missing: {finding[2] - instance_count} instances")
            elif instance_count > finding[2]:
                print(f"\n⚠️  WARNING: {instance_count} instances stored, but affected_count is only {finding[2]}")
                print(f"   Extra: {instance_count - finding[2]} instances")
            else:
                print(f"\n✅ Instance count matches affected_count")
            
            # Get sample of instances
            sample_query = text("""
                SELECT url, path, http_method, parameter, is_static_asset
                FROM finding_instances
                WHERE finding_id = :finding_id
                ORDER BY url ASC NULLS LAST, path ASC NULLS LAST
                LIMIT 10
            """)
            samples = session.execute(sample_query, {"finding_id": finding_id}).fetchall()
            
            print(f"\n📋 Sample URLs (first 10):")
            for i, sample in enumerate(samples, 1):
                url = sample[0] or sample[1] or "N/A"
                method = sample[2] or "GET"
                param = sample[3] or ""
                static = " (static)" if sample[4] else ""
                print(f"  {i}. {method} {url}{' - ' + param if param else ''}{static}")
            
            if instance_count > 10:
                print(f"  ... and {instance_count - 10} more")
        
        elif scan_id:
            # Check all findings in scan
            print(f"\n🔍 Checking all findings in scan: {scan_id}\n")
            
            findings_query = text("""
                SELECT id, title, affected_count, tool_name,
                       (SELECT COUNT(*) FROM finding_instances WHERE finding_id = findings.id) as instance_count
                FROM findings
                WHERE scan_job_id = :scan_id
                ORDER BY affected_count DESC
                LIMIT 20
            """)
            findings = session.execute(findings_query, {"scan_id": scan_id}).fetchall()
            
            print(f"Findings with instance mismatches (top 20 by affected_count):\n")
            print(f"{'Finding ID':<40} {'Title':<50} {'Affected':<10} {'In DB':<10} {'Status'}")
            print("-" * 120)
            
            mismatches = []
            for finding in findings:
                fid = finding[0]
                title = finding[1][:47] + "..." if finding[1] and len(finding[1]) > 50 else (finding[1] or "N/A")
                affected = finding[2] or 0
                in_db = finding[3] or 0
                
                if affected != in_db:
                    status = "⚠️ MISMATCH"
                    mismatches.append((fid, title, affected, in_db))
                else:
                    status = "✅ OK"
                
                print(f"{fid:<40} {title:<50} {affected:<10} {in_db:<10} {status}")
            
            if mismatches:
                print(f"\n⚠️  Found {len(mismatches)} findings with mismatches")
                print(f"\nTo check a specific finding, run:")
                print(f"  python3 check_finding_instances.py <finding_id>")
                for fid, title, affected, in_db in mismatches[:5]:
                    print(f"  python3 check_finding_instances.py {fid}")
            else:
                print(f"\n✅ All findings have matching instance counts")
        
        else:
            print("Usage:")
            print("  python3 check_finding_instances.py <finding_id>")
            print("  python3 check_finding_instances.py --scan <scan_id>")
            print("\nExample:")
            print("  python3 check_finding_instances.py abc-123-def")
            print("  python3 check_finding_instances.py --scan scan-123")
    
    finally:
        session.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 check_finding_instances.py <finding_id>")
        print("   or: python3 check_finding_instances.py --scan <scan_id>")
        sys.exit(1)
    
    if sys.argv[1] == "--scan":
        if len(sys.argv) < 3:
            print("Error: --scan requires a scan_id")
            sys.exit(1)
        check_finding_instances(scan_id=sys.argv[2])
    else:
        check_finding_instances(finding_id=sys.argv[1])

