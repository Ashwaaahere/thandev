"""
Finding normalization and deduplication module.

This module provides:
- URL normalization for static assets
- Static asset detection
- ZAP rule family categorization
- Finding key computation (fingerprinting)
- Severity normalization (de-noising)
- Canonical finding + instances grouping
"""
import hashlib
import re
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse, urlunparse

from app.models.finding import Severity
from app.utils.raw_data_parser import parse_raw_json, extract_zap_metadata

logger = logging.getLogger(__name__)


# Static asset file extensions
STATIC_ASSET_EXTENSIONS = {
    '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', 
    '.webp', '.woff', '.woff2', '.ttf', '.map', '.eot', '.otf'
}

# Static asset paths
STATIC_ASSET_PATHS = {
    '/_next/static/',
    '/static/',
    '/assets/',
    '/_assets/',
}

# Static asset filenames
STATIC_ASSET_FILENAMES = {
    '/robots.txt',
    '/favicon.ico',
    '/sitemap.xml',
}


def normalize_url(url: str, strip_query_for_static: bool = True) -> str:
    """
    Normalize URL for deduplication:
    - Strip fragments
    - Optionally strip query for static assets
    - Canonicalize scheme/host (lowercase)
    - Remove default ports
    
    Args:
        url: URL string to normalize
        strip_query_for_static: If True, strip query params for static assets
        
    Returns:
        Normalized URL string
    """
    if not url:
        return ""
    
    try:
        parsed = urlparse(url)
        
        # Lowercase scheme and host
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        
        # Remove default ports
        if ':' in netloc:
            host, port = netloc.rsplit(':', 1)
            if (scheme == 'http' and port == '80') or (scheme == 'https' and port == '443'):
                netloc = host
        
        # Normalize path
        path = parsed.path.rstrip('/') or '/'
        
        # Strip query for static assets if requested
        query = ''
        if not strip_query_for_static or not is_static_asset_path(path):
            query = parsed.query
        
        # Reconstruct URL (always strip fragment)
        normalized = urlunparse((
            scheme,
            netloc,
            path,
            '',  # params
            query,
            ''   # fragment (always removed)
        ))
        return normalized
    except Exception as e:
        logger.warning(f"Failed to normalize URL '{url}': {e}")
        # Fallback: lowercase and strip fragment
        return url.split('#')[0].lower()


def is_static_asset_path(path: str) -> bool:
    """
    Check if a path is a static asset.
    
    Args:
        path: URL path string
        
    Returns:
        True if path matches static asset patterns
    """
    if not path:
        return False
    
    path_lower = path.lower()
    
    # Check for static asset paths
    for static_path in STATIC_ASSET_PATHS:
        if path_lower.startswith(static_path):
            return True
    
    # Check for static asset filenames
    if path_lower in STATIC_ASSET_FILENAMES:
        return True
    
    # Check for static asset extensions
    for ext in STATIC_ASSET_EXTENSIONS:
        if path_lower.endswith(ext):
            return True
    
    return False


def zap_rule_family(plugin_id: Optional[str], name: Optional[str]) -> str:
    """
    Categorize ZAP rule into family based on plugin_id and name.
    
    Args:
        plugin_id: ZAP plugin ID (e.g., "10020")
        name: Alert name/title
        
    Returns:
        Rule family string: "cors", "cache", "ua_fuzzer", "csp", "headers", "info", etc.
    """
    name_lower = (name or "").lower()
    
    # Known plugin IDs for common rule families
    plugin_id_map = {
        # CORS-related plugins
        "10020": "cors",  # Cross-Domain Misconfiguration
        "10021": "cors",  # CORS Misconfiguration
        # Cache-related
        "10015": "cache",  # Retrieved from Cache
        # CSP-related
        "10038": "csp",  # Content Security Policy (CSP) Header Not Set
        "10055": "csp",  # CSP: Wildcard Directive
        # User Agent Fuzzer
        "10104": "ua_fuzzer",  # User Agent Fuzzer
    }
    
    if plugin_id and plugin_id in plugin_id_map:
        return plugin_id_map[plugin_id]
    
    # Infer from name keywords
    if any(keyword in name_lower for keyword in ["cross-domain", "cors", "cross-origin"]):
        return "cors"
    
    if any(keyword in name_lower for keyword in ["cache", "retrieved from cache", "cache-control"]):
        return "cache"
    
    if "user agent fuzzer" in name_lower or "ua fuzzer" in name_lower:
        return "ua_fuzzer"
    
    if any(keyword in name_lower for keyword in ["csp", "content security policy", "unsafe-inline", "unsafe-eval", "wildcard directive"]):
        return "csp"
    
    if any(keyword in name_lower for keyword in ["header", "missing header", "insecure header"]):
        return "headers"
    
    # Default to "info" for unknown rules
    return "info"


def compute_evidence_signature(finding_data: Dict[str, Any], raw_data: Dict[str, Any]) -> str:
    """
    Compute a stable evidence signature for a finding.
    
    This signature should capture the essence of the issue (title, riskcode, confidence,
    key evidence markers) but EXCLUDE the exact URL so same issues across many assets dedupe.
    
    Args:
        finding_data: Finding data dict
        raw_data: Parsed raw_data dict
        
    Returns:
        Evidence signature string
    """
    components = []
    
    # Title/name (most important)
    title = finding_data.get("title") or finding_data.get("name") or ""
    components.append(f"title:{title}")
    
    # ZAP-specific: riskcode and confidence
    riskcode = raw_data.get("riskcode") or finding_data.get("zap_riskcode")
    confidence = raw_data.get("confidence") or finding_data.get("zap_confidence")
    if riskcode is not None:
        components.append(f"riskcode:{riskcode}")
    if confidence is not None:
        components.append(f"confidence:{confidence}")
    
    # Plugin ID / Rule ID
    plugin_id = raw_data.get("pluginId") or finding_data.get("plugin_id")
    rule_id = finding_data.get("rule_id") or finding_data.get("template_id")
    if plugin_id:
        components.append(f"plugin:{plugin_id}")
    elif rule_id:
        components.append(f"rule:{rule_id}")
    
    # Key evidence markers (extract from description/evidence)
    evidence = finding_data.get("evidence") or ""
    description = finding_data.get("description") or ""
    
    # Extract key patterns from evidence (e.g., "ACAO=*", "unsafe-inline", etc.)
    evidence_lower = (evidence + " " + description).lower()
    
    # Look for CORS markers
    if "acao" in evidence_lower or "access-control-allow-origin" in evidence_lower:
        # Extract ACAO value if present
        acao_match = re.search(r'access-control-allow-origin[:\s=]+([^\s,;]+)', evidence_lower)
        if acao_match:
            components.append(f"acao:{acao_match.group(1)}")
        acac_match = re.search(r'access-control-allow-credentials[:\s=]+([^\s,;]+)', evidence_lower)
        if acac_match:
            components.append(f"acac:{acac_match.group(1)}")
    
    # Look for CSP markers
    if "unsafe-inline" in evidence_lower:
        components.append("csp:unsafe-inline")
    if "unsafe-eval" in evidence_lower:
        components.append("csp:unsafe-eval")
    if "wildcard" in evidence_lower and "directive" in evidence_lower:
        components.append("csp:wildcard")
    
    # Parameter name (if present)
    parameter = finding_data.get("parameter")
    if parameter:
        components.append(f"param:{parameter.lower()}")
    
    # HTTP method (if present)
    method = finding_data.get("http_method") or finding_data.get("method")
    if method:
        components.append(f"method:{method.upper()}")
    
    return "|".join(components)


def compute_finding_key(
    tool: str,
    rule_id: Optional[str],
    plugin_id: Optional[str],
    normalized_host: str,
    evidence_signature: str,
    normalized_param: Optional[str] = None,
    path_bucket: Optional[str] = None,
) -> str:
    """
    Compute stable fingerprint (SHA256) for a finding.
    
    The key is based on:
    - tool + rule/plugin_id
    - normalized_host
    - evidence_signature (includes title, riskcode, confidence, key markers)
    - normalized_param (if present)
    - path_bucket (optional, for issues where URL matters)
    
    For cors/cache/ua_fuzzer, path_bucket should be "host-level" to dedupe across all paths.
    
    Args:
        tool: Tool name
        rule_id: Rule/template ID
        plugin_id: Plugin ID (ZAP)
        normalized_host: Normalized hostname (lowercase, no port)
        evidence_signature: Evidence signature (from compute_evidence_signature)
        normalized_param: Normalized parameter name (optional)
        path_bucket: Path bucket - "host-level" for host-wide issues, or specific path pattern
        
    Returns:
        SHA256 hash as hex string (64 characters)
    """
    # Use plugin_id if available, otherwise rule_id
    rule_identifier = plugin_id or rule_id or ""
    
    # Normalize parameter
    param_str = (normalized_param or "").lower().strip()
    
    # Use path_bucket if provided, otherwise empty (host-level)
    path_str = path_bucket or ""
    
    # Build key components
    components = [
        tool or "",
        rule_identifier,
        normalized_host,
        evidence_signature,
        param_str,
        path_str,
    ]
    
    # Join and hash
    key_string = "|".join(components)
    hash_obj = hashlib.sha256(key_string.encode('utf-8'))
    return hash_obj.hexdigest()


def normalize_severity_for_finding(
    finding_data: Dict[str, Any],
    raw_data: Dict[str, Any],
    rule_family: str,
    is_static_asset: bool,
) -> Severity:
    """
    Normalize severity based on rule family and context (de-noising).
    
    Rules:
    1. CORS:
       - Static asset + no credentials risk -> INFO
       - ACAO="*" + ACAC=true -> HIGH
       - ACAO reflects Origin + ACAC=true -> HIGH
       - Else (API endpoints) -> MEDIUM
    2. Cache:
       - Static asset -> INFO
       - Authenticated path -> MEDIUM
       - Else -> INFO
    3. UA Fuzzer: INFO always
    4. CSP:
       - unsafe-eval -> MEDIUM (or HIGH)
       - unsafe-inline -> MEDIUM
       - wildcard directive -> MEDIUM
    5. Keep original severity for everything else
    
    Args:
        finding_data: Finding data dict
        raw_data: Parsed raw_data dict
        rule_family: Rule family from zap_rule_family()
        is_static_asset: Whether this is a static asset
        original_severity: Original severity from tool
        
    Returns:
        Normalized Severity enum
    """
    # Get original severity
    original_severity_raw = finding_data.get("severity")
    if isinstance(original_severity_raw, Severity):
        original_severity = original_severity_raw
    else:
        from app.core.severity import normalize_severity
        original_severity = normalize_severity(original_severity_raw)
    
    # Never upgrade INFO-only issues
    if original_severity == Severity.INFO and rule_family not in ["cors", "cache", "ua_fuzzer", "csp"]:
        return original_severity
    
    # Rule family-specific normalization
    if rule_family == "cors":
        if is_static_asset:
            # Check for credentials risk markers
            evidence = (finding_data.get("evidence") or "").lower()
            description = (finding_data.get("description") or "").lower()
            has_credentials_risk = (
                "credentials" in evidence or "credentials" in description or
                "acac" in evidence or "acac" in description
            )
            if not has_credentials_risk:
                return Severity.INFO
        
        # Check for high-risk CORS patterns
        evidence = (finding_data.get("evidence") or "").lower()
        description = (finding_data.get("description") or "").lower()
        combined = evidence + " " + description
        
        # ACAO="*" + ACAC=true -> HIGH
        if "*" in combined and ("acac" in combined or "credentials" in combined):
            acac_match = re.search(r'access-control-allow-credentials[:\s=]+(true|yes)', combined)
            if acac_match:
                return Severity.HIGH
        
        # ACAO reflects Origin + ACAC=true -> HIGH
        if "origin" in combined and ("acac" in combined or "credentials" in combined):
            acac_match = re.search(r'access-control-allow-credentials[:\s=]+(true|yes)', combined)
            if acac_match:
                return Severity.HIGH
        
        # Default for CORS on non-static assets
        return Severity.MEDIUM
    
    elif rule_family == "cache":
        if is_static_asset:
            return Severity.INFO
        
        # Check if path is likely authenticated
        url = finding_data.get("url") or ""
        path = finding_data.get("path") or ""
        combined_path = (url + " " + path).lower()
        
        authenticated_paths = ["/dashboard", "/app", "/account", "/settings", "/api/me", "/admin"]
        if any(auth_path in combined_path for auth_path in authenticated_paths):
            return Severity.MEDIUM
        
        return Severity.INFO
    
    elif rule_family == "ua_fuzzer":
        return Severity.INFO
    
    elif rule_family == "csp":
        # Keep CSP issues at MEDIUM or higher
        evidence = (finding_data.get("evidence") or "").lower()
        description = (finding_data.get("description") or "").lower()
        combined = evidence + " " + description
        
        # Severity order: INFO < LOW < MEDIUM < HIGH < CRITICAL
        severity_order = {
            Severity.INFO: 0,
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 3,
            Severity.CRITICAL: 4,
        }
        
        if "unsafe-eval" in combined:
            # Could be HIGH, but keep at MEDIUM for now
            return original_severity if severity_order.get(original_severity, 0) >= 2 else Severity.MEDIUM
        elif "unsafe-inline" in combined:
            return original_severity if severity_order.get(original_severity, 0) >= 2 else Severity.MEDIUM
        elif "wildcard" in combined and "directive" in combined:
            return original_severity if severity_order.get(original_severity, 0) >= 2 else Severity.MEDIUM
        
        # Keep original severity for other CSP issues, but ensure at least MEDIUM
        return original_severity if severity_order.get(original_severity, 0) >= 2 else Severity.MEDIUM
    
    # For all other rule families, keep original severity
    return original_severity


def normalize_and_group_finding(
    finding_data: Dict[str, Any],
    scan_id: str,
    project_id: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Normalize a finding and produce canonical finding + instance.
    
    Args:
        finding_data: Raw finding data dict
        scan_id: Current scan ID
        project_id: Project ID
        
    Returns:
        Tuple of (canonical_finding, instance) dicts
    """
    # Parse raw_data
    raw_data = parse_raw_json(finding_data.get("raw_data", finding_data.get("raw")))
    
    # Extract fields
    tool = finding_data.get("tool") or finding_data.get("tool_name") or ""
    url = finding_data.get("url") or ""
    path = finding_data.get("path") or ""
    parameter = finding_data.get("parameter")
    plugin_id = finding_data.get("plugin_id") or raw_data.get("pluginId")
    rule_id = finding_data.get("rule_id") or finding_data.get("template_id")
    title = finding_data.get("title") or finding_data.get("name") or "Security Finding"
    
    # Normalize URL and extract host
    normalized_url = normalize_url(url, strip_query_for_static=True)
    try:
        parsed = urlparse(normalized_url)
        normalized_host = parsed.netloc.lower()
        if ':' in normalized_host:
            normalized_host = normalized_host.split(':')[0]
    except Exception:
        normalized_host = ""
    
    # Check if static asset
    is_static = is_static_asset_path(path or normalized_url)
    
    # Determine rule family (for ZAP)
    rule_family = "info"
    if tool.lower() == "zap":
        rule_family = zap_rule_family(plugin_id, title)
    
    # Compute evidence signature
    evidence_sig = compute_evidence_signature(finding_data, raw_data)
    
    # Determine path bucket
    # For cors/cache/ua_fuzzer, use "host-level" to dedupe across all paths
    if rule_family in ["cors", "cache", "ua_fuzzer"]:
        path_bucket = "host-level"
    else:
        # For other issues, use normalized path (without query)
        path_bucket = parsed.path if parsed else ""
    
    # Normalize parameter
    normalized_param = parameter.lower().strip() if parameter else None
    
    # Compute finding key
    finding_key = compute_finding_key(
        tool=tool,
        rule_id=rule_id,
        plugin_id=plugin_id,
        normalized_host=normalized_host,
        evidence_signature=evidence_sig,
        normalized_param=normalized_param,
        path_bucket=path_bucket,
    )
    
    # Normalize severity
    normalized_severity = normalize_severity_for_finding(
        finding_data,
        raw_data,
        rule_family,
        is_static,
    )
    
    # Build canonical finding (no specific URL)
    canonical = {
        "finding_key": finding_key,
        "tool": tool,
        "title": title,
        "description": finding_data.get("description"),
        "severity": normalized_severity,
        "rule_family": rule_family,
        "plugin_id": plugin_id,
        "rule_id": rule_id,
        "template_id": finding_data.get("template_id"),
        "cwe_id": finding_data.get("cwe_id") or raw_data.get("cweid"),
        "cve_id": finding_data.get("cve_id"),
        "cvss_score": finding_data.get("cvss_score"),
        "zap_riskcode": finding_data.get("zap_riskcode") or raw_data.get("riskcode"),
        "zap_confidence": finding_data.get("zap_confidence") or raw_data.get("confidence"),
        "wasc_id": finding_data.get("wasc_id") or raw_data.get("wascid"),
        "alert_ref": finding_data.get("alert_ref") or raw_data.get("alertRef"),
        "vuln_type": finding_data.get("vuln_type"),
        "categories": finding_data.get("categories", []),
        "remediation_summary": finding_data.get("remediation_summary"),
        "remediation_steps": finding_data.get("remediation_steps"),
        "evidence": finding_data.get("evidence"),  # Keep first evidence as example
        "raw_data": json.dumps(raw_data, default=str),  # Store canonical raw_data
        "scan_job_id": scan_id,
        "project_id": project_id,
    }
    
    # Build instance
    instance = {
        "url": url,
        "path": path,
        "http_method": finding_data.get("http_method") or finding_data.get("method"),
        "parameter": parameter,
        "evidence_snippet": finding_data.get("evidence", "")[:200],  # Truncate for storage
        "is_static_asset": is_static,
    }
    
    return canonical, instance

