from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
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
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import ScanJob

router = APIRouter(prefix="/api/security-scan", tags=["security"])

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load presets
PRESETS = {}
PRESET_DIR = os.path.join(os.path.dirname(__file__), "..", "presets")

def load_presets():
    """Load scan level presets from YAML files"""
    global PRESETS
    try:
        for tier in ["level0", "level1", "level2"]:
            preset_file = os.path.join(PRESET_DIR, f"{tier}_surface.yaml" if tier == "level0" else f"{tier}_discovery.yaml" if tier == "level1" else f"{tier}_active.yaml")
            if os.path.exists(preset_file):
                with open(preset_file, 'r') as f:
                    PRESETS[tier] = yaml.safe_load(f)
                    logger.info(f"Loaded preset for {tier}")
    except Exception as e:
        logger.error(f"Failed to load presets: {str(e)}")

# Load presets on startup
load_presets()

# Tier to Cloud Run Job mapping
TIER_TO_JOB = {
    "level0": "thandev-surface",
    "level1": "thandev-buzz", 
    "level2": "thandev-active"
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
async def start_security_scan(request: SecurityScanRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start a security scan for the given URL"""
    # Validate tier
    if not validate_tier(request.tier):
        raise HTTPException(status_code=400, detail="Invalid tier. Must be level0, level1, or level2")
    
    # Get user_id (for now, use a default if not provided)
    user_id = request.user_id or "anonymous"
    
    # Check rate limit
    if not check_rate_limit(db, user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Maximum 3 concurrent scans allowed.")
    
    # Get preset info
    preset = PRESETS.get(request.tier)
    if not preset:
        raise HTTPException(status_code=400, detail=f"Preset not found for tier {request.tier}")
    
    job_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    # Create scan job record
    scan_job = ScanJob(
        id=job_id,
        user_id=user_id,
        url=str(request.url),
        domain=request.url.host,
        tier=request.tier,
        status="pending",
        created_at=now,
        preset_version=preset.get("version", "1.0")
    )
    
    try:
        db.add(scan_job)
        db.commit()
        db.refresh(scan_job)
        
        # Start background task
        background_tasks.add_task(run_security_scan, job_id, str(request.url), request.tier, db)
        
        return SecurityScanResponse(
            jobId=job_id,
            status="started",
            message="Security scan initiated",
            tier=request.tier,
            estimated_duration=preset.get("estimated_duration", "Unknown")
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create scan job: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start scan")

@router.get("/status/{job_id}", response_model=SecurityScanStatus)
async def get_scan_status(job_id: str, db: Session = Depends(get_db)):
    """Get the status of a security scan"""
    try:
        scan_job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
        if not scan_job:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        return SecurityScanStatus(
            jobId=str(scan_job.id),
            status=scan_job.status,
            tier=scan_job.tier,
            url=scan_job.url,
            created_at=scan_job.created_at.isoformat(),
            started_at=scan_job.started_at.isoformat() if scan_job.started_at else None,
            finished_at=scan_job.finished_at.isoformat() if scan_job.finished_at else None,
            result=scan_job.summary
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
        
        return ScanResults(
            jobId=str(scan_job.id),
            summary=scan_job.summary or {},
            artifact_urls=scan_job.artifact_urls or [],
            vulnerabilities=scan_job.summary.get("vulnerabilities", []) if scan_job.summary else [],
            created_at=scan_job.created_at.isoformat(),
            finished_at=scan_job.finished_at.isoformat()
        )
    except Exception as e:
        logger.error(f"Failed to get scan results: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get scan results")

@router.get("/list")
async def list_user_scans(user_id: str, limit: int = 10, offset: int = 0, db: Session = Depends(get_db)):
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
        scan_job.summary = results.get("summary", {})
        scan_job.artifact_urls = results.get("artifact_urls", [])
        
        db.commit()
        
        logger.info(f"Received scan results for job {job_id}")
        return {"status": "success", "message": "Results received"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to process callback for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process callback")

async def run_security_scan(job_id: str, url: str, tier: str, db: Session):
    """Run security scan using Cloud Run Job or local tools"""
    try:
        # Update status to running
        scan_job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
        if scan_job:
            scan_job.status = "running"
            scan_job.started_at = datetime.utcnow()
            db.commit()
        
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
            execution_id = await run_cloud_run_scan(job_id, url, tier, job_name, preset)
            if scan_job:
                scan_job.execution_id = execution_id
                db.commit()
        else:
            # Use local tools for development/testing
            await run_local_scan(job_id, url, tier, preset)
            
    except Exception as e:
        logger.error(f"Scan failed for job {job_id}: {str(e)}")
        scan_job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
        if scan_job:
            scan_job.status = "error"
            scan_job.finished_at = datetime.utcnow()
            scan_job.summary = {"error": str(e)}
            db.commit()

async def run_cloud_run_scan(job_id: str, url: str, tier: str, job_name: str, preset: Dict[str, Any]):
    """Trigger Cloud Run Job for security scanning"""
    try:
        # Get project ID and region from environment
        project_id = os.getenv("GCP_PROJECT_ID", "thandev")
        region = os.getenv("GCP_REGION", "us-central1")
        
        # Prepare environment variables for the Cloud Run Job
        callback_url = f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/api/security-scan/callback/{job_id}"
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
        
        # Execute the Cloud Run Job
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        if result.returncode == 0:
            logger.info(f"Cloud Run Job completed successfully for job {job_id}")
            logger.info(f"Job output: {result.stdout}")
            return job_id  # Return execution ID
        else:
            logger.error(f"Cloud Run Job failed for job {job_id}: {result.stderr}")
            raise Exception(f"Cloud Run Job failed: {result.stderr}")
                
    except subprocess.TimeoutExpired:
        logger.error(f"Cloud Run Job timed out for job {job_id}")
        raise Exception("Cloud Run Job timed out")
    except Exception as e:
        logger.error(f"Failed to trigger Cloud Run Job for {job_id}: {str(e)}")
        raise Exception(f"Failed to trigger Cloud Run Job: {str(e)}")

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
    """Run nuclei vulnerability scanner"""
    vulnerabilities = []
    
    try:
        templates = tool_config.get("templates", [])
        timeout = tool_config.get("timeout", 300)
        
        # Update nuclei templates first
        update_cmd = ["nuclei", "-update-templates"]
        subprocess.run(update_cmd, capture_output=True, timeout=60)
        
        # Run nuclei scan
        cmd = [
            "nuclei",
            "-u", url,
            "-t", ",".join(templates),
            "-json",
            "-silent"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line:
                    result_data = json.loads(line)
                    vuln = Vulnerability(
                        id=result_data.get('template-id', ''),
                        type="Nuclei Finding",
                        severity=result_data.get('info', {}).get('severity', 'info').lower(),
                        title=result_data.get('info', {}).get('name', 'Unknown'),
                        description=result_data.get('info', {}).get('description', 'No description available'),
                        recommendation=result_data.get('info', {}).get('remediation', 'No recommendation available'),
                        cwe=result_data.get('info', {}).get('cwe-id', []),
                        cvss=result_data.get('info', {}).get('classification', {}).get('cvss-score')
                    )
                    vulnerabilities.append(vuln)
        
    except Exception as e:
        logger.error(f"Nuclei scan failed: {str(e)}")
    
    return vulnerabilities

async def run_ffuf_scan(url: str, tool_config: Dict[str, Any], temp_dir: str) -> List[Vulnerability]:
    """Run ffuf directory discovery"""
    vulnerabilities = []
    
    try:
        timeout = tool_config.get("timeout", 300)
        wordlist = tool_config.get("wordlist", "small")
        
        # Use a small wordlist for directory discovery
        wordlist_path = f"/usr/share/wordlists/dirb/{wordlist}.txt"
        if not os.path.exists(wordlist_path):
            wordlist_path = "/usr/share/wordlists/dirb/common.txt"
        
        cmd = [
            "ffuf",
            "-u", f"{url}/FUZZ",
            "-w", wordlist_path,
            "-json",
            "-o", os.path.join(temp_dir, "ffuf_results.json")
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
        if result.returncode == 0:
            # Process ffuf results
            ffuf_file = os.path.join(temp_dir, "ffuf_results.json")
            if os.path.exists(ffuf_file):
                with open(ffuf_file, 'r') as f:
                    ffuf_data = json.load(f)
                    for item in ffuf_data.get('results', []):
                        if item.get('status') == 200:
                            vuln = Vulnerability(
                                id=f"ffuf-{uuid.uuid4().hex[:8]}",
                                type="Directory Discovery",
                                severity="info",
                                title=f"Directory found: {item.get('input', {}).get('FUZZ', '')}",
                                description=f"Directory {item.get('input', {}).get('FUZZ', '')} is accessible",
                                recommendation="Review discovered directories for sensitive information"
                            )
                            vulnerabilities.append(vuln)
        
    except Exception as e:
        logger.error(f"FFUF scan failed: {str(e)}")
    
    return vulnerabilities

async def run_nikto_scan(url: str, temp_dir: str) -> List[Vulnerability]:
    """Run nikto HTTP server security checks"""
    vulnerabilities = []
    
    try:
        cmd = [
            "nikto",
            "-h", url,
            "-Format", "json",
            "-output", os.path.join(temp_dir, "nikto_results.json")
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            # Process nikto results
            nikto_file = os.path.join(temp_dir, "nikto_results.json")
            if os.path.exists(nikto_file):
                with open(nikto_file, 'r') as f:
                    nikto_data = json.load(f)
                    for item in nikto_data.get('vulnerabilities', []):
                        vuln = Vulnerability(
                            id=f"nikto-{uuid.uuid4().hex[:8]}",
                            type="Nikto Finding",
                            severity=item.get('severity', 'medium').lower(),
                            title=item.get('title', 'Unknown'),
                            description=item.get('description', 'No description available'),
                            recommendation=item.get('remediation', 'No recommendation available')
                        )
                        vulnerabilities.append(vuln)
        
    except Exception as e:
        logger.error(f"Nikto scan failed: {str(e)}")
    
    return vulnerabilities

async def run_port_scan(url: str, temp_dir: str) -> List[Vulnerability]:
    """Run port scan using nmap"""
    vulnerabilities = []
    
    try:
        # Extract hostname from URL
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        
        if not hostname:
            return vulnerabilities
        
        # Run nmap scan
        cmd = [
            "nmap",
            "-sS",  # SYN scan
            "-O",   # OS detection
            "-sV",  # Service version detection
            "-T4",  # Timing template
            hostname
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            # Parse nmap output and create vulnerabilities
            # This is a simplified parser - in production, use proper XML parsing
            lines = result.stdout.split('\n')
            for line in lines:
                if 'open' in line and 'tcp' in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        port = parts[0].split('/')[0]
                        service = parts[2] if len(parts) > 2 else "unknown"
                        
                        vuln = Vulnerability(
                            id=f"port-{uuid.uuid4().hex[:8]}",
                            type="Port Scan",
                            severity="info",
                            title=f"Open Port {port}",
                            description=f"Port {port} is open and running {service}",
                            recommendation="Review open ports and ensure only necessary services are exposed",
                            port=int(port),
                            service=service
                        )
                        vulnerabilities.append(vuln)
        
    except subprocess.TimeoutExpired:
        logger.error("Port scan timed out")
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
