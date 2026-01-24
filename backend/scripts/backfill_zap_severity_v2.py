#!/usr/bin/env python3
"""
Backfill ZAP findings with correct severity and CWE IDs from raw_data.

This script:
1. Finds all ZAP findings with missing zap_riskcode or severity=INFO
2. Extracts riskcode/confidence/cweid from raw_data
3. Converts 'risk' string field (Low/Medium/High) to riskcode integer
4. Computes correct severity using severity engine
5. Updates findings in database

Usage:
    python backfill_zap_severity_v2.py [--scan-id SCAN_ID]
"""
import sys
import os
import logging
from pathlib import Path
from collections import Counter

# Add backend directory to path for imports
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.core.database import SessionLocal
from app.models.finding import Finding, Severity
from app.utils.raw_data_parser import parse_raw_json, extract_zap_metadata
from app.core.severity import zap_to_severity

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    scan_id = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != '--scan-id' else None
    if len(sys.argv) > 2 and sys.argv[1] == '--scan-id':
        scan_id = sys.argv[2]
    
    if scan_id:
        logger.info(f"Backfilling ZAP findings for scan {scan_id}")
    else:
        logger.info("Backfilling all ZAP findings with missing riskcode or INFO severity")
    
    db = SessionLocal()
    
    try:
        # Query ZAP findings that need backfill
        query = db.query(Finding).filter(Finding.tool_name == "zap")
        
        # Filter for findings that need updating:
        # - zap_riskcode is NULL (metadata not extracted), OR
        # - severity is INFO (likely wrong)
        if hasattr(Finding, 'zap_riskcode'):
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    Finding.zap_riskcode == None,
                    Finding.severity == Severity.INFO
                )
            )
        else:
            # If zap_riskcode column doesn't exist yet, just filter by severity
            query = query.filter(Finding.severity == Severity.INFO)
        
        if scan_id:
            query = query.filter(Finding.scan_job_id == scan_id)
        
        findings = query.all()
        logger.info(f"Found {len(findings)} ZAP findings to process")
        
        updates_by_severity = Counter()
        skipped = 0
        errors = 0
        
        for finding in findings:
            try:
                # Parse raw_data to extract ZAP metadata
                raw_dict = parse_raw_json(finding.raw_data)
                
                # Extract riskcode from raw_dict
                # ZAP stores it as 'risk' string field (Low/Medium/High), not 'riskcode' integer
                riskcode = 0
                if raw_dict and isinstance(raw_dict, dict):
                    # Try 'risk' field first (ZAP alert format)
                    risk_str = raw_dict.get("risk", "").lower()
                    if risk_str:
                        risk_map = {
                            "informational": 0,
                            "low": 1,
                            "medium": 2,
                            "high": 3,
                            "critical": 4,
                        }
                        riskcode = risk_map.get(risk_str, 0)
                    
                    # Fallback to 'riskcode' if present
                    if riskcode == 0 and "riskcode" in raw_dict:
                        try:
                            riskcode = int(raw_dict["riskcode"])
                        except (ValueError, TypeError):
                            pass
                
                # Extract confidence
                confidence = 0
                if raw_dict and isinstance(raw_dict, dict):
                    conf_raw = raw_dict.get("confidence", "").lower()
                    if conf_raw:
                        conf_map = {
                            "low": 0,
                            "medium": 1,
                            "high": 2,
                            "confirmed": 3,
                        }
                        confidence = conf_map.get(conf_raw, 0)
                
                # Extract CWE ID
                cweid = None
                if raw_dict and isinstance(raw_dict, dict):
                    cweid = raw_dict.get("cweid") or raw_dict.get("cweId")
                
                # Skip if no riskcode
                if riskcode == 0:
                    logger.debug(f"Skipping finding {finding.id[:8]}... - no valid riskcode (risk={raw_dict.get('risk') if raw_dict else 'N/A'})")
                    skipped += 1
                    continue
                
                # Compute severity from riskcode
                alert_name = raw_dict.get("alert") or finding.title if raw_dict else finding.title
                severity, needs_verification = zap_to_severity(
                    riskcode,
                    confidence,
                    alert_name,
                    raw_dict or {}
                )
                
                # Update finding if severity changed or metadata is missing
                needs_update = False
                
                if finding.severity != severity:
                    logger.info(
                        f"Updating finding {finding.id[:8]}...: "
                        f"{finding.severity.value} -> {severity.value} "
                        f"(riskcode={riskcode}, confidence={confidence}, risk={raw_dict.get('risk') if raw_dict else 'N/A'})"
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
                
                # Update CWE ID if missing
                if not finding.cwe_id and cweid:
                    if isinstance(cweid, (int, float)):
                        finding.cwe_id = f"CWE-{int(cweid)}"
                    elif isinstance(cweid, str) and not cweid.upper().startswith("CWE-"):
                        try:
                            finding.cwe_id = f"CWE-{int(cweid)}"
                        except (ValueError, TypeError):
                            finding.cwe_id = cweid
                    else:
                        finding.cwe_id = cweid
                    needs_update = True
                
                # Update other ZAP metadata
                if raw_dict and isinstance(raw_dict, dict):
                    if not finding.wasc_id and "wascid" in raw_dict:
                        try:
                            finding.wasc_id = int(raw_dict["wascid"])
                            needs_update = True
                        except (ValueError, TypeError):
                            pass
                    
                    if not finding.plugin_id and "pluginId" in raw_dict:
                        finding.plugin_id = str(raw_dict["pluginId"])
                        needs_update = True
                    
                    if not finding.alert_ref and "alertRef" in raw_dict:
                        finding.alert_ref = str(raw_dict["alertRef"])
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
            logger.error(f"Failed to commit changes: {e}")
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
        logger.info("="*60)
        for sev, count in sorted(updates_by_severity.items()):
            logger.info(f"  {sev.upper()}: {count}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

