import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def parse_sqlmap_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse SQLMap output (stdout text) into normalized findings.
    
    SQLMap outputs to stdout with patterns like:
    - "GET parameter 'X' is vulnerable"
    - "POST parameter 'Y' is vulnerable"
    - "sqlmap identified the following injection point(s)"
    
    Args:
        path: Path to the SQLMap output file (JSON or text)
        
    Returns:
        List of normalized finding dicts
    """
    if not path.exists():
        logger.info("SQLMap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("SQLMap output file is empty for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        if not content or not content.strip():
            logger.info("SQLMap output file is empty for %s", path)
            return []
        
        # SQLMap outputs text to stdout, not JSON
        # Look for vulnerability indicators in the text
        
        # Pattern 1: "parameter 'X' is vulnerable"
        vulnerable_param_pattern = re.compile(
            r"(GET|POST|Cookie|User-Agent|Referer|Header)\s+parameter\s+['\"]([^'\"]+)['\"]\s+is\s+vulnerable",
            re.IGNORECASE
        )
        
        # Pattern 2: "sqlmap identified the following injection point(s)"
        injection_point_pattern = re.compile(
            r"sqlmap\s+identified\s+the\s+following\s+injection\s+point\(s\)",
            re.IGNORECASE
        )
        
        # Pattern 3: "is 'X' injectable" or "appears to be 'X' injectable"
        injectable_pattern = re.compile(
            r"(is|appears\s+to\s+be)\s+['\"]([^'\"]+)['\"]\s+injectable",
            re.IGNORECASE
        )
        
        # Pattern 4: Database information extraction
        db_info_pattern = re.compile(
            r"(database|dbms|back-end\s+dbms|web\s+server|web\s+application\s+technology):\s*(.+)",
            re.IGNORECASE
        )
        
        # Extract URL from content if present
        url_match = re.search(r"target\s+url:\s*(https?://[^\s]+)", content, re.IGNORECASE)
        target_url = url_match.group(1) if url_match else None
        
        # Extract host and port from URL
        host = None
        port = None
        if target_url:
            parsed_url = urlparse(target_url)
            host = parsed_url.hostname
            port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
        
        # Check for vulnerable parameters
        vulnerable_params = []
        for match in vulnerable_param_pattern.finditer(content):
            param_type = match.group(1)
            param_name = match.group(2)
            vulnerable_params.append(f"{param_type} parameter '{param_name}'")
        
        # Check for injection points
        has_injection_points = bool(injection_point_pattern.search(content))
        
        # Check for injectable parameters
        injectable_params = []
        for match in injectable_pattern.finditer(content):
            injectable_type = match.group(2)
            injectable_params.append(injectable_type)
        
        # Extract database information
        db_info = {}
        for match in db_info_pattern.finditer(content):
            key = match.group(1).strip().lower().replace(" ", "_")
            value = match.group(2).strip()
            db_info[key] = value
        
        # Determine severity based on findings
        if vulnerable_params or has_injection_points:
            severity = "critical"
        elif injectable_params:
            severity = "high"
        elif db_info:
            severity = "medium"
        else:
            # No SQL injection found
            return []
        
        # Create finding(s)
        if vulnerable_params or has_injection_points:
            # Create one finding per vulnerable parameter or one for injection points
            if vulnerable_params:
                for param_desc in vulnerable_params:
                    findings.append({
                        "tool_id": "sqlmap",
                        "title": f"SQL Injection Vulnerability: {param_desc}",
                        "severity": severity,
                        "description": f"SQLMap detected SQL injection vulnerability in {param_desc}. The parameter is vulnerable to SQL injection attacks.",
                        "evidence": content[:2000],  # First 2000 chars as evidence
                        "url": target_url,
                        "host": host,
                        "port": port,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "raw": json.dumps({"parameter": param_desc, "content_preview": content[:500]}),
                    })
            else:
                # Injection points found but no specific parameter mentioned
                findings.append({
                    "tool_id": "sqlmap",
                    "title": "SQL Injection Vulnerability Detected",
                    "severity": severity,
                    "description": "SQLMap identified SQL injection point(s) in the target application.",
                    "evidence": content[:2000],
                    "url": target_url,
                    "host": host,
                    "port": port,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "raw": json.dumps({"injection_points": True, "content_preview": content[:500]}),
                })
        elif injectable_params:
            # Injectable but not confirmed vulnerable
            for injectable_type in injectable_params:
                findings.append({
                    "tool_id": "sqlmap",
                    "title": f"Potential SQL Injection: {injectable_type}",
                    "severity": severity,
                    "description": f"SQLMap detected potential SQL injection vulnerability ({injectable_type}). Further investigation recommended.",
                    "evidence": content[:2000],
                    "url": target_url,
                    "host": host,
                    "port": port,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "raw": json.dumps({"injectable_type": injectable_type, "content_preview": content[:500]}),
                })
        elif db_info:
            # Database information extracted (indicates successful injection)
            findings.append({
                "tool_id": "sqlmap",
                "title": "SQL Injection: Database Information Extracted",
                "severity": severity,
                "description": f"SQLMap successfully extracted database information: {', '.join(f'{k}={v}' for k, v in db_info.items())}",
                "evidence": content[:2000],
                "url": target_url,
                "host": host,
                "port": port,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "raw": json.dumps({"db_info": db_info, "content_preview": content[:500]}),
            })
        
        logger.info(f"Parsed {len(findings)} findings from SQLMap output")
        return findings
        
    except json.JSONDecodeError:
        # Not JSON, try text parsing (which we do above)
        logger.debug("SQLMap output is not JSON, parsing as text")
        return findings
    except Exception as e:
        logger.error(f"Failed to parse SQLMap output from {path}: {e}", exc_info=True)
        return []




