"""
SSLScan output parser
Parses SSLScan JSON or text output into normalized findings
"""
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def parse_sslscan_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse sslscan output file (JSON or text format) into normalized findings.
    
    Returns a list of normalized finding dicts with fields:
    - tool_id: "sslscan"
    - title: Finding title
    - severity: "critical", "high", "medium", "low", "info"
    - description: Finding description
    - evidence: Evidence string
    - host: Target host
    - timestamp: ISO timestamp
    - raw: Original JSON object (optional)
    
    Args:
        path: Path to the sslscan output file
        
    Returns:
        List of normalized finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("sslscan output file is empty for %s; treating as no findings", path)
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
                    findings.extend(_parse_sslscan_json_object(data))
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            findings.extend(_parse_sslscan_json_object(item))
        except (json.JSONDecodeError, ValueError):
            # Fall back to text parsing
            findings.extend(_parse_sslscan_text(content))
        
        logger.info("Parsed %d sslscan findings from file %s", len(findings), path)
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
    
    # Extract timestamp
    timestamp = data.get("timestamp") or data.get("time")
    if timestamp:
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        elif not isinstance(timestamp, str):
            timestamp = None
    else:
        timestamp = datetime.now(timezone.utc).isoformat()
    
    # Check for weak protocols
    ssl_version = data.get("ssl_version", {})
    
    sslv2 = ssl_version.get("SSLv2", {}).get("status", "").lower()
    if sslv2 == "enabled":
        findings.append({
            "tool_id": "sslscan",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "severity": "high",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "evidence": f"SSLv2 protocol enabled on {target}",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "host": host,
            "timestamp": timestamp,
            "raw": data,
            "cve_id": None,
            "cwe_id": "CWE-327",
        })
    
    sslv3 = ssl_version.get("SSLv3", {}).get("status", "").lower()
    if sslv3 == "enabled":
        findings.append({
            "tool_id": "sslscan",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "severity": "high",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "evidence": f"SSLv3 protocol enabled on {target}",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "host": host,
            "timestamp": timestamp,
            "raw": data,
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
        })
    
    tls10 = ssl_version.get("TLSv1.0", {}).get("status", "").lower()
    if tls10 == "enabled":
        findings.append({
            "tool_id": "sslscan",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "severity": "high",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "evidence": f"TLSv1.0 protocol enabled on {target}",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "host": host,
            "timestamp": timestamp,
            "raw": data,
            "cve_id": None,
            "cwe_id": "CWE-327",
        })
    
    tls11 = ssl_version.get("TLSv1.1", {}).get("status", "").lower()
    if tls11 == "enabled":
        findings.append({
            "tool_id": "sslscan",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "severity": "medium",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "evidence": f"TLSv1.1 protocol enabled on {target}",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "host": host,
            "timestamp": timestamp,
            "raw": data,
            "cve_id": None,
            "cwe_id": "CWE-327",
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
            "tool_id": "sslscan",
            "title": f"Weak cipher suites detected on {target}",
            "severity": "medium",
            "description": f"Weak cipher suites found on {target}: {', '.join(weak_ciphers[:5])}",
            "evidence": f"Weak ciphers: {', '.join(weak_ciphers[:5])}",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "host": host,
            "timestamp": timestamp,
            "raw": data,
            "cve_id": None,
            "cwe_id": "CWE-327",
        })
    
    # Check for certificate issues
    cert = data.get("certificate", {})
    if cert:
        # Check for expired certificate
        if cert.get("expired"):
            findings.append({
                "tool_id": "sslscan",
                "title": f"Expired certificate on {target}",
                "severity": "high",
                "description": f"Certificate on {target} has expired.",
                "evidence": f"Certificate expired on {target}",
                "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
                "host": host,
                "timestamp": timestamp,
                "raw": data,
                "cve_id": None,
                "cwe_id": None,
            })
        
        # Check for self-signed certificate
        if cert.get("self_signed") or cert.get("self-signed"):
            findings.append({
                "tool_id": "sslscan",
                "title": f"Self-signed certificate on {target}",
                "severity": "medium",
                "description": f"Certificate on {target} is self-signed.",
                "evidence": f"Self-signed certificate on {target}",
                "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
                "host": host,
                "timestamp": timestamp,
                "raw": data,
                "cve_id": None,
                "cwe_id": None,
            })
    
    return findings


def _parse_sslscan_text(content: str) -> List[Dict[str, Any]]:
    """Parse sslscan plain text output into finding dicts"""
    findings = []
    
    # Remove ANSI color codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    content_clean = ansi_escape.sub('', content)
    
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Extract host and port from output
    # Look for patterns like "Connected to 81.169.145.156" or "Testing SSL server demo.owasp-juice.shop on port 443"
    host = None
    port = 443
    url = None
    
    host_match = re.search(r'Connected to\s+([^\s\n]+)', content_clean, re.IGNORECASE)
    if host_match:
        host = host_match.group(1)
    
    server_match = re.search(r'Testing SSL server\s+([^\s\n]+)\s+on port\s+(\d+)', content_clean, re.IGNORECASE)
    if server_match:
        host = server_match.group(1)
        port = int(server_match.group(2))
    
    if host:
        url = f"https://{host}:{port}" if port == 443 else f"https://{host}:{port}"
    
    # Look for protocol version indicators - check for "disabled" vs "enabled"
    # Only report findings if protocols are enabled (not disabled)
    sslv2_match = re.search(r'SSLv2\s+(\w+)', content_clean, re.IGNORECASE)
    if sslv2_match and sslv2_match.group(1).lower() == "enabled":
        findings.append({
            "tool_id": "sslscan",
            "title": f"Weak SSL protocol enabled (SSLv2) on {host or 'target'}:{port}",
            "severity": "high",
            "description": f"SSLv2 is enabled on {host or 'target'}:{port}. SSLv2 is deprecated and vulnerable.",
            "evidence": f"SSLv2 protocol enabled on {host or 'target'}:{port}",
            "url": url,
            "host": host,
            "timestamp": timestamp,
            "raw": content,
            "cve_id": None,
            "cwe_id": "CWE-327",
        })
    
    sslv3_match = re.search(r'SSLv3\s+(\w+)', content_clean, re.IGNORECASE)
    if sslv3_match and sslv3_match.group(1).lower() == "enabled":
        findings.append({
            "tool_id": "sslscan",
            "title": f"Weak SSL protocol enabled (SSLv3) on {host or 'target'}:{port}",
            "severity": "high",
            "description": f"SSLv3 is enabled on {host or 'target'}:{port}. SSLv3 is vulnerable to POODLE attack.",
            "evidence": f"SSLv3 protocol enabled on {host or 'target'}:{port}",
            "url": url,
            "host": host,
            "timestamp": timestamp,
            "raw": content,
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
        })
    
    tls10_match = re.search(r'TLSv1\.0\s+(\w+)', content_clean, re.IGNORECASE)
    if tls10_match and tls10_match.group(1).lower() == "enabled":
        findings.append({
            "tool_id": "sslscan",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {host or 'target'}:{port}",
            "severity": "high",
            "description": f"TLSv1.0 is enabled on {host or 'target'}:{port}. TLSv1.0 is deprecated and should be disabled.",
            "evidence": f"TLSv1.0 protocol enabled on {host or 'target'}:{port}",
            "url": url,
            "host": host,
            "timestamp": timestamp,
            "raw": content,
            "cve_id": None,
            "cwe_id": "CWE-327",
        })
    
    tls11_match = re.search(r'TLSv1\.1\s+(\w+)', content_clean, re.IGNORECASE)
    if tls11_match and tls11_match.group(1).lower() == "enabled":
        findings.append({
            "tool_id": "sslscan",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {host or 'target'}:{port}",
            "severity": "medium",
            "description": f"TLSv1.1 is enabled on {host or 'target'}:{port}. TLSv1.1 is deprecated and should be disabled.",
            "evidence": f"TLSv1.1 protocol enabled on {host or 'target'}:{port}",
            "url": url,
            "host": host,
            "timestamp": timestamp,
            "raw": content,
            "cve_id": None,
            "cwe_id": "CWE-327",
        })
    
    # Look for weak cipher indicators - check for weak ciphers in the cipher list
    # Look for patterns like "bits  ECDHE-RSA-AES256-SHA" (no "GCM" means CBC mode, which is weaker)
    weak_cipher_patterns = [
        r'\d+\s+bits\s+(?:ECDHE-)?RSA-AES\d+-SHA(?!256)',  # AES-CBC (not GCM)
        r'RC4',
        r'DES',
        r'MD5',
    ]
    
    weak_ciphers_found = []
    for pattern in weak_cipher_patterns:
        if re.search(pattern, content_clean, re.IGNORECASE):
            # Extract cipher name
            cipher_match = re.search(r'(\w+(?:-\w+)*)', content_clean)
            if cipher_match:
                weak_ciphers_found.append(cipher_match.group(1))
    
    if weak_ciphers_found:
        findings.append({
            "tool_id": "sslscan",
            "title": f"Weak cipher suites detected on {host or 'target'}:{port}",
            "severity": "medium",
            "description": f"Weak cipher suites detected on {host or 'target'}:{port}. Weak ciphers: {', '.join(weak_ciphers_found[:5])}",
            "evidence": f"Weak ciphers detected: {', '.join(weak_ciphers_found[:5])}",
            "url": url,
            "host": host,
            "timestamp": timestamp,
            "raw": content,
            "cve_id": None,
            "cwe_id": "CWE-327",
        })
    
    return findings

