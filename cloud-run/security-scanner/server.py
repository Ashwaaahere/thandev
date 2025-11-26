#!/usr/bin/env python3
"""
Security Scanner Cloud Run Service
HTTP API for running security scans (nuclei, nmap, sslscan)
Matches Lighthouse scanner pattern
"""

import os
import sys
import json
import time
import asyncio
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

# Import the scanner
from scanner import SecurityScanner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# In-memory job storage (in production, use Redis or database)
jobs = {}

def generate_job_id():
    """Generate unique job ID"""
    return f"security_{int(time.time())}_{uuid.uuid4().hex[:8]}"

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "security-scanner"})

@app.route('/run', methods=['POST'])
async def run_scan():
    """Start a new security scan"""
    try:
        data = request.json
        url = data.get('url')
        tier = data.get('tier', 'level1')
        job_id = data.get('jobId') or generate_job_id()
        
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        logger.info(f"Starting security scan: job_id={job_id}, url={url}, tier={tier}")
        
        # Initialize job status
        jobs[job_id] = {
            "status": "running",
            "url": url,
            "tier": tier,
            "started_at": datetime.utcnow().isoformat(),
            "result": None,
            "error": None
        }
        
        # Run scan in background
        asyncio.create_task(run_scan_async(job_id, url, tier))
        
        return jsonify({
            "jobId": job_id,
            "status": "started",
            "message": "Security scan initiated"
        }), 200
        
    except Exception as e:
        logger.error(f"Error starting scan: {str(e)}")
        return jsonify({"error": str(e)}), 500

async def run_scan_async(job_id: str, url: str, tier: str):
    """Run the actual scan asynchronously"""
    try:
        scanner = SecurityScanner()
        
        # Get callback URL and other params from environment (if needed)
        callback_url = os.getenv("CALLBACK_URL")
        gcs_bucket = os.getenv("GCS_BUCKET", "thandev-reports")
        scan_id = job_id
        
        if callback_url:
            # Run with callback (original Job pattern)
            await scanner.run_scan_with_gcs(url, tier, callback_url, scan_id, gcs_bucket)
        else:
            # Run scan and store results in jobs dict
            results = await scanner.run_scan(url, tier)
            
            # Update job status
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["result"] = results
            jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
            
    except Exception as e:
        logger.error(f"Scan failed for job {job_id}: {str(e)}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()

@app.route('/status/<job_id>', methods=['GET'])
def get_status(job_id):
    """Get scan status and results"""
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = jobs[job_id]
    
    response = {
        "status": job["status"],
        "jobId": job_id,
        "url": job["url"],
        "tier": job["tier"]
    }
    
    if job["status"] == "completed" and job["result"]:
        response["result"] = job["result"]
    elif job["status"] == "failed" and job["error"]:
        response["error"] = job["error"]
    
    if "started_at" in job:
        response["startedAt"] = job["started_at"]
    if "completed_at" in job:
        response["completedAt"] = job["completed_at"]
    
    return jsonify(response), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

