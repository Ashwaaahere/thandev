"""
Runner callback endpoint for dependency scanning results
"""
import logging
import hmac
import hashlib
import json
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.config import settings
from app.models.scan_artifact import ScanArtifact
from app.models.scan import ScanJob

router = APIRouter(
    prefix="/runner",
    tags=["runner"],
)
logger = logging.getLogger(__name__)


class RunnerCallbackRequest(BaseModel):
    """Request from runner with scan artifact"""
    scan_id: str
    artifact_type: str  # 'url_sca' or 'repo_sca'
    payload: Dict[str, Any]


def verify_hmac_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """
    Verify HMAC signature from runner.
    
    Args:
        payload: Request body as bytes
        signature: HMAC signature from X-Runner-Signature header
        secret: Shared secret (RUNNER_CALLBACK_SECRET)
    
    Returns:
        True if signature is valid, False otherwise
    """
    if not secret:
        logger.warning("RUNNER_CALLBACK_SECRET not configured, skipping signature verification")
        return True  # In development, allow if secret not set
    
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


@router.post("/callback")
async def runner_callback(
    request: Request,
    x_runner_signature: str = Header(None, alias="X-Runner-Signature"),
    db: Session = Depends(get_db),
):
    """
    Callback endpoint for runner to post dependency scanning results.
    
    Verifies HMAC signature using RUNNER_CALLBACK_SECRET.
    Accepts scan artifacts and stores them in the database.
    """
    # Read request body
    body = await request.body()
    
    # Verify HMAC signature
    import os
    secret = getattr(settings, 'RUNNER_CALLBACK_SECRET', None) or os.getenv('RUNNER_CALLBACK_SECRET', '')
    if secret and x_runner_signature:
        if not verify_hmac_signature(body, x_runner_signature, secret):
            logger.warning(f"Invalid HMAC signature from runner: {x_runner_signature[:20]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
    elif secret and not x_runner_signature:
        logger.warning("RUNNER_CALLBACK_SECRET configured but no signature provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature required"
        )
    
    # Parse request body
    try:
        data = json.loads(body.decode('utf-8'))
        callback_request = RunnerCallbackRequest(**data)
    except Exception as e:
        logger.error(f"Error parsing callback request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request format: {str(e)}"
        )
    
    # Verify scan exists
    scan_job = db.query(ScanJob).filter(ScanJob.id == callback_request.scan_id).first()
    if not scan_job:
        logger.error(f"Scan not found: {callback_request.scan_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan not found: {callback_request.scan_id}"
        )
    
    # Validate artifact type
    if callback_request.artifact_type not in ('url_sca', 'repo_sca'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid artifact_type: {callback_request.artifact_type}. Must be 'url_sca' or 'repo_sca'"
        )
    
    # Create scan artifact
    artifact = ScanArtifact(
        scan_id=callback_request.scan_id,
        type=callback_request.artifact_type,
        payload=callback_request.payload,
    )
    
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    
    logger.info(
        f"Stored scan artifact: scan_id={callback_request.scan_id}, "
        f"type={callback_request.artifact_type}, artifact_id={artifact.id}"
    )
    
    # Process findings from artifact and create Finding records
    # This ensures dependency scan findings appear in the findings table and can be searched by CVE ID
    if callback_request.artifact_type == 'url_sca':
        try:
            from app.services.findings_ingestor import create_or_update_finding
            
            payload = callback_request.payload
            findings_list = payload.get("findings", [])
            project_id = scan_job.project_id
            
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
                        "tool": "retire",  # retire.js findings
                        "tool_name": "retire",
                        "title": f"{finding_data.get('package', 'Unknown')} {finding_data.get('version', '')} - Known Vulnerability",
                        "description": f"Vulnerable dependency detected: {finding_data.get('package', 'Unknown')} version {finding_data.get('version', 'Unknown')}",
                        "severity": finding_data.get("severity", "medium").lower(),
                        "url": finding_data.get("evidence"),  # Script URL where dependency was found
                        "cve_id": cve_id,  # Extract first CVE ID from references
                        "evidence": finding_data.get("evidence"),
                        "raw_data": json.dumps(finding_data, default=str),  # Store full finding data
                    }
                    
                    finding = create_or_update_finding(
                        db=db,
                        scan_job_id=callback_request.scan_id,
                        project_id=project_id,
                        finding_data=normalized_finding,
                        tool_result_id=None,
                    )
                    findings_created += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to create finding from artifact: {e}", exc_info=True)
                    continue
            
            if findings_created > 0:
                db.commit()
                logger.info(
                    f"Created {findings_created} Finding records from artifact {artifact.id} "
                    f"for scan {callback_request.scan_id}"
                )
        except Exception as e:
            logger.error(f"Error processing findings from artifact: {e}", exc_info=True)
            # Don't fail the callback if finding creation fails
            db.rollback()
    
    return {
        "status": "ok",
        "artifact_id": artifact.id,
        "scan_id": callback_request.scan_id,
    }
