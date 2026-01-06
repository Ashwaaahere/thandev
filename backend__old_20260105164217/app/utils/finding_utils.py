"""
Utilities for finding deduplication, normalization, and remediation hints
"""
import hashlib
import re
from typing import Optional, Dict, Any
from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> str:
    """
    Normalize URL for deduplication:
    - Remove query parameters
    - Normalize trailing slashes
    - Lowercase scheme and host
    - Remove default ports
    
    Args:
        url: URL string to normalize
        
    Returns:
        Normalized URL string
    """
    if not url:
        return ""
    
    try:
        parsed = urlparse(url.lower())
        # Reconstruct without query and fragment
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.split(':')[0] if ':' in parsed.netloc else parsed.netloc,  # Remove port
            parsed.path.rstrip('/') or '/',  # Normalize trailing slash
            '',  # params
            '',  # query (removed)
            ''   # fragment (removed)
        ))
        return normalized
    except Exception:
        # If parsing fails, return lowercase version without query
        return url.split('?')[0].lower().rstrip('/')


def normalize_parameter(param: Optional[str]) -> str:
    """
    Normalize parameter name for deduplication.
    
    Args:
        param: Parameter name string
        
    Returns:
        Normalized parameter string (lowercase, trimmed) or empty string
    """
    if not param:
        return ""
    return param.lower().strip()


def generate_dedup_key(
    project_id: str,
    tool: str,
    template_id: Optional[str] = None,
    rule_id: Optional[str] = None,
    normalized_url: Optional[str] = None,
    parameter: Optional[str] = None,
    vuln_type: Optional[str] = None,
) -> str:
    """
    Generate a deterministic deduplication key for a finding.
    
    The key is based on:
    - project_id
    - tool
    - template_id (or rule_id if template_id not available)
    - normalized_url
    - parameter (if present)
    - vuln_type (if present)
    
    Args:
        project_id: Project ID
        tool: Tool name
        template_id: Template/rule identifier (e.g., nuclei template-id)
        rule_id: Alternative rule identifier
        normalized_url: Normalized URL (use normalize_url() first)
        parameter: Parameter name (normalized)
        vuln_type: Vulnerability type (e.g., "xss", "sqli")
        
    Returns:
        SHA-256 hash as hex string (64 characters)
    """
    # Use template_id if available, otherwise rule_id
    rule_identifier = template_id or rule_id or ""
    
    # Normalize URL if provided
    if normalized_url is None:
        normalized_url = ""
    else:
        normalized_url = normalize_url(normalized_url)
    
    # Normalize parameter
    param_normalized = normalize_parameter(parameter) if parameter else ""
    
    # Normalize vuln_type
    vuln_type_normalized = vuln_type.lower().strip() if vuln_type else ""
    
    # Build key components
    components = [
        project_id or "",
        tool or "",
        rule_identifier,
        normalized_url,
        param_normalized,
        vuln_type_normalized,
    ]
    
    # Join with pipe separator and hash
    key_string = "|".join(components)
    hash_obj = hashlib.sha256(key_string.encode('utf-8'))
    return hash_obj.hexdigest()


# Remediation hints mapping
REMEDIATION_HINTS: Dict[str, Dict[str, Any]] = {
    "xss": {
        "summary": "Encode user input before rendering it in HTML and avoid inserting raw user input directly into the page.",
        "steps": [
            "Use your framework's output encoding (e.g., htmlspecialchars in PHP, html.escape in Python, React's JSX escaping)",
            "Do not insert untrusted data into HTML, JavaScript, or attributes",
            "Validate and constrain input to expected characters or patterns",
            "Implement Content Security Policy (CSP) headers to prevent XSS attacks",
            "Use parameterized templates or safe rendering functions"
        ]
    },
    "sqli": {
        "summary": "Use parameterized queries instead of building SQL statements with string concatenation.",
        "steps": [
            "Use prepared statements / ORM parameter binding for all database queries",
            "Never concatenate raw user input directly into SQL strings",
            "Apply server-side validation to limit input values to expected formats",
            "Use ORM query builders when possible",
            "Implement least-privilege database access",
            "Regularly update database software and libraries"
        ]
    },
    "open_port": {
        "summary": "Close or restrict unnecessary exposed services so they cannot be abused.",
        "steps": [
            "Close unused ports or services on the server",
            "Restrict access to required services using firewall rules or security groups",
            "Keep exposed services patched and monitored",
            "Use network segmentation to isolate services",
            "Review and audit open ports regularly"
        ]
    },
    "open_service": {
        "summary": "Close or restrict unnecessary exposed services so they cannot be abused.",
        "steps": [
            "Close unused ports or services on the server",
            "Restrict access to required services using firewall rules or security groups",
            "Keep exposed services patched and monitored",
            "Use network segmentation to isolate services",
            "Review and audit open ports regularly"
        ]
    },
    "insecure_http": {
        "summary": "Migrate traffic to HTTPS to protect data from interception and tampering.",
        "steps": [
            "Obtain and install a valid TLS certificate",
            "Redirect all HTTP requests to HTTPS",
            "Consider enabling HSTS once HTTPS is stable",
            "Ensure all internal links and resources use HTTPS",
            "Test HTTPS configuration for security headers and cipher suites"
        ]
    },
    "ssrf": {
        "summary": "Validate and whitelist allowed URLs/hosts. Use DNS rebinding protection.",
        "steps": [
            "Whitelist allowed internal IP ranges and hostnames",
            "Validate and sanitize all URL inputs",
            "Use DNS rebinding protection",
            "Block access to private/internal IP ranges (127.0.0.1, 10.x.x.x, 192.168.x.x, etc.)",
            "Implement network segmentation",
            "Use allowlists instead of blocklists"
        ]
    },
    "ssti": {
        "summary": "Use safe template engines. Avoid user-controlled template rendering.",
        "steps": [
            "Use safe template engines that don't allow code execution",
            "Avoid user-controlled template rendering",
            "Sanitize template variables",
            "Use sandboxed template execution environments",
            "Implement input validation for template variables"
        ]
    },
    "xxe": {
        "summary": "Disable XML external entity processing. Use safe XML parsers.",
        "steps": [
            "Disable XML external entity (XXE) processing",
            "Use safe XML parsers with XXE protection enabled",
            "Validate XML input against schemas",
            "Disable DTD processing if not needed",
            "Use JSON or other safe data formats when possible"
        ]
    },
    "dir_traversal": {
        "summary": "Validate file paths. Use path normalization. Restrict file access to safe directories.",
        "steps": [
            "Validate and sanitize all file path inputs",
            "Use path normalization functions",
            "Restrict file access to whitelisted directories",
            "Never allow user input to directly construct file paths",
            "Use absolute paths with base directory restrictions",
            "Implement proper file access controls"
        ]
    },
    "cors": {
        "summary": "Configure CORS headers properly. Restrict allowed origins.",
        "steps": [
            "Configure CORS headers with specific allowed origins (avoid wildcards)",
            "Use credentials only when necessary",
            "Restrict allowed HTTP methods and headers",
            "Validate Origin header on server side",
            "Use allowlists instead of wildcards for origins"
        ]
    },
    "csrf": {
        "summary": "Implement CSRF tokens. Validate origin/referer headers.",
        "steps": [
            "Implement CSRF tokens for state-changing operations",
            "Validate Origin and Referer headers",
            "Use SameSite cookie attribute",
            "Implement double-submit cookie pattern if needed",
            "Require CSRF tokens for POST/PUT/DELETE requests"
        ]
    },
    "cmdi": {
        "summary": "Avoid shell command execution with user input. Use safe APIs.",
        "steps": [
            "Avoid executing shell commands with user input",
            "Use safe APIs and libraries instead of shell commands",
            "If shell commands are necessary, use allowlists for commands and arguments",
            "Validate and sanitize all command inputs",
            "Run commands with least-privilege user accounts",
            "Use parameterized command execution when possible"
        ]
    },
    "idor": {
        "summary": "Implement proper authorization checks. Verify user owns requested resource.",
        "steps": [
            "Implement proper authorization checks for all resources",
            "Verify user owns or has permission to access requested resource",
            "Use indirect object references (e.g., UUIDs) instead of sequential IDs",
            "Implement role-based access control (RBAC)",
            "Log and monitor access attempts",
            "Validate permissions on every request"
        ]
    },
}


def get_remediation_hint(vuln_type: Optional[str]) -> Dict[str, Any]:
    """
    Get remediation hint for a vulnerability type.
    
    Args:
        vuln_type: Vulnerability type (e.g., "xss", "sqli")
        
    Returns:
        Dict with "summary" and "steps" keys, or empty dict if not found
    """
    if not vuln_type:
        return {}
    
    vuln_type_normalized = vuln_type.lower().strip()
    return REMEDIATION_HINTS.get(vuln_type_normalized, {})


def extract_vuln_type_from_categories(categories: list) -> Optional[str]:
    """
    Extract primary vulnerability type from a list of categories.
    
    Args:
        categories: List of category strings (e.g., ["xss", "sqli"])
        
    Returns:
        First matching vulnerability type, or None
    """
    if not categories:
        return None
    
    # Normalize categories
    normalized = [c.lower().strip() if isinstance(c, str) else str(c).lower().strip() for c in categories]
    
    # Return first category that matches a remediation hint
    for cat in normalized:
        if cat in REMEDIATION_HINTS:
            return cat
    
    # If no exact match, return first category
    return normalized[0] if normalized else None

