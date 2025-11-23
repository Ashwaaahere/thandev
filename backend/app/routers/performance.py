from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from ..db import get_db, SessionLocal
from ..models import PerformanceScanJob
from typing import Optional, Dict, Any
import uuid
import json
from datetime import datetime
import subprocess
import os
import tempfile
import logging
import httpx
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/performance-scan", tags=["performance"])

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

class PerformanceScanRequest(BaseModel):
    url: HttpUrl
    device: str = "desktop"
    user_id: Optional[str] = None

class PerformanceScanResponse(BaseModel):
    jobId: str
    status: str
    message: str

class PerformanceScanStatus(BaseModel):
    jobId: str
    status: str
    result: Optional[Dict[str, Any]] = None
    createdAt: str
    completedAt: Optional[str] = None
    error: Optional[str] = None

@router.post("/", response_model=PerformanceScanResponse)
@limiter.limit("10/minute")
async def start_performance_scan(
    request: Request,
    scan_request: PerformanceScanRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start a performance scan for the given URL"""
    job_id = str(uuid.uuid4())
    user_id = scan_request.user_id or "anonymous"
    now = datetime.utcnow()
    
    logger.info(f"Performance scan request received: job_id={job_id}, url={scan_request.url}, device={scan_request.device}, user_id={user_id}")
    
    # Create scan job record in database
    scan_job = PerformanceScanJob(
        id=job_id,
        user_id=user_id,
        url=str(scan_request.url),
        device=scan_request.device,
        status="pending",
        created_at=now
    )
    
    try:
        db.add(scan_job)
        db.commit()
        db.refresh(scan_job)
        logger.info(f"Performance scan job created in database: {job_id}")
        
        # Start background task
        background_tasks.add_task(
            run_lighthouse_scan,
            job_id,
            str(scan_request.url),
            scan_request.device
        )
        logger.info(f"Background task scheduled for performance scan: {job_id}")
        
        return PerformanceScanResponse(
            jobId=job_id,
            status="started",
            message="Performance scan initiated"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create performance scan job {job_id}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to start scan: {str(e)}")

@router.get("/{job_id}", response_model=PerformanceScanStatus)
async def get_scan_status(job_id: str, db: Session = Depends(get_db)):
    """Get the status of a performance scan"""
    scan_job = db.query(PerformanceScanJob).filter(PerformanceScanJob.id == job_id).first()
    
    if not scan_job:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Parse result if it's a JSON string
    result = None
    if scan_job.result:
        try:
            if isinstance(scan_job.result, str):
                result = json.loads(scan_job.result)
            else:
                result = scan_job.result
        except:
            result = scan_job.result
    
    return PerformanceScanStatus(
        jobId=str(scan_job.id),
        status=scan_job.status,
        result=result,
        createdAt=scan_job.created_at.isoformat(),
        completedAt=scan_job.finished_at.isoformat() if scan_job.finished_at else None,
        error=scan_job.error
    )

async def run_lighthouse_scan(job_id: str, url: str, device: str):
    """Run Lighthouse scan using Cloud Run Service or local fallback"""
    logger.info(f"Background task started for performance scan: job_id={job_id}, url={url}, device={device}")
    
    # Create a new database session for the background task
    db = SessionLocal()
    scan_job = None
    
    try:
        # Update status to running
        scan_job = db.query(PerformanceScanJob).filter(PerformanceScanJob.id == job_id).first()
        if scan_job:
            scan_job.status = "running"
            scan_job.started_at = datetime.utcnow()
            db.commit()
            logger.info(f"Performance scan job status updated to 'running': {job_id}")
        else:
            logger.warning(f"Performance scan job not found in database: {job_id}")
        
        # Check if Cloud Run Service is enabled
        # Handle common mistake where users include "-a thandev-backend" in the value
        cloud_run_enabled_raw = os.getenv("CLOUD_RUN_ENABLED", "true").strip()
        # Remove common mistakes: "-a thandev-backend", quotes, etc.
        cloud_run_enabled_clean = cloud_run_enabled_raw.split()[0].strip('"\'')
        cloud_run_enabled = cloud_run_enabled_clean.lower() == "true"
        cloud_run_url = os.getenv("CLOUD_RUN_LIGHTHOUSE_URL", "").strip()
        
        # Debug: Log all environment variables that start with CLOUD_RUN
        cloud_run_env_vars = {k: v[:50] + "..." if len(v) > 50 else v for k, v in os.environ.items() if k.startswith("CLOUD_RUN")}
        logger.info(f"Cloud Run environment variables: {cloud_run_env_vars}")
        logger.info(f"Cloud Run configuration: enabled={cloud_run_enabled}, url_set={bool(cloud_run_url)}, url_length={len(cloud_run_url) if cloud_run_url else 0}, url_value={cloud_run_url[:50] if cloud_run_url else 'EMPTY'}")
        
        if cloud_run_enabled and cloud_run_url:
            # Use Cloud Run Service
            logger.info(f"Using Cloud Run Service for performance scan: {job_id}")
            await run_cloud_run_lighthouse_scan(job_id, url, device, cloud_run_url, db)
        else:
            # Fallback to local Lighthouse (for development)
            logger.warning(f"Cloud Run not configured, falling back to local Lighthouse for job: {job_id}")
            logger.warning(f"This may cause out-of-memory errors on Fly.io!")
            await run_local_lighthouse_scan(job_id, url, device, db)
            
    except Exception as e:
        logger.error(f"Performance scan failed for job {job_id}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        if scan_job:
            scan_job.status = "error"
            scan_job.finished_at = datetime.utcnow()
            scan_job.error = str(e)
            db.commit()
    finally:
        db.close()

async def run_cloud_run_lighthouse_scan(job_id: str, url: str, device: str, cloud_run_url: str, db: Session):
    """Run Lighthouse scan via Cloud Run Service"""
    logger.info(f"Calling Cloud Run Service: {cloud_run_url}/run for job {job_id}")
    
    scan_job = db.query(PerformanceScanJob).filter(PerformanceScanJob.id == job_id).first()
    
    try:
        # Call Cloud Run Service to start scan
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Sending POST request to Cloud Run Service: {cloud_run_url}/run")
            response = await client.post(
                f"{cloud_run_url}/run",
                json={
                    "url": url,
                    "device": device,
                    "category": "performance"
                }
            )
            
            logger.info(f"Cloud Run Service response: status={response.status_code}, headers={dict(response.headers)}")
            
            if response.status_code != 200:
                error_text = response.text[:500]  # Limit error text length
                logger.error(f"Cloud Run Service failed to start scan: status={response.status_code}, error={error_text}")
                raise Exception(f"Cloud Run Service failed to start scan: {error_text}")
            
            cloud_job_data = response.json()
            cloud_job_id = cloud_job_data.get("jobId")
            
            if not cloud_job_id:
                logger.error(f"Cloud Run Service response missing jobId: {cloud_job_data}")
                raise Exception("Cloud Run Service did not return a jobId")
            
            logger.info(f"Started Cloud Run scan for job {job_id}, cloud job ID: {cloud_job_id}")
            
            # Poll for results (max 5 minutes)
            max_polls = 60  # 60 polls * 5 seconds = 5 minutes
            poll_interval = 5  # seconds
            
            for poll_count in range(max_polls):
                await asyncio.sleep(poll_interval)
                
                status_response = await client.get(f"{cloud_run_url}/status/{cloud_job_id}")
                
                if status_response.status_code != 200:
                    logger.warning(f"Failed to get status for cloud job {cloud_job_id}: {status_response.text}")
                    continue
                
                status_data = status_response.json()
                cloud_status = status_data.get("status", "unknown")
                
                logger.info(f"Cloud Run scan status for job {job_id}: {cloud_status} (poll {poll_count + 1}/{max_polls})")
                
                if cloud_status == "completed":
                    # Process and save results
                    result = status_data.get("result", {})
                    processed_result = process_cloud_run_results(result)
                    
                    if scan_job:
                        scan_job.status = "completed"
                        scan_job.finished_at = datetime.utcnow()
                        scan_job.result = json.dumps(processed_result) if isinstance(processed_result, dict) else processed_result
                        db.commit()
                        logger.info(f"Performance scan completed for job {job_id}")
                    return
                
                elif cloud_status == "failed":
                    error_msg = status_data.get("error", "Unknown error")
                    raise Exception(f"Cloud Run scan failed: {error_msg}")
            
            # Timeout
            raise Exception("Cloud Run scan timed out after 5 minutes")
            
    except httpx.TimeoutException:
        raise Exception("Cloud Run Service request timed out")
    except Exception as e:
        logger.error(f"Cloud Run scan error for job {job_id}: {str(e)}")
        raise

async def run_local_lighthouse_scan(job_id: str, url: str, device: str, db: Session):
    """Run Lighthouse scan locally (fallback for development)"""
    scan_job = db.query(PerformanceScanJob).filter(PerformanceScanJob.id == job_id).first()
    
    try:
        # Create temporary directory for Lighthouse
        with tempfile.TemporaryDirectory() as temp_dir:
            # Get Chrome path from environment or use default
            chrome_path = os.getenv("CHROME_PATH", "/usr/bin/google-chrome-stable")
            
            # Run Lighthouse command
            cmd = [
                "lighthouse",
                url,
                "--output=json",
                "--output-path=" + os.path.join(temp_dir, "report.json"),
                "--chrome-flags=--headless --no-sandbox --disable-gpu",
                "--only-categories=performance,accessibility,best-practices,seo",
                "--quiet"
            ]
            
            # Set CHROME_PATH environment variable for Lighthouse
            env = os.environ.copy()
            env["CHROME_PATH"] = chrome_path
            
            # Add device-specific Chrome flags
            if device == "mobile":
                cmd.extend(["--chrome-flags=--headless --window-size=375,667 --user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"])
            else:
                cmd.extend(["--chrome-flags=--headless --window-size=1280,720"])
            
            # Run the command with Chrome path in environment
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
            
            if result.returncode != 0:
                raise Exception(f"Lighthouse failed: {result.stderr}")
            
            # Read the results
            with open(os.path.join(temp_dir, "report.json"), "r") as f:
                lighthouse_data = json.load(f)
            
            # Process the results
            processed_result = process_lighthouse_results(lighthouse_data)
            
            # Update scan job with results
            if scan_job:
                scan_job.status = "completed"
                scan_job.finished_at = datetime.utcnow()
                # Store result as JSON string for SQLite compatibility
                scan_job.result = json.dumps(processed_result) if isinstance(processed_result, dict) else processed_result
                db.commit()
                logger.info(f"Performance scan completed for job {job_id}")
                
    except subprocess.TimeoutExpired:
        if scan_job:
            scan_job.status = "error"
            scan_job.finished_at = datetime.utcnow()
            scan_job.error = "Scan timed out"
            db.commit()
        raise Exception("Lighthouse scan timed out")
    except Exception as e:
        if scan_job:
            scan_job.status = "error"
            scan_job.finished_at = datetime.utcnow()
            scan_job.error = str(e)
            db.commit()
        raise

def process_cloud_run_results(cloud_result: Dict[str, Any]) -> Dict[str, Any]:
    """Process Cloud Run Service results into our format"""
    try:
        # Cloud Run Service returns results in a specific format
        # Extract categories, metrics, opportunities, diagnostics
        categories = cloud_result.get("categories", {})
        metrics = cloud_result.get("metrics", {})
        opportunities = cloud_result.get("opportunities", [])
        diagnostics = cloud_result.get("diagnostics", [])
        
        return {
            "categories": categories,
            "metrics": metrics,
            "opportunities": opportunities,
            "diagnostics": diagnostics,
            "screenshot": cloud_result.get("screenshot")
        }
    except Exception as e:
        logger.error(f"Failed to process Cloud Run results: {str(e)}")
        return {
            "error": f"Failed to process Cloud Run results: {str(e)}",
            "categories": {"performance": 0, "accessibility": 0, "bestPractices": 0, "seo": 0},
            "metrics": {},
            "opportunities": [],
            "diagnostics": []
        }

def process_lighthouse_results(lighthouse_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process Lighthouse results into our format"""
    try:
        # Extract categories scores
        categories = lighthouse_data.get("categories", {})
        category_scores = {
            "performance": int(categories.get("performance", {}).get("score", 0) * 100),
            "accessibility": int(categories.get("accessibility", {}).get("score", 0) * 100),
            "bestPractices": int(categories.get("best-practices", {}).get("score", 0) * 100),
            "seo": int(categories.get("seo", {}).get("score", 0) * 100),
        }
        
        # Extract metrics
        audits = lighthouse_data.get("audits", {})
        metrics = {
            "firstContentfulPaint": audits.get("first-contentful-paint", {}).get("numericValue", 0),
            "largestContentfulPaint": audits.get("largest-contentful-paint", {}).get("numericValue", 0),
            "firstMeaningfulPaint": audits.get("first-meaningful-paint", {}).get("numericValue", 0),
            "speedIndex": audits.get("speed-index", {}).get("numericValue", 0),
            "cumulativeLayoutShift": audits.get("cumulative-layout-shift", {}).get("numericValue", 0),
            "totalBlockingTime": audits.get("total-blocking-time", {}).get("numericValue", 0),
            "interactive": audits.get("interactive", {}).get("numericValue", 0),
            "firstInputDelay": audits.get("max-potential-fid", {}).get("numericValue", 0),
        }
        
        # Extract opportunities
        opportunities = []
        opportunity_audits = [
            "unused-css-rules",
            "unused-javascript",
            "render-blocking-resources",
            "unminified-css",
            "unminified-javascript",
            "efficient-animated-content",
            "uses-optimized-images",
            "uses-text-compression",
            "uses-responsive-images",
            "offscreen-images",
            "modern-image-formats",
            "uses-webp-images"
        ]
        
        for audit_id in opportunity_audits:
            if audit_id in audits:
                audit = audits[audit_id]
                if audit.get("score") is not None and audit.get("score") < 1:
                    opportunities.append({
                        "id": audit_id,
                        "title": audit.get("title", ""),
                        "description": audit.get("description", ""),
                        "score": audit.get("score", 0),
                        "displayValue": audit.get("displayValue", ""),
                        "details": {
                            "items": audit.get("details", {}).get("items", [])
                        }
                    })
        
        # Extract diagnostics
        diagnostics = []
        diagnostic_audits = [
            "mainthread-work-breakdown",
            "bootup-time",
            "dom-size",
            "duplicated-javascript",
            "efficient-animated-content",
            "legacy-javascript",
            "no-document-write",
            "no-vulnerable-libraries",
            "notification-on-start",
            "password-inputs-can-be-pasted-into",
            "uses-http2",
            "uses-long-cache-ttl",
            "uses-rel-preconnect",
            "uses-rel-preload",
            "valid-source-maps"
        ]
        
        for audit_id in diagnostic_audits:
            if audit_id in audits:
                audit = audits[audit_id]
                if audit.get("score") is not None:
                    diagnostics.append({
                        "id": audit_id,
                        "title": audit.get("title", ""),
                        "description": audit.get("description", ""),
                        "score": audit.get("score", 0),
                        "displayValue": audit.get("displayValue", ""),
                        "details": {
                            "items": audit.get("details", {}).get("items", [])
                        }
                    })
        
        return {
            "categories": category_scores,
            "metrics": metrics,
            "opportunities": opportunities,
            "diagnostics": diagnostics,
            "screenshot": None  # Could add screenshot if needed
        }
        
    except Exception as e:
        return {
            "error": f"Failed to process Lighthouse results: {str(e)}",
            "categories": {"performance": 0, "accessibility": 0, "bestPractices": 0, "seo": 0},
            "metrics": {},
            "opportunities": [],
            "diagnostics": []
        }

@router.get("/")
@limiter.limit("30/minute")
async def list_scans(
    request: Request,
    user_id: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List performance scans for a user"""
    query = db.query(PerformanceScanJob)
    
    if user_id:
        query = query.filter(PerformanceScanJob.user_id == user_id)
    
    scans = query.order_by(PerformanceScanJob.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "scans": [
            {
                "jobId": str(scan.id),
                "url": scan.url,
                "device": scan.device,
                "status": scan.status,
                "createdAt": scan.created_at.isoformat(),
                "finishedAt": scan.finished_at.isoformat() if scan.finished_at else None
            }
            for scan in scans
        ],
        "total": query.count()
    }

@router.delete("/{job_id}")
async def delete_scan(job_id: str, db: Session = Depends(get_db)):
    """Delete a performance scan"""
    scan_job = db.query(PerformanceScanJob).filter(PerformanceScanJob.id == job_id).first()
    
    if not scan_job:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    try:
        db.delete(scan_job)
        db.commit()
        return {"message": "Scan deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete scan {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete scan: {str(e)}")
