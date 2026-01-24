#!/usr/bin/env python3
"""
Backfill script to fix ZAP findings severity based on riskcode.

Usage:
    python backfill_zap_severity.py [scan_id]
    
If scan_id is provided, only backfill findings for that scan.
Otherwise, backfill all ZAP findings where zap_riskcode is null OR severity == 'info'.
"""
import sys
import os
import json
import logging
from collections import Counter

# Add backend directory to path (works both locally and in container)
from pathlib import Path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
# Also ensure /app is in path for container
if '/app' not in sys.path:
    sys.path.insert(0, '/app')

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.finding import Finding, Severity
from app.models.scan import ScanJob
from app.core.severity import zap_to_severity
from app.utils.raw_data_parser import parse_raw_json, extract_zap_metadata

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def backfill_zap_severity(db: Session, scan_id: str = None):
    """
    Backfill ZAP findings severity based on riskcode from raw_data.
    
    Args:
        db: Database session
        scan_id: Optional scan ID to limit backfilling to specific scan
    """
    # Query ZAP findings that need backfilling
    query = db.query(Finding).filter(Finding.tool_name == "zap")
    
    if scan_id:
        query = query.join(ScanJob).filter(ScanJob.id == scan_id)
        logger.info(f"Backfilling ZAP findings for scan: {scan_id}")
    else:
        # Only backfill findings where zap_riskcode is null OR severity is INFO
        # Check if zap_riskcode column exists
        if hasattr(Finding, 'zap_riskcode'):
            query = query.filter(
                (Finding.zap_riskcode.is_(None)) | (Finding.severity == Severity.INFO)
            )
        else:
            # If column doesn't exist, just backfill all INFO findings
            query = query.filter(Finding.severity == Severity.INFO)
        logger.info("Backfilling all ZAP findings with missing riskcode or INFO severity")
    
    findings = query.all()
    logger.info(f"Found {len(findings)} ZAP findings to process")
    
    if not findings:
        logger.info("No findings to backfill")
        return
    
    # Track updates by severity
    updates_by_severity = Counter()
    skipped = 0
    errors = 0
    
    for finding in findings:
        try:
            # Parse raw_data to extract riskcode
            raw_dict = parse_raw_json(finding.raw_data)
            zap_meta = extract_zap_metadata(finding.raw_data)
            
            riskcode = zap_meta["riskcode"]
            confidence = zap_meta["confidence"]
            alert_name = zap_meta["alert"] or finding.title
            
            # Skip if we can't extract riskcode and it's not already stored
            existing_riskcode = getattr(finding, 'zap_riskcode', None) if hasattr(Finding, 'zap_riskcode') else None
            if riskcode == 0 and existing_riskcode is None:
                # Try to use existing zap_riskcode if available
                if existing_riskcode is not None:
                    riskcode = existing_riskcode
                else:
                    logger.debug(f"Skipping finding {finding.id[:8]}... - no riskcode found in raw_data")
                    skipped += 1
                    continue
            
            # Compute severity from riskcode
            severity, needs_verification = zap_to_severity(
                riskcode,
                confidence,
                alert_name,
                raw_dict
            )
            
            # Update finding if severity changed or metadata is missing
            needs_update = False
            
            if finding.severity != severity:
                logger.info(
                    f"Updating finding {finding.id[:8]}...: "
                    f"{finding.severity.value} -> {severity.value} "
                    f"(riskcode={riskcode}, confidence={confidence})"
                )
                finding.severity = severity
                needs_update = True
            
            if hasattr(Finding, 'zap_riskcode'):
                if getattr(finding, 'zap_riskcode', None) != riskcode:
                    setattr(finding, 'zap_riskcode', riskcode)
                    needs_update = True
            
            if hasattr(Finding, 'zap_confidence'):
                if getattr(finding, 'zap_confidence', None) != confidence:
                    setattr(finding, 'zap_confidence', confidence)
                    needs_update = True
            
            if finding.needs_verification != needs_verification:
                finding.needs_verification = needs_verification
                needs_update = True
            
            # Update ZAP metadata if missing
            if not finding.wasc_id and zap_meta["wascid"]:
                finding.wasc_id = zap_meta["wascid"]
                needs_update = True
            
            if not finding.plugin_id and zap_meta["pluginId"]:
                finding.plugin_id = zap_meta["pluginId"]
                needs_update = True
            
            if not finding.alert_ref and zap_meta["alertRef"]:
                finding.alert_ref = zap_meta["alertRef"]
                needs_update = True
            
            if not finding.cwe_id and zap_meta["cweid"]:
                cwe_id = zap_meta["cweid"]
                if isinstance(cwe_id, (int, float)):
                    finding.cwe_id = f"CWE-{int(cwe_id)}"
                elif isinstance(cwe_id, str) and not cwe_id.upper().startswith("CWE-"):
                    try:
                        finding.cwe_id = f"CWE-{int(cwe_id)}"
                    except (ValueError, TypeError):
                        finding.cwe_id = cwe_id
                else:
                    finding.cwe_id = cwe_id
                needs_update = True
            
            if needs_update:
                updates_by_severity[severity.value] += 1
                db.flush()  # Flush to get errors early
            else:
                skipped += 1
                
        except Exception as e:
            logger.error(f"Error processing finding {finding.id[:8]}...: {e}", exc_info=True)
            errors += 1
            continue
    
    # Commit all changes
    try:
        db.commit()
        logger.info("✓ Successfully committed all updates")
    except Exception as e:
        logger.error(f"Error committing changes: {e}", exc_info=True)
        db.rollback()
        raise
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("BACKFILL SUMMARY")
    logger.info("="*60)
    logger.info(f"Total findings processed: {len(findings)}")
    logger.info(f"Updated: {sum(updates_by_severity.values())}")
    logger.info(f"Skipped: {skipped}")
    logger.info(f"Errors: {errors}")
    logger.info("\nUpdates by severity:")
    for sev in ["critical", "high", "medium", "low", "info"]:
        count = updates_by_severity.get(sev, 0)
        if count > 0:
            logger.info(f"  {sev.upper()}: {count}")
    logger.info("="*60)


if __name__ == "__main__":
    db = SessionLocal()
    try:
        scan_id = sys.argv[1] if len(sys.argv) > 1 else None
        backfill_zap_severity(db, scan_id)
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        db.rollback()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

