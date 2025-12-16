"""
Findings ingestor service
Handles parsing tool output and creating Finding records
"""
import logging
import json
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from urllib.parse import urlparse

from app.models.finding import Finding, Severity, FindingStatus
from app.models.scan import ScanJob

logger = logging.getLogger(__name__)


# Explicit tag-to-category mapping for Nuclei findings
# Maps Nuclei template tags to vulnerability categories
NUCLEI_TAG_TO_CATEGORY = {
    # XSS
    "xss": "xss",
    "cross-site-scripting": "xss",
    # SQL Injection
    "sqli": "sqli",
    "sql-injection": "sqli",
    "sql": "sqli",
    # SSRF
    "ssrf": "ssrf",
    "server-side-request-forgery": "ssrf",
    # SSTI
    "ssti": "ssti",
    "server-side-template-injection": "ssti",
    "template-injection": "ssti",
    # XXE
    "xxe": "xxe",
    "xml-external-entity": "xxe",
    # Directory Traversal / File Inclusion
    "path-traversal": "dir_traversal",
    "directory-traversal": "dir_traversal",
    "lfi": "dir_traversal",
    "rfi": "dir_traversal",
    "local-file-inclusion": "dir_traversal",
    "remote-file-inclusion": "dir_traversal",
    "file-inclusion": "dir_traversal",
    # CORS
    "cors-misconfig": "cors",
    "cors": "cors",
    "cross-origin-resource-sharing": "cors",
    # CSRF
    "csrf": "csrf",
    "cross-site-request-forgery": "csrf",
    # Command Injection / RCE
    "cmd-injection": "cmdi",
    "command-injection": "cmdi",
    "cmdi": "cmdi",
    "rce": "cmdi",
    "remote-code-execution": "cmdi",
    "code-execution": "cmdi",
    "os-commanding": "cmdi",
    # IDOR
    "idor": "idor",
    "insecure-direct-object-reference": "idor",
    "authorization": "idor",
}


def categorize_nuclei_finding(template_tags: list[str]) -> list[str]:
    """
    Categorize a Nuclei finding based on its template tags using explicit mapping.
    
    Returns lowercase category strings for attacker-relevant findings.
    
    Args:
        template_tags: List of template tags from Nuclei finding (e.g., ["xss", "sqli", "cve"])
        
    Returns:
        List of unique lowercase category strings (e.g., ["xss", "sqli"])
        
    Example:
        >>> categorize_nuclei_finding(["xss", "sqli", "cve"])
        ["xss", "sqli"]
        >>> categorize_nuclei_finding(["lfi", "rfi"])
        ["dir_traversal"]
    """
    if not template_tags:
        return []
    
    # Normalize tags to lowercase
    tags_lower = [tag.lower().strip() for tag in template_tags if tag]
    
    categories = []
    
    # Map tags to categories using explicit dictionary
    for tag in tags_lower:
        category = NUCLEI_TAG_TO_CATEGORY.get(tag)
        if category and category not in categories:
            categories.append(category)
    
    return categories


def ingest_nuclei_findings(
    db: Session,
    scan_job_id: str,
    nuclei_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Given a scan_job_id and a list of nuclei JSON objects, create Finding rows.
    
    This function is idempotent: it deletes existing findings for this scan_job
    before inserting new ones, so it can be safely called multiple times.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nuclei_results: List of Nuclei JSON objects (one per finding)
        
    Returns:
        List of created Finding objects
    """
    # Delete existing findings for this scan job AND tool (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "nuclei"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing nuclei findings for scan {scan_job_id}")
    
    findings = []
    
    for nuclei_data in nuclei_results:
        try:
            # Extract severity
            severity_str = nuclei_data.get("info", {}).get("severity", "info")
            if isinstance(severity_str, str):
                severity_str = severity_str.lower()
            else:
                severity_str = "info"
            
            # Normalize severity to allowed enum values
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            # Extract title
            title = (
                nuclei_data.get("info", {}).get("name") or
                nuclei_data.get("template-id") or
                nuclei_data.get("matcher-name") or
                "Nuclei Finding"
            )
            
            # Extract description
            description = nuclei_data.get("info", {}).get("description", "")
            matched_at = nuclei_data.get("matched-at", "")
            if matched_at and description:
                description = f"{description}\n\nMatched at: {matched_at}"
            elif matched_at:
                description = f"Matched at: {matched_at}"
            
            # Extract CVE ID
            cve_id = None
            # Try multiple possible locations for CVE
            if "cve" in nuclei_data:
                cve_id = nuclei_data["cve"]
            elif "info" in nuclei_data and "classification" in nuclei_data["info"]:
                cve_list = nuclei_data["info"]["classification"].get("cve-id", [])
                if cve_list and isinstance(cve_list, list) and len(cve_list) > 0:
                    cve_id = cve_list[0]
                elif isinstance(nuclei_data["info"]["classification"].get("cve-id"), str):
                    cve_id = nuclei_data["info"]["classification"]["cve-id"]
            
            # Extract CWE ID
            cwe_id = None
            if "cwe-id" in nuclei_data:
                cwe_id = nuclei_data["cwe-id"]
            elif "info" in nuclei_data and "classification" in nuclei_data["info"]:
                cwe_list = nuclei_data["info"]["classification"].get("cwe-id", [])
                if cwe_list and isinstance(cwe_list, list) and len(cwe_list) > 0:
                    cwe_id = cwe_list[0]
                elif isinstance(nuclei_data["info"]["classification"].get("cwe-id"), str):
                    cwe_id = nuclei_data["info"]["classification"]["cwe-id"]
            
            # Extract URL
            url = matched_at or nuclei_data.get("host", "")
            
            # Extract template tags for categorization
            template_tags = []
            if "info" in nuclei_data and "tags" in nuclei_data["info"]:
                tags = nuclei_data["info"]["tags"]
                if isinstance(tags, list):
                    template_tags = tags
                elif isinstance(tags, str):
                    # Tags might be comma-separated string
                    template_tags = [t.strip() for t in tags.split(",")]
            
            # Categorize finding based on tags
            categories = categorize_nuclei_finding(template_tags)
            
            # Store raw JSON as string, but add categories to the dict first
            raw_data_dict = nuclei_data.copy() if isinstance(nuclei_data, dict) else {}
            if categories:
                raw_data_dict["categories"] = categories
            
            raw_data = json.dumps(raw_data_dict) if isinstance(raw_data_dict, dict) else json.dumps(nuclei_data) if isinstance(nuclei_data, dict) else str(nuclei_data)
            
            # Create Finding
            finding = Finding(
                scan_job_id=scan_job_id,
                title=title[:500],  # Ensure title fits in column
                description=description,
                severity=severity,
                cve_id=cve_id[:50] if cve_id else None,  # Ensure CVE ID fits
                cwe_id=cwe_id[:50] if cwe_id else None,  # Ensure CWE ID fits
                url=url[:2048] if url else None,  # Ensure URL fits
                tool_name="nuclei",
                raw_data=raw_data,
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nuclei finding: {e}", exc_info=True)
            logger.debug(f"Problematic Nuclei data: {nuclei_data}")
            continue
    
    # Commit all findings at once
    try:
        db.commit()
        logger.info(
            "Ingested %d nuclei findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def parse_nuclei_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nuclei JSONL output file (one JSON object per line) into a list of dicts.
    
    This function is robust to non-JSON lines (like ASCII tables, logs, etc.)
    and will skip them gracefully. Handles empty files and zero-byte files.
    
    Args:
        path: Path to the Nuclei output file (JSONL format)
        
    Returns:
        List of parsed Nuclei JSON objects (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    # Check if file is zero bytes
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                
                # Skip obvious non-JSON lines (tables, logs, etc.)
                # JSON objects/arrays start with { or [
                if not (line.startswith("{") or line.startswith("[")):
                    logger.debug(
                        "Skipping non-JSON line %d in nuclei output %s: %r",
                        line_no, path, line[:80]
                    )
                    continue
                
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        findings.append(obj)
                    else:
                        logger.debug("Skipping non-dict JSON on line %d in %s", line_no, path)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON line %d in nuclei output %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
                except Exception as e:
                    logger.warning(
                        "Unexpected error parsing line %d in %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d nuclei findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse Nuclei output file %s: %s", path, e, exc_info=True)
        return []


def parse_nmap_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nmap XML output file into a list of finding dicts.
    
    Each open port becomes a finding. Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the Nmap XML output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Extract host information
        for host in root.findall("host"):
            host_status = host.find("status")
            if host_status is None or host_status.get("state") != "up":
                continue
            
            # Get host address
            address_elem = host.find("address")
            host_ip = address_elem.get("addr") if address_elem is not None else "unknown"
            
            # Get hostname
            hostnames_elem = host.find("hostnames")
            hostname = host_ip
            if hostnames_elem is not None:
                hostname_elem = hostnames_elem.find("hostname")
                if hostname_elem is not None:
                    hostname = hostname_elem.get("name", host_ip)
            
            # Process ports
            ports_elem = host.find("ports")
            if ports_elem is None:
                continue
            
            for port_elem in ports_elem.findall("port"):
                port_state = port_elem.find("state")
                if port_state is None or port_state.get("state") != "open":
                    continue
                
                port_num = port_elem.get("portid")
                protocol = port_elem.get("protocol", "tcp")
                
                # Get service info
                service_elem = port_elem.find("service")
                service_name = service_elem.get("name", "unknown") if service_elem is not None else "unknown"
                service_product = service_elem.get("product", "") if service_elem is not None else ""
                service_version = service_elem.get("version", "") if service_elem is not None else ""
                
                # Build description
                description_parts = [
                    f"Host: {hostname} ({host_ip})",
                    f"Port: {port_num}/{protocol}",
                    f"Service: {service_name}",
                ]
                if service_product:
                    description_parts.append(f"Product: {service_product}")
                if service_version:
                    description_parts.append(f"Version: {service_version}")
                
                description = "\n".join(description_parts)
                
                # Determine severity based on port/service
                severity = "info"
                if port_num in ["22", "3389", "5900"]:  # SSH, RDP, VNC
                    severity = "medium"
                elif port_num in ["3306", "5432", "1433"]:  # MySQL, PostgreSQL, MSSQL
                    severity = "medium"
                elif port_num in ["21", "23", "25"]:  # FTP, Telnet, SMTP
                    severity = "low"
                elif port_num in ["80", "443", "8080", "8443"]:  # HTTP/HTTPS
                    severity = "info"
                
                # Build title
                title = f"Open port {port_num}/{protocol} ({service_name}) on {hostname}"
                
                # Build URL
                url = f"{hostname}:{port_num}"
                if port_num in ["80", "8080"]:
                    url = f"http://{hostname}:{port_num}"
                elif port_num in ["443", "8443"]:
                    url = f"https://{hostname}:{port_num}"
                
                # Store raw XML for this port as JSON
                raw_data = json.dumps({
                    "host": hostname,
                    "ip": host_ip,
                    "port": port_num,
                    "protocol": protocol,
                    "service": service_name,
                    "product": service_product,
                    "version": service_version,
                })
                
                findings.append({
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "cve_id": None,
                    "cwe_id": None,
                    "url": url,
                    "tool_name": "nmap",
                    "raw_data": raw_data,
                })
        
        logger.info("Parsed %d nmap findings from file for scan %s", len(findings), path)
        return findings
        
    except ET.ParseError as e:
        logger.warning("Failed to parse Nmap XML file %s: %s", path, e)
        return []
    except Exception as e:
        logger.error("Failed to read/parse Nmap output file %s: %s", path, e, exc_info=True)
        return []


def parse_sslscan_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse sslscan output file (JSON or text format) into a list of finding dicts.
    
    Handles both JSON output (when --json flag is used) and plain text output.
    Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the sslscan output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        # Try to parse as JSON first
        try:
            # Remove ANSI color codes if present
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            content_clean = ansi_escape.sub('', content)
            
            # Try to find JSON object/array
            json_start = content_clean.find('{')
            json_end = content_clean.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content_clean[json_start:json_end]
                data = json.loads(json_str)
                
                # Handle JSON format
                if isinstance(data, dict):
                    # Single JSON object
                    findings.extend(_parse_sslscan_json_object(data))
                elif isinstance(data, list):
                    # Array of JSON objects
                    for item in data:
                        if isinstance(item, dict):
                            findings.extend(_parse_sslscan_json_object(item))
        except (json.JSONDecodeError, ValueError):
            # Fall back to text parsing
            findings.extend(_parse_sslscan_text(content))
        
        logger.info("Parsed %d sslscan findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse sslscan output file %s: %s", path, e, exc_info=True)
        return []


def _parse_sslscan_json_object(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse a single sslscan JSON object into finding dicts"""
    findings = []
    
    host = data.get("host", "unknown")
    port = data.get("port", 443)
    target = f"{host}:{port}"
    
    # Check for weak protocols
    sslv2 = data.get("ssl_version", {}).get("SSLv2", {}).get("status", "").lower()
    sslv3 = data.get("ssl_version", {}).get("SSLv3", {}).get("status", "").lower()
    tls10 = data.get("ssl_version", {}).get("TLSv1.0", {}).get("status", "").lower()
    tls11 = data.get("ssl_version", {}).get("TLSv1.1", {}).get("status", "").lower()
    
    if sslv2 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if sslv3 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls10 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls11 == "enabled":
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    # Check for weak ciphers
    ciphers = data.get("cipher_suites", [])
    weak_ciphers = []
    for cipher in ciphers:
        cipher_name = cipher.get("cipher", "")
        key_length = cipher.get("key_length", 0)
        if key_length < 128 or "RC4" in cipher_name or "DES" in cipher_name or "MD5" in cipher_name:
            weak_ciphers.append(cipher_name)
    
    if weak_ciphers:
        findings.append({
            "severity": "medium",
            "title": f"Weak cipher suites detected on {target}",
            "description": f"Weak cipher suites found on {target}: {', '.join(weak_ciphers[:5])}",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    return findings


def _parse_sslscan_text(content: str) -> List[Dict[str, Any]]:
    """Parse sslscan plain text output into finding dicts"""
    findings = []
    
    # Remove ANSI color codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    content_clean = ansi_escape.sub('', content)
    
    # Extract host and port from content
    host_match = re.search(r'Testing SSL server\s+(\S+)\s+on port\s+(\d+)', content_clean)
    if not host_match:
        # Try alternative pattern
        host_match = re.search(r'Connected to\s+([\d.]+)', content_clean)
        port_match = re.search(r'port\s+(\d+)', content_clean)
        host = host_match.group(1) if host_match else "unknown"
        port = int(port_match.group(1)) if port_match else 443
    else:
        host = host_match.group(1)
        port = int(host_match.group(2))
    
    target = f"{host}:{port}"
    
    # Check for weak protocols in text
    if re.search(r'SSLv2\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],  # Store first 1000 chars
        })
    
    if re.search(r'SSLv3\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.0\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.1\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    return findings


def ingest_nmap_findings(
    db: Session,
    scan_job_id: str,
    nmap_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Ingest Nmap findings into the database.
    
    Per-tool idempotency: deletes existing nmap findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nmap_results: List of finding dicts from parse_nmap_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing nmap findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "nmap"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing nmap findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in nmap_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "Nmap Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="nmap",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nmap finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        logger.info(
            "Ingested %d nmap findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit nmap findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_sslscan_findings(
    db: Session,
    scan_job_id: str,
    sslscan_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Ingest sslscan findings into the database.
    
    Per-tool idempotency: deletes existing sslscan findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        sslscan_results: List of finding dicts from parse_sslscan_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing sslscan findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "sslscan"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing sslscan findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in sslscan_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "SSL/TLS Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="sslscan",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse sslscan finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        logger.info(
            "Ingested %d sslscan findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit sslscan findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_http_header_findings(
    db: Session,
    scan_job_id: str,
    header_findings: List[Finding],
) -> List[Finding]:
    """
    Ingest HTTP header findings into the database.
    
    Per-tool idempotency: deletes existing http_headers findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        header_findings: List of Finding objects for missing headers
        
    Returns:
        List of created Finding objects
    """
    # Delete existing http_headers findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "http_headers"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing http_headers findings for scan {scan_job_id}")
    
    # Add all findings to session
    for finding in header_findings:
        db.add(finding)
    
    # Commit all findings at once
    try:
        db.commit()
        logger.info(
            "Ingested %d http_headers findings into DB for scan %s",
            len(header_findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit http_headers findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return header_findings


def parse_httpx_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse httpx JSONL output file into a list of finding dicts.
    
    Each line is a JSON object representing an HTTP response.
    Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the httpx JSONL output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("httpx output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("httpx output file is empty for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Extract key fields from httpx JSON output
                    url = data.get("url", "")
                    status_code = data.get("status_code", 0)
                    title = data.get("title", "")
                    tech = data.get("tech", [])
                    tls_version = data.get("tls_version", "")
                    
                    # Build title
                    title_parts = [f"HTTP surface: {url}"]
                    if status_code:
                        title_parts.append(f"[{status_code}]")
                    if title:
                        title_parts.append(title)
                    elif tech:
                        title_parts.append(f"Tech: {', '.join(tech[:3])}")
                    
                    finding_title = " ".join(title_parts)
                    
                    # Build description
                    desc_parts = []
                    if status_code:
                        desc_parts.append(f"HTTP Status: {status_code}")
                    if title:
                        desc_parts.append(f"Page Title: {title}")
                    if tech:
                        desc_parts.append(f"Technologies: {', '.join(tech)}")
                    if tls_version:
                        desc_parts.append(f"TLS Version: {tls_version}")
                    
                    description = "\n".join(desc_parts) if desc_parts else f"HTTP surface discovered at {url}"
                    
                    findings.append({
                        "title": finding_title[:500],
                        "description": description,
                        "severity": "info",
                        "url": url[:2048] if url else None,
                        "raw_data": json.dumps(data),
                    })
                    
                except json.JSONDecodeError:
                    logger.debug("Skipping non-JSON line %d in httpx output %s", line_no, path)
                    continue
                except Exception as e:
                    logger.warning(
                        "Unexpected error parsing line %d in %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d httpx findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse httpx output file %s: %s", path, e, exc_info=True)
        return []


def ingest_httpx_findings(
    db: Session,
    scan_job_id: str,
    httpx_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Ingest httpx findings into the database with aggregation to reduce noise.
    
    Implements aggregation to reduce noise:
    - Prioritizes URLs with interesting keywords (admin, login, debug, etc.)
    - Limits to max 200 individual findings per scan
    - Creates a summary finding for remaining endpoints
    
    Per-tool idempotency: deletes existing httpx findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        httpx_results: List of finding dicts from parse_httpx_output
        
    Returns:
        List of created Finding objects
    """
    # Early return if no results
    if not httpx_results:
        return []
    
    # Delete existing httpx findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "httpx"
    ).delete(synchronize_session=False)
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing httpx findings for scan {scan_job_id}")
    
    # Aggregation parameters
    MAX_INDIVIDUAL = 200
    
    # Interesting keywords to prioritize
    interesting_keywords = [
        "admin", "login", "auth", "debug", "backup", "test",
        "staging", "dev", "api", ".git", ".env", ".bak",
        "config", "console", "manage", "dashboard",
    ]
    
    def is_interesting(url: str) -> bool:
        """Check if URL contains interesting keywords"""
        if not url:
            return False
        url_lower = url.lower()
        return any(keyword in url_lower for keyword in interesting_keywords)
    
    # Separate prioritized and others
    prioritized = []
    others = []
    
    for finding_data in httpx_results:
        url = finding_data.get("url", "")
        if is_interesting(url):
            prioritized.append(finding_data)
        else:
            others.append(finding_data)
    
    # Sort prioritized by URL for consistency
    prioritized.sort(key=lambda x: x.get("url", ""))
    
    # Take up to MAX_INDIVIDUAL total (prioritize interesting)
    findings_to_create = prioritized[:MAX_INDIVIDUAL]
    remaining_slots = MAX_INDIVIDUAL - len(findings_to_create)
    if remaining_slots > 0:
        findings_to_create.extend(others[:remaining_slots])
        others = others[remaining_slots:]
    
    findings = []
    
    # Create individual findings for prioritized endpoints
    for finding_data in findings_to_create:
        try:
            url = finding_data.get("url", "")
            status_code = finding_data.get("status_code", 0)
            
            # Parse raw_data to extract additional info
            raw_data_str = finding_data.get("raw_data", "{}")
            try:
                raw_data_dict = json.loads(raw_data_str) if isinstance(raw_data_str, str) else raw_data_str
            except:
                raw_data_dict = {}
            if not isinstance(raw_data_dict, dict):
                raw_data_dict = {}
            
            # Build title
            title = f"HTTP surface: {url}"
            if status_code:
                title += f" (HTTP {status_code})"
            title = title[:500]
            
            # Build description from raw_data
            description_parts = []
            if status_code:
                description_parts.append(f"HTTP Status: {status_code}")
            
            title_page = raw_data_dict.get("title", "")
            if title_page:
                description_parts.append(f"Page Title: {title_page}")
            
            tech = raw_data_dict.get("tech", [])
            if tech:
                if isinstance(tech, list):
                    tech_str = ", ".join(tech[:5])  # Limit to 5 technologies
                else:
                    tech_str = str(tech)
                description_parts.append(f"Technologies: {tech_str}")
            
            tls_version = raw_data_dict.get("tls_version", "")
            if tls_version:
                description_parts.append(f"TLS Version: {tls_version}")
            
            description = "\n".join(description_parts) if description_parts else f"HTTP surface discovered at {url}"
            
            # Ensure categories in raw_data
            raw_data_dict["categories"] = ["HTTP Surface"]
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=title,
                description=description,
                severity=Severity.INFO,
                url=url[:2048] if url else None,
                tool_name="httpx",
                raw_data=json.dumps(raw_data_dict),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse httpx finding: {e}", exc_info=True)
            continue
    
    # Create summary finding if there are remaining endpoints
    if others:
        try:
            # Get scan job to extract target URL/domain
            scan_job = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
            root_domain = ""
            if scan_job and scan_job.project:
                target_url = getattr(scan_job.project, "target_url", "")
                if target_url:
                    parsed = urlparse(target_url)
                    root_domain = parsed.netloc or parsed.path.split("/")[0] if parsed.path else ""
            
            if not root_domain and httpx_results:
                # Fallback: extract from first URL
                first_url = httpx_results[0].get("url", "")
                if first_url:
                    parsed = urlparse(first_url)
                    root_domain = parsed.netloc or ""
            
            # Count by status code
            status_counts = {}
            for finding_data in others:
                raw_data_str = finding_data.get("raw_data", "{}")
                try:
                    raw_data_dict = json.loads(raw_data_str) if isinstance(raw_data_str, str) else raw_data_str
                except:
                    raw_data_dict = {}
                status = raw_data_dict.get("status_code", finding_data.get("status_code", "unknown"))
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Build summary description
            description_lines = [
                f"HTTP surface discovery identified {len(httpx_results)} total endpoints on {root_domain or 'target'}.",
                f"Of these, {len(findings_to_create)} are shown individually (prioritized by interesting keywords).",
                f"The remaining {len(others)} endpoints are summarized below.",
                "",
                "Status code breakdown for summarized endpoints:"
            ]
            for status, count in sorted(status_counts.items()):
                description_lines.append(f"  - HTTP {status}: {count} endpoints")
            
            description_lines.extend([
                "",
                "These endpoints were discovered but not individually reported to reduce noise.",
                "Review the full httpx output for complete endpoint list."
            ])
            
            raw_data_summary = {
                "summary": True,
                "total_endpoints": len(httpx_results),
                "summarized_endpoints": len(others),
                "status_breakdown": status_counts,
                "categories": ["HTTP Surface"]
            }
            
            summary_title = f"HTTP surface summary: {root_domain or 'target'} ({len(others)} additional endpoints)"
            if len(summary_title) > 500:
                summary_title = summary_title[:497] + "..."
            
            summary_finding = Finding(
                scan_job_id=scan_job_id,
                title=summary_title,
                description="\n".join(description_lines),
                severity=Severity.INFO,
                url=None,
                tool_name="httpx",
                raw_data=json.dumps(raw_data_summary),
                status=FindingStatus.OPEN,
            )
            
            findings.append(summary_finding)
            db.add(summary_finding)
            
        except Exception as e:
            logger.warning(f"Failed to create httpx summary finding: {e}", exc_info=True)
    
    try:
        db.commit()
        logger.info(
            "Ingested %d httpx findings into DB for scan %s (%d individual + %d summary)",
            len(findings), scan_job_id, len(findings_to_create), 1 if others else 0
        )
    except Exception as e:
        logger.error("Failed to commit httpx findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def parse_ffuf_output(path: Path, baseline_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Parse ffuf JSON output file into a list of finding dicts.
    
    ffuf with -json produces a JSON stream where each line contains a "result" object
    for discovered paths. We parse line by line and extract relevant information.
    
    PR-4C: Filters out 404/wildcard responses using baseline signature.
    
    Args:
        path: Path to the ffuf JSON output file
        baseline_filter: Optional baseline signature dict with:
            - status_code: Baseline status code
            - content_length: Baseline content length
            - word_count: Baseline word count
            - line_count: Baseline line count
            - content_hash: Baseline content hash (first 1000 chars)
        
    Returns:
        List of finding dicts (empty list if file is empty/missing or parsing fails)
    """
    if not path.exists():
        logger.info("ffuf output file is missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("ffuf output file is empty for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    # ffuf JSON output contains a "result" key with the actual finding
                    result = None
                    if "result" in data:
                        result = data["result"]
                    # Some ffuf versions may output the result directly
                    elif "url" in data or "status" in data:
                        result = data
                    
                    if result:
                        # PR-4C: Filter by baseline if provided
                        if baseline_filter:
                            # Check status code
                            result_status = result.get("status", result.get("StatusCode", 0))
                            if result_status == 404:
                                continue  # Skip 404s
                            
                            # Check if matches baseline signature
                            result_size = result.get("length", result.get("ContentLength", 0))
                            baseline_size = baseline_filter.get("content_length", 0)
                            
                            if baseline_size > 0:
                                tolerance = max(10, int(baseline_size * 0.05))
                                if abs(result_size - baseline_size) <= tolerance:
                                    # Size matches baseline, likely a wildcard 404
                                    # Also check word/line count if available
                                    result_words = result.get("words", 0)
                                    baseline_words = baseline_filter.get("word_count", 0)
                                    if baseline_words > 0 and abs(result_words - baseline_words) <= 2:
                                        logger.debug(f"Filtered ffuf result matching baseline: {result.get('url', 'unknown')}")
                                        continue
                        
                        findings.append(result)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON line %d in ffuf output %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d ffuf results from file %s", len(findings), path)
        return findings
    except Exception as e:
        logger.error("Failed to read/parse ffuf output file %s: %s", path, e, exc_info=True)
        return []


def ingest_ffuf_findings(
    db: Session,
    scan_job_id: str,
    ffuf_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Ingest ffuf findings into the database with aggregation to reduce noise.
    
    Implements aggregation to reduce noise:
    - Prioritizes URLs with interesting keywords and important status codes
    - Limits to max 300 individual findings per scan
    - Creates a summary finding for remaining endpoints
    
    Per-tool idempotency: deletes existing ffuf findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        ffuf_results: List of raw ffuf result objects
        
    Returns:
        List of created Finding objects
    """
    # Early return if no results
    if not ffuf_results:
        return []
    
    # Delete existing ffuf findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "ffuf"
    ).delete(synchronize_session=False)
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing ffuf findings for scan {scan_job_id}")
    
    # Aggregation parameters
    MAX_INDIVIDUAL = 300
    
    # Interesting keywords to prioritize (reuse from httpx plus file patterns)
    interesting_keywords = [
        "admin", "login", "auth", "debug", "backup", "test",
        "staging", "dev", "api", ".git", ".env", ".bak",
        "config", "console", "manage", "dashboard",
        ".php", ".jsp", ".aspx", ".old", ".zip",
    ]
    
    # Important status codes for ffuf
    interesting_status = {200, 204, 301, 302, 307, 401, 403, 500}
    
    def is_interesting(url: str, status_code: int) -> bool:
        """Check if URL/status should be prioritized"""
        if not url:
            return False
        url_lower = url.lower()
        has_keyword = any(keyword in url_lower for keyword in interesting_keywords)
        has_important_status = status_code in interesting_status
        return has_keyword or has_important_status
    
    # Separate prioritized and others
    prioritized = []
    others = []
    
    for ffuf_data in ffuf_results:
        url = ffuf_data.get("url", "") or ffuf_data.get("url_full", "")
        status_code = ffuf_data.get("status", 0)
        if is_interesting(url, status_code):
            prioritized.append(ffuf_data)
        else:
            others.append(ffuf_data)
    
    # Sort prioritized by status code (200/204 first) then URL
    prioritized.sort(key=lambda x: (
        0 if x.get("status", 0) in [200, 204] else 1,
        x.get("url", "") or x.get("url_full", "")
    ))
    
    # Take up to MAX_INDIVIDUAL total (prioritize interesting)
    findings_to_create = prioritized[:MAX_INDIVIDUAL]
    remaining_slots = MAX_INDIVIDUAL - len(findings_to_create)
    if remaining_slots > 0:
        findings_to_create.extend(others[:remaining_slots])
        others = others[remaining_slots:]
    
    findings = []
    
    # Create individual findings for prioritized endpoints
    for ffuf_data in findings_to_create:
        try:
            # Extract URL and status code
            url = ffuf_data.get("url", "") or ffuf_data.get("url_full", "")
            url_full = ffuf_data.get("url_full", url)
            status_code = ffuf_data.get("status", 0)
            
            # Determine severity based on status code
            if status_code in [200, 204]:
                severity = Severity.MEDIUM
            elif status_code in [301, 302, 307, 401, 403, 500]:
                severity = Severity.LOW
            else:
                severity = Severity.LOW  # Default to LOW for other codes
            
            # Extract additional fields
            host = ffuf_data.get("host", "")
            length = ffuf_data.get("length", ffuf_data.get("size", 0))
            redirect_location = ffuf_data.get("redirectlocation", "")
            words = ffuf_data.get("words", 0)
            lines = ffuf_data.get("lines", 0)
            
            # Build title
            title = f"Discovered endpoint: {url_full or url} (HTTP {status_code})"
            if len(title) > 500:
                title = title[:497] + "..."
            
            # Build description
            description_lines = []
            
            if host:
                description_lines.append(
                    f"ffuf discovered a reachable path at `{url_full or url}` on `{host}`."
                )
            else:
                description_lines.append(
                    f"ffuf discovered a reachable path at `{url_full or url}`."
                )
            
            description_lines.append(f"HTTP status: {status_code}")
            
            if length > 0:
                description_lines.append(f"Response size: {length} bytes")
            
            if redirect_location:
                description_lines.append(f"Redirects to: {redirect_location}")
            
            if words > 0 or lines > 0:
                content_info = []
                if words > 0:
                    content_info.append(f"{words} words")
                if lines > 0:
                    content_info.append(f"{lines} lines")
                if content_info:
                    description_lines.append(f"Content analysis: {', '.join(content_info)}")
            
            # Contextual explanation
            if status_code in [200, 204]:
                description_lines.append(
                    "This endpoint was found via wordlist-based content discovery and may reveal "
                    "hidden functionality, admin panels, or debug paths."
                )
            elif status_code in [301, 302, 307]:
                description_lines.append(
                    "This endpoint redirects to another location. The redirect may reveal "
                    "internal paths or authentication flows."
                )
            elif status_code in [401, 403]:
                description_lines.append(
                    "This endpoint requires authentication or is protected. The presence of "
                    "this path may indicate hidden functionality or administrative interfaces."
                )
            elif status_code == 500:
                description_lines.append(
                    "This endpoint returned a server error, which may indicate misconfiguration "
                    "or reveal internal application structure."
                )
            else:
                description_lines.append(
                    "This endpoint was found via wordlist-based content discovery and may reveal "
                    "hidden functionality or additional attack surface."
                )
            
            description = "\n".join(description_lines)
            
            # Prepare raw_data with Content Discovery category
            raw_data_dict = ffuf_data.copy() if isinstance(ffuf_data, dict) else {}
            raw_data_dict["categories"] = ["Content Discovery"]
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=title,
                description=description,
                severity=severity,
                url=url[:2048] if url else None,
                tool_name="ffuf",
                raw_data=json.dumps(raw_data_dict),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse ffuf finding: {e}", exc_info=True)
            continue
    
    # Create summary finding if there are remaining endpoints
    if others:
        try:
            # Get scan job to extract target URL/domain
            scan_job = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
            root_domain = ""
            if scan_job and scan_job.project:
                target_url = getattr(scan_job.project, "target_url", "")
                if target_url:
                    parsed = urlparse(target_url)
                    root_domain = parsed.netloc or parsed.path.split("/")[0] if parsed.path else ""
            
            if not root_domain and ffuf_results:
                # Fallback: extract from first URL
                first_url = ffuf_results[0].get("url", "") or ffuf_results[0].get("url_full", "")
                if first_url:
                    parsed = urlparse(first_url)
                    root_domain = parsed.netloc or ""
            
            # Count by status code
            status_counts = {}
            for ffuf_data in others:
                status = ffuf_data.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Build summary description
            description_lines = [
                f"Content discovery identified {len(ffuf_results)} total endpoints on {root_domain or 'target'}.",
                f"Of these, {len(findings_to_create)} are shown individually (prioritized by interesting keywords and status codes).",
                f"The remaining {len(others)} endpoints are summarized below.",
                "",
                "Status code breakdown for summarized endpoints:"
            ]
            for status, count in sorted(status_counts.items()):
                description_lines.append(f"  - HTTP {status}: {count} endpoints")
            
            description_lines.extend([
                "",
                "These endpoints were discovered but not individually reported to reduce noise.",
                "Review the full ffuf output for complete endpoint list."
            ])
            
            raw_data_summary = {
                "summary": True,
                "total_endpoints": len(ffuf_results),
                "summarized_endpoints": len(others),
                "status_breakdown": status_counts,
                "categories": ["Content Discovery"]
            }
            
            summary_title = f"Content discovery summary: {root_domain or 'target'} ({len(ffuf_results)} endpoints, {len(others)} summarized)"
            if len(summary_title) > 500:
                summary_title = summary_title[:497] + "..."
            
            summary_finding = Finding(
                scan_job_id=scan_job_id,
                title=summary_title,
                description="\n".join(description_lines),
                severity=Severity.INFO,
                url=None,
                tool_name="ffuf",
                raw_data=json.dumps(raw_data_summary),
                status=FindingStatus.OPEN,
            )
            
            findings.append(summary_finding)
            db.add(summary_finding)
            
        except Exception as e:
            logger.warning(f"Failed to create ffuf summary finding: {e}", exc_info=True)
    
    try:
        db.commit()
        logger.info(
            "Ingested %d ffuf findings into DB for scan %s (%d individual + %d summary)",
            len(findings), scan_job_id, len(findings_to_create), 1 if others else 0
        )
    except Exception as e:
        logger.error("Failed to commit ffuf findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def parse_dalfox_output(path: Path) -> list[dict]:
    """
    Parse Dalfox JSON output file into a list of finding dicts.
    
    Dalfox with --output-type json produces JSON output that can be:
    - A single JSON object with "results" array
    - Line-delimited JSON (one JSON object per line)
    
    Args:
        path: Path to the Dalfox JSON output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing or parsing fails)
    """
    results: list[dict] = []
    
    if not path.exists():
        logger.info("Dalfox output file is missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Dalfox output file is empty for %s; treating as no findings", path)
        return []
    
    try:
        raw = path.read_text().strip()
        if not raw:
            return []
        
        # Try parsing as single JSON object first (with "results" array)
        try:
            data = json.loads(raw)
            # Check if it's wrapped in "results" key
            if isinstance(data, dict) and "results" in data:
                results_list = data.get("results", [])
                if isinstance(results_list, list):
                    results.extend(results_list)
                else:
                    results.append(data)
            elif isinstance(data, list):
                # Already an array
                results.extend(data)
            else:
                # Single object
                results.append(data)
        except json.JSONDecodeError:
            # Try line-by-line parsing (NDJSON format)
            for line_no, line in enumerate(raw.splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    # Handle both wrapped and direct formats
                    if isinstance(data, dict) and "results" in data:
                        results.extend(data.get("results", []))
                    else:
                        results.append(data)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON line %d in Dalfox output %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d Dalfox results from file %s", len(results), path)
        return results
    except Exception as e:
        logger.error("Failed to read/parse Dalfox output file %s: %s", path, e, exc_info=True)
        return []


def ingest_dalfox_findings(
    db: Session,
    scan_job_id: str,
    dalfox_results: list[dict],
) -> None:
    """
    Ingest Dalfox findings into the database.
    
    Per-tool idempotency: deletes existing dalfox findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        dalfox_results: List of raw Dalfox result objects
    """
    if not dalfox_results:
        return
    
    from app.models.scan import ScanJob
    from app.models.finding import Finding, Severity, FindingStatus
    import uuid
    
    # Load scan job to get project/tenant/owner info
    scan_job = db.query(ScanJob).options(joinedload(ScanJob.project)).filter(ScanJob.id == scan_job_id).first()
    if not scan_job:
        logger.warning(f"Scan job {scan_job_id} not found, skipping Dalfox findings ingestion")
        return
    
    if not scan_job.project:
        logger.warning(f"Project not found for scan job {scan_job_id}, skipping Dalfox findings ingestion")
        return
    
    # Delete existing dalfox findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "dalfox",
    ).delete(synchronize_session=False)
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing dalfox findings for scan {scan_job_id}")
    
    findings = []
    
    for item in dalfox_results:
        try:
            if not isinstance(item, dict):
                continue
            
            # Extract fields from Dalfox result
            url = item.get("url") or item.get("raw") or ""
            param = item.get("param") or item.get("parameter") or ""
            payload = item.get("payload") or ""
            itype = (item.get("type") or "").lower()
            method = item.get("method") or "GET"
            
            # Severity based on XSS type
            if itype in {"stored", "blind"}:
                severity = Severity.HIGH
            else:  # reflected or unknown
                severity = Severity.MEDIUM
            
            # Build title
            if param:
                title = f"Cross-Site Scripting (XSS) in parameter '{param}'"
            else:
                title = "Cross-Site Scripting (XSS) detected"
            
            # Build description
            description_lines = [
                "Dalfox identified a potential Cross-Site Scripting (XSS) issue.",
            ]
            if param:
                description_lines.append(f"- Parameter: `{param}`")
            if url:
                description_lines.append(f"- Location: `{url}`")
            if payload:
                truncated_payload = payload[:120] + ('…' if len(payload) > 120 else '')
                description_lines.append(f"- Example payload (truncated): `{truncated_payload}`")
            description_lines.append(
                "\nAn attacker could leverage this to execute arbitrary JavaScript "
                "in the victim's browser."
            )
            
            description = "\n".join(description_lines)
            
            # Prepare raw_data with categories
            raw_data = item.copy()
            raw_data["categories"] = ["xss"]
            
            # Create finding
            # Note: project_id, tenant_id, and owner_id are not columns in Finding model
            # They can be accessed via scan_job.project relationship if needed
            finding = Finding(
                scan_job_id=scan_job_id,
                title=title,
                description=description,
                severity=severity,
                status=FindingStatus.OPEN,
                tool_name="dalfox",
                url=url[:2048] if url else None,
                raw_data=json.dumps(raw_data),
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Dalfox finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        if len(findings) > 0:
            logger.info(
                "Ingested %d Dalfox findings into DB for scan %s",
                len(findings), scan_job_id
            )
        else:
            logger.info(
                "Dalfox scan completed for scan %s: no XSS vulnerabilities detected (0 findings ingested)",
                scan_job_id
            )
    except Exception as e:
        logger.error("Failed to commit Dalfox findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise

def parse_sqlmap_output(output_dir: Path) -> List[Dict[str, Any]]:
    """
    Parse sqlmap output directory into a list of finding dicts.
    
    sqlmap outputs results in CSV and JSON formats in the output directory.
    We primarily look for CSV files with injection results.
    
    Args:
        output_dir: Path to the sqlmap output directory (e.g., scan_job_dir/sqlmap)
        
    Returns:
        List of finding dicts (empty list if directory is empty/missing or parsing fails)
    """
    results: List[Dict[str, Any]] = []
    
    if not output_dir.exists() or not output_dir.is_dir():
        logger.info("sqlmap output directory is missing for %s; treating as no findings", output_dir)
        return []
    
    # sqlmap creates CSV files with results
    # Look for CSV files in the output directory
    csv_files = list(output_dir.glob("*.csv"))
    
    if not csv_files:
        logger.info("No sqlmap CSV result files found in %s", output_dir)
        return []
    
    import csv
    
    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                # Try to detect delimiter
                sample = f.read(1024)
                f.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    # Extract relevant fields from CSV row
                    # sqlmap CSV typically has: url, parameter, title, payload, etc.
                    url = row.get("url", "") or row.get("target", "")
                    parameter = row.get("parameter", "") or row.get("Parameter", "")
                    title = row.get("title", "") or row.get("Title", "")
                    payload = row.get("payload", "") or row.get("Payload", "")
                    dbms = row.get("dbms", "") or row.get("DBMS", "") or row.get("database", "")
                    
                    if url or parameter:
                        results.append({
                            "url": url,
                            "parameter": parameter,
                            "title": title,
                            "payload": payload,
                            "dbms": dbms,
                            "raw_row": row,  # Keep full row for reference
                        })
        except Exception as e:
            logger.warning(
                "Failed to parse sqlmap CSV file %s: %s",
                csv_file, e
            )
            continue
    
    # Also check for JSON files if available
    json_files = list(output_dir.glob("*.json"))
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # sqlmap JSON structure varies, try to extract findings
                if isinstance(data, dict):
                    # Look for common keys
                    if "target" in data:
                        target = data["target"]
                        if isinstance(target, dict):
                            url = target.get("url", "")
                            parameters = target.get("parameters", [])
                            for param in parameters:
                                if isinstance(param, dict):
                                    results.append({
                                        "url": url,
                                        "parameter": param.get("name", ""),
                                        "title": param.get("title", ""),
                                        "payload": param.get("payload", ""),
                                        "dbms": param.get("dbms", ""),
                                        "raw_data": param,
                                    })
        except Exception as e:
            logger.warning(
                "Failed to parse sqlmap JSON file %s: %s",
                json_file, e
            )
            continue
    
    logger.info("Parsed %d sqlmap results from directory %s", len(results), output_dir)
    return results


def ingest_sqlmap_findings(
    db: Session,
    scan_job_id: str,
    sqlmap_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Ingest sqlmap findings into the database.
    
    Per-tool idempotency: deletes existing sqlmap findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        sqlmap_results: List of finding dicts from parse_sqlmap_output
        
    Returns:
        List of created Finding objects
    """
    if not sqlmap_results:
        return []
    
    # Delete existing sqlmap findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "sqlmap"
    ).delete(synchronize_session=False)
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing sqlmap findings for scan {scan_job_id}")
    
    findings = []
    
    for result_data in sqlmap_results:
        try:
            url = result_data.get("url", "")
            parameter = result_data.get("parameter", "")
            title = result_data.get("title", "")
            payload = result_data.get("payload", "")
            dbms = result_data.get("dbms", "")
            
            # Determine severity
            # CRITICAL if DBMS is confirmed and exploitation is possible
            # HIGH if SQLi is detected but DBMS not fully confirmed
            if dbms and dbms.lower() not in ["", "none", "unknown"]:
                severity = Severity.CRITICAL
            else:
                severity = Severity.HIGH
            
            # Build title
            if parameter:
                finding_title = f"SQL Injection on parameter '{parameter}'"
                if url:
                    # Extract path from URL for brevity
                    try:
                        parsed = urlparse(url)
                        path = parsed.path[:50]  # Truncate long paths
                        finding_title += f" at {path}"
                    except:
                        pass
            else:
                finding_title = "SQL Injection detected"
                if url:
                    try:
                        parsed = urlparse(url)
                        finding_title += f" at {parsed.path[:50]}"
                    except:
                        pass
            
            finding_title = finding_title[:500]
            
            # Build description
            description_lines = [
                "sqlmap identified a SQL injection vulnerability.",
            ]
            
            if parameter:
                description_lines.append(f"- Vulnerable parameter: `{parameter}`")
            
            if url:
                description_lines.append(f"- Location: `{url}`")
            
            if dbms and dbms.lower() not in ["", "none", "unknown"]:
                description_lines.append(f"- Database management system: {dbms}")
            
            if payload:
                # Sanitize payload (truncate and escape)
                sanitized_payload = payload[:200].replace('\n', ' ').replace('\r', ' ')
                description_lines.append(f"- Example payload (truncated): `{sanitized_payload}...`")
            
            description_lines.append(
                "\nAn attacker could leverage this vulnerability to:"
            )
            description_lines.append("- Access and manipulate database contents")
            description_lines.append("- Extract sensitive information (user credentials, personal data)")
            description_lines.append("- Potentially gain unauthorized access to the application")
            
            if dbms:
                description_lines.append(f"\nConfirmed database system: {dbms}")
            
            description = "\n".join(description_lines)
            
            # Prepare raw_data with categories
            raw_data_dict = result_data.copy()
            raw_data_dict["categories"] = ["sqli"]
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_title,
                description=description,
                severity=severity,
                status=FindingStatus.OPEN,
                tool_name="sqlmap",
                url=url[:2048] if url else None,
                raw_data=json.dumps(raw_data_dict),
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse sqlmap finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        logger.info(
            "Ingested %d sqlmap findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit sqlmap findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings

import logging
import json
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from urllib.parse import urlparse

from app.models.finding import Finding, Severity, FindingStatus

logger = logging.getLogger(__name__)


def categorize_nuclei_finding(template_tags: list[str]) -> list[str]:
    """
    Categorize a Nuclei finding based on its template tags.
    
    Normalizes tags to lowercase and returns a list of category strings
    based on the presence of common vulnerability tags.
    
    Args:
        template_tags: List of template tags from Nuclei finding (e.g., ["xss", "sqli", "cve"])
        
    Returns:
        List of category strings (e.g., ["xss", "sqli"])
        
    Example:
        >>> categorize_nuclei_finding(["xss", "sqli", "cve"])
        ["xss", "sqli"]
        >>> categorize_nuclei_finding(["lfi", "rfi"])
        ["dir_traversal"]
    """
    if not template_tags:
        return []
    
    # Normalize tags to lowercase
    tags_lower = [tag.lower() for tag in template_tags if tag]
    
    categories = []
    
    # Map tags to simple lowercase category names (attacker-relevant findings)
    # XSS
    if any(tag in tags_lower for tag in ["xss", "cross-site-scripting"]):
        categories.append("xss")
    
    # SQL Injection
    if any(tag in tags_lower for tag in ["sqli", "sql-injection", "sql"]):
        categories.append("sqli")
    
    # SSRF
    if any(tag in tags_lower for tag in ["ssrf", "server-side-request-forgery"]):
        categories.append("ssrf")
    
    # SSTI
    if any(tag in tags_lower for tag in ["ssti", "server-side-template-injection", "template-injection"]):
        categories.append("ssti")
    
    # XXE
    if any(tag in tags_lower for tag in ["xxe", "xml-external-entity"]):
        categories.append("xxe")
    
    # Directory Traversal (LFI/RFI)
    if any(tag in tags_lower for tag in ["lfi", "rfi", "local-file-inclusion", "remote-file-inclusion", "path-traversal", "directory-traversal", "file-inclusion"]):
        categories.append("directory_traversal")
    
    # CSRF
    if any(tag in tags_lower for tag in ["csrf", "cross-site-request-forgery"]):
        categories.append("csrf")
    
    # CORS
    if any(tag in tags_lower for tag in ["cors", "cross-origin-resource-sharing", "cors-misconfig"]):
        categories.append("cors_misconfig")
    
    # Command Injection
    if any(tag in tags_lower for tag in ["cmdi", "command-injection", "rce", "remote-code-execution", "code-execution", "os-commanding"]):
        categories.append("command_injection")
    
    # IDOR
    if any(tag in tags_lower for tag in ["idor", "insecure-direct-object-reference", "authorization"]):
        categories.append("idor")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_categories = []
    for cat in categories:
        if cat not in seen:
            seen.add(cat)
            unique_categories.append(cat)
    
    return unique_categories


def ingest_nuclei_findings(
    db: Session,
    scan_job_id: str,
    nuclei_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Given a scan_job_id and a list of nuclei JSON objects, create Finding rows.
    
    This function is idempotent: it deletes existing findings for this scan_job
    before inserting new ones, so it can be safely called multiple times.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nuclei_results: List of Nuclei JSON objects (one per finding)
        
    Returns:
        List of created Finding objects
    """
    # Delete existing findings for this scan job AND tool (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "nuclei"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing nuclei findings for scan {scan_job_id}")
    
    findings = []
    
    for nuclei_data in nuclei_results:
        try:
            # Extract severity
            severity_str = nuclei_data.get("info", {}).get("severity", "info")
            if isinstance(severity_str, str):
                severity_str = severity_str.lower()
            else:
                severity_str = "info"
            
            # Normalize severity to allowed enum values
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            # Extract title
            title = (
                nuclei_data.get("info", {}).get("name") or
                nuclei_data.get("template-id") or
                nuclei_data.get("matcher-name") or
                "Nuclei Finding"
            )
            
            # Extract description
            description = nuclei_data.get("info", {}).get("description", "")
            matched_at = nuclei_data.get("matched-at", "")
            if matched_at and description:
                description = f"{description}\n\nMatched at: {matched_at}"
            elif matched_at:
                description = f"Matched at: {matched_at}"
            
            # Extract CVE ID
            cve_id = None
            # Try multiple possible locations for CVE
            if "cve" in nuclei_data:
                cve_id = nuclei_data["cve"]
            elif "info" in nuclei_data and "classification" in nuclei_data["info"]:
                cve_list = nuclei_data["info"]["classification"].get("cve-id", [])
                if cve_list and isinstance(cve_list, list) and len(cve_list) > 0:
                    cve_id = cve_list[0]
                elif isinstance(nuclei_data["info"]["classification"].get("cve-id"), str):
                    cve_id = nuclei_data["info"]["classification"]["cve-id"]
            
            # Extract CWE ID
            cwe_id = None
            if "cwe-id" in nuclei_data:
                cwe_id = nuclei_data["cwe-id"]
            elif "info" in nuclei_data and "classification" in nuclei_data["info"]:
                cwe_list = nuclei_data["info"]["classification"].get("cwe-id", [])
                if cwe_list and isinstance(cwe_list, list) and len(cwe_list) > 0:
                    cwe_id = cwe_list[0]
                elif isinstance(nuclei_data["info"]["classification"].get("cwe-id"), str):
                    cwe_id = nuclei_data["info"]["classification"]["cwe-id"]
            
            # Extract URL
            url = matched_at or nuclei_data.get("host", "")
            
            # Extract template tags for categorization
            template_tags = []
            if "info" in nuclei_data and "tags" in nuclei_data["info"]:
                tags = nuclei_data["info"]["tags"]
                if isinstance(tags, list):
                    template_tags = tags
                elif isinstance(tags, str):
                    # Tags might be comma-separated string
                    template_tags = [t.strip() for t in tags.split(",")]
            
            # Categorize finding based on tags
            categories = categorize_nuclei_finding(template_tags)
            
            # Store raw JSON as string, but add categories to the dict first
            raw_data_dict = nuclei_data.copy() if isinstance(nuclei_data, dict) else {}
            if categories:
                raw_data_dict["categories"] = categories
            
            raw_data = json.dumps(raw_data_dict) if isinstance(raw_data_dict, dict) else json.dumps(nuclei_data) if isinstance(nuclei_data, dict) else str(nuclei_data)
            
            # Create Finding
            finding = Finding(
                scan_job_id=scan_job_id,
                title=title[:500],  # Ensure title fits in column
                description=description,
                severity=severity,
                cve_id=cve_id[:50] if cve_id else None,  # Ensure CVE ID fits
                cwe_id=cwe_id[:50] if cwe_id else None,  # Ensure CWE ID fits
                url=url[:2048] if url else None,  # Ensure URL fits
                tool_name="nuclei",
                raw_data=raw_data,
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nuclei finding: {e}", exc_info=True)
            logger.debug(f"Problematic Nuclei data: {nuclei_data}")
            continue
    
    # Commit all findings at once
    try:
        db.commit()
        logger.info(
            "Ingested %d nuclei findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def parse_nuclei_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nuclei JSONL output file (one JSON object per line) into a list of dicts.
    
    This function is robust to non-JSON lines (like ASCII tables, logs, etc.)
    and will skip them gracefully. Handles empty files and zero-byte files.
    
    Args:
        path: Path to the Nuclei output file (JSONL format)
        
    Returns:
        List of parsed Nuclei JSON objects (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    # Check if file is zero bytes
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                
                # Skip obvious non-JSON lines (tables, logs, etc.)
                # JSON objects/arrays start with { or [
                if not (line.startswith("{") or line.startswith("[")):
                    logger.debug(
                        "Skipping non-JSON line %d in nuclei output %s: %r",
                        line_no, path, line[:80]
                    )
                    continue
                
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        findings.append(obj)
                    else:
                        logger.debug("Skipping non-dict JSON on line %d in %s", line_no, path)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON line %d in nuclei output %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
                except Exception as e:
                    logger.warning(
                        "Unexpected error parsing line %d in %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d nuclei findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse Nuclei output file %s: %s", path, e, exc_info=True)
        return []


def parse_nmap_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nmap XML output file into a list of finding dicts.
    
    Each open port becomes a finding. Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the Nmap XML output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Extract host information
        for host in root.findall("host"):
            host_status = host.find("status")
            if host_status is None or host_status.get("state") != "up":
                continue
            
            # Get host address
            address_elem = host.find("address")
            host_ip = address_elem.get("addr") if address_elem is not None else "unknown"
            
            # Get hostname
            hostnames_elem = host.find("hostnames")
            hostname = host_ip
            if hostnames_elem is not None:
                hostname_elem = hostnames_elem.find("hostname")
                if hostname_elem is not None:
                    hostname = hostname_elem.get("name", host_ip)
            
            # Process ports
            ports_elem = host.find("ports")
            if ports_elem is None:
                continue
            
            for port_elem in ports_elem.findall("port"):
                port_state = port_elem.find("state")
                if port_state is None or port_state.get("state") != "open":
                    continue
                
                port_num = port_elem.get("portid")
                protocol = port_elem.get("protocol", "tcp")
                
                # Get service info
                service_elem = port_elem.find("service")
                service_name = service_elem.get("name", "unknown") if service_elem is not None else "unknown"
                service_product = service_elem.get("product", "") if service_elem is not None else ""
                service_version = service_elem.get("version", "") if service_elem is not None else ""
                
                # Build description
                description_parts = [
                    f"Host: {hostname} ({host_ip})",
                    f"Port: {port_num}/{protocol}",
                    f"Service: {service_name}",
                ]
                if service_product:
                    description_parts.append(f"Product: {service_product}")
                if service_version:
                    description_parts.append(f"Version: {service_version}")
                
                description = "\n".join(description_parts)
                
                # Determine severity based on port/service
                severity = "info"
                if port_num in ["22", "3389", "5900"]:  # SSH, RDP, VNC
                    severity = "medium"
                elif port_num in ["3306", "5432", "1433"]:  # MySQL, PostgreSQL, MSSQL
                    severity = "medium"
                elif port_num in ["21", "23", "25"]:  # FTP, Telnet, SMTP
                    severity = "low"
                elif port_num in ["80", "443", "8080", "8443"]:  # HTTP/HTTPS
                    severity = "info"
                
                # Build title
                title = f"Open port {port_num}/{protocol} ({service_name}) on {hostname}"
                
                # Build URL
                url = f"{hostname}:{port_num}"
                if port_num in ["80", "8080"]:
                    url = f"http://{hostname}:{port_num}"
                elif port_num in ["443", "8443"]:
                    url = f"https://{hostname}:{port_num}"
                
                # Store raw XML for this port as JSON
                raw_data = json.dumps({
                    "host": hostname,
                    "ip": host_ip,
                    "port": port_num,
                    "protocol": protocol,
                    "service": service_name,
                    "product": service_product,
                    "version": service_version,
                })
                
                findings.append({
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "cve_id": None,
                    "cwe_id": None,
                    "url": url,
                    "tool_name": "nmap",
                    "raw_data": raw_data,
                })
        
        logger.info("Parsed %d nmap findings from file for scan %s", len(findings), path)
        return findings
        
    except ET.ParseError as e:
        logger.warning("Failed to parse Nmap XML file %s: %s", path, e)
        return []
    except Exception as e:
        logger.error("Failed to read/parse Nmap output file %s: %s", path, e, exc_info=True)
        return []


def parse_sslscan_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse sslscan output file (JSON or text format) into a list of finding dicts.
    
    Handles both JSON output (when --json flag is used) and plain text output.
    Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the sslscan output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        # Try to parse as JSON first
        try:
            # Remove ANSI color codes if present
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            content_clean = ansi_escape.sub('', content)
            
            # Try to find JSON object/array
            json_start = content_clean.find('{')
            json_end = content_clean.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content_clean[json_start:json_end]
                data = json.loads(json_str)
                
                # Handle JSON format
                if isinstance(data, dict):
                    # Single JSON object
                    findings.extend(_parse_sslscan_json_object(data))
                elif isinstance(data, list):
                    # Array of JSON objects
                    for item in data:
                        if isinstance(item, dict):
                            findings.extend(_parse_sslscan_json_object(item))
        except (json.JSONDecodeError, ValueError):
            # Fall back to text parsing
            findings.extend(_parse_sslscan_text(content))
        
        logger.info("Parsed %d sslscan findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse sslscan output file %s: %s", path, e, exc_info=True)
        return []


def _parse_sslscan_json_object(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse a single sslscan JSON object into finding dicts"""
    findings = []
    
    host = data.get("host", "unknown")
    port = data.get("port", 443)
    target = f"{host}:{port}"
    
    # Check for weak protocols
    sslv2 = data.get("ssl_version", {}).get("SSLv2", {}).get("status", "").lower()
    sslv3 = data.get("ssl_version", {}).get("SSLv3", {}).get("status", "").lower()
    tls10 = data.get("ssl_version", {}).get("TLSv1.0", {}).get("status", "").lower()
    tls11 = data.get("ssl_version", {}).get("TLSv1.1", {}).get("status", "").lower()
    
    if sslv2 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if sslv3 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls10 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls11 == "enabled":
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    # Check for weak ciphers
    ciphers = data.get("cipher_suites", [])
    weak_ciphers = []
    for cipher in ciphers:
        cipher_name = cipher.get("cipher", "")
        key_length = cipher.get("key_length", 0)
        if key_length < 128 or "RC4" in cipher_name or "DES" in cipher_name or "MD5" in cipher_name:
            weak_ciphers.append(cipher_name)
    
    if weak_ciphers:
        findings.append({
            "severity": "medium",
            "title": f"Weak cipher suites detected on {target}",
            "description": f"Weak cipher suites found on {target}: {', '.join(weak_ciphers[:5])}",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    return findings


def _parse_sslscan_text(content: str) -> List[Dict[str, Any]]:
    """Parse sslscan plain text output into finding dicts"""
    findings = []
    
    # Remove ANSI color codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    content_clean = ansi_escape.sub('', content)
    
    # Extract host and port from content
    host_match = re.search(r'Testing SSL server\s+(\S+)\s+on port\s+(\d+)', content_clean)
    if not host_match:
        # Try alternative pattern
        host_match = re.search(r'Connected to\s+([\d.]+)', content_clean)
        port_match = re.search(r'port\s+(\d+)', content_clean)
        host = host_match.group(1) if host_match else "unknown"
        port = int(port_match.group(1)) if port_match else 443
    else:
        host = host_match.group(1)
        port = int(host_match.group(2))
    
    target = f"{host}:{port}"
    
    # Check for weak protocols in text
    if re.search(r'SSLv2\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],  # Store first 1000 chars
        })
    
    if re.search(r'SSLv3\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.0\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.1\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    return findings


def ingest_nmap_findings(
    db: Session,
    scan_job_id: str,
    nmap_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Ingest Nmap findings into the database.
    
    Per-tool idempotency: deletes existing nmap findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nmap_results: List of finding dicts from parse_nmap_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing nmap findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "nmap"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing nmap findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in nmap_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "Nmap Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="nmap",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nmap finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        logger.info(
            "Ingested %d nmap findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit nmap findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_sslscan_findings(
    db: Session,
    scan_job_id: str,
    sslscan_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Ingest sslscan findings into the database.
    
    Per-tool idempotency: deletes existing sslscan findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        sslscan_results: List of finding dicts from parse_sslscan_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing sslscan findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "sslscan"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing sslscan findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in sslscan_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "SSL/TLS Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="sslscan",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse sslscan finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        logger.info(
            "Ingested %d sslscan findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit sslscan findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_http_header_findings(
    db: Session,
    scan_job_id: str,
    header_findings: List[Finding],
) -> List[Finding]:
    """
    Ingest HTTP header findings into the database.
    
    Per-tool idempotency: deletes existing http_headers findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        header_findings: List of Finding objects for missing headers
        
    Returns:
        List of created Finding objects
    """
    # Delete existing http_headers findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "http_headers"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing http_headers findings for scan {scan_job_id}")
    
    # Add all findings to session
    for finding in header_findings:
        db.add(finding)
    
    # Commit all findings at once
    try:
        db.commit()
        logger.info(
            "Ingested %d http_headers findings into DB for scan %s",
            len(header_findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit http_headers findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return header_findings


def parse_dalfox_output(path: Path) -> list[dict]:
    """
    Parse Dalfox JSON output file into a list of finding dicts.
    
    Dalfox with --output-type json produces JSON output that can be:
    - A single JSON object with "results" array
    - Line-delimited JSON (one JSON object per line)
    
    Args:
        path: Path to the Dalfox JSON output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing or parsing fails)
    """
    results: list[dict] = []
    
    if not path.exists():
        logger.info("Dalfox output file is missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Dalfox output file is empty for %s; treating as no findings", path)
        return []
    
    try:
        raw = path.read_text().strip()
        if not raw:
            return []
        
        # Try parsing as single JSON object first (with "results" array)
        try:
            data = json.loads(raw)
            # Check if it's wrapped in "results" key
            if isinstance(data, dict) and "results" in data:
                results_list = data.get("results", [])
                if isinstance(results_list, list):
                    results.extend(results_list)
                else:
                    results.append(data)
            elif isinstance(data, list):
                # Already an array
                results.extend(data)
            else:
                # Single object
                results.append(data)
        except json.JSONDecodeError:
            # Try line-by-line parsing (NDJSON format)
            for line_no, line in enumerate(raw.splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    # Handle both wrapped and direct formats
                    if isinstance(data, dict) and "results" in data:
                        results.extend(data.get("results", []))
                    else:
                        results.append(data)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON line %d in Dalfox output %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d Dalfox results from file %s", len(results), path)
        return results
    except Exception as e:
        logger.error("Failed to read/parse Dalfox output file %s: %s", path, e, exc_info=True)
        return []


def ingest_dalfox_findings(
    db: Session,
    scan_job_id: str,
    dalfox_results: list[dict],
) -> None:
    """
    Ingest Dalfox findings into the database.
    
    Per-tool idempotency: deletes existing dalfox findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        dalfox_results: List of raw Dalfox result objects
    """
    if not dalfox_results:
        return
    
    from app.models.scan import ScanJob
    from app.models.finding import Finding, Severity, FindingStatus
    import uuid
    
    # Load scan job to get project/tenant/owner info
    scan_job = db.query(ScanJob).options(joinedload(ScanJob.project)).filter(ScanJob.id == scan_job_id).first()
    if not scan_job:
        logger.warning(f"Scan job {scan_job_id} not found, skipping Dalfox findings ingestion")
        return
    
    if not scan_job.project:
        logger.warning(f"Project not found for scan job {scan_job_id}, skipping Dalfox findings ingestion")
        return
    
    # Delete existing dalfox findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "dalfox",
    ).delete(synchronize_session=False)
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing dalfox findings for scan {scan_job_id}")
    
    findings = []
    
    for item in dalfox_results:
        try:
            if not isinstance(item, dict):
                continue
            
            # Extract fields from Dalfox result
            url = item.get("url") or item.get("raw") or ""
            param = item.get("param") or item.get("parameter") or ""
            payload = item.get("payload") or ""
            itype = (item.get("type") or "").lower()
            method = item.get("method") or "GET"
            
            # Severity based on XSS type
            if itype in {"stored", "blind"}:
                severity = Severity.HIGH
            else:  # reflected or unknown
                severity = Severity.MEDIUM
            
            # Build title
            if param:
                title = f"Cross-Site Scripting (XSS) in parameter '{param}'"
            else:
                title = "Cross-Site Scripting (XSS) detected"
            
            # Build description
            description_lines = [
                "Dalfox identified a potential Cross-Site Scripting (XSS) issue.",
            ]
            if param:
                description_lines.append(f"- Parameter: `{param}`")
            if url:
                description_lines.append(f"- Location: `{url}`")
            if payload:
                truncated_payload = payload[:120] + ('…' if len(payload) > 120 else '')
                description_lines.append(f"- Example payload (truncated): `{truncated_payload}`")
            description_lines.append(
                "\nAn attacker could leverage this to execute arbitrary JavaScript "
                "in the victim's browser."
            )
            
            description = "\n".join(description_lines)
            
            # Prepare raw_data with categories
            raw_data = item.copy()
            raw_data["categories"] = ["xss"]
            
            # Create finding
            # Note: project_id, tenant_id, and owner_id are not columns in Finding model
            # They can be accessed via scan_job.project relationship if needed
            finding = Finding(
                scan_job_id=scan_job_id,
                title=title,
                description=description,
                severity=severity,
                status=FindingStatus.OPEN,
                tool_name="dalfox",
                url=url[:2048] if url else None,
                raw_data=json.dumps(raw_data),
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Dalfox finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        if len(findings) > 0:
            logger.info(
                "Ingested %d Dalfox findings into DB for scan %s",
                len(findings), scan_job_id
            )
        else:
            logger.info(
                "Dalfox scan completed for scan %s: no XSS vulnerabilities detected (0 findings ingested)",
                scan_job_id
            )
    except Exception as e:
        logger.error("Failed to commit Dalfox findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
import logging
import json
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from urllib.parse import urlparse

from app.models.finding import Finding, Severity, FindingStatus

logger = logging.getLogger(__name__)


def categorize_nuclei_finding(template_tags: list[str]) -> list[str]:
    """
    Categorize a Nuclei finding based on its template tags.
    
    Normalizes tags to lowercase and returns a list of category strings
    based on the presence of common vulnerability tags.
    
    Args:
        template_tags: List of template tags from Nuclei finding (e.g., ["xss", "sqli", "cve"])
        
    Returns:
        List of category strings (e.g., ["xss", "sqli"])
        
    Example:
        >>> categorize_nuclei_finding(["xss", "sqli", "cve"])
        ["xss", "sqli"]
        >>> categorize_nuclei_finding(["lfi", "rfi"])
        ["dir_traversal"]
    """
    if not template_tags:
        return []
    
    # Normalize tags to lowercase
    tags_lower = [tag.lower() for tag in template_tags if tag]
    
    categories = []
    
    # Map tags to simple lowercase category names (attacker-relevant findings)
    # XSS
    if any(tag in tags_lower for tag in ["xss", "cross-site-scripting"]):
        categories.append("xss")
    
    # SQL Injection
    if any(tag in tags_lower for tag in ["sqli", "sql-injection", "sql"]):
        categories.append("sqli")
    
    # SSRF
    if any(tag in tags_lower for tag in ["ssrf", "server-side-request-forgery"]):
        categories.append("ssrf")
    
    # SSTI
    if any(tag in tags_lower for tag in ["ssti", "server-side-template-injection", "template-injection"]):
        categories.append("ssti")
    
    # XXE
    if any(tag in tags_lower for tag in ["xxe", "xml-external-entity"]):
        categories.append("xxe")
    
    # Directory Traversal (LFI/RFI)
    if any(tag in tags_lower for tag in ["lfi", "rfi", "local-file-inclusion", "remote-file-inclusion", "path-traversal", "directory-traversal", "file-inclusion"]):
        categories.append("directory_traversal")
    
    # CSRF
    if any(tag in tags_lower for tag in ["csrf", "cross-site-request-forgery"]):
        categories.append("csrf")
    
    # CORS
    if any(tag in tags_lower for tag in ["cors", "cross-origin-resource-sharing", "cors-misconfig"]):
        categories.append("cors_misconfig")
    
    # Command Injection
    if any(tag in tags_lower for tag in ["cmdi", "command-injection", "rce", "remote-code-execution", "code-execution", "os-commanding"]):
        categories.append("command_injection")
    
    # IDOR
    if any(tag in tags_lower for tag in ["idor", "insecure-direct-object-reference", "authorization"]):
        categories.append("idor")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_categories = []
    for cat in categories:
        if cat not in seen:
            seen.add(cat)
            unique_categories.append(cat)
    
    return unique_categories


def ingest_nuclei_findings(
    db: Session,
    scan_job_id: str,
    nuclei_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Given a scan_job_id and a list of nuclei JSON objects, create Finding rows.
    
    This function is idempotent: it deletes existing findings for this scan_job
    before inserting new ones, so it can be safely called multiple times.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nuclei_results: List of Nuclei JSON objects (one per finding)
        
    Returns:
        List of created Finding objects
    """
    # Delete existing findings for this scan job AND tool (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "nuclei"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing nuclei findings for scan {scan_job_id}")
    
    findings = []
    
    for nuclei_data in nuclei_results:
        try:
            # Extract severity
            severity_str = nuclei_data.get("info", {}).get("severity", "info")
            if isinstance(severity_str, str):
                severity_str = severity_str.lower()
            else:
                severity_str = "info"
            
            # Normalize severity to allowed enum values
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            # Extract title
            title = (
                nuclei_data.get("info", {}).get("name") or
                nuclei_data.get("template-id") or
                nuclei_data.get("matcher-name") or
                "Nuclei Finding"
            )
            
            # Extract description
            description = nuclei_data.get("info", {}).get("description", "")
            matched_at = nuclei_data.get("matched-at", "")
            if matched_at and description:
                description = f"{description}\n\nMatched at: {matched_at}"
            elif matched_at:
                description = f"Matched at: {matched_at}"
            
            # Extract CVE ID
            cve_id = None
            # Try multiple possible locations for CVE
            if "cve" in nuclei_data:
                cve_id = nuclei_data["cve"]
            elif "info" in nuclei_data and "classification" in nuclei_data["info"]:
                cve_list = nuclei_data["info"]["classification"].get("cve-id", [])
                if cve_list and isinstance(cve_list, list) and len(cve_list) > 0:
                    cve_id = cve_list[0]
                elif isinstance(nuclei_data["info"]["classification"].get("cve-id"), str):
                    cve_id = nuclei_data["info"]["classification"]["cve-id"]
            
            # Extract CWE ID
            cwe_id = None
            if "cwe-id" in nuclei_data:
                cwe_id = nuclei_data["cwe-id"]
            elif "info" in nuclei_data and "classification" in nuclei_data["info"]:
                cwe_list = nuclei_data["info"]["classification"].get("cwe-id", [])
                if cwe_list and isinstance(cwe_list, list) and len(cwe_list) > 0:
                    cwe_id = cwe_list[0]
                elif isinstance(nuclei_data["info"]["classification"].get("cwe-id"), str):
                    cwe_id = nuclei_data["info"]["classification"]["cwe-id"]
            
            # Extract URL
            url = matched_at or nuclei_data.get("host", "")
            
            # Extract template tags for categorization
            template_tags = []
            if "info" in nuclei_data and "tags" in nuclei_data["info"]:
                tags = nuclei_data["info"]["tags"]
                if isinstance(tags, list):
                    template_tags = tags
                elif isinstance(tags, str):
                    # Tags might be comma-separated string
                    template_tags = [t.strip() for t in tags.split(",")]
            
            # Categorize finding based on tags
            categories = categorize_nuclei_finding(template_tags)
            
            # Store raw JSON as string, but add categories to the dict first
            raw_data_dict = nuclei_data.copy() if isinstance(nuclei_data, dict) else {}
            if categories:
                raw_data_dict["categories"] = categories
            
            raw_data = json.dumps(raw_data_dict) if isinstance(raw_data_dict, dict) else json.dumps(nuclei_data) if isinstance(nuclei_data, dict) else str(nuclei_data)
            
            # Create Finding
            finding = Finding(
                scan_job_id=scan_job_id,
                title=title[:500],  # Ensure title fits in column
                description=description,
                severity=severity,
                cve_id=cve_id[:50] if cve_id else None,  # Ensure CVE ID fits
                cwe_id=cwe_id[:50] if cwe_id else None,  # Ensure CWE ID fits
                url=url[:2048] if url else None,  # Ensure URL fits
                tool_name="nuclei",
                raw_data=raw_data,
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nuclei finding: {e}", exc_info=True)
            logger.debug(f"Problematic Nuclei data: {nuclei_data}")
            continue
    
    # Commit all findings at once
    try:
        db.commit()
        logger.info(
            "Ingested %d nuclei findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def parse_nuclei_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nuclei JSONL output file (one JSON object per line) into a list of dicts.
    
    This function is robust to non-JSON lines (like ASCII tables, logs, etc.)
    and will skip them gracefully. Handles empty files and zero-byte files.
    
    Args:
        path: Path to the Nuclei output file (JSONL format)
        
    Returns:
        List of parsed Nuclei JSON objects (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    # Check if file is zero bytes
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                
                # Skip obvious non-JSON lines (tables, logs, etc.)
                # JSON objects/arrays start with { or [
                if not (line.startswith("{") or line.startswith("[")):
                    logger.debug(
                        "Skipping non-JSON line %d in nuclei output %s: %r",
                        line_no, path, line[:80]
                    )
                    continue
                
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        findings.append(obj)
                    else:
                        logger.debug("Skipping non-dict JSON on line %d in %s", line_no, path)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON line %d in nuclei output %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
                except Exception as e:
                    logger.warning(
                        "Unexpected error parsing line %d in %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d nuclei findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse Nuclei output file %s: %s", path, e, exc_info=True)
        return []


def parse_nmap_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nmap XML output file into a list of finding dicts.
    
    Each open port becomes a finding. Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the Nmap XML output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Extract host information
        for host in root.findall("host"):
            host_status = host.find("status")
            if host_status is None or host_status.get("state") != "up":
                continue
            
            # Get host address
            address_elem = host.find("address")
            host_ip = address_elem.get("addr") if address_elem is not None else "unknown"
            
            # Get hostname
            hostnames_elem = host.find("hostnames")
            hostname = host_ip
            if hostnames_elem is not None:
                hostname_elem = hostnames_elem.find("hostname")
                if hostname_elem is not None:
                    hostname = hostname_elem.get("name", host_ip)
            
            # Process ports
            ports_elem = host.find("ports")
            if ports_elem is None:
                continue
            
            for port_elem in ports_elem.findall("port"):
                port_state = port_elem.find("state")
                if port_state is None or port_state.get("state") != "open":
                    continue
                
                port_num = port_elem.get("portid")
                protocol = port_elem.get("protocol", "tcp")
                
                # Get service info
                service_elem = port_elem.find("service")
                service_name = service_elem.get("name", "unknown") if service_elem is not None else "unknown"
                service_product = service_elem.get("product", "") if service_elem is not None else ""
                service_version = service_elem.get("version", "") if service_elem is not None else ""
                
                # Build description
                description_parts = [
                    f"Host: {hostname} ({host_ip})",
                    f"Port: {port_num}/{protocol}",
                    f"Service: {service_name}",
                ]
                if service_product:
                    description_parts.append(f"Product: {service_product}")
                if service_version:
                    description_parts.append(f"Version: {service_version}")
                
                description = "\n".join(description_parts)
                
                # Determine severity based on port/service
                severity = "info"
                if port_num in ["22", "3389", "5900"]:  # SSH, RDP, VNC
                    severity = "medium"
                elif port_num in ["3306", "5432", "1433"]:  # MySQL, PostgreSQL, MSSQL
                    severity = "medium"
                elif port_num in ["21", "23", "25"]:  # FTP, Telnet, SMTP
                    severity = "low"
                elif port_num in ["80", "443", "8080", "8443"]:  # HTTP/HTTPS
                    severity = "info"
                
                # Build title
                title = f"Open port {port_num}/{protocol} ({service_name}) on {hostname}"
                
                # Build URL
                url = f"{hostname}:{port_num}"
                if port_num in ["80", "8080"]:
                    url = f"http://{hostname}:{port_num}"
                elif port_num in ["443", "8443"]:
                    url = f"https://{hostname}:{port_num}"
                
                # Store raw XML for this port as JSON
                raw_data = json.dumps({
                    "host": hostname,
                    "ip": host_ip,
                    "port": port_num,
                    "protocol": protocol,
                    "service": service_name,
                    "product": service_product,
                    "version": service_version,
                })
                
                findings.append({
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "cve_id": None,
                    "cwe_id": None,
                    "url": url,
                    "tool_name": "nmap",
                    "raw_data": raw_data,
                })
        
        logger.info("Parsed %d nmap findings from file for scan %s", len(findings), path)
        return findings
        
    except ET.ParseError as e:
        logger.warning("Failed to parse Nmap XML file %s: %s", path, e)
        return []
    except Exception as e:
        logger.error("Failed to read/parse Nmap output file %s: %s", path, e, exc_info=True)
        return []


def parse_sslscan_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse sslscan output file (JSON or text format) into a list of finding dicts.
    
    Handles both JSON output (when --json flag is used) and plain text output.
    Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the sslscan output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        # Try to parse as JSON first
        try:
            # Remove ANSI color codes if present
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            content_clean = ansi_escape.sub('', content)
            
            # Try to find JSON object/array
            json_start = content_clean.find('{')
            json_end = content_clean.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content_clean[json_start:json_end]
                data = json.loads(json_str)
                
                # Handle JSON format
                if isinstance(data, dict):
                    # Single JSON object
                    findings.extend(_parse_sslscan_json_object(data))
                elif isinstance(data, list):
                    # Array of JSON objects
                    for item in data:
                        if isinstance(item, dict):
                            findings.extend(_parse_sslscan_json_object(item))
        except (json.JSONDecodeError, ValueError):
            # Fall back to text parsing
            findings.extend(_parse_sslscan_text(content))
        
        logger.info("Parsed %d sslscan findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse sslscan output file %s: %s", path, e, exc_info=True)
        return []


def _parse_sslscan_json_object(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse a single sslscan JSON object into finding dicts"""
    findings = []
    
    host = data.get("host", "unknown")
    port = data.get("port", 443)
    target = f"{host}:{port}"
    
    # Check for weak protocols
    sslv2 = data.get("ssl_version", {}).get("SSLv2", {}).get("status", "").lower()
    sslv3 = data.get("ssl_version", {}).get("SSLv3", {}).get("status", "").lower()
    tls10 = data.get("ssl_version", {}).get("TLSv1.0", {}).get("status", "").lower()
    tls11 = data.get("ssl_version", {}).get("TLSv1.1", {}).get("status", "").lower()
    
    if sslv2 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if sslv3 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls10 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls11 == "enabled":
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    # Check for weak ciphers
    ciphers = data.get("cipher_suites", [])
    weak_ciphers = []
    for cipher in ciphers:
        cipher_name = cipher.get("cipher", "")
        key_length = cipher.get("key_length", 0)
        if key_length < 128 or "RC4" in cipher_name or "DES" in cipher_name or "MD5" in cipher_name:
            weak_ciphers.append(cipher_name)
    
    if weak_ciphers:
        findings.append({
            "severity": "medium",
            "title": f"Weak cipher suites detected on {target}",
            "description": f"Weak cipher suites found on {target}: {', '.join(weak_ciphers[:5])}",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    return findings


def _parse_sslscan_text(content: str) -> List[Dict[str, Any]]:
    """Parse sslscan plain text output into finding dicts"""
    findings = []
    
    # Remove ANSI color codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    content_clean = ansi_escape.sub('', content)
    
    # Extract host and port from content
    host_match = re.search(r'Testing SSL server\s+(\S+)\s+on port\s+(\d+)', content_clean)
    if not host_match:
        # Try alternative pattern
        host_match = re.search(r'Connected to\s+([\d.]+)', content_clean)
        port_match = re.search(r'port\s+(\d+)', content_clean)
        host = host_match.group(1) if host_match else "unknown"
        port = int(port_match.group(1)) if port_match else 443
    else:
        host = host_match.group(1)
        port = int(host_match.group(2))
    
    target = f"{host}:{port}"
    
    # Check for weak protocols in text
    if re.search(r'SSLv2\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],  # Store first 1000 chars
        })
    
    if re.search(r'SSLv3\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.0\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.1\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    return findings


def ingest_nmap_findings(
    db: Session,
    scan_job_id: str,
    nmap_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Ingest Nmap findings into the database.
    
    Per-tool idempotency: deletes existing nmap findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nmap_results: List of finding dicts from parse_nmap_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing nmap findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "nmap"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing nmap findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in nmap_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "Nmap Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="nmap",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nmap finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        logger.info(
            "Ingested %d nmap findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit nmap findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_sslscan_findings(
    db: Session,
    scan_job_id: str,
    sslscan_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Ingest sslscan findings into the database.
    
    Per-tool idempotency: deletes existing sslscan findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        sslscan_results: List of finding dicts from parse_sslscan_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing sslscan findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "sslscan"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing sslscan findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in sslscan_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "SSL/TLS Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="sslscan",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse sslscan finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        logger.info(
            "Ingested %d sslscan findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit sslscan findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_http_header_findings(
    db: Session,
    scan_job_id: str,
    header_findings: List[Finding],
) -> List[Finding]:
    """
    Ingest HTTP header findings into the database.
    
    Per-tool idempotency: deletes existing http_headers findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        header_findings: List of Finding objects for missing headers
        
    Returns:
        List of created Finding objects
    """
    # Delete existing http_headers findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "http_headers"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing http_headers findings for scan {scan_job_id}")
    
    # Add all findings to session
    for finding in header_findings:
        db.add(finding)
    
    # Commit all findings at once
    try:
        db.commit()
        logger.info(
            "Ingested %d http_headers findings into DB for scan %s",
            len(header_findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit http_headers findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return header_findings


def parse_dalfox_output(path: Path) -> list[dict]:
    """
    Parse Dalfox JSON output file into a list of finding dicts.
    
    Dalfox with --output-type json produces JSON output that can be:
    - A single JSON object with "results" array
    - Line-delimited JSON (one JSON object per line)
    
    Args:
        path: Path to the Dalfox JSON output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing or parsing fails)
    """
    results: list[dict] = []
    
    if not path.exists():
        logger.info("Dalfox output file is missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Dalfox output file is empty for %s; treating as no findings", path)
        return []
    
    try:
        raw = path.read_text().strip()
        if not raw:
            return []
        
        # Try parsing as single JSON object first (with "results" array)
        try:
            data = json.loads(raw)
            # Check if it's wrapped in "results" key
            if isinstance(data, dict) and "results" in data:
                results_list = data.get("results", [])
                if isinstance(results_list, list):
                    results.extend(results_list)
                else:
                    results.append(data)
            elif isinstance(data, list):
                # Already an array
                results.extend(data)
            else:
                # Single object
                results.append(data)
        except json.JSONDecodeError:
            # Try line-by-line parsing (NDJSON format)
            for line_no, line in enumerate(raw.splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    # Handle both wrapped and direct formats
                    if isinstance(data, dict) and "results" in data:
                        results.extend(data.get("results", []))
                    else:
                        results.append(data)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON line %d in Dalfox output %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d Dalfox results from file %s", len(results), path)
        return results
    except Exception as e:
        logger.error("Failed to read/parse Dalfox output file %s: %s", path, e, exc_info=True)
        return []


def ingest_dalfox_findings(
    db: Session,
    scan_job_id: str,
    dalfox_results: list[dict],
) -> None:
    """
    Ingest Dalfox findings into the database.
    
    Per-tool idempotency: deletes existing dalfox findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        dalfox_results: List of raw Dalfox result objects
    """
    if not dalfox_results:
        return
    
    from app.models.scan import ScanJob
    from app.models.finding import Finding, Severity, FindingStatus
    import uuid
    
    # Load scan job to get project/tenant/owner info
    scan_job = db.query(ScanJob).options(joinedload(ScanJob.project)).filter(ScanJob.id == scan_job_id).first()
    if not scan_job:
        logger.warning(f"Scan job {scan_job_id} not found, skipping Dalfox findings ingestion")
        return
    
    if not scan_job.project:
        logger.warning(f"Project not found for scan job {scan_job_id}, skipping Dalfox findings ingestion")
        return
    
    # Delete existing dalfox findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "dalfox",
    ).delete(synchronize_session=False)
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing dalfox findings for scan {scan_job_id}")
    
    findings = []
    
    for item in dalfox_results:
        try:
            if not isinstance(item, dict):
                continue
            
            # Extract fields from Dalfox result
            url = item.get("url") or item.get("raw") or ""
            param = item.get("param") or item.get("parameter") or ""
            payload = item.get("payload") or ""
            itype = (item.get("type") or "").lower()
            method = item.get("method") or "GET"
            
            # Severity based on XSS type
            if itype in {"stored", "blind"}:
                severity = Severity.HIGH
            else:  # reflected or unknown
                severity = Severity.MEDIUM
            
            # Build title
            if param:
                title = f"Cross-Site Scripting (XSS) in parameter '{param}'"
            else:
                title = "Cross-Site Scripting (XSS) detected"
            
            # Build description
            description_lines = [
                "Dalfox identified a potential Cross-Site Scripting (XSS) issue.",
            ]
            if param:
                description_lines.append(f"- Parameter: `{param}`")
            if url:
                description_lines.append(f"- Location: `{url}`")
            if payload:
                truncated_payload = payload[:120] + ('…' if len(payload) > 120 else '')
                description_lines.append(f"- Example payload (truncated): `{truncated_payload}`")
            description_lines.append(
                "\nAn attacker could leverage this to execute arbitrary JavaScript "
                "in the victim's browser."
            )
            
            description = "\n".join(description_lines)
            
            # Prepare raw_data with categories
            raw_data = item.copy()
            raw_data["categories"] = ["xss"]
            
            # Create finding
            # Note: project_id, tenant_id, and owner_id are not columns in Finding model
            # They can be accessed via scan_job.project relationship if needed
            finding = Finding(
                scan_job_id=scan_job_id,
                title=title,
                description=description,
                severity=severity,
                status=FindingStatus.OPEN,
                tool_name="dalfox",
                url=url[:2048] if url else None,
                raw_data=json.dumps(raw_data),
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Dalfox finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        if len(findings) > 0:
            logger.info(
                "Ingested %d Dalfox findings into DB for scan %s",
                len(findings), scan_job_id
            )
        else:
            logger.info(
                "Dalfox scan completed for scan %s: no XSS vulnerabilities detected (0 findings ingested)",
                scan_job_id
            )
    except Exception as e:
        logger.error("Failed to commit Dalfox findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
import logging
import json
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from urllib.parse import urlparse

from app.models.finding import Finding, Severity, FindingStatus

logger = logging.getLogger(__name__)


def categorize_nuclei_finding(template_tags: list[str]) -> list[str]:
    """
    Categorize a Nuclei finding based on its template tags.
    
    Normalizes tags to lowercase and returns a list of category strings
    based on the presence of common vulnerability tags.
    
    Args:
        template_tags: List of template tags from Nuclei finding (e.g., ["xss", "sqli", "cve"])
        
    Returns:
        List of category strings (e.g., ["xss", "sqli"])
        
    Example:
        >>> categorize_nuclei_finding(["xss", "sqli", "cve"])
        ["xss", "sqli"]
        >>> categorize_nuclei_finding(["lfi", "rfi"])
        ["dir_traversal"]
    """
    if not template_tags:
        return []
    
    # Normalize tags to lowercase
    tags_lower = [tag.lower() for tag in template_tags if tag]
    
    categories = []
    
    # Map tags to simple lowercase category names (attacker-relevant findings)
    # XSS
    if any(tag in tags_lower for tag in ["xss", "cross-site-scripting"]):
        categories.append("xss")
    
    # SQL Injection
    if any(tag in tags_lower for tag in ["sqli", "sql-injection", "sql"]):
        categories.append("sqli")
    
    # SSRF
    if any(tag in tags_lower for tag in ["ssrf", "server-side-request-forgery"]):
        categories.append("ssrf")
    
    # SSTI
    if any(tag in tags_lower for tag in ["ssti", "server-side-template-injection", "template-injection"]):
        categories.append("ssti")
    
    # XXE
    if any(tag in tags_lower for tag in ["xxe", "xml-external-entity"]):
        categories.append("xxe")
    
    # Directory Traversal (LFI/RFI)
    if any(tag in tags_lower for tag in ["lfi", "rfi", "local-file-inclusion", "remote-file-inclusion", "path-traversal", "directory-traversal", "file-inclusion"]):
        categories.append("directory_traversal")
    
    # CSRF
    if any(tag in tags_lower for tag in ["csrf", "cross-site-request-forgery"]):
        categories.append("csrf")
    
    # CORS
    if any(tag in tags_lower for tag in ["cors", "cross-origin-resource-sharing", "cors-misconfig"]):
        categories.append("cors_misconfig")
    
    # Command Injection
    if any(tag in tags_lower for tag in ["cmdi", "command-injection", "rce", "remote-code-execution", "code-execution", "os-commanding"]):
        categories.append("command_injection")
    
    # IDOR
    if any(tag in tags_lower for tag in ["idor", "insecure-direct-object-reference", "authorization"]):
        categories.append("idor")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_categories = []
    for cat in categories:
        if cat not in seen:
            seen.add(cat)
            unique_categories.append(cat)
    
    return unique_categories


def ingest_nuclei_findings(
    db: Session,
    scan_job_id: str,
    nuclei_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Given a scan_job_id and a list of nuclei JSON objects, create Finding rows.
    
    This function is idempotent: it deletes existing findings for this scan_job
    before inserting new ones, so it can be safely called multiple times.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nuclei_results: List of Nuclei JSON objects (one per finding)
        
    Returns:
        List of created Finding objects
    """
    # Delete existing findings for this scan job AND tool (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "nuclei"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing nuclei findings for scan {scan_job_id}")
    
    findings = []
    
    for nuclei_data in nuclei_results:
        try:
            # Extract severity
            severity_str = nuclei_data.get("info", {}).get("severity", "info")
            if isinstance(severity_str, str):
                severity_str = severity_str.lower()
            else:
                severity_str = "info"
            
            # Normalize severity to allowed enum values
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            # Extract title
            title = (
                nuclei_data.get("info", {}).get("name") or
                nuclei_data.get("template-id") or
                nuclei_data.get("matcher-name") or
                "Nuclei Finding"
            )
            
            # Extract description
            description = nuclei_data.get("info", {}).get("description", "")
            matched_at = nuclei_data.get("matched-at", "")
            if matched_at and description:
                description = f"{description}\n\nMatched at: {matched_at}"
            elif matched_at:
                description = f"Matched at: {matched_at}"
            
            # Extract CVE ID
            cve_id = None
            # Try multiple possible locations for CVE
            if "cve" in nuclei_data:
                cve_id = nuclei_data["cve"]
            elif "info" in nuclei_data and "classification" in nuclei_data["info"]:
                cve_list = nuclei_data["info"]["classification"].get("cve-id", [])
                if cve_list and isinstance(cve_list, list) and len(cve_list) > 0:
                    cve_id = cve_list[0]
                elif isinstance(nuclei_data["info"]["classification"].get("cve-id"), str):
                    cve_id = nuclei_data["info"]["classification"]["cve-id"]
            
            # Extract CWE ID
            cwe_id = None
            if "cwe-id" in nuclei_data:
                cwe_id = nuclei_data["cwe-id"]
            elif "info" in nuclei_data and "classification" in nuclei_data["info"]:
                cwe_list = nuclei_data["info"]["classification"].get("cwe-id", [])
                if cwe_list and isinstance(cwe_list, list) and len(cwe_list) > 0:
                    cwe_id = cwe_list[0]
                elif isinstance(nuclei_data["info"]["classification"].get("cwe-id"), str):
                    cwe_id = nuclei_data["info"]["classification"]["cwe-id"]
            
            # Extract URL
            url = matched_at or nuclei_data.get("host", "")
            
            # Extract template tags for categorization
            template_tags = []
            if "info" in nuclei_data and "tags" in nuclei_data["info"]:
                tags = nuclei_data["info"]["tags"]
                if isinstance(tags, list):
                    template_tags = tags
                elif isinstance(tags, str):
                    # Tags might be comma-separated string
                    template_tags = [t.strip() for t in tags.split(",")]
            
            # Categorize finding based on tags
            categories = categorize_nuclei_finding(template_tags)
            
            # Store raw JSON as string, but add categories to the dict first
            raw_data_dict = nuclei_data.copy() if isinstance(nuclei_data, dict) else {}
            if categories:
                raw_data_dict["categories"] = categories
            
            raw_data = json.dumps(raw_data_dict) if isinstance(raw_data_dict, dict) else json.dumps(nuclei_data) if isinstance(nuclei_data, dict) else str(nuclei_data)
            
            # Create Finding
            finding = Finding(
                scan_job_id=scan_job_id,
                title=title[:500],  # Ensure title fits in column
                description=description,
                severity=severity,
                cve_id=cve_id[:50] if cve_id else None,  # Ensure CVE ID fits
                cwe_id=cwe_id[:50] if cwe_id else None,  # Ensure CWE ID fits
                url=url[:2048] if url else None,  # Ensure URL fits
                tool_name="nuclei",
                raw_data=raw_data,
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nuclei finding: {e}", exc_info=True)
            logger.debug(f"Problematic Nuclei data: {nuclei_data}")
            continue
    
    # Commit all findings at once
    try:
        db.commit()
        logger.info(
            "Ingested %d nuclei findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def parse_nuclei_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nuclei JSONL output file (one JSON object per line) into a list of dicts.
    
    This function is robust to non-JSON lines (like ASCII tables, logs, etc.)
    and will skip them gracefully. Handles empty files and zero-byte files.
    
    Args:
        path: Path to the Nuclei output file (JSONL format)
        
    Returns:
        List of parsed Nuclei JSON objects (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    # Check if file is zero bytes
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                
                # Skip obvious non-JSON lines (tables, logs, etc.)
                # JSON objects/arrays start with { or [
                if not (line.startswith("{") or line.startswith("[")):
                    logger.debug(
                        "Skipping non-JSON line %d in nuclei output %s: %r",
                        line_no, path, line[:80]
                    )
                    continue
                
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        findings.append(obj)
                    else:
                        logger.debug("Skipping non-dict JSON on line %d in %s", line_no, path)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON line %d in nuclei output %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
                except Exception as e:
                    logger.warning(
                        "Unexpected error parsing line %d in %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d nuclei findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse Nuclei output file %s: %s", path, e, exc_info=True)
        return []


def parse_nmap_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nmap XML output file into a list of finding dicts.
    
    Each open port becomes a finding. Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the Nmap XML output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Extract host information
        for host in root.findall("host"):
            host_status = host.find("status")
            if host_status is None or host_status.get("state") != "up":
                continue
            
            # Get host address
            address_elem = host.find("address")
            host_ip = address_elem.get("addr") if address_elem is not None else "unknown"
            
            # Get hostname
            hostnames_elem = host.find("hostnames")
            hostname = host_ip
            if hostnames_elem is not None:
                hostname_elem = hostnames_elem.find("hostname")
                if hostname_elem is not None:
                    hostname = hostname_elem.get("name", host_ip)
            
            # Process ports
            ports_elem = host.find("ports")
            if ports_elem is None:
                continue
            
            for port_elem in ports_elem.findall("port"):
                port_state = port_elem.find("state")
                if port_state is None or port_state.get("state") != "open":
                    continue
                
                port_num = port_elem.get("portid")
                protocol = port_elem.get("protocol", "tcp")
                
                # Get service info
                service_elem = port_elem.find("service")
                service_name = service_elem.get("name", "unknown") if service_elem is not None else "unknown"
                service_product = service_elem.get("product", "") if service_elem is not None else ""
                service_version = service_elem.get("version", "") if service_elem is not None else ""
                
                # Build description
                description_parts = [
                    f"Host: {hostname} ({host_ip})",
                    f"Port: {port_num}/{protocol}",
                    f"Service: {service_name}",
                ]
                if service_product:
                    description_parts.append(f"Product: {service_product}")
                if service_version:
                    description_parts.append(f"Version: {service_version}")
                
                description = "\n".join(description_parts)
                
                # Determine severity based on port/service
                severity = "info"
                if port_num in ["22", "3389", "5900"]:  # SSH, RDP, VNC
                    severity = "medium"
                elif port_num in ["3306", "5432", "1433"]:  # MySQL, PostgreSQL, MSSQL
                    severity = "medium"
                elif port_num in ["21", "23", "25"]:  # FTP, Telnet, SMTP
                    severity = "low"
                elif port_num in ["80", "443", "8080", "8443"]:  # HTTP/HTTPS
                    severity = "info"
                
                # Build title
                title = f"Open port {port_num}/{protocol} ({service_name}) on {hostname}"
                
                # Build URL
                url = f"{hostname}:{port_num}"
                if port_num in ["80", "8080"]:
                    url = f"http://{hostname}:{port_num}"
                elif port_num in ["443", "8443"]:
                    url = f"https://{hostname}:{port_num}"
                
                # Store raw XML for this port as JSON
                raw_data = json.dumps({
                    "host": hostname,
                    "ip": host_ip,
                    "port": port_num,
                    "protocol": protocol,
                    "service": service_name,
                    "product": service_product,
                    "version": service_version,
                })
                
                findings.append({
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "cve_id": None,
                    "cwe_id": None,
                    "url": url,
                    "tool_name": "nmap",
                    "raw_data": raw_data,
                })
        
        logger.info("Parsed %d nmap findings from file for scan %s", len(findings), path)
        return findings
        
    except ET.ParseError as e:
        logger.warning("Failed to parse Nmap XML file %s: %s", path, e)
        return []
    except Exception as e:
        logger.error("Failed to read/parse Nmap output file %s: %s", path, e, exc_info=True)
        return []


def parse_sslscan_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse sslscan output file (JSON or text format) into a list of finding dicts.
    
    Handles both JSON output (when --json flag is used) and plain text output.
    Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the sslscan output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        # Try to parse as JSON first
        try:
            # Remove ANSI color codes if present
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            content_clean = ansi_escape.sub('', content)
            
            # Try to find JSON object/array
            json_start = content_clean.find('{')
            json_end = content_clean.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content_clean[json_start:json_end]
                data = json.loads(json_str)
                
                # Handle JSON format
                if isinstance(data, dict):
                    # Single JSON object
                    findings.extend(_parse_sslscan_json_object(data))
                elif isinstance(data, list):
                    # Array of JSON objects
                    for item in data:
                        if isinstance(item, dict):
                            findings.extend(_parse_sslscan_json_object(item))
        except (json.JSONDecodeError, ValueError):
            # Fall back to text parsing
            findings.extend(_parse_sslscan_text(content))
        
        logger.info("Parsed %d sslscan findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse sslscan output file %s: %s", path, e, exc_info=True)
        return []


def _parse_sslscan_json_object(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse a single sslscan JSON object into finding dicts"""
    findings = []
    
    host = data.get("host", "unknown")
    port = data.get("port", 443)
    target = f"{host}:{port}"
    
    # Check for weak protocols
    sslv2 = data.get("ssl_version", {}).get("SSLv2", {}).get("status", "").lower()
    sslv3 = data.get("ssl_version", {}).get("SSLv3", {}).get("status", "").lower()
    tls10 = data.get("ssl_version", {}).get("TLSv1.0", {}).get("status", "").lower()
    tls11 = data.get("ssl_version", {}).get("TLSv1.1", {}).get("status", "").lower()
    
    if sslv2 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if sslv3 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls10 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls11 == "enabled":
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    # Check for weak ciphers
    ciphers = data.get("cipher_suites", [])
    weak_ciphers = []
    for cipher in ciphers:
        cipher_name = cipher.get("cipher", "")
        key_length = cipher.get("key_length", 0)
        if key_length < 128 or "RC4" in cipher_name or "DES" in cipher_name or "MD5" in cipher_name:
            weak_ciphers.append(cipher_name)
    
    if weak_ciphers:
        findings.append({
            "severity": "medium",
            "title": f"Weak cipher suites detected on {target}",
            "description": f"Weak cipher suites found on {target}: {', '.join(weak_ciphers[:5])}",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    return findings


def _parse_sslscan_text(content: str) -> List[Dict[str, Any]]:
    """Parse sslscan plain text output into finding dicts"""
    findings = []
    
    # Remove ANSI color codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    content_clean = ansi_escape.sub('', content)
    
    # Extract host and port from content
    host_match = re.search(r'Testing SSL server\s+(\S+)\s+on port\s+(\d+)', content_clean)
    if not host_match:
        # Try alternative pattern
        host_match = re.search(r'Connected to\s+([\d.]+)', content_clean)
        port_match = re.search(r'port\s+(\d+)', content_clean)
        host = host_match.group(1) if host_match else "unknown"
        port = int(port_match.group(1)) if port_match else 443
    else:
        host = host_match.group(1)
        port = int(host_match.group(2))
    
    target = f"{host}:{port}"
    
    # Check for weak protocols in text
    if re.search(r'SSLv2\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],  # Store first 1000 chars
        })
    
    if re.search(r'SSLv3\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.0\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.1\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    return findings


def ingest_nmap_findings(
    db: Session,
    scan_job_id: str,
    nmap_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Ingest Nmap findings into the database.
    
    Per-tool idempotency: deletes existing nmap findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nmap_results: List of finding dicts from parse_nmap_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing nmap findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "nmap"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing nmap findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in nmap_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "Nmap Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="nmap",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nmap finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        logger.info(
            "Ingested %d nmap findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit nmap findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_sslscan_findings(
    db: Session,
    scan_job_id: str,
    sslscan_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Ingest sslscan findings into the database.
    
    Per-tool idempotency: deletes existing sslscan findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        sslscan_results: List of finding dicts from parse_sslscan_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing sslscan findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "sslscan"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing sslscan findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in sslscan_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "SSL/TLS Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="sslscan",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse sslscan finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        logger.info(
            "Ingested %d sslscan findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit sslscan findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_http_header_findings(
    db: Session,
    scan_job_id: str,
    header_findings: List[Finding],
) -> List[Finding]:
    """
    Ingest HTTP header findings into the database.
    
    Per-tool idempotency: deletes existing http_headers findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        header_findings: List of Finding objects for missing headers
        
    Returns:
        List of created Finding objects
    """
    # Delete existing http_headers findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "http_headers"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing http_headers findings for scan {scan_job_id}")
    
    # Add all findings to session
    for finding in header_findings:
        db.add(finding)
    
    # Commit all findings at once
    try:
        db.commit()
        logger.info(
            "Ingested %d http_headers findings into DB for scan %s",
            len(header_findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit http_headers findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return header_findings


def parse_dalfox_output(path: Path) -> list[dict]:
    """
    Parse Dalfox JSON output file into a list of finding dicts.
    
    Dalfox with --output-type json produces JSON output that can be:
    - A single JSON object with "results" array
    - Line-delimited JSON (one JSON object per line)
    
    Args:
        path: Path to the Dalfox JSON output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing or parsing fails)
    """
    results: list[dict] = []
    
    if not path.exists():
        logger.info("Dalfox output file is missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Dalfox output file is empty for %s; treating as no findings", path)
        return []
    
    try:
        raw = path.read_text().strip()
        if not raw:
            return []
        
        # Try parsing as single JSON object first (with "results" array)
        try:
            data = json.loads(raw)
            # Check if it's wrapped in "results" key
            if isinstance(data, dict) and "results" in data:
                results_list = data.get("results", [])
                if isinstance(results_list, list):
                    results.extend(results_list)
                else:
                    results.append(data)
            elif isinstance(data, list):
                # Already an array
                results.extend(data)
            else:
                # Single object
                results.append(data)
        except json.JSONDecodeError:
            # Try line-by-line parsing (NDJSON format)
            for line_no, line in enumerate(raw.splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    # Handle both wrapped and direct formats
                    if isinstance(data, dict) and "results" in data:
                        results.extend(data.get("results", []))
                    else:
                        results.append(data)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON line %d in Dalfox output %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d Dalfox results from file %s", len(results), path)
        return results
    except Exception as e:
        logger.error("Failed to read/parse Dalfox output file %s: %s", path, e, exc_info=True)
        return []


def ingest_dalfox_findings(
    db: Session,
    scan_job_id: str,
    dalfox_results: list[dict],
) -> None:
    """
    Ingest Dalfox findings into the database.
    
    Per-tool idempotency: deletes existing dalfox findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        dalfox_results: List of raw Dalfox result objects
    """
    if not dalfox_results:
        return
    
    from app.models.scan import ScanJob
    from app.models.finding import Finding, Severity, FindingStatus
    import uuid
    
    # Load scan job to get project/tenant/owner info
    scan_job = db.query(ScanJob).options(joinedload(ScanJob.project)).filter(ScanJob.id == scan_job_id).first()
    if not scan_job:
        logger.warning(f"Scan job {scan_job_id} not found, skipping Dalfox findings ingestion")
        return
    
    if not scan_job.project:
        logger.warning(f"Project not found for scan job {scan_job_id}, skipping Dalfox findings ingestion")
        return
    
    # Delete existing dalfox findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "dalfox",
    ).delete(synchronize_session=False)
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing dalfox findings for scan {scan_job_id}")
    
    findings = []
    
    for item in dalfox_results:
        try:
            if not isinstance(item, dict):
                continue
            
            # Extract fields from Dalfox result
            url = item.get("url") or item.get("raw") or ""
            param = item.get("param") or item.get("parameter") or ""
            payload = item.get("payload") or ""
            itype = (item.get("type") or "").lower()
            method = item.get("method") or "GET"
            
            # Severity based on XSS type
            if itype in {"stored", "blind"}:
                severity = Severity.HIGH
            else:  # reflected or unknown
                severity = Severity.MEDIUM
            
            # Build title
            if param:
                title = f"Cross-Site Scripting (XSS) in parameter '{param}'"
            else:
                title = "Cross-Site Scripting (XSS) detected"
            
            # Build description
            description_lines = [
                "Dalfox identified a potential Cross-Site Scripting (XSS) issue.",
            ]
            if param:
                description_lines.append(f"- Parameter: `{param}`")
            if url:
                description_lines.append(f"- Location: `{url}`")
            if payload:
                truncated_payload = payload[:120] + ('…' if len(payload) > 120 else '')
                description_lines.append(f"- Example payload (truncated): `{truncated_payload}`")
            description_lines.append(
                "\nAn attacker could leverage this to execute arbitrary JavaScript "
                "in the victim's browser."
            )
            
            description = "\n".join(description_lines)
            
            # Prepare raw_data with categories
            raw_data = item.copy()
            raw_data["categories"] = ["xss"]
            
            # Create finding
            # Note: project_id, tenant_id, and owner_id are not columns in Finding model
            # They can be accessed via scan_job.project relationship if needed
            finding = Finding(
                scan_job_id=scan_job_id,
                title=title,
                description=description,
                severity=severity,
                status=FindingStatus.OPEN,
                tool_name="dalfox",
                url=url[:2048] if url else None,
                raw_data=json.dumps(raw_data),
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Dalfox finding: {e}", exc_info=True)
            continue
    
    try:
        db.commit()
        if len(findings) > 0:
            logger.info(
                "Ingested %d Dalfox findings into DB for scan %s",
                len(findings), scan_job_id
            )
        else:
            logger.info(
                "Dalfox scan completed for scan %s: no XSS vulnerabilities detected (0 findings ingested)",
                scan_job_id
            )
    except Exception as e:
        logger.error("Failed to commit Dalfox findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise

