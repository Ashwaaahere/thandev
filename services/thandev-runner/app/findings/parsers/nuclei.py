"""
Nuclei output parser
Parses Nuclei JSONL output into normalized findings
"""
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


def parse_nuclei_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nuclei JSONL output file (one JSON object per line) into normalized findings.
    
    Returns a list of normalized finding dicts with fields:
    - tool_id: "nuclei"
    - title: Finding title
    - severity: "critical", "high", "medium", "low", "info"
    - description: Finding description
    - evidence: Evidence string
    - url: Matched URL
    - timestamp: ISO timestamp
    - raw: Original JSON object (optional)
    
    Args:
        path: Path to the Nuclei output file (JSONL format)
        
    Returns:
        List of normalized finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nuclei output file is empty for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                
                # Skip obvious non-JSON lines
                if not (line.startswith("{") or line.startswith("[")):
                    logger.debug(
                        "Skipping non-JSON line %d in nuclei output %s: %r",
                        line_no, path, line[:80]
                    )
                    continue
                
                try:
                    nuclei_data = json.loads(line)
                    if not isinstance(nuclei_data, dict):
                        logger.debug("Skipping non-dict JSON on line %d in %s", line_no, path)
                        continue
                    
                    # Extract severity
                    severity_str = "info"
                    if "info" in nuclei_data and "severity" in nuclei_data["info"]:
                        severity_str = nuclei_data["info"]["severity"].lower()
                    elif "severity" in nuclei_data:
                        severity_str = nuclei_data["severity"].lower()
                    
                    # Normalize severity
                    severity_map = {
                        "critical": "critical",
                        "high": "high",
                        "medium": "medium",
                        "low": "low",
                        "info": "info",
                    }
                    severity = severity_map.get(severity_str, "info")
                    
                    # Extract CVE ID
                    cve_id = None
                    if "info" in nuclei_data and "classification" in nuclei_data["info"]:
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
                    
                    # Extract CVSS score
                    cvss_score = None
                    if "info" in nuclei_data and "classification" in nuclei_data["info"]:
                        cvss_score = nuclei_data["info"]["classification"].get("cvss-score")
                        if cvss_score and isinstance(cvss_score, (int, float)):
                            pass  # Keep as is
                        else:
                            cvss_score = None
                    
                    # Extract URL
                    matched_at = nuclei_data.get("matched-at") or nuclei_data.get("matched_at")
                    url = matched_at or nuclei_data.get("host", "") or nuclei_data.get("url", "")
                    
                    # Extract template ID
                    template_id = (
                        nuclei_data.get("template-id") or
                        nuclei_data.get("info", {}).get("id") or
                        nuclei_data.get("id") or
                        ""
                    )
                    
                    # Extract template name
                    template_name = (
                        nuclei_data.get("info", {}).get("name") or
                        nuclei_data.get("name") or
                        template_id
                    )
                    
                    # Extract description
                    description = (
                        nuclei_data.get("info", {}).get("description") or
                        nuclei_data.get("description") or
                        f"Vulnerability detected by Nuclei template {template_id}"
                    )
                    
                    # Extract template tags
                    template_tags = []
                    if "info" in nuclei_data and "tags" in nuclei_data["info"]:
                        tags = nuclei_data["info"]["tags"]
                        if isinstance(tags, list):
                            template_tags = tags
                        elif isinstance(tags, str):
                            template_tags = [t.strip() for t in tags.split(",")]
                    
                    # Extract HTTP method
                    http_method = None
                    request_data = nuclei_data.get("request") or nuclei_data.get("curl-command") or ""
                    if request_data:
                        if isinstance(request_data, str):
                            first_line = request_data.split('\n')[0] if '\n' in request_data else request_data
                            method_match = re.match(r'^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)', first_line.upper())
                            if method_match:
                                http_method = method_match.group(1)
                    
                    if not http_method:
                        method_field = nuclei_data.get("method")
                        if method_field and isinstance(method_field, str):
                            http_method = method_field.upper().split()[0] if " " in method_field else method_field.upper()
                            if http_method not in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
                                http_method = None
                    
                    # Extract parameter
                    parameter = None
                    if url:
                        try:
                            parsed_url = urlparse(url)
                            if parsed_url.query:
                                params = parse_qs(parsed_url.query)
                                if params:
                                    parameter = list(params.keys())[0]
                        except:
                            pass
                    
                    if not parameter:
                        extracted_results = nuclei_data.get("extracted-results") or nuclei_data.get("extracted_results")
                        if extracted_results:
                            if isinstance(extracted_results, list) and extracted_results:
                                for result in extracted_results[:3]:
                                    if isinstance(result, str) and '=' in result:
                                        param_match = re.search(r'([^=]+)=', result)
                                        if param_match:
                                            parameter = param_match.group(1).strip()
                                            break
                    
                    # Build evidence
                    evidence_parts = []
                    if template_name and template_name != template_id:
                        evidence_parts.append(f"Template: {template_name}")
                    if matched_at:
                        evidence_parts.append(f"Matched at: {matched_at}")
                    
                    extracted_results = nuclei_data.get("extracted-results") or nuclei_data.get("extracted_results")
                    if extracted_results:
                        if isinstance(extracted_results, list):
                            results_str = ", ".join(str(r) for r in extracted_results[:3])
                            if len(extracted_results) > 3:
                                results_str += "..."
                            evidence_parts.append(f"Extracted: {results_str}")
                        elif isinstance(extracted_results, str):
                            truncated = extracted_results[:200] + ('…' if len(extracted_results) > 200 else '')
                            evidence_parts.append(f"Extracted: {truncated}")
                    
                    matcher_name = nuclei_data.get("matcher-name") or nuclei_data.get("matcher_name")
                    if matcher_name:
                        evidence_parts.append(f"Matcher: {matcher_name}")
                    
                    if request_data and isinstance(request_data, str):
                        request_snippet = request_data.split('\n')[0][:150] if '\n' in request_data else request_data[:150]
                        if len(request_data) > 150:
                            request_snippet += '…'
                        evidence_parts.append(f"Request: {request_snippet}")
                    
                    evidence = ". ".join(evidence_parts) if evidence_parts else None
                    if evidence:
                        evidence = evidence[:500]
                    
                    # Extract timestamp
                    timestamp = nuclei_data.get("timestamp") or nuclei_data.get("time")
                    if timestamp:
                        # Convert to ISO format if needed
                        if isinstance(timestamp, (int, float)):
                            from datetime import datetime, timezone
                            timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
                        elif not isinstance(timestamp, str):
                            timestamp = None
                    else:
                        from datetime import datetime, timezone
                        timestamp = datetime.now(timezone.utc).isoformat()
                    
                    # Build title
                    title = template_name or f"Nuclei Finding: {template_id}"
                    
                    # Create normalized finding
                    finding = {
                        "tool_id": "nuclei",
                        "title": title[:500],
                        "severity": severity,
                        "description": description,
                        "evidence": evidence,
                        "url": url[:2048] if url else None,
                        "host": None,  # Nuclei uses URLs, not hosts
                        "timestamp": timestamp,
                        "raw": nuclei_data,  # Include full raw data
                        # Additional fields for backend ingestion
                        "cve_id": cve_id,
                        "cwe_id": cwe_id,
                        "cvss_score": cvss_score,
                        "template_id": template_id,
                        "categories": template_tags,
                        "http_method": http_method,
                        "parameter": parameter,
                    }
                    
                    findings.append(finding)
                    
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
        
        logger.info("Parsed %d nuclei findings from file %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse Nuclei output file %s: %s", path, e, exc_info=True)
        return []

