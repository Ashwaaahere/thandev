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
from app.utils.noise_rules_engine import apply_noise_rules

logger = logging.getLogger(__name__)


def _normalize_zap_confidence(confidence: Any) -> Optional[int]:
    """
    Normalize ZAP confidence to integer (0=Low, 1=Medium, 2=High, 3=Confirmed).
    
    Args:
        confidence: Can be int, str ("Low", "Medium", "High", "Confirmed"), or None
        
    Returns:
        Integer confidence value (0-3) or None
    """
    if confidence is None:
        return None
    
    if isinstance(confidence, int):
        return max(0, min(3, confidence))  # Clamp to 0-3
    
    if isinstance(confidence, str):
        conf_lower = confidence.lower()
        if conf_lower in ["low", "0"]:
            return 0
        elif conf_lower in ["medium", "1"]:
            return 1
        elif conf_lower in ["high", "2"]:
            return 2
        elif conf_lower in ["confirmed", "3", "true"]:
            return 3
        else:
            # Try to parse as int
            try:
                return int(confidence) if confidence.isdigit() else 0
            except (ValueError, AttributeError):
                return 0
    
    # Try to convert to int
    try:
        return int(confidence)
    except (ValueError, TypeError):
        return 0


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
        Rule family string: "cors", "cache", "ua_fuzzer", "csp", "headers", "cookies", "csrf", "info", etc.
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
    
    # Cookie-related findings (host-level, but group by cookie name)
    if any(keyword in name_lower for keyword in [
        "cookie no httponly", "cookie without samesite", "cookie without secure",
        "httponly flag", "samesite attribute", "secure flag", "cookie"
    ]):
        return "cookies"
    
    # CSRF-related findings (form_action scope)
    if any(keyword in name_lower for keyword in [
        "absence of anti-csrf", "csrf token", "anti-csrf", "cross-site request forgery"
    ]):
        return "csrf"
    
    # Header-related findings (host-level issues)
    if any(keyword in name_lower for keyword in [
        "header", "missing header", "insecure header",
        "x-content-type-options", "x-frame-options", "anti-clickjacking",
        "strict-transport-security", "hsts", "x-frame-options header missing",
        "missing anti-clickjacking", "re-examine cache-control"
    ]):
        return "headers"
    
    # Modern Web Application is an informational finding (host-level)
    if "modern web application" in name_lower:
        return "headers"  # Treat as header/info finding for grouping purposes
    
    # Default to "info" for unknown rules
    return "info"


def group_scope_for_zap(plugin_id: Optional[str], title: Optional[str], rule_family: str) -> str:
    """
    Determine grouping scope for a ZAP alert.
    
    Returns:
        "host" - Group across all URLs on same host (headers, CSP, CORS, cookies, etc.)
        "path" - Group by path pattern (vulnerabilities on specific endpoints, redirects)
        "param" - Group by parameter name (XSS, SQLi in specific params)
        "form_action" - Group by form action endpoint (CSRF tokens on same form)
    """
    title_lower = (title or "").lower()
    
    # Host-level issues (group across all URLs):
    # - Header-related findings
    # - CSP issues
    # - CORS misconfigurations
    # - Cache-control directives
    # - Cookie issues (group by cookie name, but host-level)
    # - Modern Web Application (informational)
    
    if rule_family in ["cors", "cache", "ua_fuzzer", "csp", "headers", "cookies"]:
        return "host"
    
    # Form action scope (group by form endpoint):
    # - CSRF token absence (group by form action path, not full URL)
    if rule_family == "csrf":
        return "form_action"
    
    # Check title patterns for host-level issues
    host_level_patterns = [
        "header not set", "header missing", "missing header",
        "anti-clickjacking", "x-content-type-options", "x-frame-options",
        "strict-transport-security", "hsts", "csp", "content security policy",
        "cache-control", "re-examine cache-control",
        "modern web application", "cross-domain", "cors",
        "cookie no httponly", "cookie without samesite", "cookie without secure",
        "httponly flag", "samesite attribute", "secure flag"
    ]
    
    if any(pattern in title_lower for pattern in host_level_patterns):
        return "host"
    
    # Form action patterns (CSRF)
    if any(pattern in title_lower for pattern in [
        "absence of anti-csrf", "csrf token", "anti-csrf", "cross-site request forgery"
    ]):
        return "form_action"
    
    # Path-level issues (group by normalized path):
    # - Big Redirect Detected (group by redirecting path, not destination)
    if "big redirect" in title_lower or "redirect detected" in title_lower:
        return "path"
    
    # Param-level issues (group by parameter):
    # - XSS in specific parameter
    # - SQLi in specific parameter
    # - Other parameter-specific vulnerabilities
    
    param_patterns = ["xss", "cross-site scripting", "sqli", "sql injection", "parameter"]
    if any(pattern in title_lower for pattern in param_patterns):
        # Check if there's a parameter mentioned
        if "parameter" in title_lower or "param" in title_lower:
            return "param"
    
    # Default to path-level for specific endpoint vulnerabilities
    return "path"


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
    # Normalize evidence to avoid breaking grouping - only include stable signatures
    evidence = finding_data.get("evidence") or ""
    description = finding_data.get("description") or ""
    
    # Extract key patterns from evidence (e.g., "ACAO=*", "unsafe-inline", etc.)
    evidence_lower = (evidence + " " + description).lower()
    
    # Normalize evidence: extract header names, not full values
    # This prevents URL-specific evidence from breaking grouping
    
    # Look for CORS markers
    if "acao" in evidence_lower or "access-control-allow-origin" in evidence_lower:
        # Extract ACAO value if present (normalized)
        acao_match = re.search(r'access-control-allow-origin[:\s=]+([^\s,;]+)', evidence_lower)
        if acao_match:
            acao_val = acao_match.group(1).lower().strip()
            # Normalize wildcard variations
            if acao_val in ["*", "null", "wildcard"]:
                acao_val = "*"
            components.append(f"acao:{acao_val}")
        acac_match = re.search(r'access-control-allow-credentials[:\s=]+([^\s,;]+)', evidence_lower)
        if acac_match:
            acac_val = acac_match.group(1).lower().strip()
            components.append(f"acac:{acac_val}")
    
    # Look for CSP markers (normalized)
    if "unsafe-inline" in evidence_lower:
        components.append("csp:unsafe-inline")
    if "unsafe-eval" in evidence_lower:
        components.append("csp:unsafe-eval")
    if "wildcard" in evidence_lower and "directive" in evidence_lower:
        components.append("csp:wildcard")
    
    # Extract header names (not values) for header-related findings
    # This ensures "X-Content-Type-Options Header Missing" groups together regardless of URL
    header_names = [
        "content-security-policy", "csp", "x-content-type-options",
        "x-frame-options", "strict-transport-security", "hsts",
        "cache-control", "x-xss-protection"
    ]
    for header_name in header_names:
        if header_name in evidence_lower or header_name.replace("-", " ") in evidence_lower:
            # Normalize header name (remove variations)
            normalized_header = header_name.replace(" ", "-").lower()
            components.append(f"header:{normalized_header}")
            break  # Only include first matching header
    
    # Extract cookie name for cookie-related findings
    # This allows grouping by cookie name (e.g., "GRUYERE" cookie issues group together)
    cookie_patterns = [
        r'cookie[:\s]+([a-zA-Z0-9_-]+)',
        r'setcookie[:\s]+([a-zA-Z0-9_-]+)',
        r'([a-zA-Z0-9_-]+)\s*=\s*[^;]+;\s*httponly',
        r'([a-zA-Z0-9_-]+)\s*=\s*[^;]+;\s*samesite',
        r'([a-zA-Z0-9_-]+)\s*=\s*[^;]+;\s*secure',
    ]
    for pattern in cookie_patterns:
        cookie_match = re.search(pattern, evidence_lower)
        if cookie_match:
            cookie_name = cookie_match.group(1).lower().strip()
            if cookie_name and len(cookie_name) > 0:
                components.append(f"cookie:{cookie_name}")
                break  # Only include first matching cookie
    
    # Extract form action for CSRF findings
    # Group by normalized form action path (e.g., "/upload.gtl")
    if "csrf" in evidence_lower or "anti-csrf" in evidence_lower or "cross-site request forgery" in evidence_lower:
        # Try to extract form action from evidence or URL
        form_action_match = re.search(r'action[:\s=]+([^\s,;<>"\']+)', evidence_lower)
        if form_action_match:
            form_action = form_action_match.group(1).lower().strip()
            # Normalize form action (extract path only)
            try:
                from urllib.parse import urlparse
                parsed = urlparse(form_action if form_action.startswith('http') else f"http://example.com{form_action}")
                form_path = parsed.path or "/"
                components.append(f"form_action:{form_path}")
            except:
                components.append(f"form_action:{form_action}")
    
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
    
    First applies noise rules engine, then falls back to rule-family-specific logic.
    
    Args:
        finding_data: Finding data dict
        raw_data: Parsed raw_data dict
        rule_family: Rule family from zap_rule_family()
        is_static_asset: Whether this is a static asset
        
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
    
    # First, try noise rules engine (YAML-based)
    try:
        adjusted_severity, tag, reason = apply_noise_rules(finding_data, raw_data, original_severity)
        if adjusted_severity != original_severity:
            logger.debug(f"Severity adjusted by noise rules: {original_severity.value} -> {adjusted_severity.value} ({reason})")
            return adjusted_severity
    except Exception as e:
        logger.warning(f"Error applying noise rules, falling back to rule-family logic: {e}")
    
    # Fallback to rule-family-specific normalization (backward compatibility)
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
    
    # Determine path bucket based on grouping scope
    # Host-level issues should group across all URLs on the same host
    # Path-level issues should group by path pattern
    # Param-level issues should group by parameter name
    # Form_action-level issues should group by form action endpoint
    grouping_scope = group_scope_for_zap(plugin_id, title, rule_family)
    
    if grouping_scope == "host":
        # Host-level: group all URLs on same host (e.g., CSP, headers, CORS, cookies)
        path_bucket = "host-level"
    elif grouping_scope == "form_action":
        # Form action-level: group by normalized form action path (e.g., CSRF on /upload.gtl)
        # For CSRF, the URL itself is usually the form action endpoint
        # Extract normalized path from URL (strip query params)
        form_action_path = None
        if parsed:
            form_action_path = parsed.path or "/"
        # Try to extract from evidence if URL path is not clear
        if not form_action_path or form_action_path == "/":
            evidence = finding_data.get("evidence") or ""
            if evidence:
                form_action_match = re.search(r'action[:\s=]+([^\s,;<>"\']+)', evidence.lower())
                if form_action_match:
                    form_action = form_action_match.group(1).strip()
                    try:
                        from urllib.parse import urlparse
                        parsed_action = urlparse(form_action if form_action.startswith('http') else f"http://example.com{form_action}")
                        form_action_path = parsed_action.path or "/"
                    except:
                        form_action_path = form_action if form_action.startswith('/') else f"/{form_action}"
        path_bucket = f"form_action:{form_action_path}" if form_action_path else "form_action:unknown"
    elif grouping_scope == "param":
        # Param-level: group by parameter name (e.g., XSS in specific param)
        path_bucket = "param-level"
    else:
        # Path-level: group by normalized path (e.g., SQLi on specific endpoint, Big Redirect)
        # For redirects, use the redirecting path (not the destination)
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
        "zap_confidence": _normalize_zap_confidence(finding_data.get("zap_confidence") or raw_data.get("confidence")),
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

