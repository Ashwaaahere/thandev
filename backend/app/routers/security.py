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
import subprocess
import os
import tempfile
import shutil
import httpx
import logging
import threading
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

# Tier to Cloud Run Job mapping
TIER_TO_JOB = {
    "level0": "security-scanner-job",
    "level1": "security-scanner-job", 
    "level2": "security-scanner-job"
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
async def scan_callback(job_id: str, results: Dict[str, Any], db: Session = Depends(get_db)):
    """Webhook callback to receive scan results from Cloud Run Job"""
    try:
        scan_job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
        if not scan_job:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Update scan job with results
        scan_job.status = "completed"
        scan_job.finished_at = datetime.utcnow()
        scan_job.summary = json.dumps(results.get("summary", {}))
        scan_job.artifact_urls = json.dumps(results.get("artifact_urls", []))
        
        db.commit()
        
        logger.info(f"Received scan results for job {job_id}")
        return {"status": "success", "message": "Results received"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to process callback for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process callback")

def run_security_scan_sync(job_id: str, url: str, tier: str, db: Session):
    """Run security scan synchronously (for testing)"""
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
        
        # Get Cloud Run Job name
        job_name = TIER_TO_JOB.get(tier)
        if not job_name:
            raise Exception(f"Cloud Run Job not found for tier {tier}")
        
        # Check if we should use Cloud Run Job or local scanning
        cloud_run_enabled = os.getenv("CLOUD_RUN_ENABLED", "true").lower() == "true"
        
        if cloud_run_enabled:
            # Use Cloud Run Job for production scanning
            try:
                execution_id = run_cloud_run_scan_sync(job_id, url, tier, job_name, preset)
                if scan_job:
                    scan_job.execution_id = execution_id
                    background_db.commit()
            except Exception as e:
                logger.error(f"Cloud Run scan failed for job {job_id}: {str(e)}")
                if scan_job:
                    scan_job.status = "error"
                    scan_job.finished_at = datetime.utcnow()
                    scan_job.summary = json.dumps({"error": str(e)})
                    background_db.commit()
        else:
            # Use local tools for development/testing
            try:
                result = run_local_scan_sync(job_id, url, tier, preset)
                
                # Update scan job with results
                if scan_job:
                    scan_job.status = "completed"
                    scan_job.finished_at = datetime.utcnow()
                    scan_job.summary = json.dumps(result)  # Convert to JSON string for SQLite
                    background_db.commit()
                    logger.info(f"Scan completed for job {job_id}")
            except Exception as e:
                logger.error(f"Local scan failed for job {job_id}: {str(e)}")
                if scan_job:
                    scan_job.status = "error"
                    scan_job.finished_at = datetime.utcnow()
                    scan_job.summary = json.dumps({"error": str(e)})
                    background_db.commit()
            
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

async def run_security_scan(job_id: str, url: str, tier: str):
    """Run security scan using Cloud Run Job or local tools"""
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
        
        # Get Cloud Run Job name
        job_name = TIER_TO_JOB.get(tier)
        if not job_name:
            raise Exception(f"Cloud Run Job not found for tier {tier}")
        
        # Check if we should use Cloud Run Job or local scanning
        cloud_run_enabled = os.getenv("CLOUD_RUN_ENABLED", "true").lower() == "true"
        
        logger.info(f"Security scan configuration: cloud_run_enabled={cloud_run_enabled}, tier={tier}, job_name={job_name}")
        
        if cloud_run_enabled:
            # Use Cloud Run Job for production scanning
            try:
                execution_id = await run_cloud_run_scan(job_id, url, tier, job_name, preset)
                if scan_job:
                    scan_job.execution_id = execution_id
                    background_db.commit()
            except Exception as cloud_run_error:
                error_msg = str(cloud_run_error)
                logger.error(f"Cloud Run scan failed for job {job_id}: {error_msg}")
                
                # Check if we should fall back to local scanning
                fallback_to_local = os.getenv("FALLBACK_TO_LOCAL_SCAN", "false").lower() == "true"
                
                if fallback_to_local:
                    logger.info(f"Falling back to local scanning for job {job_id}")
                    try:
                        result = run_local_scan_sync(job_id, url, tier, preset)
                        
                        # Update scan job with results
                        if scan_job:
                            scan_job.status = "completed"
                            scan_job.finished_at = datetime.utcnow()
                            scan_job.summary = json.dumps(result)
                            background_db.commit()
                            logger.info(f"Local scan completed for job {job_id}")
                    except Exception as local_error:
                        logger.error(f"Local scan also failed for job {job_id}: {str(local_error)}")
                        if scan_job:
                            scan_job.status = "error"
                            scan_job.finished_at = datetime.utcnow()
                            scan_job.summary = json.dumps({
                                "error": f"Both Cloud Run and local scanning failed. Cloud Run error: {error_msg}. Local error: {str(local_error)}"
                            })
                            background_db.commit()
                else:
                    # Don't fall back, just report the error
                    if scan_job:
                        scan_job.status = "error"
                        scan_job.finished_at = datetime.utcnow()
                        scan_job.summary = json.dumps({
                            "error": error_msg,
                            "hint": "Set FALLBACK_TO_LOCAL_SCAN=true to enable local scanning fallback, or set CLOUD_RUN_ENABLED=false to use local scanning only."
                        })
                        background_db.commit()
        else:
            # Use local tools for development/testing
            try:
                result = run_local_scan_sync(job_id, url, tier, preset)
                
                # Update scan job with results
                if scan_job:
                    scan_job.status = "completed"
                    scan_job.finished_at = datetime.utcnow()
                    scan_job.summary = json.dumps(result)  # Convert to JSON string for SQLite
                    background_db.commit()
                    logger.info(f"Scan completed for job {job_id}")
            except Exception as e:
                logger.error(f"Local scan failed for job {job_id}: {str(e)}")
                if scan_job:
                    scan_job.status = "error"
                    scan_job.finished_at = datetime.utcnow()
                    scan_job.summary = json.dumps({"error": str(e)})
                    background_db.commit()
            
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

async def run_cloud_run_scan(job_id: str, url: str, tier: str, job_name: str, preset: Dict[str, Any]):
    """Trigger Cloud Run Job for security scanning"""
    try:
        # Check if gcloud CLI is available
        try:
            gcloud_check = subprocess.run(
                ["gcloud", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if gcloud_check.returncode != 0:
                raise Exception("gcloud CLI not available or not working")
        except FileNotFoundError:
            logger.warning("gcloud CLI not found. Falling back to local scanning.")
            raise Exception("gcloud CLI not installed. Please install gcloud CLI or set CLOUD_RUN_ENABLED=false to use local scanning.")
        except Exception as e:
            logger.warning(f"gcloud CLI check failed: {str(e)}")
            raise Exception(f"gcloud CLI not available: {str(e)}")
        
        # Get project ID and region from environment
        project_id = os.getenv("GCP_PROJECT_ID")
        region = os.getenv("GCP_REGION", "us-central1")
        
        if not project_id:
            logger.error("GCP_PROJECT_ID environment variable not set")
            raise Exception("GCP_PROJECT_ID environment variable is required for Cloud Run scanning. Set it or use CLOUD_RUN_ENABLED=false for local scanning.")
        
        # Prepare environment variables for the Cloud Run Job
        backend_url = os.getenv("BACKEND_URL")
        if not backend_url:
            logger.warning("BACKEND_URL not set, using default localhost")
            backend_url = "http://localhost:8000"
        
        callback_url = f"{backend_url}/api/security-scan/callback/{job_id}"
        callback_secret = os.getenv("CALLBACK_SECRET", "default-secret")
        
        env_vars = {
            "URL": url,
            "TIER": tier,
            "JOB_ID": job_id,
            "CALLBACK_URL": callback_url,
            "CALLBACK_SECRET": callback_secret,
            "PRESET_NAME": preset.get("preset_name", tier)
        }
        
        # Build gcloud command to execute the job
        cmd = [
            "gcloud", "run", "jobs", "execute", job_name,
            "--region", region,
            "--project", project_id,
            "--wait"
        ]
        
        # Add environment variables
        env_vars_str = ",".join([f"{key}={value}" for key, value in env_vars.items()])
        cmd.extend(["--update-env-vars", env_vars_str])
        
        logger.info(f"Executing Cloud Run Job: {' '.join(cmd)}")
        logger.info(f"Cloud Run configuration: project={project_id}, region={region}, job={job_name}, callback_url={callback_url}")
        
        # Execute the Cloud Run Job
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        if result.returncode == 0:
            logger.info(f"Cloud Run Job completed successfully for job {job_id}")
            logger.info(f"Job output: {result.stdout}")
            return job_id  # Return execution ID
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            logger.error(f"Cloud Run Job failed for job {job_id}")
            logger.error(f"Error output: {error_msg}")
            logger.error(f"Command: {' '.join(cmd)}")
            raise Exception(f"Cloud Run Job failed: {error_msg}")
                
    except subprocess.TimeoutExpired:
        logger.error(f"Cloud Run Job timed out for job {job_id}")
        raise Exception("Cloud Run Job timed out after 30 minutes")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to trigger Cloud Run Job for {job_id}: {error_msg}")
        logger.error(f"Diagnostic info: GCP_PROJECT_ID={'set' if os.getenv('GCP_PROJECT_ID') else 'NOT SET'}, "
                    f"GCP_REGION={os.getenv('GCP_REGION', 'NOT SET')}, "
                    f"BACKEND_URL={os.getenv('BACKEND_URL', 'NOT SET')}")
        raise Exception(f"Failed to trigger Cloud Run Job: {error_msg}")

def run_cloud_run_scan_sync(job_id: str, url: str, tier: str, job_name: str, preset: Dict[str, Any]):
    """Trigger Cloud Run Job for security scanning (synchronous version)"""
    try:
        # Check if gcloud CLI is available
        try:
            gcloud_check = subprocess.run(
                ["gcloud", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if gcloud_check.returncode != 0:
                raise Exception("gcloud CLI not available or not working")
        except FileNotFoundError:
            logger.warning("gcloud CLI not found. Falling back to local scanning.")
            raise Exception("gcloud CLI not installed. Please install gcloud CLI or set CLOUD_RUN_ENABLED=false to use local scanning.")
        except Exception as e:
            logger.warning(f"gcloud CLI check failed: {str(e)}")
            raise Exception(f"gcloud CLI not available: {str(e)}")
        
        # Get project ID and region from environment
        project_id = os.getenv("GCP_PROJECT_ID")
        region = os.getenv("GCP_REGION", "us-central1")
        
        if not project_id:
            logger.error("GCP_PROJECT_ID environment variable not set")
            raise Exception("GCP_PROJECT_ID environment variable is required for Cloud Run scanning. Set it or use CLOUD_RUN_ENABLED=false for local scanning.")
        
        # Prepare environment variables for the Cloud Run Job
        backend_url = os.getenv("BACKEND_URL")
        if not backend_url:
            logger.warning("BACKEND_URL not set, using default localhost")
            backend_url = "http://localhost:8000"
        
        callback_url = f"{backend_url}/api/security-scan/callback/{job_id}"
        callback_secret = os.getenv("CALLBACK_SECRET", "default-secret")
        
        env_vars = {
            "URL": url,
            "TIER": tier,
            "JOB_ID": job_id,
            "CALLBACK_URL": callback_url,
            "CALLBACK_SECRET": callback_secret,
            "PRESET_NAME": preset.get("preset_name", tier)
        }
        
        # Build gcloud command to execute the job
        cmd = [
            "gcloud", "run", "jobs", "execute", job_name,
            "--region", region,
            "--project", project_id,
            "--wait"
        ]
        
        # Add environment variables
        env_vars_str = ",".join([f"{key}={value}" for key, value in env_vars.items()])
        cmd.extend(["--update-env-vars", env_vars_str])
        
        logger.info(f"Executing Cloud Run Job: {' '.join(cmd)}")
        logger.info(f"Cloud Run configuration: project={project_id}, region={region}, job={job_name}, callback_url={callback_url}")
        
        # Execute the Cloud Run Job
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        if result.returncode == 0:
            logger.info(f"Cloud Run Job completed successfully for job {job_id}")
            logger.info(f"Job output: {result.stdout}")
            return job_id  # Return execution ID
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            logger.error(f"Cloud Run Job failed for job {job_id}")
            logger.error(f"Error output: {error_msg}")
            logger.error(f"Command: {' '.join(cmd)}")
            raise Exception(f"Cloud Run Job failed: {error_msg}")
                
    except subprocess.TimeoutExpired:
        logger.error(f"Cloud Run Job timed out for job {job_id}")
        raise Exception("Cloud Run Job timed out after 30 minutes")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to trigger Cloud Run Job for {job_id}: {error_msg}")
        logger.error(f"Diagnostic info: GCP_PROJECT_ID={'set' if os.getenv('GCP_PROJECT_ID') else 'NOT SET'}, "
                    f"GCP_REGION={os.getenv('GCP_REGION', 'NOT SET')}, "
                    f"BACKEND_URL={os.getenv('BACKEND_URL', 'NOT SET')}")
        raise Exception(f"Failed to trigger Cloud Run Job: {error_msg}")

def run_local_scan_sync(job_id: str, url: str, tier: str, preset: Dict[str, Any]):
    """Run local security scan synchronously"""
    try:
        # Create temporary directory for scan results
        with tempfile.TemporaryDirectory() as temp_dir:
            vulnerabilities = []
            
            # Run scans based on preset configuration
            tools = preset.get("tools", [])
            
            for tool_config in tools:
                tool_name = tool_config.get("name")
                if tool_name == "nuclei":
                    nuclei_results = run_nuclei_scan_sync(url, tool_config, temp_dir)
                    vulnerabilities.extend(nuclei_results)
                elif tool_name == "sslscan":
                    ssl_results = run_ssl_scan_sync(url, temp_dir)
                    vulnerabilities.extend(ssl_results)
                elif tool_name == "nmap":
                    port_results = run_port_scan_sync(url, temp_dir)
                    vulnerabilities.extend(port_results)
                elif tool_name == "ffuf":
                    ffuf_results = run_ffuf_scan_sync(url, tool_config, temp_dir)
                    vulnerabilities.extend(ffuf_results)
                elif tool_name == "nikto":
                    nikto_results = run_nikto_scan_sync(url, temp_dir)
                    vulnerabilities.extend(nikto_results)
            
            # Process and format results
            processed_result = {
                "vulnerabilities": [vuln.dict() for vuln in vulnerabilities],  # Convert to dict for JSON storage
                "tier": tier,
                "url": url,
                "totalVulnerabilities": len(vulnerabilities),
                "severityBreakdown": get_severity_breakdown(vulnerabilities),
                "scanDuration": 0,  # Calculate actual duration
                "timestamp": datetime.utcnow().isoformat(),
                "preset_version": preset.get("version", "1.0")
            }
            
            return processed_result
            
    except Exception as e:
        logger.error(f"Local scan failed for job {job_id}: {str(e)}")
        raise

async def run_local_scan(job_id: str, url: str, tier: str, preset: Dict[str, Any]):
    """Run local security scan using available tools"""
    try:
        # Create temporary directory for scan results
        with tempfile.TemporaryDirectory() as temp_dir:
            vulnerabilities = []
            
            # Run scans based on preset configuration
            tools = preset.get("tools", [])
            
            for tool_config in tools:
                tool_name = tool_config.get("name")
                if tool_name == "nuclei":
                    nuclei_results = await run_nuclei_scan(url, tool_config, temp_dir)
                    vulnerabilities.extend(nuclei_results)
                elif tool_name == "sslscan":
                    ssl_results = await run_ssl_scan(url, temp_dir)
                    vulnerabilities.extend(ssl_results)
                elif tool_name == "nmap":
                    port_results = await run_port_scan(url, temp_dir)
                    vulnerabilities.extend(port_results)
                elif tool_name == "ffuf":
                    ffuf_results = await run_ffuf_scan(url, tool_config, temp_dir)
                    vulnerabilities.extend(ffuf_results)
                elif tool_name == "nikto":
                    nikto_results = await run_nikto_scan(url, temp_dir)
                    vulnerabilities.extend(nikto_results)
            
            # Process and format results
            processed_result = {
                "vulnerabilities": vulnerabilities,
                "tier": tier,
                "url": url,
                "totalVulnerabilities": len(vulnerabilities),
                "severityBreakdown": get_severity_breakdown(vulnerabilities),
                "scanDuration": 0,  # Calculate actual duration
                "timestamp": datetime.utcnow().isoformat(),
                "preset_version": preset.get("version", "1.0")
            }
            
            # Update scan job in database
            # This would be called from the main scan function
            return processed_result
            
    except Exception as e:
        logger.error(f"Local scan failed for job {job_id}: {str(e)}")
        raise

async def run_ssl_scan(url: str, temp_dir: str) -> List[Vulnerability]:
    """Run SSL/TLS security scan using Python SSL library"""
    vulnerabilities = []
    
    try:
        from urllib.parse import urlparse
        import ssl
        import socket
        
        # Parse URL to get hostname and port
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
        
        if not hostname or port != 443:
            return vulnerabilities  # Only scan HTTPS sites
        
        # Create SSL context for testing
        context = ssl.create_default_context()
        
        # Test SSL/TLS connection
        try:
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    # Get SSL certificate and connection info
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    
                    # Check TLS version
                    if version in ['TLSv1', 'TLSv1.1']:
                        vulnerabilities.append(Vulnerability(
                            id=f"ssl-version-{uuid.uuid4().hex[:8]}",
                            type="SSL/TLS",
                            severity="high",
                            title="Outdated TLS Version",
                            description=f"Server is using {version}, which is considered insecure.",
                            recommendation="Upgrade to TLS 1.2 or higher",
                            cwe="CWE-326",
                            cvss=7.5
                        ))
                    
                    # Check cipher strength
                    if cipher:
                        cipher_name, cipher_version, cipher_bits = cipher
                        if cipher_bits and cipher_bits < 128:
                            vulnerabilities.append(Vulnerability(
                                id=f"ssl-cipher-{uuid.uuid4().hex[:8]}",
                                type="SSL/TLS",
                                severity="medium",
                                title="Weak Cipher Suite",
                                description=f"Server is using weak cipher: {cipher_name} ({cipher_bits} bits)",
                                recommendation="Use stronger cipher suites with at least 128-bit encryption",
                                cwe="CWE-326",
                                cvss=5.3
                            ))
                    
                    # Check certificate validity
                    if cert:
                        import datetime
                        not_after = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                        days_until_expiry = (not_after - datetime.datetime.now()).days
                        
                        if days_until_expiry < 30:
                            severity = "critical" if days_until_expiry < 7 else "high"
                            vulnerabilities.append(Vulnerability(
                                id=f"ssl-cert-{uuid.uuid4().hex[:8]}",
                                type="SSL/TLS",
                                severity=severity,
                                title="SSL Certificate Expiring Soon",
                                description=f"SSL certificate expires in {days_until_expiry} days",
                                recommendation="Renew the SSL certificate before it expires",
                                cwe="CWE-295",
                                cvss=6.5 if days_until_expiry < 7 else 4.3
                            ))
                    
                    # If we get here without issues, the SSL configuration is good
                    logger.info(f"SSL scan completed for {hostname}: TLS {version}, Cipher: {cipher_name if cipher else 'Unknown'}")
                    
        except ssl.SSLError as e:
            # SSL connection failed - this is a real issue
            vulnerabilities.append(Vulnerability(
                id=f"ssl-connection-{uuid.uuid4().hex[:8]}",
                type="SSL/TLS",
                severity="high",
                title="SSL Connection Failed",
                description=f"Failed to establish SSL connection: {str(e)}",
                recommendation="Check SSL configuration and certificate validity",
                cwe="CWE-295",
                cvss=6.8
            ))
        except Exception as e:
            logger.warning(f"SSL scan error for {hostname}: {str(e)}")
            
    except Exception as e:
        logger.error(f"SSL scan failed: {str(e)}")
    
    return vulnerabilities

async def run_nuclei_scan(url: str, tool_config: Dict[str, Any], temp_dir: str) -> List[Vulnerability]:
    """Run nuclei vulnerability scanner (mock for testing)"""
    vulnerabilities = []
    
    try:
        # Mock nuclei scan for testing
        logger.info(f"Mock nuclei scan for {url}")
        
        # Simulate some vulnerabilities
        vulnerabilities.append(Vulnerability(
            id="mock-nuclei-1",
            type="Mock Finding",
            title="Mock Vulnerability",
            description="This is a mock vulnerability for testing",
            severity="medium",
            recommendation="This is a mock recommendation",
            cve_id="MOCK-CVE-2024-0001",
            url=url,
            evidence="Mock evidence from nuclei scan",
            tool="nuclei"
        ))
        
    except Exception as e:
        logger.error(f"Nuclei scan failed: {str(e)}")
    
    return vulnerabilities

async def run_ffuf_scan(url: str, tool_config: Dict[str, Any], temp_dir: str) -> List[Vulnerability]:
    """Run ffuf directory discovery (mock for testing)"""
    vulnerabilities = []
    
    try:
        logger.info(f"Mock ffuf scan for {url}")
        
        # Simulate some directory findings
        vulnerabilities.append(Vulnerability(
            id="mock-ffuf-1",
            type="Directory Discovery",
            title="Mock Directory Found",
            description="This is a mock directory finding for testing",
            severity="info",
            recommendation="Review discovered directories for sensitive information",
            url=f"{url}/admin",
            evidence="Status: 200, Size: 1024",
            tool="ffuf"
        ))
        
    except Exception as e:
        logger.error(f"FFUF scan failed: {str(e)}")
    
    return vulnerabilities

async def run_nikto_scan(url: str, temp_dir: str) -> List[Vulnerability]:
    """Run nikto HTTP server security checks (mock for testing)"""
    vulnerabilities = []
    
    try:
        logger.info(f"Mock nikto scan for {url}")
        
        # Simulate some HTTP security findings
        vulnerabilities.append(Vulnerability(
            id="mock-nikto-1",
            type="HTTP Security",
            title="Mock HTTP Security Issue",
            description="This is a mock HTTP security finding for testing",
            severity="medium",
            recommendation="This is a mock recommendation for HTTP security",
            url=url,
            evidence="Mock nikto evidence",
            tool="nikto"
        ))
        
    except Exception as e:
        logger.error(f"Nikto scan failed: {str(e)}")
    
    return vulnerabilities

async def run_port_scan(url: str, temp_dir: str) -> List[Vulnerability]:
    """Run port scan using nmap (mock for testing)"""
    vulnerabilities = []
    
    try:
        logger.info(f"Mock port scan for {url}")
        
        # Simulate some port findings
        vulnerabilities.append(Vulnerability(
            id="mock-port-1",
            type="Port Scan",
            title="Mock Open Port",
            description="This is a mock port finding for testing",
            severity="info",
            recommendation="Review open ports and ensure only necessary services are exposed",
            url=url,
            evidence="Port 80/tcp open",
            tool="nmap"
        ))
        
    except Exception as e:
        logger.error(f"Port scan failed: {str(e)}")
    
    return vulnerabilities

async def run_header_scan(url: str) -> List[Vulnerability]:
    """Scan for missing security headers with improved logic"""
    vulnerabilities = []
    
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                headers = response.headers
                
                # Convert headers to lowercase for case-insensitive checking
                headers_lower = {k.lower(): v for k, v in headers.items()}
                
                # Check for security headers with improved logic
                security_issues = []
                
                # 1. Frame Options (clickjacking protection)
                frame_options = headers_lower.get('x-frame-options', '').lower()
                if not frame_options or frame_options in ['deny', 'sameorigin', 'allow-from']:
                    # Check if it's properly configured
                    if frame_options not in ['deny', 'sameorigin']:
                        security_issues.append("X-Frame-Options should be set to 'DENY' or 'SAMEORIGIN'")
                else:
                    security_issues.append("Missing or misconfigured X-Frame-Options")
                
                # 2. Content Type Options (MIME sniffing protection)
                content_type_options = headers_lower.get('x-content-type-options', '').lower()
                if content_type_options != 'nosniff':
                    security_issues.append("Missing X-Content-Type-Options: nosniff")
                
                # 3. XSS Protection (legacy but still useful)
                xss_protection = headers_lower.get('x-xss-protection', '').lower()
                if xss_protection not in ['1', '1; mode=block', '0']:
                    security_issues.append("Missing X-XSS-Protection header")
                
                # 4. HSTS (HTTP Strict Transport Security)
                hsts = headers_lower.get('strict-transport-security', '')
                if not hsts and url.startswith('https://'):
                    security_issues.append("Missing Strict-Transport-Security header for HTTPS site")
                
                # 5. Content Security Policy
                csp = headers_lower.get('content-security-policy', '')
                csp_report_only = headers_lower.get('content-security-policy-report-only', '')
                if not csp and not csp_report_only:
                    security_issues.append("Missing Content-Security-Policy header")
                
                # 6. Referrer Policy
                referrer_policy = headers_lower.get('referrer-policy', '')
                if not referrer_policy:
                    security_issues.append("Missing Referrer-Policy header")
                
                # Only report if there are significant security issues
                if len(security_issues) >= 4:  # Only flag if missing 4+ important headers
                    vuln = Vulnerability(
                        id=f"headers-{uuid.uuid4().hex[:8]}",
                        type="Security Headers",
                        severity="medium",
                        title="Missing Security Headers",
                        description=f"Missing security headers: {', '.join(security_issues[:3])}",
                        recommendation="Implement comprehensive security headers to protect against common attacks",
                        cwe="CWE-693",
                        cvss=3.7
                    )
                    vulnerabilities.append(vuln)
                elif len(security_issues) >= 2 and any("Strict-Transport-Security" in issue for issue in security_issues):
                    # Flag HSTS missing as a more serious issue for HTTPS sites
                    vuln = Vulnerability(
                        id=f"headers-{uuid.uuid4().hex[:8]}",
                        type="Security Headers",
                        severity="low",
                        title="Minor Security Headers Missing",
                        description=f"Missing security headers: {', '.join(security_issues[:2])}",
                        recommendation="Consider adding missing security headers for enhanced protection",
                        cwe="CWE-693",
                        cvss=2.5
                    )
                    vulnerabilities.append(vuln)
                    
    except Exception as e:
        logger.error(f"Header scan failed: {str(e)}")
    
    return vulnerabilities

def get_severity_breakdown(vulnerabilities: List[Vulnerability]) -> Dict[str, int]:
    """Calculate severity breakdown of vulnerabilities"""
    breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    
    for vuln in vulnerabilities:
        if vuln.severity in breakdown:
            breakdown[vuln.severity] += 1
    
    return breakdown

# Synchronous versions of scan functions for testing
def run_nuclei_scan_sync(url: str, tool_config: Dict[str, Any], temp_dir: str) -> List[Vulnerability]:
    """Run nuclei vulnerability scanner (synchronous version)"""
    vulnerabilities = []
    
    try:
        logger.info(f"Running nuclei scan for {url}")
        
        # Parse URL to get hostname
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname or parsed_url.netloc
        
        # Get nuclei templates based on tier
        templates = tool_config.get("templates", ["info", "technologies"])
        
        # Build nuclei command
        cmd = ["nuclei", "-u", hostname, "-silent", "-json"]
        
        # Add templates
        if templates:
            cmd.extend(["-t", ",".join(templates)])
        
        # Add timeout
        cmd.extend(["-timeout", "30"])
        
        logger.info(f"Executing nuclei command: {' '.join(cmd)}")
        
        # Run nuclei scan
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and result.stdout.strip():
            # Parse nuclei JSON output
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        vuln_data = json.loads(line)
                        
                        vulnerability = Vulnerability(
                            id=f"nuclei-{vuln_data.get('template_id', 'unknown')}-{hash(line) % 10000}",
                            type=vuln_data.get('info', {}).get('name', 'Nuclei Finding'),
                            title=vuln_data.get('info', {}).get('name', 'Security Finding'),
                            description=vuln_data.get('info', {}).get('description', 'No description available'),
                            severity=vuln_data.get('info', {}).get('severity', 'info').lower(),
                            recommendation=vuln_data.get('info', {}).get('remediation', 'No recommendation available'),
                            cve_id=vuln_data.get('info', {}).get('classification', {}).get('cve-id', [None])[0] if vuln_data.get('info', {}).get('classification', {}).get('cve-id') else None,
                            url=vuln_data.get('matched-at', url),
                            evidence=vuln_data.get('info', {}).get('reference', ''),
                            tool="nuclei"
                        )
                        vulnerabilities.append(vulnerability)
                        
                    except json.JSONDecodeError:
                        continue
        else:
            logger.info(f"Nuclei scan completed with no findings for {hostname}")
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Nuclei scan timed out for {url}")
    except Exception as e:
        logger.error(f"Nuclei scan failed for {url}: {str(e)}")
    
    return vulnerabilities

def run_ssl_scan_sync(url: str, temp_dir: str) -> List[Vulnerability]:
    """Run SSL/TLS security scan (synchronous version)"""
    vulnerabilities = []
    
    try:
        from urllib.parse import urlparse
        import ssl
        import socket
        
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
        
        if not hostname or port != 443:
            return vulnerabilities  # Only scan HTTPS sites
        
        # Create SSL context for testing
        context = ssl.create_default_context()
        
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cipher = ssock.cipher()
                protocol = ssock.version()
                
                logger.info(f"SSL scan completed for {hostname}: TLS {protocol}, Cipher: {cipher[0] if cipher else 'Unknown'}")
                
                # Analyze SSL configuration
                cipher_name = cipher[0] if cipher else "Unknown"
                
                # Check for weak TLS versions
                if protocol in ['TLSv1', 'TLSv1.1']:
                    vulnerabilities.append(Vulnerability(
                        id=f"ssl-tls-weak-{hash(hostname) % 10000}",
                        type="SSL/TLS",
                        title="Weak TLS Version",
                        description=f"Server supports weak TLS version: {protocol}",
                        severity="medium",
                        recommendation="Upgrade to TLS 1.2 or higher",
                        url=url,
                        evidence=f"TLS Version: {protocol}",
                        tool="sslscan"
                    ))
                
                # Check for weak ciphers
                if cipher_name and any(weak in cipher_name.lower() for weak in ['rc4', 'des', 'md5', '3des']):
                    vulnerabilities.append(Vulnerability(
                        id=f"ssl-cipher-weak-{hash(hostname) % 10000}",
                        type="SSL/TLS",
                        title="Weak Cipher Suite",
                        description=f"Server uses weak cipher: {cipher_name}",
                        severity="medium",
                        recommendation="Use strong cipher suites (AES-GCM, ChaCha20-Poly1305)",
                        url=url,
                        evidence=f"Cipher: {cipher_name}",
                        tool="sslscan"
                    ))
                
                # Get certificate info
                cert = ssock.getpeercert()
                if cert:
                    # Check certificate expiration
                    from datetime import datetime
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    days_until_expiry = (not_after - datetime.now()).days
                    
                    if days_until_expiry < 30:
                        vulnerabilities.append(Vulnerability(
                            id=f"ssl-cert-expiry-{hash(hostname) % 10000}",
                            type="SSL/TLS",
                            title="Certificate Expiring Soon",
                            description=f"SSL certificate expires in {days_until_expiry} days",
                            severity="low" if days_until_expiry > 7 else "medium",
                            recommendation="Renew SSL certificate before expiration",
                            url=url,
                            evidence=f"Expires: {cert['notAfter']}",
                            tool="sslscan"
                        ))
                
    except Exception as e:
        logger.warning(f"SSL scan error for {hostname}: {str(e)}")
        
    return vulnerabilities

def run_port_scan_sync(url: str, temp_dir: str) -> List[Vulnerability]:
    """Run port scan (synchronous version)"""
    vulnerabilities = []
    
    try:
        logger.info(f"Running port scan for {url}")
        
        # Parse URL to get hostname
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname or parsed_url.netloc
        
        # Run nmap scan
        cmd = ["nmap", "-sV", "-Pn", "--top-ports", "100", hostname]
        
        logger.info(f"Executing nmap command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            # Parse nmap output
            lines = result.stdout.split('\n')
            open_ports = []
            
            for line in lines:
                if '/tcp' in line and 'open' in line:
                    # Parse port line: "80/tcp   open  http    Apache httpd 2.4.41"
                    parts = line.split()
                    if len(parts) >= 3:
                        port_info = parts[0]  # e.g., "80/tcp"
                        state = parts[1]      # e.g., "open"
                        service = parts[2] if len(parts) > 2 else "unknown"
                        
                        if state == 'open':
                            open_ports.append({
                                'port': port_info,
                                'service': service,
                                'line': line.strip()
                            })
            
            # Create port findings
            for port_info in open_ports:
                port = port_info['port'].split('/')[0]
                service = port_info['service']
                
                # Check for potentially risky services
                risky_services = ['ftp', 'telnet', 'ssh', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch']
                severity = "medium" if service.lower() in risky_services else "info"
                
                vulnerabilities.append(Vulnerability(
                    id=f"port-{port}-{hash(hostname) % 10000}",
                    type="Port Scan",
                    title=f"Open Port {port}",
                    description=f"Port {port} is open and running {service}",
                    severity=severity,
                    recommendation=f"Review if {service} on port {port} is necessary and properly secured",
                    url=url,
                    evidence=port_info['line'],
                    tool="nmap"
                ))
            
            logger.info(f"Port scan completed for {hostname}: {len(open_ports)} open ports found")
        else:
            logger.warning(f"Port scan failed for {hostname}: {result.stderr}")
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Port scan timed out for {url}")
    except Exception as e:
        logger.error(f"Port scan failed for {url}: {str(e)}")
    
    return vulnerabilities

def run_ffuf_scan_sync(url: str, tool_config: Dict[str, Any], temp_dir: str) -> List[Vulnerability]:
    """Run ffuf directory discovery (synchronous version)"""
    vulnerabilities = []
    
    try:
        logger.info(f"Mock ffuf scan for {url}")
        
        # Simulate some directory findings
        vulnerabilities.append(Vulnerability(
            id="mock-ffuf-1",
            type="Directory Discovery",
            title="Mock Directory Found",
            description="This is a mock directory finding for testing",
            severity="info",
            recommendation="Review discovered directories for sensitive information",
            url=f"{url}/admin",
            evidence="Status: 200, Size: 1024",
            tool="ffuf"
        ))
        
    except Exception as e:
        logger.error(f"FFUF scan failed: {str(e)}")
    
    return vulnerabilities

def run_nikto_scan_sync(url: str, temp_dir: str) -> List[Vulnerability]:
    """Run nikto HTTP server security checks (synchronous version)"""
    vulnerabilities = []
    
    try:
        logger.info(f"Running nikto scan for {url}")
        
        # Parse URL to get hostname and port
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname or parsed_url.netloc
        port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
        
        # Run nikto scan
        cmd = ["nikto", "-h", hostname, "-p", str(port), "-Format", "json"]
        
        logger.info(f"Executing nikto command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and result.stdout.strip():
            try:
                nikto_data = json.loads(result.stdout)
                findings = nikto_data.get('vulnerabilities', [])
                
                for finding in findings:
                    vuln_id = finding.get('id', 'unknown')
                    description = finding.get('description', 'No description')
                    severity = finding.get('severity', 'info').lower()
                    
                    vulnerabilities.append(Vulnerability(
                        id=f"nikto-{vuln_id}-{hash(description) % 10000}",
                        type="HTTP Security",
                        title=f"Nikto Finding: {vuln_id}",
                        description=description,
                        severity=severity,
                        recommendation="Review HTTP server configuration and apply security patches",
                        url=url,
                        evidence=f"Nikto ID: {vuln_id}",
                        tool="nikto"
                    ))
                
                logger.info(f"Nikto scan completed for {hostname}: {len(findings)} findings")
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse nikto JSON output for {url}")
        else:
            logger.info(f"Nikto scan completed with no findings for {url}")
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Nikto scan timed out for {url}")
    except Exception as e:
        logger.error(f"Nikto scan failed for {url}: {str(e)}")
    
    return vulnerabilities
