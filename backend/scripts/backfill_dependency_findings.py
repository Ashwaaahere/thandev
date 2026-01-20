"""
Backfill script to convert dependency scan artifacts into Finding records.

This script processes existing ScanArtifact records and creates Finding records
from them so they can be searched by CVE ID.
"""
import sys
import os
import json
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.scan_artifact import ScanArtifact
from app.models.scan import ScanJob
from app.services.findings_ingestor import create_or_update_finding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill_dependency_findings(dry_run: bool = False, scan_id: str = None):
    """
    Process dependency scan artifacts and create Finding records.
    
    Args:
        dry_run: If True, only log what would be done without making changes
        scan_id: Optional specific scan ID to process. If None, processes all.
    """
    db: Session = SessionLocal()
    
    try:
        # Query artifacts
        query = db.query(ScanArtifact).filter(ScanArtifact.type == 'url_sca')
        if scan_id:
            query = query.filter(ScanArtifact.scan_id == scan_id)
        
        artifacts = query.all()
        logger.info(f"Found {len(artifacts)} url_sca artifacts to process")
        
        total_findings_created = 0
        
        for artifact in artifacts:
            try:
                # Get scan job to get project_id
                scan_job = db.query(ScanJob).filter(ScanJob.id == artifact.scan_id).first()
                if not scan_job:
                    logger.warning(f"Scan job {artifact.scan_id} not found, skipping artifact {artifact.id}")
                    continue
                
                project_id = scan_job.project_id
                if not project_id:
                    logger.warning(f"Scan job {artifact.scan_id} has no project_id, skipping")
                    continue
                
                # Get payload
                payload = artifact.payload
                if isinstance(payload, str):
                    payload = json.loads(payload)
                
                findings_list = payload.get("findings", [])
                if not findings_list:
                    logger.debug(f"Artifact {artifact.id} has no findings, skipping")
                    continue
                
                logger.info(f"Processing artifact {artifact.id} for scan {artifact.scan_id}: {len(findings_list)} findings")
                
                findings_created = 0
                for finding_data in findings_list:
                    try:
                        # Extract CVE IDs from references field (retire.js stores them there)
                        cve_id = None
                        references = finding_data.get("references", [])
                        if isinstance(references, list) and len(references) > 0:
                            # Take the first CVE ID from references
                            for ref in references:
                                if isinstance(ref, str) and ref.upper().startswith("CVE-"):
                                    cve_id = ref.upper()
                                    break
                        
                        # Build finding data structure
                        normalized_finding = {
                            "tool": "retire",
                            "tool_name": "retire",
                            "title": f"{finding_data.get('package', 'Unknown')} {finding_data.get('version', '')} - Known Vulnerability",
                            "description": f"Vulnerable dependency detected: {finding_data.get('package', 'Unknown')} version {finding_data.get('version', 'Unknown')}",
                            "severity": finding_data.get("severity", "medium").lower(),
                            "url": finding_data.get("evidence"),  # Script URL where dependency was found
                            "cve_id": cve_id,  # Extract first CVE ID from references
                            "evidence": finding_data.get("evidence"),
                            "raw_data": json.dumps(finding_data, default=str),  # Store full finding data
                        }
                        
                        if not dry_run:
                            finding = create_or_update_finding(
                                db=db,
                                scan_job_id=artifact.scan_id,
                                project_id=project_id,
                                finding_data=normalized_finding,
                                tool_result_id=None,
                            )
                            findings_created += 1
                            total_findings_created += 1
                        else:
                            logger.info(f"[DRY RUN] Would create finding: {normalized_finding['title']} (CVE: {cve_id})")
                            findings_created += 1
                            total_findings_created += 1
                            
                    except Exception as e:
                        logger.warning(f"Failed to create finding from artifact {artifact.id}: {e}", exc_info=True)
                        continue
                
                if findings_created > 0 and not dry_run:
                    db.commit()
                    logger.info(f"Created {findings_created} Finding records from artifact {artifact.id}")
                elif findings_created > 0:
                    logger.info(f"[DRY RUN] Would create {findings_created} Finding records from artifact {artifact.id}")
                    
            except Exception as e:
                logger.error(f"Error processing artifact {artifact.id}: {e}", exc_info=True)
                db.rollback()
                continue
        
        logger.info(f"Total findings created: {total_findings_created}")
        return total_findings_created
        
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill dependency scan findings")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (don't make changes)")
    parser.add_argument("--scan-id", type=str, help="Process specific scan ID only")
    args = parser.parse_args()
    
    backfill_dependency_findings(dry_run=args.dry_run, scan_id=args.scan_id)
