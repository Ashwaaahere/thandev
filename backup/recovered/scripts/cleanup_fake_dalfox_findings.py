#!/usr/bin/env python3
"""
Cleanup script to remove fake/empty dalfox findings from the database.

Fake findings are those where:
- tool_name = 'dalfox'
- url IS NULL or empty
- parameter IS NULL or empty
- These were created from empty dalfox output like [{}] before the validation fix
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.finding import Finding
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_fake_dalfox_findings(scan_job_id: str = None, dry_run: bool = True):
    """
    Remove fake dalfox findings from the database.
    
    Args:
        scan_job_id: Optional specific scan job ID to clean. If None, cleans all scans.
        dry_run: If True, only show what would be deleted without actually deleting.
    """
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Build query for fake dalfox findings
        query = db.query(Finding).filter(
            Finding.tool_name == "dalfox",
            or_(
                Finding.url.is_(None),
                Finding.url == "",
                Finding.url == "None"
            ),
            or_(
                Finding.parameter.is_(None),
                Finding.parameter == "",
                Finding.parameter == "None"
            )
        )
        
        # Filter by scan_job_id if provided
        if scan_job_id:
            query = query.filter(Finding.scan_job_id == scan_job_id)
            logger.info(f"Looking for fake dalfox findings in scan {scan_job_id}")
        else:
            logger.info("Looking for fake dalfox findings across all scans")
        
        fake_findings = query.all()
        
        if not fake_findings:
            logger.info("No fake dalfox findings found")
            return 0
        
        logger.info(f"Found {len(fake_findings)} fake dalfox finding(s)")
        
        # Show details
        for finding in fake_findings:
            logger.info(
                f"  - Finding ID: {finding.id}, "
                f"Scan: {finding.scan_job_id}, "
                f"Title: {finding.title}, "
                f"URL: {finding.url or '(empty)'}, "
                f"Parameter: {finding.parameter or '(empty)'}"
            )
        
        if dry_run:
            logger.info("\n*** DRY RUN MODE - No changes made ***")
            logger.info(f"Would delete {len(fake_findings)} fake finding(s)")
            return len(fake_findings)
        
        # Delete the findings
        deleted_count = query.delete(synchronize_session=False)
        db.commit()
        
        logger.info(f"\nSuccessfully deleted {deleted_count} fake dalfox finding(s)")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error cleaning up fake findings: {e}", exc_info=True)
        db.rollback()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cleanup fake dalfox findings from database")
    parser.add_argument(
        "--scan-id",
        type=str,
        help="Specific scan job ID to clean (optional, cleans all if not provided)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete findings (default is dry-run mode)"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    if dry_run:
        logger.info("Running in DRY RUN mode. Use --execute to actually delete findings.")
    
    cleanup_fake_dalfox_findings(scan_job_id=args.scan_id, dry_run=dry_run)

