"""
Reusable helper functions for building finding API responses with location extraction and remediation hints.
"""
import json
from typing import Optional, Dict, Any
from app.models.finding import Finding
from app.utils.finding_utils import get_remediation_hint


def extract_location_from_raw_data(finding: Finding) -> Dict[str, Optional[str]]:
    """
    Extract url, http_method, and parameter from finding.raw_data if database fields are missing.
    
    Priority:
    1. Database fields (if non-empty)
    2. raw_data extraction (for Dalfox, httpx, nmap, etc.)
    3. Defaults (e.g., GET for http_method if URL exists)
    
    Returns dict with keys: url, http_method, parameter
    """
    # Helper to safely strip and validate strings
    def _safe_strip(value):
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return str(value).strip() if str(value).strip() else None
    
    # Initialize result with database values (handle None and empty strings)
    result = {
        "url": _safe_strip(finding.url),
        "http_method": _safe_strip(finding.http_method),
        "parameter": _safe_strip(finding.parameter),
    }
    
    # Always try to extract from raw_data if available (to improve data quality)
    # This ensures we get the best possible data - prefer raw_data over DB fields when DB is None/empty
    if finding.raw_data:
        try:
            raw_data_dict = json.loads(finding.raw_data) if isinstance(finding.raw_data, str) else finding.raw_data
            if isinstance(raw_data_dict, dict):
                # Extract URL - dalfox uses "raw" field, check it first
                # Only use raw_data if DB field is missing/empty
                if not result["url"]:
                    url_candidates = ["raw", "url", "target", "path", "matched-at", "matched_at", "matched", "request_url"]
                    for key in url_candidates:
                        if key in raw_data_dict and raw_data_dict[key]:
                            url_value = _safe_strip(raw_data_dict[key])
                            if url_value:
                                result["url"] = url_value[:2048]
                                break
                
                # Extract HTTP method - only use raw_data if DB field is missing/empty
                if not result["http_method"]:
                    method = raw_data_dict.get("method") or raw_data_dict.get("http_method")
                    if method:
                        method_upper = str(method).upper().strip()
                        if method_upper in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
                            result["http_method"] = method_upper
                
                # Extract parameter - dalfox uses "param" field, only use raw_data if DB field is missing/empty
                if not result["parameter"]:
                    param_value = (
                        raw_data_dict.get("param") or 
                        raw_data_dict.get("parameter") or 
                        raw_data_dict.get("param_name") or
                        raw_data_dict.get("paramName")
                    )
                    if param_value:
                        param_stripped = _safe_strip(param_value)
                        if param_stripped:
                            result["parameter"] = param_stripped[:255]
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Default: If we have a URL but no method found, default to GET
    if not result["http_method"] and result["url"]:
        result["http_method"] = "GET"
    
    return result


def get_impact_summary(finding: Finding) -> Optional[str]:
    """
    Get impact summary for a finding.
    
    Priority:
    1. AI-enriched impact_summary from DB (preferred)
    2. Lightweight vuln_type-based fallback for common types
    3. Tool-specific fallback for info-level findings (httpx, nmap)
    
    Returns None if no summary can be derived.
    """
    # Prefer AI-enriched impact_summary from DB
    if hasattr(finding, 'impact_summary') and finding.impact_summary:
        impact_value = finding.impact_summary.strip() if isinstance(finding.impact_summary, str) else str(finding.impact_summary)
        if impact_value:
            return impact_value
    
    # Lightweight fallback for common vuln types
    vuln_type_lower = (finding.vuln_type or "").lower()
    tool_name_lower = ((finding.tool_name or finding.tool) or "").lower()
    title_lower = (finding.title or "").lower()
    
    # XSS fallback (works for dalfox, nuclei, etc.)
    if "xss" in vuln_type_lower or "cross-site scripting" in title_lower:
        return (
            "An attacker can run JavaScript in the user's browser, "
            "steal session cookies, or act as the user in your application."
        )
    
    # Minimal fallback map - only most common types
    impact_map = {
        'sqli': "An attacker can read or modify application data in the database.",
        'open_port': "Exposed services can be attacked or misconfigured, potentially allowing unauthorized access.",
        'open_service': "Exposed services can be attacked or misconfigured, potentially allowing unauthorized access.",
        'insecure_http': "Unencrypted HTTP traffic can be intercepted or modified by attackers.",
    }
    
    # Check vuln_type first
    if vuln_type_lower:
        if vuln_type_lower in impact_map:
            return impact_map[vuln_type_lower]
        # Check if vuln_type contains keywords
        for key, value in impact_map.items():
            if key in vuln_type_lower:
                return value
    
    # Tool-specific fallbacks for info-level findings
    if tool_name_lower == "httpx" and finding.title and "HTTP surface" in finding.title:
        return "This endpoint is part of your publicly exposed attack surface and can be probed for vulnerabilities or brute-force attempts."
    
    if tool_name_lower == "nmap" and finding.title and ("Open port" in finding.title or "open port" in finding.title.lower()):
        return "Exposed services can be attacked or misconfigured, potentially allowing unauthorized access."
    
    return None


def get_remediation_data(finding: Finding) -> Dict[str, Optional[str]]:
    """
    Get remediation summary and default steps for a finding.
    
    Priority:
    1. AI-enriched data from finding.remediation_summary and finding.remediation_steps (preferred)
    2. Static hints from get_remediation_hint() as fallback
    3. Tool-specific fallback for info-level findings (httpx, nmap)
    
    Returns dict with keys: remediation_summary, default_remediation_steps
    """
    # Prefer AI-enriched remediation_summary from DB
    remediation_summary_value = None
    if hasattr(finding, 'remediation_summary') and finding.remediation_summary:
        if isinstance(finding.remediation_summary, str) and finding.remediation_summary.strip():
            remediation_summary_value = finding.remediation_summary.strip()
    
    # Prefer AI-enriched remediation_steps from DB
    remediation_steps_value = None
    if hasattr(finding, 'remediation_steps') and finding.remediation_steps:
        if isinstance(finding.remediation_steps, str) and finding.remediation_steps.strip():
            remediation_steps_value = finding.remediation_steps.strip()
    
    # Fallback to static hints only if AI data is missing
    default_remediation_steps = None
    tool_name_lower = ((finding.tool_name or finding.tool) or "").lower()
    title_lower = (finding.title or "").lower()
    vuln_type_lower = (finding.vuln_type or "").lower()
    
    if not remediation_summary_value and not remediation_steps_value and not default_remediation_steps:
        # XSS-specific fallback (works for dalfox, nuclei, etc.)
        if "xss" in vuln_type_lower or "cross-site scripting" in title_lower or tool_name_lower == "dalfox":
            remediation_summary_value = "Sanitize and encode user input before rendering it in the browser and avoid executing untrusted data as code."
            default_remediation_steps = "\n".join([
                "Encode all untrusted data before including it in HTML, attributes, or JavaScript.",
                "Use your framework's built-in templating/escaping facilities instead of building HTML strings manually.",
                "Validate and constrain user input to expected characters and formats.",
                "Avoid using unsafe sinks such as innerHTML/outerHTML/eval on untrusted data.",
                "Consider enforcing a Content Security Policy (CSP) to reduce XSS impact.",
            ])
        # Check tool-specific fallbacks for info-level findings
        elif tool_name_lower == "httpx" and finding.title and "HTTP surface" in finding.title:
            if not remediation_summary_value:
                remediation_summary_value = "Review and harden this endpoint as part of your external attack surface."
            if not remediation_steps_value:
                default_remediation_steps = "\n".join([
                    "Confirm it should be public; restrict if not needed.",
                    "Enforce authentication/rate limiting for sensitive functions.",
                    "Validate and sanitize inputs.",
                    "Serve over HTTPS and keep server software patched."
                ])
        elif tool_name_lower == "nmap" and finding.title and ("Open port" in finding.title or "open port" in finding.title.lower()):
            if not remediation_summary_value:
                remediation_summary_value = "Close or restrict unnecessary exposed services so they cannot be abused."
            if not remediation_steps_value:
                default_remediation_steps = "\n".join([
                    "Close unused ports or services on the server.",
                    "Restrict access to required services using firewall rules or security groups.",
                    "Keep exposed services patched and monitored.",
                    "Use network segmentation to isolate services."
                ])
        elif finding.vuln_type:
            # Use static hints for known vuln types
            remediation_hint = get_remediation_hint(finding.vuln_type)
            if remediation_hint:
                # Use hint summary only if AI summary is missing
                if not remediation_summary_value and remediation_hint.get("summary"):
                    remediation_summary_value = remediation_hint["summary"]
                
                # Use hint steps only if AI steps are missing
                if not remediation_steps_value and remediation_hint.get("steps"):
                    default_remediation_steps = "\n".join(remediation_hint["steps"])
    
    # If we have AI-enriched steps, use them as default_remediation_steps too
    if remediation_steps_value and not default_remediation_steps:
        default_remediation_steps = remediation_steps_value
    
    result = {
        "remediation_summary": remediation_summary_value,
        "default_remediation_steps": default_remediation_steps,
    }
    
    return result

