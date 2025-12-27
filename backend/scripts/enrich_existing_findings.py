#!/usr/bin/env python3
"""
Optional backfill script to enrich existing findings with AI-generated content.

This script:
1. Selects findings where impact_summary and remediation_summary are NULL
2. Batches them (50 at a time)
3. Calls BrainClient.enrich_findings on each batch
4. Writes results back to the database

Usage:
    python -m backend.scripts.enrich_existing_findings [--dry-run] [--limit N]
"""
import sys
import argparse
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.finding import Finding
from app.services.finding_enrichment import enrich_findings_sync
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def enrich_existing_findings(dry_run: bool = False, limit: int = None, batch_size: int = 50):
    """
    Enrich existing findings that don't have AI-generated content.
    
    Args:
        dry_run: If True, don't actually update the database
        limit: Maximum number of findings to process (None = all)
        batch_size: Number of findings to process per batch
    """
    db: Session = SessionLocal()
    
    try:
        # Query findings that need enrichment
        query = db.query(Finding).filter(
            Finding.remediation_summary.is_(None),
            Finding.remediation_steps.is_(None),
            Finding.raw_data.isnot(None),
        )
        
        if limit:
            query = query.limit(limit)
        
        findings = query.all()
        
        if not findings:
            logger.info("No findings found that need enrichment")
            return
        
        logger.info(f"Found {len(findings)} findings to enrich")
        
        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made to the database")
            for finding in findings[:10]:  # Show first 10 as sample
                logger.info(f"  - Finding {finding.id}: {finding.title[:50]} (vuln_type: {finding.vuln_type})")
            return
        
        # Process in batches
        total_processed = 0
        total_enriched = 0
        
        for i in range(0, len(findings), batch_size):
            batch = findings[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} findings)...")
            
            # Get org_id and project_id from first finding in batch
            # (assuming all findings in batch are from same project)
            org_id = None
            project_id = batch[0].project_id if batch else None
            target_url = None
            
            if batch and batch[0].scan_job:
                scan_job = batch[0].scan_job
                if scan_job.project and hasattr(scan_job.project, 'tenant') and scan_job.project.tenant:
                    org_id = scan_job.project.tenant.id
                if scan_job.stack_info and isinstance(scan_job.stack_info, dict):
                    target_url = scan_job.stack_info.get("target_url")
            
            # Enrich batch
            try:
                enrich_findings_sync(db, batch, org_id, project_id, target_url)
                
                # Count how many were actually enriched
                db.refresh(batch[0])  # Refresh to see if remediation_summary was set
                enriched_in_batch = sum(
                    1 for f in batch
                    if f.remediation_summary or f.remediation_steps
                )
                total_enriched += enriched_in_batch
                total_processed += len(batch)
                
                logger.info(f"  Enriched {enriched_in_batch}/{len(batch)} findings in this batch")
            except Exception as e:
                logger.error(f"  Failed to enrich batch: {e}", exc_info=True)
                continue
        
        logger.info(f"\nCompleted: Processed {total_processed} findings, enriched {total_enriched}")
        
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich existing findings with AI-generated content")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update the database")
    parser.add_argument("--limit", type=int, help="Maximum number of findings to process")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of findings per batch")
    
    args = parser.parse_args()
    
    enrich_existing_findings(
        dry_run=args.dry_run,
        limit=args.limit,
        batch_size=args.batch_size,
    )




