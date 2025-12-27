#!/usr/bin/env python3
"""
Security Scanner Cloud Run Job
Runs nuclei, nmap, and sslscan tools for comprehensive security assessment
"""

import os
import sys
import json
import time
import asyncio
import subprocess
import tempfile
import shutil
from datetime import datetime
from urllib.parse import urlparse
import aiohttp
import logging

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import result processing utilities
try:
    from result_processor import result_processor, result_cache
    RESULT_PROCESSING_AVAILABLE = True
except ImportError:
    logger.warning("Result processing utilities not available, using basic processing")
    RESULT_PROCESSING_AVAILABLE = False

class SecurityScanner:
    def __init__(self):
        self.results = {
            "vulnerabilities": [],
            "ports": [],
            "ssl_issues": [],
            "scan_metadata": {}
        }
    
    async def run_scan_with_gcs(self, url: str, tier: str, callback_url: str, scan_id: str, gcs_bucket: str):
        """Main scan orchestration with GCS upload"""
        try:
            from urllib.parse import urlparse
            import xml.etree.ElementTree as ET
            from google.cloud import storage
            
            logger.info(f"Starting {tier} scan for {url}, scan_id={scan_id}")
            
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname or parsed_url.netloc
            
            # Step 1: Run Nuclei scan
            logger.info("Running Nuclei scan...")
            nuclei_output_file = "/tmp/nuclei-output.json"
            nuclei_cmd = [
                "nuclei", "-u", url,
                "-severity", "low,medium,high,critical",
                "-silent", "-json", "-o", nuclei_output_file
            ]
            
            nuclei_result = subprocess.run(nuclei_cmd, capture_output=True, text=True, timeout=300)
            if nuclei_result.returncode != 0:
                logger.warning(f"Nuclei scan had issues: {nuclei_result.stderr}")
            
            # Step 2: Run Nmap scan
            logger.info("Running Nmap scan...")
            nmap_output_file = "/tmp/nmap-output.xml"
            nmap_cmd = [
                "nmap", "-sV", "-Pn", "--top-ports", "100",
                hostname, "-oX", nmap_output_file
            ]
            
            nmap_result = subprocess.run(nmap_cmd, capture_output=True, text=True, timeout=300)
            if nmap_result.returncode != 0:
                logger.warning(f"Nmap scan had issues: {nmap_result.stderr}")
            
            # Step 3: Parse results
            vulnerabilities = []
            ports = []
            
            # Parse Nuclei results
            if os.path.exists(nuclei_output_file):
                with open(nuclei_output_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            try:
                                vuln_data = json.loads(line)
                                vulnerabilities.append({
                                    "type": vuln_data.get('info', {}).get('name', 'Nuclei Finding'),
                                    "severity": vuln_data.get('info', {}).get('severity', 'info').lower(),
                                    "title": vuln_data.get('info', {}).get('name', 'Security Finding'),
                                    "description": vuln_data.get('info', {}).get('description', ''),
                                    "recommendation": vuln_data.get('info', {}).get('remediation', ''),
                                    "cwe": vuln_data.get('info', {}).get('classification', {}).get('cwe-id', []),
                                    "cvss": vuln_data.get('info', {}).get('classification', {}).get('cvss-score'),
                                    "matched_at": vuln_data.get('matched-at', url)
                                })
                            except json.JSONDecodeError:
                                continue
            
            # Parse Nmap results
            if os.path.exists(nmap_output_file):
                try:
                    tree = ET.parse(nmap_output_file)
                    root = tree.getroot()
                    for host in root.findall('host'):
                        for port in host.findall('ports/port'):
                            if port.find('state').get('state') == 'open':
                                port_id = port.get('portid')
                                service_elem = port.find('service')
                                service_name = service_elem.get('name', 'unknown') if service_elem is not None else 'unknown'
                                service_version = service_elem.get('version', '') if service_elem is not None else ''
                                ports.append({
                                    "port": int(port_id),
                                    "service": service_name,
                                    "version": service_version,
                                    "state": "open"
                                })
                except Exception as e:
                    logger.error(f"Failed to parse nmap XML: {str(e)}")
            
            # Step 4: Upload to GCS
            artifacts_prefix = f"security/{scan_id}/"
            gcs_client = storage.Client()
            bucket = gcs_client.bucket(gcs_bucket)
            
            # Upload nuclei output
            if os.path.exists(nuclei_output_file):
                blob_name = f"{artifacts_prefix}nuclei-output.json"
                blob = bucket.blob(blob_name)
                blob.upload_from_filename(nuclei_output_file)
                logger.info(f"Uploaded nuclei results to gs://{gcs_bucket}/{blob_name}")
            
            # Upload nmap output
            if os.path.exists(nmap_output_file):
                blob_name = f"{artifacts_prefix}nmap-output.xml"
                blob = bucket.blob(blob_name)
                blob.upload_from_filename(nmap_output_file)
                logger.info(f"Uploaded nmap results to gs://{gcs_bucket}/{blob_name}")
            
            # Step 5: Generate summary
            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
            for vuln in vulnerabilities:
                severity = vuln.get('severity', 'info')
                if severity in severity_counts:
                    severity_counts[severity] += 1
            
            summary = {
                "url": url,
                "tier": tier,
                "timestamp": datetime.utcnow().isoformat(),
                "vulnerabilities": vulnerabilities,
                "ports": ports,
                "totalVulnerabilities": len(vulnerabilities),
                "severityBreakdown": severity_counts,
                "openPorts": len(ports),
                "scanMetadata": {
                    "scanDuration": 0,
                    "toolsUsed": ["nuclei", "nmap"],
                    "scanTime": datetime.utcnow().isoformat()
                }
            }
            
            # Step 6: Send callback (format matches backend expectation)
            callback_data = {
                "scanId": scan_id,
                "status": "done",
                "summary": summary,
                "artifactsPrefix": artifacts_prefix,
                "secret": os.getenv('CALLBACK_SECRET', '')  # Include secret if provided
            }
            
            await self.send_callback(callback_url, callback_data)
            logger.info(f"Scan completed successfully for {url}, scan_id={scan_id}")
            
        except Exception as e:
            logger.error(f"Scan failed: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            await self.send_error_callback(callback_url, str(e))
    
    async def run_scan(self, url: str, tier: str, callback_url: str):
        """Main scan orchestration"""
        try:
            logger.info(f"Starting {tier} scan for {url}")
            
            # Check cache first (if result processing is available)
            if RESULT_PROCESSING_AVAILABLE:
                cached_results = result_cache.get(url, tier)
                if cached_results:
                    logger.info(f"Using cached results for {url} (tier: {tier})")
                    await self.send_callback(callback_url, cached_results)
                    return
            
            # Parse URL
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname
            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
            
            # Run scans based on tier
            if tier == "level0":
                await self.run_level0_scan(url, hostname, port)
            elif tier == "level1":
                await self.run_level0_scan(url, hostname, port)
                await self.run_level1_scan(url, hostname)
            elif tier == "level2":
                await self.run_level0_scan(url, hostname, port)
                await self.run_level1_scan(url, hostname)
                await self.run_level2_scan(url, hostname)
            else:
                raise Exception(f"Unknown tier: {tier}")
            
            # Process and format results
            processed_results = self.process_results(url, tier)
            
            # Cache results (if result processing is available)
            if RESULT_PROCESSING_AVAILABLE:
                result_cache.set(url, tier, processed_results)
            
            # Send results back via callback
            await self.send_callback(callback_url, processed_results)
            
            logger.info(f"Scan completed successfully for {url}")
            
        except Exception as e:
            logger.error(f"Scan failed: {str(e)}")
            await self.send_error_callback(callback_url, str(e))
    
    async def run_level0_scan(self, url: str, hostname: str, port: int):
        """Level 0 - Surface (Quick) scan"""
        logger.info("Running Level 0 - Surface scan")
        
        # nuclei (info, technologies templates)
        await self.run_nuclei_scan(url, ["info", "technologies"])
        
        # sslscan or sslyze (TLS/cert checks) — fallback to openssl s_client if unavailable
        await self.run_ssl_scan(hostname, port)
        
        # nmap (--top-ports 100 -sV -Pn)
        await self.run_nmap_scan(hostname, ["--top-ports", "100", "-sV", "-Pn"])
    
    async def run_level1_scan(self, url: str, hostname: str):
        """Level 1 - Discovery (Buzz) scan"""
        logger.info("Running Level 1 - Discovery scan")
        
        # subfinder or amass (passive enumeration)
        await self.run_subdomain_enumeration(hostname)
        
        # crt.sh/certificate-transparency lookups (passive)
        await self.run_certificate_transparency_lookup(hostname)
        
        # ffuf or gobuster (directory discovery with small tuned wordlist)
        await self.run_directory_discovery(url, "small")
        
        # nuclei medium templates (misconfig/exposures)
        await self.run_nuclei_scan(url, ["misconfig", "exposures"])
    
    async def run_level2_scan(self, url: str, hostname: str):
        """Level 2 - Active (Non-destructive) scan"""
        logger.info("Running Level 2 - Active scan")
        
        # nuclei (CVE/exposure templates at medium severity)
        await self.run_nuclei_scan(url, ["cves", "vulnerabilities"], severity="medium")
        
        # nikto (HTTP server checks)
        await self.run_nikto_scan(url)
        
        # nmap with safe NSE scripts and service detection (-sC -sV)
        await self.run_nmap_scan(hostname, ["-sC", "-sV", "-Pn"])
    
    async def run_ssl_scan(self, hostname: str, port: int):
        """Run SSL/TLS security scan using sslscan and Python SSL library"""
        try:
            logger.info(f"Running SSL scan on {hostname}:{port}")
            
            # Try sslscan first
            sslscan_success = False
            try:
                cmd = [
                    "sslscan",
                    "--json",
                    f"{hostname}:{port}"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0 and result.stdout.strip():
                    ssl_data = json.loads(result.stdout)
                    self.process_ssl_results(ssl_data)
                    sslscan_success = True
                    logger.info(f"sslscan completed successfully for {hostname}")
                else:
                    logger.warning(f"sslscan failed: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                logger.error("sslscan timed out")
            except Exception as e:
                logger.error(f"sslscan error: {str(e)}")
            
            # Fallback to Python SSL library if sslscan failed
            if not sslscan_success:
                await self.run_python_ssl_scan(hostname, port)
                
        except Exception as e:
            logger.error(f"SSL scan error: {str(e)}")
    
    async def run_python_ssl_scan(self, hostname: str, port: int):
        """Fallback SSL scan using Python SSL library"""
        try:
            import ssl
            import socket
            
            logger.info(f"Running Python SSL scan on {hostname}:{port}")
            
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
                            self.results['ssl_issues'].append({
                                "type": "Outdated SSL/TLS Version",
                                "severity": "high",
                                "description": f"Server is using {version}, which is considered insecure.",
                                "recommendation": "Upgrade to TLS 1.2 or higher"
                            })
                        
                        # Check cipher strength
                        if cipher:
                            cipher_name, cipher_version, cipher_bits = cipher
                            if cipher_bits and cipher_bits < 128:
                                self.results['ssl_issues'].append({
                                    "type": "Weak Cipher Suite",
                                    "severity": "medium",
                                    "description": f"Server is using weak cipher: {cipher_name} ({cipher_bits} bits)",
                                    "recommendation": "Use stronger cipher suites with at least 128-bit encryption"
                                })
                        
                        # Check certificate validity
                        if cert:
                            import datetime
                            not_after = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                            days_until_expiry = (not_after - datetime.datetime.now()).days
                            
                            if days_until_expiry < 30:
                                severity = "critical" if days_until_expiry < 7 else "high"
                                self.results['ssl_issues'].append({
                                    "type": "SSL Certificate Expiring Soon",
                                    "severity": severity,
                                    "description": f"SSL certificate expires in {days_until_expiry} days",
                                    "recommendation": "Renew the SSL certificate before it expires"
                                })
                        
                        # If we get here without issues, the SSL configuration is good
                        logger.info(f"Python SSL scan completed for {hostname}: TLS {version}, Cipher: {cipher_name if cipher else 'Unknown'}")
                        
            except ssl.SSLError as e:
                # SSL connection failed - this is a real issue
                self.results['ssl_issues'].append({
                    "type": "SSL Connection Failed",
                    "severity": "high",
                    "description": f"Failed to establish SSL connection: {str(e)}",
                    "recommendation": "Check SSL configuration and certificate validity"
                })
            except Exception as e:
                logger.warning(f"Python SSL scan error for {hostname}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Python SSL scan failed: {str(e)}")
    
    def process_ssl_results(self, ssl_data):
        """Process SSL scan results"""
        try:
            # Check for weak ciphers
            if 'ciphers' in ssl_data:
                for cipher in ssl_data['ciphers']:
                    strength = cipher.get('strength', 0)
                    cipher_name = cipher.get('cipher', 'Unknown')
                    
                    # Only flag weak ciphers (less than 128 bits)
                    if strength < 128:
                        self.results['ssl_issues'].append({
                            "type": "Weak Cipher Suite",
                            "severity": "medium",
                            "description": f"Weak cipher detected: {cipher_name} ({strength} bits)",
                            "recommendation": "Disable weak ciphers and use only strong encryption"
                        })
            
            # Check for SSL/TLS version issues
            if 'ssl_version' in ssl_data:
                version = ssl_data['ssl_version']
                # Only flag truly outdated versions
                if version in ['SSLv2', 'SSLv3', 'TLSv1.0']:
                    self.results['ssl_issues'].append({
                        "type": "Outdated SSL/TLS Version",
                        "severity": "high",
                        "description": f"Outdated SSL/TLS version detected: {version}",
                        "recommendation": "Upgrade to TLS 1.2 or higher"
                    })
            
            # Check for certificate issues
            if 'certificate' in ssl_data:
                cert = ssl_data['certificate']
                if 'expired' in cert and cert['expired']:
                    self.results['ssl_issues'].append({
                        "type": "Expired SSL Certificate",
                        "severity": "critical",
                        "description": "SSL certificate has expired",
                        "recommendation": "Renew the SSL certificate immediately"
                    })
                elif 'expires_soon' in cert and cert['expires_soon']:
                    self.results['ssl_issues'].append({
                        "type": "SSL Certificate Expiring Soon",
                        "severity": "high",
                        "description": "SSL certificate expires soon",
                        "recommendation": "Renew the SSL certificate before it expires"
                    })
                    
        except Exception as e:
            logger.error(f"Error processing SSL results: {str(e)}")
    
    async def run_port_scan(self, hostname: str):
        """Run port scan using nmap"""
        try:
            logger.info(f"Running port scan on {hostname}")
            
            cmd = [
                "nmap",
                "-sS",  # SYN scan
                "-O",   # OS detection
                "-sV",  # Service version detection
                "-T4",  # Timing template
                "--open",  # Only show open ports
                "-oX", "-",  # Output in XML format to stdout
                hostname
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.process_nmap_results(result.stdout)
            else:
                logger.warning(f"Port scan failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("Port scan timed out")
        except Exception as e:
            logger.error(f"Port scan error: {str(e)}")
    
    def process_nmap_results(self, xml_output):
        """Process nmap XML output"""
        try:
            import xml.etree.ElementTree as ET
            
            root = ET.fromstring(xml_output)
            
            for host in root.findall('host'):
                for port in host.findall('ports/port'):
                    if port.find('state').get('state') == 'open':
                        port_id = port.get('portid')
                        protocol = port.get('protocol')
                        
                        service_elem = port.find('service')
                        service_name = service_elem.get('name', 'unknown') if service_elem is not None else 'unknown'
                        service_version = service_elem.get('version', '') if service_elem is not None else ''
                        
                        self.results['ports'].append({
                            "port": int(port_id),
                            "protocol": protocol,
                            "service": service_name,
                            "version": service_version,
                            "state": "open"
                        })
                        
                        # Check for potentially risky services
                        if service_name in ['ftp', 'telnet', 'rlogin', 'rsh']:
                            self.results['vulnerabilities'].append({
                                "type": "Insecure Service",
                                "severity": "high",
                                "title": f"Insecure Service: {service_name}",
                                "description": f"Service {service_name} is running on port {port_id} which may be insecure",
                                "recommendation": f"Consider disabling {service_name} or securing it properly",
                                "port": int(port_id),
                                "service": service_name
                            })
                            
        except Exception as e:
            logger.error(f"Error processing nmap results: {str(e)}")
    
    async def run_nuclei_scan(self, url: str, scan_type: str):
        """Run nuclei vulnerability scanner"""
        try:
            logger.info(f"Running nuclei scan on {url}")
            
            # Select nuclei templates based on scan type with OWASP focus
            if scan_type == "quick":
                templates = [
                    "vulnerabilities/", "exposures/", "misconfiguration/",
                    "owasp-top10/", "cves/", "default-logins/"
                ]
            elif scan_type == "comprehensive":
                templates = [
                    "vulnerabilities/", "exposures/", "misconfiguration/", 
                    "cves/", "default-logins/", "owasp-top10/", "fuzzing/",
                    "technologies/", "network/", "ssl/"
                ]
            else:  # deep
                templates = [
                    "vulnerabilities/", "exposures/", "misconfiguration/", 
                    "cves/", "default-logins/", "fuzzing/", "owasp-top10/",
                    "technologies/", "network/", "ssl/", "cms/", "panels/"
                ]
            
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
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.process_nuclei_results(result.stdout)
            else:
                logger.warning(f"Nuclei scan failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("Nuclei scan timed out")
        except Exception as e:
            logger.error(f"Nuclei scan error: {str(e)}")
    
    def process_nuclei_results(self, json_output):
        """Process nuclei JSON output"""
        try:
            for line in json_output.strip().split('\n'):
                if line:
                    result = json.loads(line)
                    
                    # Extract vulnerability information
                    vuln = {
                        "type": "Nuclei Finding",
                        "severity": result.get('info', {}).get('severity', 'info').lower(),
                        "title": result.get('info', {}).get('name', 'Unknown'),
                        "description": result.get('info', {}).get('description', 'No description available'),
                        "recommendation": result.get('info', {}).get('remediation', 'No remediation available'),
                        "cwe": result.get('info', {}).get('cwe-id', []),
                        "cvss": result.get('info', {}).get('classification', {}).get('cvss-score'),
                        "template_id": result.get('template-id', ''),
                        "matched_at": result.get('matched-at', '')
                    }
                    
                    self.results['vulnerabilities'].append(vuln)
                    
        except Exception as e:
            logger.error(f"Error processing nuclei results: {str(e)}")
    
    async def run_comprehensive_scan(self, hostname: str, url: str):
        """Run comprehensive security checks"""
        try:
            logger.info(f"Running comprehensive scan on {hostname}")
            
            # Check for common security misconfigurations
            await self.check_security_headers(url)
            await self.check_directory_listing(url)
            await self.check_robots_txt(url)
            
        except Exception as e:
            logger.error(f"Comprehensive scan error: {str(e)}")
    
    async def check_security_headers(self, url: str):
        """Check for missing security headers with improved logic"""
        try:
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
                        self.results['vulnerabilities'].append({
                            "type": "Security Headers",
                            "severity": "medium",
                            "title": "Missing Security Headers",
                            "description": f"Missing security headers: {', '.join(security_issues[:3])}",
                            "recommendation": "Implement comprehensive security headers to protect against common attacks",
                            "cwe": "CWE-693",
                            "cvss": 3.7
                        })
                    elif len(security_issues) >= 2 and any("Strict-Transport-Security" in issue for issue in security_issues):
                        # Flag HSTS missing as a more serious issue for HTTPS sites
                        self.results['vulnerabilities'].append({
                            "type": "Security Headers",
                            "severity": "low",
                            "title": "Minor Security Headers Missing",
                            "description": f"Missing security headers: {', '.join(security_issues[:2])}",
                            "recommendation": "Consider adding missing security headers for enhanced protection",
                            "cwe": "CWE-693",
                            "cvss": 2.5
                        })
                        
        except Exception as e:
            logger.error(f"Security headers check failed: {str(e)}")
    
    async def check_directory_listing(self, url: str):
        """Check for directory listing vulnerabilities"""
        try:
            test_paths = ['/admin/', '/backup/', '/config/', '/logs/', '/tmp/']
            
            async with aiohttp.ClientSession() as session:
                for path in test_paths:
                    test_url = url.rstrip('/') + path
                    try:
                        async with session.get(test_url, timeout=5) as response:
                            if response.status == 200:
                                content = await response.text()
                                if 'Index of' in content or 'Directory listing' in content:
                                    self.results['vulnerabilities'].append({
                                        "type": "Directory Listing",
                                        "severity": "medium",
                                        "title": f"Directory Listing Enabled: {path}",
                                        "description": f"Directory listing is enabled at {test_url}",
                                        "recommendation": "Disable directory listing to prevent information disclosure",
                                        "cwe": "CWE-548",
                                        "cvss": 4.3
                                    })
                    except:
                        continue
                        
        except Exception as e:
            logger.error(f"Directory listing check failed: {str(e)}")
    
    async def check_robots_txt(self, url: str):
        """Check robots.txt for sensitive information"""
        try:
            robots_url = url.rstrip('/') + '/robots.txt'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(robots_url, timeout=5) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Check for sensitive paths in robots.txt
                        sensitive_patterns = ['admin', 'backup', 'config', 'logs', 'database', 'private']
                        found_sensitive = [pattern for pattern in sensitive_patterns if pattern in content.lower()]
                        
                        if found_sensitive:
                            self.results['vulnerabilities'].append({
                                "type": "Information Disclosure",
                                "severity": "low",
                                "title": "Sensitive Paths in robots.txt",
                                "description": f"robots.txt contains potentially sensitive paths: {', '.join(found_sensitive)}",
                                "recommendation": "Review robots.txt and remove sensitive path references",
                                "cwe": "CWE-200",
                                "cvss": 2.1
                            })
                            
        except Exception as e:
            logger.error(f"robots.txt check failed: {str(e)}")
    
    async def run_deep_scan(self, hostname: str, url: str):
        """Run deep security analysis"""
        try:
            logger.info(f"Running deep scan on {hostname}")
            
            # Subdomain enumeration
            await self.enumerate_subdomains(hostname)
            
            # Directory brute force
            await self.directory_brute_force(url)
            
        except Exception as e:
            logger.error(f"Deep scan error: {str(e)}")
    
    async def enumerate_subdomains(self, hostname: str):
        """Enumerate subdomains"""
        try:
            # Use nuclei for subdomain enumeration
            cmd = [
                "nuclei",
                "-t", "dns/",
                "-u", hostname,
                "-json",
                "-silent"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        result_data = json.loads(line)
                        # Process subdomain results
                        pass
                        
        except Exception as e:
            logger.error(f"Subdomain enumeration failed: {str(e)}")
    
    async def directory_brute_force(self, url: str):
        """Perform directory brute force"""
        try:
            # Use nuclei for directory brute force
            cmd = [
                "nuclei",
                "-t", "fuzzing/",
                "-u", url,
                "-json",
                "-silent"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        result_data = json.loads(line)
                        # Process directory brute force results
                        pass
                        
        except Exception as e:
            logger.error(f"Directory brute force failed: {str(e)}")
    
    def process_results(self, url: str, tier: str):
        """Process and format final results with deduplication, filtering, and prioritization"""
        # Use result processor if available
        if RESULT_PROCESSING_AVAILABLE:
            processed = result_processor.process_results(
                self.results['vulnerabilities'],
                self.results.get('ports', []),
                self.results.get('ssl_issues', [])
            )
            
            # Use processed vulnerabilities
            vulnerabilities = processed['vulnerabilities']
            ports = processed['ports']
            ssl_issues = processed['ssl_issues']
            stats = processed['statistics']
        else:
            # Fallback to basic processing
            vulnerabilities = self.results['vulnerabilities']
            ports = self.results.get('ports', [])
            ssl_issues = self.results.get('ssl_issues', [])
            stats = {}
        
        # Calculate severity breakdown
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        
        for vuln in vulnerabilities:
            severity = vuln.get('severity', 'info')
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        # Calculate security score
        total_vulns = len(vulnerabilities)
        critical_penalty = severity_counts['critical'] * 20
        high_penalty = severity_counts['high'] * 10
        medium_penalty = severity_counts['medium'] * 5
        low_penalty = severity_counts['low'] * 2
        
        security_score = max(0, 100 - critical_penalty - high_penalty - medium_penalty - low_penalty)
        
        # Get tools used based on tier
        tools_used = ["nuclei", "nmap", "sslscan"]
        if tier in ["level1", "level2"]:
            tools_used.extend(["subfinder", "ffuf", "crt.sh"])
        if tier == "level2":
            tools_used.extend(["nikto"])
        
        return {
            "summary": {
                "url": url,
                "tier": tier,
                "timestamp": datetime.utcnow().isoformat(),
                "vulnerabilities": vulnerabilities,
                "ports": ports,
                "ssl_issues": ssl_issues,
                "totalVulnerabilities": total_vulns,
                "severityBreakdown": severity_counts,
                "securityScore": security_score,
                "openPorts": len(ports),
                "sslIssuesCount": len(ssl_issues),
                "scanMetadata": {
                    "scanDuration": 0,  # Calculate actual duration
                    "toolsUsed": tools_used,
                    "scanTime": datetime.utcnow().isoformat(),
                    "processingStats": stats  # Include processing statistics
                }
            },
            "artifact_urls": []  # Would be populated with actual artifact URLs
        }
    
    async def send_callback(self, callback_url: str, results: dict):
        """Send results back to the backend"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    callback_url,
                    json=results,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        logger.info("Results sent successfully")
                    else:
                        logger.error(f"Callback failed: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to send callback: {str(e)}")
    
    async def send_error_callback(self, callback_url: str, error_message: str):
        """Send error back to the backend"""
        try:
            error_results = {
                "error": error_message,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    callback_url,
                    json=error_results,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        logger.info("Error sent successfully")
                    else:
                        logger.error(f"Error callback failed: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to send error callback: {str(e)}")
    
    async def run_owasp_tests(self, url: str):
        """Run OWASP Top 10 specific tests for bWAPP-like applications"""
        try:
            logger.info(f"Running OWASP Top 10 tests on {url}")
            
            # Test for common bWAPP vulnerabilities
            await self.test_sql_injection(url)
            await self.test_xss_vulnerabilities(url)
            await self.test_authentication_bypass(url)
            await self.test_file_upload_vulnerabilities(url)
            await self.test_directory_traversal(url)
            await self.test_csrf_vulnerabilities(url)
            
        except Exception as e:
            logger.error(f"OWASP tests error: {str(e)}")
    
    async def test_sql_injection(self, url: str):
        """Test for SQL injection vulnerabilities"""
        try:
            # Common SQL injection payloads
            sql_payloads = [
                "' OR '1'='1",
                "' UNION SELECT NULL--",
                "'; DROP TABLE users--",
                "' OR 1=1--",
                "admin'--",
                "' OR 'x'='x",
                "1' OR '1'='1' AND '1'='1",
                "1' UNION SELECT 1,2,3--",
                "' OR '1'='1' /*",
                "1' AND (SELECT * FROM (SELECT(SLEEP(5)))a)--"
            ]
            
            # Test common parameters
            test_params = ['id', 'user', 'login', 'search', 'q', 'name', 'email']
            
            for param in test_params:
                for payload in sql_payloads[:5]:  # Limit to first 5 payloads
                    test_url = f"{url}?{param}={payload}"
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(test_url, timeout=10) as response:
                                content = await response.text()
                                
                                # Check for SQL error patterns
                                sql_errors = [
                                    "mysql_fetch_array()", "ORA-01756", "Microsoft OLE DB Provider",
                                    "SQLServer JDBC Driver", "PostgreSQL query failed",
                                    "Warning: mysql_", "valid MySQL result", "MySqlClient.",
                                    "SQL syntax", "mysql_num_rows()", "mysql_query()",
                                    "mysql_fetch_assoc()", "mysql_fetch_row()", "mysql_fetch_array()"
                                ]
                                
                                if any(error in content.lower() for error in sql_errors):
                                    self.results['vulnerabilities'].append({
                                        "type": "SQL Injection",
                                        "severity": "high",
                                        "title": f"SQL Injection in parameter '{param}'",
                                        "description": f"SQL injection vulnerability detected in parameter '{param}' with payload: {payload}",
                                        "recommendation": "Use parameterized queries and input validation to prevent SQL injection",
                                        "cwe": "CWE-89",
                                        "cvss": 8.8,
                                        "parameter": param,
                                        "payload": payload
                                    })
                                    break  # Found vulnerability, move to next parameter
                    except Exception as e:
                        logger.debug(f"SQL injection test failed for {param}: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"SQL injection testing error: {str(e)}")
    
    async def test_xss_vulnerabilities(self, url: str):
        """Test for Cross-Site Scripting (XSS) vulnerabilities"""
        try:
            # Common XSS payloads
            xss_payloads = [
                "<script>alert('XSS')</script>",
                "<img src=x onerror=alert('XSS')>",
                "<svg onload=alert('XSS')>",
                "javascript:alert('XSS')",
                "<iframe src=javascript:alert('XSS')>",
                "<body onload=alert('XSS')>",
                "<input onfocus=alert('XSS') autofocus>",
                "<select onfocus=alert('XSS') autofocus>",
                "<textarea onfocus=alert('XSS') autofocus>",
                "<keygen onfocus=alert('XSS') autofocus>"
            ]
            
            # Test common parameters
            test_params = ['search', 'q', 'name', 'comment', 'message', 'input', 'data']
            
            for param in test_params:
                for payload in xss_payloads[:5]:  # Limit to first 5 payloads
                    test_url = f"{url}?{param}={payload}"
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(test_url, timeout=10) as response:
                                content = await response.text()
                                
                                # Check if payload is reflected without encoding
                                if payload in content and '<script>' in payload:
                                    self.results['vulnerabilities'].append({
                                        "type": "Cross-Site Scripting (XSS)",
                                        "severity": "medium",
                                        "title": f"Reflected XSS in parameter '{param}'",
                                        "description": f"XSS vulnerability detected in parameter '{param}' with payload: {payload}",
                                        "recommendation": "Implement proper input validation and output encoding to prevent XSS",
                                        "cwe": "CWE-79",
                                        "cvss": 6.1,
                                        "parameter": param,
                                        "payload": payload
                                    })
                                    break
                    except Exception as e:
                        logger.debug(f"XSS test failed for {param}: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"XSS testing error: {str(e)}")
    
    async def test_authentication_bypass(self, url: str):
        """Test for authentication bypass vulnerabilities"""
        try:
            # Common authentication bypass techniques
            bypass_payloads = [
                "admin",
                "administrator", 
                "admin'--",
                "admin' OR '1'='1'--",
                "' OR '1'='1'--",
                "admin' OR 1=1--",
                "' OR 1=1--",
                "admin'/*",
                "' OR 'x'='x'--",
                "admin' OR 'x'='x'--"
            ]
            
            # Test login endpoints
            login_endpoints = ['/login', '/admin', '/auth', '/signin', '/user/login']
            
            for endpoint in login_endpoints:
                login_url = f"{url.rstrip('/')}{endpoint}"
                for payload in bypass_payloads[:3]:  # Limit to first 3 payloads
                    try:
                        async with aiohttp.ClientSession() as session:
                            # Test with different parameter names
                            test_data = {
                                'username': payload,
                                'password': 'test',
                                'user': payload,
                                'login': payload,
                                'email': payload
                            }
                            
                            async with session.post(login_url, data=test_data, timeout=10) as response:
                                content = await response.text()
                                
                                # Check for successful login indicators
                                success_indicators = [
                                    "welcome", "dashboard", "logout", "profile", "admin panel",
                                    "success", "logged in", "authentication successful"
                                ]
                                
                                if any(indicator in content.lower() for indicator in success_indicators):
                                    self.results['vulnerabilities'].append({
                                        "type": "Authentication Bypass",
                                        "severity": "critical",
                                        "title": f"Authentication bypass at {endpoint}",
                                        "description": f"Authentication bypass vulnerability detected at {endpoint} with payload: {payload}",
                                        "recommendation": "Implement proper authentication mechanisms and input validation",
                                        "cwe": "CWE-287",
                                        "cvss": 9.8,
                                        "endpoint": endpoint,
                                        "payload": payload
                                    })
                                    break
                    except Exception as e:
                        logger.debug(f"Auth bypass test failed for {endpoint}: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"Authentication bypass testing error: {str(e)}")
    
    async def test_file_upload_vulnerabilities(self, url: str):
        """Test for file upload vulnerabilities"""
        try:
            # Test file upload endpoints
            upload_endpoints = ['/upload', '/file-upload', '/upload.php', '/upload.html']
            
            for endpoint in upload_endpoints:
                upload_url = f"{url.rstrip('/')}{endpoint}"
                try:
                    async with aiohttp.ClientSession() as session:
                        # Test if upload endpoint exists
                        async with session.get(upload_url, timeout=10) as response:
                            if response.status == 200:
                                self.results['vulnerabilities'].append({
                                    "type": "File Upload",
                                    "severity": "medium",
                                    "title": f"File upload endpoint found: {endpoint}",
                                    "description": f"File upload functionality detected at {endpoint}. Verify proper file type validation and restrictions.",
                                    "recommendation": "Implement proper file type validation, size limits, and store uploaded files outside web root",
                                    "cwe": "CWE-434",
                                    "cvss": 5.3,
                                    "endpoint": endpoint
                                })
                except Exception as e:
                    logger.debug(f"File upload test failed for {endpoint}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"File upload testing error: {str(e)}")
    
    async def test_directory_traversal(self, url: str):
        """Test for directory traversal vulnerabilities"""
        try:
            # Common directory traversal payloads
            traversal_payloads = [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
                "....//....//....//etc/passwd",
                "..%2F..%2F..%2Fetc%2Fpasswd",
                "..%252F..%252F..%252Fetc%252Fpasswd",
                "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd"
            ]
            
            # Test common parameters
            test_params = ['file', 'path', 'page', 'include', 'doc', 'template']
            
            for param in test_params:
                for payload in traversal_payloads[:3]:  # Limit to first 3 payloads
                    test_url = f"{url}?{param}={payload}"
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(test_url, timeout=10) as response:
                                content = await response.text()
                                
                                # Check for file content indicators
                                file_indicators = [
                                    "root:x:0:0:", "daemon:x:1:1:", "bin:x:2:2:",
                                    "127.0.0.1", "localhost", "::1",
                                    "Microsoft Windows", "Windows NT"
                                ]
                                
                                if any(indicator in content for indicator in file_indicators):
                                    self.results['vulnerabilities'].append({
                                        "type": "Directory Traversal",
                                        "severity": "high",
                                        "title": f"Directory traversal in parameter '{param}'",
                                        "description": f"Directory traversal vulnerability detected in parameter '{param}' with payload: {payload}",
                                        "recommendation": "Implement proper path validation and avoid direct file inclusion",
                                        "cwe": "CWE-22",
                                        "cvss": 7.5,
                                        "parameter": param,
                                        "payload": payload
                                    })
                                    break
                    except Exception as e:
                        logger.debug(f"Directory traversal test failed for {param}: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"Directory traversal testing error: {str(e)}")
    
    async def test_csrf_vulnerabilities(self, url: str):
        """Test for CSRF vulnerabilities"""
        try:
            # Test for forms without CSRF protection
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    content = await response.text()
                    
                    # Look for forms
                    if '<form' in content.lower():
                        # Check for CSRF tokens
                        csrf_indicators = [
                            'csrf_token', 'csrf-token', '_token', 'authenticity_token',
                            'csrfmiddlewaretoken', '__RequestVerificationToken'
                        ]
                        
                        has_csrf_protection = any(indicator in content.lower() for indicator in csrf_indicators)
                        
                        if not has_csrf_protection:
                            self.results['vulnerabilities'].append({
                                "type": "Cross-Site Request Forgery (CSRF)",
                                "severity": "medium",
                                "title": "Missing CSRF protection",
                                "description": "Forms detected without CSRF token protection",
                                "recommendation": "Implement CSRF tokens for all state-changing operations",
                                "cwe": "CWE-352",
                                "cvss": 6.1
                            })
                            
        except Exception as e:
            logger.error(f"CSRF testing error: {str(e)}")
    
    async def run_interactive_tests(self, url: str):
        """Run interactive tests for deep scanning"""
        try:
            logger.info(f"Running interactive tests on {url}")
            
            # Additional interactive tests for deep scanning
            await self.test_http_methods(url)
            await self.test_parameter_pollution(url)
            await self.test_session_management(url)
            
        except Exception as e:
            logger.error(f"Interactive tests error: {str(e)}")
    
    async def test_http_methods(self, url: str):
        """Test for dangerous HTTP methods"""
        try:
            dangerous_methods = ['PUT', 'DELETE', 'PATCH', 'TRACE', 'OPTIONS']
            
            async with aiohttp.ClientSession() as session:
                for method in dangerous_methods:
                    try:
                        async with session.request(method, url, timeout=10) as response:
                            if response.status not in [405, 501]:  # Method not allowed
                                self.results['vulnerabilities'].append({
                                    "type": "HTTP Method",
                                    "severity": "low",
                                    "title": f"Dangerous HTTP method allowed: {method}",
                                    "description": f"HTTP {method} method is allowed and may pose security risks",
                                    "recommendation": "Disable unnecessary HTTP methods and implement proper access controls",
                                    "cwe": "CWE-650",
                                    "cvss": 3.7,
                                    "method": method
                                })
                    except Exception as e:
                        logger.debug(f"HTTP method test failed for {method}: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"HTTP methods testing error: {str(e)}")
    
    async def test_parameter_pollution(self, url: str):
        """Test for HTTP parameter pollution"""
        try:
            # Test parameter pollution
            test_url = f"{url}?id=1&id=2&id=3"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(test_url, timeout=10) as response:
                    content = await response.text()
                    
                    # Check if multiple parameters are processed
                    if 'id=1' in content and 'id=2' in content:
                        self.results['vulnerabilities'].append({
                            "type": "HTTP Parameter Pollution",
                            "severity": "low",
                            "title": "HTTP Parameter Pollution detected",
                            "description": "Multiple parameters with same name are processed, which may lead to security issues",
                            "recommendation": "Implement proper parameter handling and validation",
                            "cwe": "CWE-235",
                            "cvss": 2.5
                        })
                        
        except Exception as e:
            logger.error(f"Parameter pollution testing error: {str(e)}")
    
    async def test_session_management(self, url: str):
        """Test for session management issues"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    headers = response.headers
                    
                    # Check for session cookie security
                    set_cookie = headers.get('Set-Cookie', '')
                    
                    security_issues = []
                    if 'HttpOnly' not in set_cookie:
                        security_issues.append("Missing HttpOnly flag")
                    if 'Secure' not in set_cookie and url.startswith('https://'):
                        security_issues.append("Missing Secure flag for HTTPS")
                    if 'SameSite' not in set_cookie:
                        security_issues.append("Missing SameSite attribute")
                    
                    if security_issues:
                        self.results['vulnerabilities'].append({
                            "type": "Session Management",
                            "severity": "medium",
                            "title": "Insecure session cookie configuration",
                            "description": f"Session cookie security issues: {', '.join(security_issues)}",
                            "recommendation": "Implement secure cookie attributes (HttpOnly, Secure, SameSite)",
                            "cwe": "CWE-614",
                            "cvss": 4.3
                        })
                        
        except Exception as e:
            logger.error(f"Session management testing error: {str(e)}")
    
    async def run_subdomain_enumeration(self, hostname: str):
        """Run subdomain enumeration using subfinder or amass"""
        try:
            logger.info(f"Running subdomain enumeration on {hostname}")
            
            # Try subfinder first
            try:
                cmd = ["subfinder", "-d", hostname, "-silent", "-json"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            subdomain = json.loads(line).get('host', '')
                            if subdomain:
                                self.results['vulnerabilities'].append({
                                    "type": "Subdomain Discovery",
                                    "severity": "info",
                                    "title": f"Subdomain found: {subdomain}",
                                    "description": f"Subdomain {subdomain} discovered",
                                    "recommendation": "Review discovered subdomains for security implications"
                                })
                    return
            except Exception as e:
                logger.warning(f"subfinder failed: {str(e)}")
            
            # Fallback to amass
            try:
                cmd = ["amass", "enum", "-passive", "-d", hostname, "-json"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            data = json.loads(line)
                            subdomain = data.get('name', '')
                            if subdomain:
                                self.results['vulnerabilities'].append({
                                    "type": "Subdomain Discovery",
                                    "severity": "info",
                                    "title": f"Subdomain found: {subdomain}",
                                    "description": f"Subdomain {subdomain} discovered",
                                    "recommendation": "Review discovered subdomains for security implications"
                                })
            except Exception as e:
                logger.warning(f"amass failed: {str(e)}")
                
        except Exception as e:
            logger.error(f"Subdomain enumeration failed: {str(e)}")
    
    async def run_certificate_transparency_lookup(self, hostname: str):
        """Run certificate transparency lookup"""
        try:
            logger.info(f"Running certificate transparency lookup for {hostname}")
            
            # Use crt.sh API
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://crt.sh/?q=%.{hostname}&output=json", timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        for cert in data:
                            name_value = cert.get('name_value', '')
                            if name_value and hostname in name_value:
                                self.results['vulnerabilities'].append({
                                    "type": "Certificate Transparency",
                                    "severity": "info",
                                    "title": f"Certificate found: {name_value}",
                                    "description": f"Certificate for {name_value} found in CT logs",
                                    "recommendation": "Review certificate transparency logs for security implications"
                                })
        except Exception as e:
            logger.error(f"Certificate transparency lookup failed: {str(e)}")
    
    async def run_directory_discovery(self, url: str, wordlist_size: str = "small"):
        """Run directory discovery using ffuf or gobuster"""
        try:
            logger.info(f"Running directory discovery on {url}")
            
            # Select wordlist based on size
            wordlist_path = f"/usr/share/wordlists/dirb/{wordlist_size}.txt"
            if not os.path.exists(wordlist_path):
                wordlist_path = "/usr/share/wordlists/dirb/common.txt"
            
            # Try ffuf first
            try:
                cmd = [
                    "ffuf",
                    "-u", f"{url}/FUZZ",
                    "-w", wordlist_path,
                    "-json",
                    "-o", "/tmp/ffuf_results.json"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    with open("/tmp/ffuf_results.json", 'r') as f:
                        data = json.load(f)
                        for item in data.get('results', []):
                            if item.get('status') == 200:
                                self.results['vulnerabilities'].append({
                                    "type": "Directory Discovery",
                                    "severity": "info",
                                    "title": f"Directory found: {item.get('input', {}).get('FUZZ', '')}",
                                    "description": f"Directory {item.get('input', {}).get('FUZZ', '')} is accessible",
                                    "recommendation": "Review discovered directories for sensitive information"
                                })
                    return
            except Exception as e:
                logger.warning(f"ffuf failed: {str(e)}")
            
            # Fallback to gobuster
            try:
                cmd = [
                    "gobuster",
                    "dir",
                    "-u", url,
                    "-w", wordlist_path,
                    "-o", "/tmp/gobuster_results.txt"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    with open("/tmp/gobuster_results.txt", 'r') as f:
                        for line in f:
                            if "Status: 200" in line:
                                directory = line.split()[0]
                                self.results['vulnerabilities'].append({
                                    "type": "Directory Discovery",
                                    "severity": "info",
                                    "title": f"Directory found: {directory}",
                                    "description": f"Directory {directory} is accessible",
                                    "recommendation": "Review discovered directories for sensitive information"
                                })
            except Exception as e:
                logger.warning(f"gobuster failed: {str(e)}")
                
        except Exception as e:
            logger.error(f"Directory discovery failed: {str(e)}")
    
    async def run_nmap_scan(self, hostname: str, args: list):
        """Run nmap scan with specified arguments"""
        try:
            logger.info(f"Running nmap scan on {hostname}")
            
            cmd = ["nmap"] + args + ["-oX", "/tmp/nmap_results.xml", hostname]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.process_nmap_results(result.stdout)
        except Exception as e:
            logger.error(f"nmap scan failed: {str(e)}")
    
    async def run_nikto_scan(self, url: str):
        """Run nikto HTTP server security checks"""
        try:
            logger.info(f"Running nikto scan on {url}")
            
            cmd = [
                "nikto",
                "-h", url,
                "-Format", "json",
                "-output", "/tmp/nikto_results.json"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                with open("/tmp/nikto_results.json", 'r') as f:
                    data = json.load(f)
                    for item in data.get('vulnerabilities', []):
                        self.results['vulnerabilities'].append({
                            "type": "Nikto Finding",
                            "severity": item.get('severity', 'medium').lower(),
                            "title": item.get('title', 'Unknown'),
                            "description": item.get('description', 'No description available'),
                            "recommendation": item.get('remediation', 'No recommendation available')
                        })
        except Exception as e:
            logger.error(f"nikto scan failed: {str(e)}")

async def main():
    """Main function to handle Cloud Run Job execution"""
    # Get parameters from environment variables (new naming convention)
    url = os.getenv('TARGET_URL')
    tier = os.getenv('SCAN_TIER', 'level0')
    callback_url = os.getenv('CALLBACK_URL')
    scan_id = os.getenv('SCAN_ID')
    gcs_bucket = os.getenv('GCS_BUCKET', 'thandev-reports')
    
    if not url or not callback_url or not scan_id:
        logger.error(f"Missing required parameters: TARGET_URL={url}, CALLBACK_URL={callback_url}, SCAN_ID={scan_id}")
        sys.exit(1)
    
    logger.info(f"Starting security scan: scan_id={scan_id}, url={url}, tier={tier}, gcs_bucket={gcs_bucket}")
    
    # Create scanner instance and run scan
    scanner = SecurityScanner()
    await scanner.run_scan_with_gcs(url, tier, callback_url, scan_id, gcs_bucket)

if __name__ == "__main__":
    asyncio.run(main())
