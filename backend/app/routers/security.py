from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
from slowapi import Limiter
from slowapi.util import get_remote_address
import asyncio
import uuid
import json
import time
import yaml
from datetime import datetime
import os
import logging
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import ScanJob

router = APIRouter(prefix="/api/security-scan", tags=["security"])

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load presets
PRESETS = {}
PRESET_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "presets")

def load_presets():
    """Load scan level presets from YAML files"""
    global PRESETS
    try:
        preset_files = {
            "level0": "level0_surface.yaml",
            "level1": "level1_discovery.yaml", 
            "level2": "level2_active.yaml"
        }
        
        for tier, filename in preset_files.items():
            preset_file = os.path.join(PRESET_DIR, filename)
            if os.path.exists(preset_file):
                with open(preset_file, 'r') as f:
                    PRESETS[tier] = yaml.safe_load(f)
                    logger.info(f"Loaded preset for {tier} from {filename}")
            else:
                logger.error(f"Preset file not found: {preset_file}")
    except Exception as e:
        logger.error(f"Failed to load presets: {str(e)}")

# Load presets on startup
load_presets()

# Tier to scan level mapping for Runner service
TIER_TO_SCAN_LEVEL = {
    "level0": "basic",
    "level1": "pro", 
    "level2": "advanced"
}

class SecurityScanRequest(BaseModel):
    url: HttpUrl
    tier: str  # level0, level1, level2
    user_id: Optional[str] = None

class SecurityScanResponse(BaseModel):
    jobId: str
    status: str
    message: str
    tier: str
    estimated_duration: str

class SecurityScanStatus(BaseModel):
    jobId: str
    status: str
    tier: str
    url: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

class ScanResults(BaseModel):
    jobId: str
    summary: Dict[str, Any]
    artifact_urls: List[str]
    vulnerabilities: List[Dict[str, Any]]
    created_at: str
    finished_at: str

class Vulnerability(BaseModel):
    id: str
    type: str
    severity: str
    title: str
    description: str
    recommendation: str
    cwe: Optional[str] = None
    cvss: Optional[float] = None
    port: Optional[int] = None
    service: Optional[str] = None

def check_rate_limit(db: Session, user_id: str) -> bool:
    """Check if user has exceeded rate limit (max 3 concurrent jobs)"""
    try:
        active_jobs = db.query(ScanJob).filter(
            ScanJob.user_id == user_id,
            ScanJob.status.in_(['pending', 'running'])
        ).count()
        return active_jobs < 3
    except Exception as e:
        logger.error(f"Rate limit check failed: {str(e)}")
        return True  # Allow on error

def validate_tier(tier: str) -> bool:
    """Validate that tier is one of the supported levels"""
    return tier in ["level0", "level1", "level2"]

@router.post("/", response_model=SecurityScanResponse)
@limiter.limit("10/minute")
async def start_security_scan(
    request: Request,
    scan_request: SecurityScanRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start a security scan for the given URL"""
    # Validate tier
    if not validate_tier(scan_request.tier):
        raise HTTPException(status_code=400, detail="Invalid tier. Must be level0, level1, or level2")
    
    # Get user_id (for now, use a default if not provided)
    user_id = scan_request.user_id or "anonymous"
    
    # Check rate limit
    if not check_rate_limit(db, user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Maximum 3 concurrent scans allowed.")
    
    # Get preset info
    preset = PRESETS.get(scan_request.tier)
    if not preset:
        raise HTTPException(status_code=400, detail=f"Preset not found for tier {scan_request.tier}")
    
    job_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    # Create scan job record
    scan_job = ScanJob(
        id=job_id,
        user_id=user_id,
        url=str(scan_request.url),
        domain=scan_request.url.host,
        tier=scan_request.tier,
        status="pending",
        created_at=now,
        preset_version=preset.get("version", "1.0")
    )
    
    try:
        db.add(scan_job)
        db.commit()
        db.refresh(scan_job)
        
        # Start the scan in the background
        background_tasks.add_task(run_security_scan, job_id, str(scan_request.url), scan_request.tier)
        
        return SecurityScanResponse(
            jobId=job_id,
            status="started",
            message="Security scan initiated",
            tier=scan_request.tier,
            estimated_duration=preset.get("estimated_duration", "Unknown")
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create scan job: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to start scan: {str(e)}")

@router.get("/status/{job_id}", response_model=SecurityScanStatus)
async def get_scan_status(job_id: str, db: Session = Depends(get_db)):
    """Get the status of a security scan"""
    try:
        scan_job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
        if not scan_job:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Parse summary if it's a JSON string
        result = None
        if scan_job.summary:
            try:
                result = json.loads(scan_job.summary)
            except:
                result = scan_job.summary
        
        return SecurityScanStatus(
            jobId=str(scan_job.id),
            status=scan_job.status,
            tier=scan_job.tier,
            url=scan_job.url,
            created_at=scan_job.created_at.isoformat(),
            started_at=scan_job.started_at.isoformat() if scan_job.started_at else None,
            finished_at=scan_job.finished_at.isoformat() if scan_job.finished_at else None,
            result=result
        )
    except Exception as e:
        logger.error(f"Failed to get scan status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get scan status")

@router.get("/results/{job_id}", response_model=ScanResults)
async def get_scan_results(job_id: str, db: Session = Depends(get_db)):
    """Get the results of a completed security scan"""
    try:
        scan_job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
        if not scan_job:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        if scan_job.status != "completed":
            raise HTTPException(status_code=400, detail="Scan not completed yet")
        
        # Parse summary if it's a JSON string
        summary = {}
        vulnerabilities = []
        if scan_job.summary:
            try:
                summary = json.loads(scan_job.summary)
                vulnerabilities = summary.get("vulnerabilities", [])
            except:
                summary = scan_job.summary or {}
        
        # Parse artifact_urls if it's a JSON string
        artifact_urls = []
        if scan_job.artifact_urls:
            try:
                artifact_urls = json.loads(scan_job.artifact_urls)
            except:
                artifact_urls = scan_job.artifact_urls or []
        
        return ScanResults(
            jobId=str(scan_job.id),
            summary=summary,
            artifact_urls=artifact_urls,
            vulnerabilities=vulnerabilities,
            created_at=scan_job.created_at.isoformat(),
            finished_at=scan_job.finished_at.isoformat()
        )
    except Exception as e:
        logger.error(f"Failed to get scan results: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get scan results")

@router.get("/list")
@limiter.limit("30/minute")
async def list_user_scans(
    request: Request,
    user_id: str,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get paginated list of scans for a user"""
    try:
        scans = db.query(ScanJob).filter(
            ScanJob.user_id == user_id
        ).order_by(ScanJob.created_at.desc()).offset(offset).limit(limit).all()
        
        return {
            "scans": [
                {
                    "jobId": str(scan.id),
                    "url": scan.url,
                    "tier": scan.tier,
                    "status": scan.status,
                    "created_at": scan.created_at.isoformat(),
                    "finished_at": scan.finished_at.isoformat() if scan.finished_at else None
                }
                for scan in scans
            ],
            "total": db.query(ScanJob).filter(ScanJob.user_id == user_id).count()
        }
    except Exception as e:
        logger.error(f"Failed to list scans: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list scans")

@router.post("/callback/{job_id}")
async def scan_callback(
    job_id: str, 
    request: Request,
    db: Session = Depends(get_db)
):
    """Webhook callback to receive scan results from Runner service"""
    try:
        # Validate scan ID exists
        scan_job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
        if not scan_job:
            logger.error(f"Callback received for non-existent job: {job_id}")
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Parse request body
        try:
            results = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse callback JSON for job {job_id}: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid JSON in callback")
        
        # Validate callback secret if provided
        callback_secret = os.getenv("CALLBACK_SECRET")
        if callback_secret and results.get("secret") != callback_secret:
            logger.warning(f"Invalid callback secret for job {job_id}")
            # Don't fail, but log the warning
        
        # Extract results
        status = results.get("status", "done")
        summary = results.get("summary", {})
        artifacts_prefix = results.get("artifactsPrefix", f"security/{job_id}/")
        
        # Build artifact URLs from GCS bucket
        gcs_bucket = os.getenv("GCS_BUCKET", "thandev-reports")
        artifact_urls = []
        if artifacts_prefix:
            artifact_urls = [
                f"gs://{gcs_bucket}/{artifacts_prefix}nuclei-output.json",
                f"gs://{gcs_bucket}/{artifacts_prefix}nmap-output.xml"
            ]
        
        # Update scan job with results
        if status == "done":
            scan_job.status = "completed"
            scan_job.finished_at = datetime.utcnow()
        elif status == "error":
            scan_job.status = "error"
            scan_job.finished_at = datetime.utcnow()
        else:
            scan_job.status = "running"  # Still running
        
        scan_job.summary = json.dumps(summary)
        scan_job.artifact_urls = json.dumps(artifact_urls)
        
        db.commit()
        
        logger.info(f"Received scan results for job {job_id}, status={status}")
        return {"status": "success", "message": "Results received", "scanId": job_id}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to process callback for job {job_id}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to process callback")

# ============================================================================
# LEGACY v1 CODE REMOVED
# ============================================================================
# Security scans now use Runner service via Redis streams
# Local execution functions removed: run_local_scan_sync, run_local_scan, 
# run_nuclei_scan, run_nmap_scan, run_ssl_scan, run_ffuf_scan, run_nikto_scan, etc.
# Security scans now use the Runner service via Redis streams
# This endpoint is deprecated - use /api/scans instead
# ============================================================================

async def run_security_scan(job_id: str, url: str, tier: str):
    """Run security scan using Runner service via Redis streams"""
    # Create a new database session for the background task
    from app.db import SessionLocal
    background_db = SessionLocal()
    
    try:
        # Update status to running
        scan_job = background_db.query(ScanJob).filter(ScanJob.id == job_id).first()
        if scan_job:
            scan_job.status = "running"
            scan_job.started_at = datetime.utcnow()
            background_db.commit()
        
        # Get preset configuration
        preset = PRESETS.get(tier)
        if not preset:
            raise Exception(f"Preset not found for tier {tier}")
        
        # Map tier to scan_level for runner
        tier_to_scan_level = {
            "level0": "basic",
            "level1": "pro", 
            "level2": "advanced"
        }
        scan_level = tier_to_scan_level.get(tier, "pro")
        
        # Use Runner service via Redis streams
        logger.info(f"Using Runner service for security scan: {job_id}, tier={tier}, scan_level={scan_level}")
        from app.services.runner_client import publish_scan_steps_to_runner
        
        # Get tenant and project from scan_job if available
        org_id = getattr(scan_job, 'org_id', None) if scan_job else None
        project_id = getattr(scan_job, 'project_id', None) if scan_job else None
        
        success = await publish_scan_steps_to_runner(
            scan_job_id=job_id,
            target_url=url,
            scan_level=scan_level,
            org_id=org_id,
            project_id=project_id,
        )
        
        if not success:
            error_msg = "Failed to publish scan steps to Runner. Make sure Runner service is running and Redis is accessible."
            logger.error(error_msg)
            if scan_job:
                scan_job.status = "error"
                scan_job.finished_at = datetime.utcnow()
                scan_job.summary = json.dumps({"error": error_msg})
                background_db.commit()
        else:
            logger.info(f"Security scan {job_id} published to Runner successfully")
            
    except Exception as e:
        logger.error(f"Scan failed for job {job_id}: {str(e)}")
        scan_job = background_db.query(ScanJob).filter(ScanJob.id == job_id).first()
        if scan_job:
            scan_job.status = "error"
            scan_job.finished_at = datetime.utcnow()
            scan_job.summary = json.dumps({"error": str(e)})
            background_db.commit()
    finally:
        background_db.close()

