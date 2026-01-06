#!/usr/bin/env python3
"""
Backfill script to extract location fields (url, http_method, parameter) from raw_data
for existing findings where these fields are NULL.

Usage:
    python -m backend.scripts.backfill_finding_locations
    python -m backend.scripts.backfill_finding_locations --dry-run  # Preview changes
"""

import sys
import json
import argparse
from pathlib import Path

# Add backend directory to path to import app modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.finding import Finding
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_location_from_raw_data(raw_data_str: str) -> dict:
    """
    Extract url, http_method, and parameter from raw_data JSON.
    
    Returns dict with keys: url, http_method, parameter (values may be None)
    """
    result = {"url": None, "http_method": None, "parameter": None}
    
    if not raw_data_str:
        return result
    
    try:
        raw_data = json.loads(raw_data_str) if isinstance(raw_data_str, str) else raw_data_str
        if not isinstance(raw_data, dict):
            return result
        
        # Extract URL from various possible keys
        url_candidates = ["url", "target", "path", "matched-at", "matched_at", "matched", "request_url"]
        for key in url_candidates:
            if key in raw_data and raw_data[key]:
                result["url"] = str(raw_data[key])[:2048]  # Respect column length limit
                break
        
        # Extract HTTP method
        method = raw_data.get("method") or raw_data.get("http_method") or raw_data.get("request_method")
        if method:
            method_upper = str(method).upper().strip()
            # Normalize to valid HTTP methods
            valid_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
            if method_upper in valid_methods:
                result["http_method"] = method_upper
            else:
                # Default to GET if method is invalid
                result["http_method"] = "GET"
        else:
            # If no method found but we have a URL, default to GET
            if result["url"]:
                result["http_method"] = "GET"
        
        # Extract parameter
        param_candidates = ["param", "parameter", "param_name", "paramName", "query_param", "queryParam"]
        for key in param_candidates:
            if key in raw_data and raw_data[key]:
                result["parameter"] = str(raw_data[key])[:255]  # Respect column length limit
                break
        
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.debug(f"Failed to parse raw_data: {e}")
        return result
    
    return result


def backfill_finding_locations(db: Session, dry_run: bool = False) -> dict:
    """
    Backfill url, http_method, and parameter fields from raw_data.
    
    Returns dict with stats: {"updated": int, "skipped": int, "errors": int}
    """
    stats = {"updated": 0, "skipped": 0, "errors": 0}
    
    # Find findings where at least one location field is NULL
    findings = db.query(Finding).filter(
        (Finding.url.is_(None)) | 
        (Finding.http_method.is_(None)) | 
        (Finding.parameter.is_(None))
    ).all()
    
    logger.info(f"Found {len(findings)} findings with missing location fields")
    
    for finding in findings:
        try:
            if not finding.raw_data:
                stats["skipped"] += 1
                continue
            
            # Extract location from raw_data
            extracted = extract_location_from_raw_data(finding.raw_data)
            
            # Only update fields that are currently NULL
            updated = False
            if not finding.url and extracted["url"]:
                finding.url = extracted["url"]
                updated = True
            
            if not finding.http_method and extracted["http_method"]:
                finding.http_method = extracted["http_method"]
                updated = True
            
            if not finding.parameter and extracted["parameter"]:
                finding.parameter = extracted["parameter"]
                updated = True
            
            if updated:
                if not dry_run:
                    db.commit()
                stats["updated"] += 1
                logger.debug(f"Updated finding {finding.id}: url={extracted['url']}, method={extracted['http_method']}, param={extracted['parameter']}")
            else:
                stats["skipped"] += 1
                
        except Exception as e:
            logger.error(f"Error processing finding {finding.id}: {e}", exc_info=True)
            stats["errors"] += 1
            if not dry_run:
                db.rollback()
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Backfill finding location fields from raw_data")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without committing")
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        logger.info(f"Starting backfill (dry_run={args.dry_run})...")
        stats = backfill_finding_locations(db, dry_run=args.dry_run)
        
        logger.info("Backfill completed:")
        logger.info(f"  - Updated: {stats['updated']}")
        logger.info(f"  - Skipped: {stats['skipped']}")
        logger.info(f"  - Errors: {stats['errors']}")
        
        if args.dry_run:
            logger.info("DRY RUN: No changes were committed")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

