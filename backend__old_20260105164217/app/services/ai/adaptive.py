"""
Adaptive scan refinement service
Analyzes initial findings and stack_info to plan follow-up scan waves
"""
import logging
from typing import Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.finding import Finding

logger = logging.getLogger(__name__)


def refine_scan(
    stack_info: Dict[str, Any],
    findings: List["Finding"],
    scan_level: str
) -> Dict[str, Any]:
    """
    Refine scan plan based on initial findings and stack_info.
    
    This function analyzes the results from the initial scan wave and determines
    if additional follow-up waves are needed. Currently returns empty waves as a
    placeholder for future advanced logic.
    
    Args:
        stack_info: Dictionary containing target metadata:
            - target_url: Target URL
            - scan_level: Scan level string
            - http: Optional HTTP response info (status_code, headers)
        findings: List of Finding objects from initial scan wave
        scan_level: Scan level string ("basic", "pro", or "advanced")
        
    Returns:
        Dictionary with additional scan waves:
        {
            "waves": [
                {
                    "phase": "follow-up",
                    "tools": [
                        {"name": "tool_name", "config": {}},
                        ...
                    ]
                },
                ...
            ]
        }
        Currently always returns {"waves": []} (no follow-up waves).
        
    Future Behavior (Placeholder for Advanced Logic):
    
    The following logic will be implemented in future versions:
    
    1. High-Severity Findings on Auth Endpoints:
       - If scan_level == "advanced" and findings contain high/critical severity
         issues on login or authentication endpoints (e.g., URLs containing
         "/login", "/auth", "/admin"), we might:
         - Add a second wave with extra XSS/SQLi-specific nuclei templates
         - Add authentication-focused tools for deeper testing
         - Add session management testing tools
    
    2. No Findings or Low Severity Only:
       - If no findings are found, or only low/info severity findings exist,
         we probably return no more waves (current behavior).
       - This avoids unnecessary follow-up scans when the target appears secure.
    
    3. Technology-Specific Follow-ups:
       - If WordPress detected in stack_info["http"]["headers"], add
         WordPress-specific nuclei templates in follow-up wave
       - If SQL injection found, add database-specific enumeration tools
       - If XSS found, add XSS-specific testing templates
    
    4. API-Specific Enhancements:
       - If is_json_api is True in stack_info, add API-specific security
         testing tools in follow-up wave
       - Focus on API authentication, rate limiting, and input validation
    
    Current Implementation:
    - Always returns {"waves": []} (no follow-up waves)
    - Logs findings count and severity breakdown for future use
    - Maintains backward compatibility
    """
    logger.info(f"Refining scan plan based on {len(findings)} findings for level '{scan_level}'")
    
    # Analyze findings for future logic
    if findings:
        # Count findings by severity
        severity_counts = {}
        high_severity_count = 0
        auth_endpoint_findings = []
        
        for finding in findings:
            severity = finding.severity.value if hasattr(finding.severity, 'value') else str(finding.severity)
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Track high/critical severity
            if severity in ["high", "critical"]:
                high_severity_count += 1
            
            # Track findings on auth-related endpoints
            finding_url = (finding.url or "").lower()
            if any(keyword in finding_url for keyword in ["/login", "/auth", "/admin", "/signin"]):
                auth_endpoint_findings.append(finding)
        
        logger.debug(f"Findings analysis: severity_counts={severity_counts}, "
                    f"high_severity={high_severity_count}, "
                    f"auth_endpoints={len(auth_endpoint_findings)}")
        
        # TODO: Future logic will use these values:
        # - If scan_level == "advanced" and high_severity_count > 0 and len(auth_endpoint_findings) > 0:
        #     return follow-up wave with XSS/SQLi templates and auth-focused tools
    else:
        logger.debug("No findings from initial wave - no follow-up needed")
    
    # Check stack_info for technology detection (future use)
    if stack_info:
        http_info = stack_info.get("http", {})
        if http_info:
            headers = http_info.get("headers", {})
            server = headers.get("server", "").lower()
            logger.debug(f"HTTP info: status={http_info.get('status_code')}, server={server}")
            
            # TODO: Future logic will detect technologies:
            # - If "wordpress" in server or headers, add WordPress templates
            # - If "drupal" in server, add Drupal templates
            # - etc.
    
    # For now, always return empty waves (no follow-up needed)
    # This maintains current behavior while preparing for future enhancements
    return {
        "waves": []
    }

