"""
HTTPx output parser
Parses HTTPx JSONL output into normalized findings
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def parse_httpx_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse httpx JSONL output file into normalized findings.
    
    Returns a list of normalized finding dicts with fields:
    - tool_id: "httpx"
    - title: Finding title
    - severity: "info" (httpx findings are informational)
    - description: Finding description
    - evidence: Evidence string
    - url: Discovered URL
    - timestamp: ISO timestamp
    - raw: Original JSON object (optional)
    
    Args:
        path: Path to the httpx JSONL output file
        
    Returns:
        List of normalized finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("httpx output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("httpx output file is empty for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    seen: set = set()
    
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
                    
                    # Build evidence
                    evidence_parts = []
                    if status_code:
                        evidence_parts.append(f"Status: {status_code}")
                    if tech:
                        evidence_parts.append(f"Tech: {', '.join(tech[:5])}")
                    if tls_version:
                        evidence_parts.append(f"TLS: {tls_version}")
                    
                    evidence = ". ".join(evidence_parts) if evidence_parts else None
                    
                    # Extract timestamp
                    timestamp = data.get("timestamp") or data.get("time")
                    if timestamp:
                        if isinstance(timestamp, (int, float)):
                            timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
                        elif not isinstance(timestamp, str):
                            timestamp = None
                    else:
                        timestamp = datetime.now(timezone.utc).isoformat()
                    
                    # Extract host from URL
                    host = None
                    if url:
                        try:
                            from urllib.parse import urlparse
                            parsed = urlparse(url)
                            host = parsed.netloc or parsed.hostname
                        except:
                            pass
                    
                    finding_key = (url, status_code, title, tls_version)
                    if finding_key in seen:
                        continue
                    seen.add(finding_key)

                    finding = {
                        "tool_id": "httpx",
                        "title": finding_title[:500],
                        "severity": "info",
                        "description": description,
                        "evidence": evidence,
                        "url": url[:2048] if url else None,
                        "host": host,
                        "timestamp": timestamp,
                        "raw": data,  # Include full raw data
                    }
                    
                    findings.append(finding)
                    
                except json.JSONDecodeError:
                    logger.debug("Skipping non-JSON line %d in httpx output %s", line_no, path)
                    continue
                except Exception as e:
                    logger.warning(
                        "Unexpected error parsing line %d in %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d httpx findings from file %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse httpx output file %s: %s", path, e, exc_info=True)
        return []

