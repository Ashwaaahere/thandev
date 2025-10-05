from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any
import asyncio
import uuid
import json
import time
from datetime import datetime
import subprocess
import os
import tempfile
import shutil

router = APIRouter(prefix="/api/performance-scan", tags=["performance"])

# In-memory storage for scan results (in production, use Redis or database)
scan_results: Dict[str, Dict[str, Any]] = {}

class PerformanceScanRequest(BaseModel):
    url: HttpUrl
    device: str = "desktop"
    timestamp: str

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

@router.post("/", response_model=PerformanceScanResponse)
async def start_performance_scan(request: PerformanceScanRequest, background_tasks: BackgroundTasks):
    """Start a performance scan for the given URL"""
    job_id = str(uuid.uuid4())
    
    # Initialize scan result
    scan_results[job_id] = {
        "jobId": job_id,
        "status": "pending",
        "url": str(request.url),
        "device": request.device,
        "createdAt": request.timestamp,
        "result": None,
        "completedAt": None
    }
    
    # Start background task
    background_tasks.add_task(run_lighthouse_scan, job_id, str(request.url), request.device)
    
    return PerformanceScanResponse(
        jobId=job_id,
        status="started",
        message="Performance scan initiated"
    )

@router.get("/{job_id}", response_model=PerformanceScanStatus)
async def get_scan_status(job_id: str):
    """Get the status of a performance scan"""
    if job_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    result = scan_results[job_id]
    return PerformanceScanStatus(
        jobId=result["jobId"],
        status=result["status"],
        result=result["result"],
        createdAt=result["createdAt"],
        completedAt=result["completedAt"]
    )

async def run_lighthouse_scan(job_id: str, url: str, device: str):
    """Run Lighthouse scan in background"""
    try:
        # Update status to running
        scan_results[job_id]["status"] = "running"
        
        # Create temporary directory for Lighthouse
        with tempfile.TemporaryDirectory() as temp_dir:
            # Run Lighthouse command
            cmd = [
                "lighthouse",
                url,
                "--output=json",
                "--output-path=" + os.path.join(temp_dir, "report.json"),
                "--chrome-flags=--headless",
                "--only-categories=performance,accessibility,best-practices,seo",
                "--quiet"
            ]
            
            # Add device-specific Chrome flags instead of form-factor
            if device == "mobile":
                cmd.extend(["--chrome-flags=--headless --window-size=375,667 --user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"])
            else:
                cmd.extend(["--chrome-flags=--headless --window-size=1280,720"])
            
            # Run the command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                raise Exception(f"Lighthouse failed: {result.stderr}")
            
            # Read the results
            with open(os.path.join(temp_dir, "report.json"), "r") as f:
                lighthouse_data = json.load(f)
            
            # Process the results
            processed_result = process_lighthouse_results(lighthouse_data)
            
            # Update scan results
            scan_results[job_id]["status"] = "completed"
            scan_results[job_id]["result"] = processed_result
            scan_results[job_id]["completedAt"] = datetime.utcnow().isoformat()
            
    except subprocess.TimeoutExpired:
        scan_results[job_id]["status"] = "failed"
        scan_results[job_id]["result"] = {"error": "Scan timed out"}
    except Exception as e:
        scan_results[job_id]["status"] = "failed"
        scan_results[job_id]["result"] = {"error": str(e)}

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
            "unused-css-rules",
            "modern-image-formats",
            "uses-webp-images",
            "uses-optimized-images",
            "uses-text-compression",
            "uses-responsive-images",
            "offscreen-images",
            "unused-css-rules",
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
async def list_scans():
    """List all performance scans"""
    return {"scans": list(scan_results.values())}

@router.delete("/{job_id}")
async def delete_scan(job_id: str):
    """Delete a performance scan"""
    if job_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    del scan_results[job_id]
    return {"message": "Scan deleted successfully"}
