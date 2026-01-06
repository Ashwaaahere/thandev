"""
HTTP Security Header Checker
Checks for missing or misconfigured security headers in HTTP responses
"""
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import httpx
import json

from app.models.finding import Finding, Severity, FindingStatus
from app.models.scan import ScanJob

logger = logging.getLogger(__name__)

# Security headers to check
SECURITY_HEADERS = [
    "Content-Security-Policy",
    "Strict-Transport-Security",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
]

# Severity mapping for missing headers
HEADER_SEVERITY = {
    "Content-Security-Policy": Severity.MEDIUM,
    "Strict-Transport-Security": Severity.MEDIUM,
    "X-Frame-Options": Severity.MEDIUM,
    "X-Content-Type-Options": Severity.LOW,
    "Referrer-Policy": Severity.LOW,
    "Permissions-Policy": Severity.INFO,
}

# Header descriptions and recommendations
HEADER_INFO = {
    "Content-Security-Policy": {
        "description": "Content-Security-Policy (CSP) helps prevent XSS attacks by controlling which resources can be loaded. Without CSP, your application is vulnerable to cross-site scripting and data injection attacks.",
        "recommendation": "Implement a Content-Security-Policy header that restricts resource loading. Example: Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';",
    },
    "Strict-Transport-Security": {
        "description": "Strict-Transport-Security (HSTS) forces browsers to use HTTPS connections, preventing man-in-the-middle attacks and protocol downgrade attacks. Without HSTS, users may be vulnerable to SSL stripping attacks.",
        "recommendation": "Add a Strict-Transport-Security header with appropriate max-age. Example: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload",
    },
    "X-Frame-Options": {
        "description": "X-Frame-Options prevents clickjacking attacks by controlling whether your site can be embedded in frames. Without this header, your site could be embedded in malicious iframes.",
        "recommendation": "Set X-Frame-Options to prevent framing. Example: X-Frame-Options: DENY or X-Frame-Options: SAMEORIGIN",
    },
    "X-Content-Type-Options": {
        "description": "X-Content-Type-Options prevents browsers from MIME-sniffing, which can lead to security vulnerabilities. Without this header, browsers may misinterpret content types.",
        "recommendation": "Add X-Content-Type-Options header. Example: X-Content-Type-Options: nosniff",
    },
    "Referrer-Policy": {
        "description": "Referrer-Policy controls how much referrer information is sent with requests. Without a proper policy, sensitive information may leak through referrer headers.",
        "recommendation": "Set a Referrer-Policy to control referrer information. Example: Referrer-Policy: strict-origin-when-cross-origin",
    },
    "Permissions-Policy": {
        "description": "Permissions-Policy (formerly Feature-Policy) controls which browser features and APIs can be used. Without this header, you have less control over browser capabilities.",
        "recommendation": "Configure Permissions-Policy to restrict unnecessary browser features. Example: Permissions-Policy: geolocation=(), microphone=(), camera=()",
    },
}


class HttpSecurityResult(BaseModel):
    """Result of HTTP security header check"""
    final_url: str
    status_code: int
    headers: Dict[str, str]


async def fetch_http_security(target_url: str, timeout: float = 10.0) -> Optional[HttpSecurityResult]:
    """
    Fetch HTTP response and collect security headers.
    
    Args:
        target_url: URL to check (must start with http:// or https://)
        timeout: Request timeout in seconds
        
    Returns:
        HttpSecurityResult with final URL, status code, and headers, or None on error
    """
    # Validate URL scheme
    if not target_url.startswith(("http://", "https://")):
        logger.debug(f"Skipping HTTP header check for non-HTTP URL: {target_url}")
        return None
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(target_url)
            
            # Only process successful responses (status < 500)
            if response.status_code >= 500:
                logger.warning(
                    f"HTTP request to {target_url} returned status {response.status_code}, "
                    "skipping header checks"
                )
                return None
            
            # Normalize headers to case-insensitive dict (lowercase keys)
            normalized_headers = {k.lower(): v for k, v in response.headers.items()}
            
            return HttpSecurityResult(
                final_url=str(response.url),
                status_code=response.status_code,
                headers=normalized_headers,
            )
            
    except httpx.TimeoutException:
        logger.warning(f"Timeout while fetching HTTP headers from {target_url}")
        return None
    except httpx.RequestError as e:
        logger.warning(f"Network error while fetching HTTP headers from {target_url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error while fetching HTTP headers from {target_url}: {e}", exc_info=True)
        return None


def build_header_findings(result: HttpSecurityResult, scan_job: ScanJob) -> List[Finding]:
    """
    Build Finding objects for missing security headers.
    
    Args:
        result: HttpSecurityResult from fetch_http_security
        scan_job: ScanJob instance
        
    Returns:
        List of Finding objects (not yet added to session)
    """
    findings = []
    headers_lower = result.headers
    
    for header_name in SECURITY_HEADERS:
        header_lower = header_name.lower()
        
        # Check if header is missing
        if header_lower not in headers_lower:
            # Get header info
            header_info = HEADER_INFO.get(header_name, {
                "description": f"Missing {header_name} header.",
                "recommendation": f"Add {header_name} header to improve security.",
            })
            
            # Get severity
            severity = HEADER_SEVERITY.get(header_name, Severity.INFO)
            
            # Build raw_data JSON
            raw_data = {
                "checked_url": result.final_url,
                "status_code": result.status_code,
                "response_headers": {k: v for k, v in result.headers.items()},
            }
            
            # Create finding
            finding = Finding(
                scan_job_id=scan_job.id,
                title=f"Missing {header_name} header",
                description=header_info["description"],
                severity=severity,
                recommendation=header_info["recommendation"],
                url=result.final_url,
                tool_name="http_headers",
                raw_data=json.dumps(raw_data),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            logger.debug(f"Created finding for missing header: {header_name}")
    
    logger.info(f"Created {len(findings)} HTTP header findings for scan {scan_job.id}")
    return findings
