"""
Dalfox output parser for XSS findings
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def parse_dalfox_output(output_file: Path) -> List[Dict[str, Any]]:
    """
    Parse Dalfox JSON output file into a list of finding dicts.
    
    Dalfox outputs JSON array format with XSS findings.
    Each finding contains information about the XSS vulnerability.
    
    Args:
        output_file: Path to the dalfox output file (JSON format)
        
    Returns:
        List of parsed dalfox finding dicts (empty list if no findings)
    """
    if not output_file.exists():
        logger.info(f"Dalfox output file does not exist: {output_file}")
        return []
    
    file_size = output_file.stat().st_size
    if file_size == 0:
        logger.info(f"Dalfox output file is empty: {output_file}")
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        content = output_file.read_text(encoding="utf-8", errors="ignore")
        
        # Handle empty content
        if not content or not content.strip():
            logger.info(f"Dalfox output file has no content: {output_file}")
            return []
        
        # Parse JSON - handle malformed JSON by trying to repair it
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse dalfox JSON from {output_file}: {e}. Attempting to repair...")
            # Try to repair common JSON issues:
            # 1. Truncated JSON - try to find last complete object
            # 2. Missing closing bracket
            # 3. Trailing comma
            try:
                # Try to find the last complete JSON object/array
                # Look for the last '}' or ']' that might close the structure
                repaired = content.rstrip()
                # Remove trailing comma if present
                if repaired.rstrip().endswith(','):
                    repaired = repaired.rstrip()[:-1]
                # Try to close unclosed arrays/objects
                open_braces = repaired.count('{') - repaired.count('}')
                open_brackets = repaired.count('[') - repaired.count(']')
                if open_braces > 0:
                    repaired += '}' * open_braces
                if open_brackets > 0:
                    repaired += ']' * open_brackets
                # Try parsing repaired JSON
                data = json.loads(repaired)
                logger.info(f"Successfully repaired and parsed dalfox JSON from {output_file}")
            except (json.JSONDecodeError, ValueError) as repair_error:
                # If repair fails, try NDJSON parsing (line-by-line)
                logger.warning(f"JSON repair failed, trying NDJSON parsing: {repair_error}")
                data = []
                for line_no, line in enumerate(content.splitlines(), 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        line_data = json.loads(line)
                        if isinstance(line_data, dict):
                            data.append(line_data)
                        elif isinstance(line_data, list):
                            data.extend(line_data)
                    except json.JSONDecodeError:
                        continue
                if not data:
                    logger.error(f"Failed to parse dalfox output from {output_file} as JSON or NDJSON")
                    return []
        
        # Dalfox outputs an array of findings
        if not isinstance(data, list):
            logger.warning(f"Dalfox output is not a list: {type(data)}")
            return []
        
        # Filter out empty objects
        for item in data:
            if not isinstance(item, dict):
                continue
            
            # Skip truly empty dicts
            if not item or len(item) == 0:
                continue
            
            # Skip dicts with only None/empty values
            has_data = any(v is not None and str(v).strip() for v in item.values())
            if not has_data:
                continue
            
            # This is a real finding - normalize it
            # Dalfox actual output fields:
            # - message_str: Human-readable message
            # - data: Full URL with payload
            # - param: Parameter name
            # - payload: XSS payload used
            # - evidence: Evidence from page
            # - cwe: CWE-79
            # - severity: High/Medium/Low
            # - type: V (Verified), R (Reflected), etc.
            
            finding = {
                "tool_id": "dalfox",
                "title": item.get("message_str") or item.get("message") or "XSS Vulnerability",
                "description": item.get("evidence") or item.get("message_str") or "",
                "severity": _map_dalfox_severity(item.get("severity") or item.get("cwe")),
                "url": item.get("data") or item.get("url") or "",
                "parameter": item.get("param") or item.get("parameter") or "",
                "http_method": item.get("method", "GET").upper() if item.get("method") else "GET",
                "evidence": item.get("payload") or item.get("evidence") or "",
                "cwe_id": item.get("cwe"),
                "raw": item,
            }
            
            findings.append(finding)
        
        logger.info(f"Parsed {len(findings)} dalfox findings from {output_file}")
        return findings
        
    except Exception as e:
        logger.error(f"Failed to parse dalfox output from {output_file}: {e}", exc_info=True)
        return []


def _map_dalfox_severity(severity_str: str | None) -> str:
    """
    Map dalfox severity to standard severity levels.
    
    Args:
        severity_str: Dalfox severity string or CWE ID
        
    Returns:
        Normalized severity: critical/high/medium/low/info
    """
    if not severity_str:
        return "medium"  # XSS is typically medium severity
    
    severity_lower = str(severity_str).lower()
    
    # Direct severity mappings
    if "critical" in severity_lower or "high" in severity_lower:
        return "high"
    elif "medium" in severity_lower:
        return "medium"
    elif "low" in severity_lower:
        return "low"
    elif "info" in severity_lower:
        return "info"
    
    # CWE-based severity (XSS is typically medium-high)
    if "79" in severity_lower:  # CWE-79: XSS
        return "medium"
    
    # Default for XSS
    return "medium"
