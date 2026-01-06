#!/usr/bin/env python3
"""
Script to cancel all queued and running scans.
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.scan import ScanJob, ScanStatus
from datetime import datetime, timezone

def cancel_all_queued_scans():
    """Cancel all QUEUED and RUNNING scans"""
    db = SessionLocal()
    try:
        # Find all queued and running scans
        queued_scans = db.query(ScanJob).filter(
            ScanJob.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING])
        ).all()
        
        if not queued_scans:
            print("No queued or running scans found.")
            return
        
        print(f"Found {len(queued_scans)} queued/running scans to cancel:")
        
        cancelled_count = 0
        for scan in queued_scans:
            print(f"  - Scan {scan.id} ({scan.status.value}) - Project: {scan.project_id}")
            scan.status = ScanStatus.CANCELLED
            scan.completed_at = datetime.now(timezone.utc)
            scan.error_message = "Cancelled by user"
            cancelled_count += 1
        
        db.commit()
        print(f"\n✅ Successfully cancelled {cancelled_count} scan(s).")
        
    except Exception as e:
        print(f"❌ Error cancelling scans: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    cancel_all_queued_scans()


Script to cancel all queued and running scans.
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.scan import ScanJob, ScanStatus
from datetime import datetime, timezone

def cancel_all_queued_scans():
    """Cancel all QUEUED and RUNNING scans"""
    db = SessionLocal()
    try:
        # Find all queued and running scans
        queued_scans = db.query(ScanJob).filter(
            ScanJob.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING])
        ).all()
        
        if not queued_scans:
            print("No queued or running scans found.")
            return
        
        print(f"Found {len(queued_scans)} queued/running scans to cancel:")
        
        cancelled_count = 0
        for scan in queued_scans:
            print(f"  - Scan {scan.id} ({scan.status.value}) - Project: {scan.project_id}")
            scan.status = ScanStatus.CANCELLED
            scan.completed_at = datetime.now(timezone.utc)
            scan.error_message = "Cancelled by user"
            cancelled_count += 1
        
        db.commit()
        print(f"\n✅ Successfully cancelled {cancelled_count} scan(s).")
        
    except Exception as e:
        print(f"❌ Error cancelling scans: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    cancel_all_queued_scans()


Script to cancel all queued and running scans.
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.scan import ScanJob, ScanStatus
from datetime import datetime, timezone

def cancel_all_queued_scans():
    """Cancel all QUEUED and RUNNING scans"""
    db = SessionLocal()
    try:
        # Find all queued and running scans
        queued_scans = db.query(ScanJob).filter(
            ScanJob.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING])
        ).all()
        
        if not queued_scans:
            print("No queued or running scans found.")
            return
        
        print(f"Found {len(queued_scans)} queued/running scans to cancel:")
        
        cancelled_count = 0
        for scan in queued_scans:
            print(f"  - Scan {scan.id} ({scan.status.value}) - Project: {scan.project_id}")
            scan.status = ScanStatus.CANCELLED
            scan.completed_at = datetime.now(timezone.utc)
            scan.error_message = "Cancelled by user"
            cancelled_count += 1
        
        db.commit()
        print(f"\n✅ Successfully cancelled {cancelled_count} scan(s).")
        
    except Exception as e:
        print(f"❌ Error cancelling scans: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    cancel_all_queued_scans()


Script to cancel all queued and running scans.
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.scan import ScanJob, ScanStatus
from datetime import datetime, timezone

def cancel_all_queued_scans():
    """Cancel all QUEUED and RUNNING scans"""
    db = SessionLocal()
    try:
        # Find all queued and running scans
        queued_scans = db.query(ScanJob).filter(
            ScanJob.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING])
        ).all()
        
        if not queued_scans:
            print("No queued or running scans found.")
            return
        
        print(f"Found {len(queued_scans)} queued/running scans to cancel:")
        
        cancelled_count = 0
        for scan in queued_scans:
            print(f"  - Scan {scan.id} ({scan.status.value}) - Project: {scan.project_id}")
            scan.status = ScanStatus.CANCELLED
            scan.completed_at = datetime.now(timezone.utc)
            scan.error_message = "Cancelled by user"
            cancelled_count += 1
        
        db.commit()
        print(f"\n✅ Successfully cancelled {cancelled_count} scan(s).")
        
    except Exception as e:
        print(f"❌ Error cancelling scans: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    cancel_all_queued_scans()

