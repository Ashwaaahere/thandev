"""
Unified severity engine for Thandev findings.

This module provides deterministic, industry-standard severity mapping for all security findings,
respecting tool-provided severity (especially ZAP riskcode/confidence) while applying
evidence-based rules for non-ZAP tools.
"""
from typing import Dict, Any, Optional, Tuple
from app.models.finding import Severity
import json
import re


def normalize_severity(value: Any) -> Severity:
    """
    Normalize a severity value (string, enum, int riskcode, or None) to Severity enum.
    
    Args:
        value: Severity value (string like "info", "low", etc., Severity enum, 
               integer riskcode (0-4), or None)
        
    Returns:
        Severity enum (defaults to INFO if invalid)
    """
    if value is None:
        return Severity.INFO
    
    if isinstance(value, Severity):
        return value
    
    # Handle integer riskcodes (ZAP format: 0=Info, 1=Low, 2=Medium, 3=High, 4=Critical)
    if isinstance(value, (int, float)):
        riskcode = int(value)
        riskcode_map = {
            0: Severity.INFO,
            1: Severity.LOW,
            2: Severity.MEDIUM,
            3: Severity.HIGH,
            4: Severity.CRITICAL,
        }
        return riskcode_map.get(riskcode, Severity.INFO)
    
    if isinstance(value, str):
        severity_str = value.lower().strip()
        severity_map = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
            "informational": Severity.INFO,
        }
        return severity_map.get(severity_str, Severity.INFO)
    
    return Severity.INFO


def zap_to_severity(riskcode: Any, confidence: Any = None, alert_name: str = "", raw_alert: Dict[str, Any] = None) -> Tuple[Severity, bool]:
    """
    Map ZAP riskcode and confidence to Thandev severity.
    
    ZAP riskcode mapping:
    - 0 = Informational -> Info
    - 1 = Low -> Low
    - 2 = Medium -> Medium
    - 3 = High -> High
    - 4 = Critical -> Critical (rare, but possible)
    
    Confidence adjustment:
    - Low confidence (0/False) + Medium/High risk -> add needs_verification flag
    - Confirmed (3/True) + High risk + severe attack patterns -> may escalate to Critical
    
    Args:
        riskcode: ZAP riskcode (0-4, or string representation)
        confidence: ZAP confidence (0-3, or string like "Low", "Medium", "High", "Confirmed")
        alert_name: Alert name (for pattern matching)
        raw_alert: Full ZAP alert dict (for additional context)
        
    Returns:
        Tuple of (severity: Severity, needs_verification: bool)
    """
    # Normalize riskcode
    if riskcode is None:
        return (Severity.INFO, False)
    
    if isinstance(riskcode, str):
        try:
            riskcode = int(riskcode)
        except (ValueError, TypeError):
            riskcode = 0
    elif not isinstance(riskcode, int):
        riskcode = 0
    
    # Map riskcode to base severity
    riskcode_map = {
        0: Severity.INFO,
        1: Severity.LOW,
        2: Severity.MEDIUM,
        3: Severity.HIGH,
        4: Severity.CRITICAL,
    }
    base_severity = riskcode_map.get(riskcode, Severity.INFO)
    
    # Normalize confidence
    confidence_level = _normalize_confidence(confidence)
    
    # Apply confidence adjustments
    needs_verification = False
    
    # Low confidence + Medium/High risk -> needs verification
    if confidence_level == "low" and base_severity in [Severity.MEDIUM, Severity.HIGH]:
        needs_verification = True
    
    # Check for Critical escalation (only for confirmed High-severity attacks)
    if base_severity == Severity.HIGH and confidence_level == "confirmed":
        # Check if this is a severe attack pattern that warrants Critical
        if _is_severe_attack_pattern(alert_name, raw_alert):
            return (Severity.CRITICAL, False)
    
    return (base_severity, needs_verification)


def _normalize_confidence(confidence: Any) -> str:
    """Normalize ZAP confidence to string: low, medium, high, confirmed"""
    if confidence is None:
        return "medium"  # Default assumption
    
    if isinstance(confidence, str):
        conf_lower = confidence.lower()
        if conf_lower in ["low", "0"]:
            return "low"
        elif conf_lower in ["medium", "1"]:
            return "medium"
        elif conf_lower in ["high", "2"]:
            return "high"
        elif conf_lower in ["confirmed", "3", "true"]:
            return "confirmed"
        return "medium"
    
    if isinstance(confidence, (int, float)):
        if confidence == 0:
            return "low"
        elif confidence == 1:
            return "medium"
        elif confidence == 2:
            return "high"
        elif confidence >= 3:
            return "confirmed"
        return "medium"
    
    if isinstance(confidence, bool):
        return "confirmed" if confidence else "low"
    
    return "medium"


def _is_severe_attack_pattern(alert_name: str, raw_alert: Dict[str, Any] = None) -> bool:
    """
    Check if alert represents a severe attack pattern (RCE, auth bypass, data exfil).
    
    Only escalate to Critical for confirmed severe attacks, not headers/CSP issues.
    """
    if not alert_name:
        return False
    
    alert_lower = alert_name.lower()
    
    # Severe attack patterns
    severe_patterns = [
        "sql injection",
        "sqli",
        "remote code execution",
        "rce",
        "command injection",
        "authentication bypass",
        "authorization bypass",
        "path traversal",
        "file inclusion",
        "xxe",
        "server-side request forgery",
        "ssrf",
    ]
    
    for pattern in severe_patterns:
        if pattern in alert_lower:
            return True
    
    # Check raw alert for additional indicators
    if raw_alert:
        description = raw_alert.get("description", "").lower()
        solution = raw_alert.get("solution", "").lower()
        
        for pattern in severe_patterns:
            if pattern in description or pattern in solution:
                return True
    
    return False


def nuclei_to_severity(template_meta: Dict[str, Any]) -> Severity:
    """
    Compute severity for Nuclei findings.
    
    Priority:
    1. Use info.severity as SOURCE OF TRUTH if present (even if "info")
    2. Use top-level severity field if info.severity missing
    3. Infer from CVSS score if present
    4. Infer from tags (rce, sqli, lfi, ssrf, auth-bypass, exposed-panel, creds) -> High/Critical
    5. Default to Info
    
    Args:
        template_meta: Nuclei template metadata (info dict or full finding)
        
    Returns:
        Severity enum
    """
    if not isinstance(template_meta, dict):
        return Severity.INFO
    
    info = template_meta.get("info", {})
    if not isinstance(info, dict):
        info = {}
    
    # 1. Use info.severity as primary source of truth (even if it maps to INFO)
    severity_str = info.get("severity", "").lower().strip() if isinstance(info.get("severity"), str) else ""
    if severity_str and severity_str in ("critical", "high", "medium", "low", "info", "informational"):
        return normalize_severity(severity_str)
    
    # 2. Fallback: check top-level severity field (from runner parser)
    top_level_severity = template_meta.get("severity", "")
    if isinstance(top_level_severity, str):
        top_level_severity = top_level_severity.lower().strip()
        if top_level_severity and top_level_severity in ("critical", "high", "medium", "low", "info", "informational"):
            return normalize_severity(top_level_severity)
    
    # 3. Fallback: infer from CVSS score if present
    classification = info.get("classification", {})
    if isinstance(classification, dict):
        cvss_score = classification.get("cvss-score")
        if cvss_score is not None:
            try:
                cvss = float(cvss_score)
                if cvss >= 9.0:
                    return Severity.CRITICAL
                elif cvss >= 7.0:
                    return Severity.HIGH
                elif cvss >= 4.0:
                    return Severity.MEDIUM
                elif cvss >= 0.1:
                    return Severity.LOW
                else:
                    return Severity.INFO
            except (ValueError, TypeError):
                pass
    
    # 4. Fallback: infer from tags
    tags = info.get("tags", [])
    if not tags:
        tags = template_meta.get("tags", [])

    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]

    if isinstance(tags, list):
        tags_lower = [str(t).lower() for t in tags]

        # Critical patterns
        critical_tags = ["rce", "remote-code-execution", "sqli", "sql-injection", "auth-bypass", "authentication-bypass"]
        if any(tag in tags_lower for tag in critical_tags):
            return Severity.CRITICAL

        # High patterns
        high_tags = ["lfi", "rfi", "ssrf", "xxe", "exposed-panel", "creds", "credentials", "cmdi", "command-injection"]
        if any(tag in tags_lower for tag in high_tags):
            return Severity.HIGH
    
    # 5. Default
    return Severity.INFO


def retire_to_severity(finding_data: Dict[str, Any]) -> Severity:
    """
    Compute severity for Retire.js findings (vulnerable libraries).
    
    Rules:
    - Known vulnerabilities/CVE => Medium
    - High impact (XSS/RCE/Prototype pollution) + very old version => High
    
    Args:
        finding_data: Retire.js finding data
        
    Returns:
        Severity enum
    """
    # Check for high-impact vulnerabilities
    component = finding_data.get("component", "").lower()
    version = finding_data.get("version", "")
    vulnerabilities = finding_data.get("vulnerabilities", [])
    
    # Check if any vulnerability is high impact
    high_impact_patterns = ["rce", "xss", "prototype pollution", "remote code execution"]
    
    for vuln in vulnerabilities:
        if isinstance(vuln, dict):
            info = vuln.get("info", [])
            if isinstance(info, list):
                for info_item in info:
                    if isinstance(info_item, str):
                        info_lower = info_item.lower()
                        for pattern in high_impact_patterns:
                            if pattern in info_lower:
                                # Check if version is very old (heuristic: version number < 1.0 or year < 2020)
                                if _is_old_version(version):
                                    return Severity.HIGH
                                return Severity.MEDIUM
    
    # Default: Medium for any known vulnerability
    if vulnerabilities:
        return Severity.MEDIUM
    
    return Severity.INFO


def _is_old_version(version: str) -> bool:
    """Heuristic to check if version is very old"""
    if not version:
        return False
    
    # Extract year if present (e.g., "2020.1.0" or "1.0.0" from 2020)
    year_match = re.search(r'20\d{2}', version)
    if year_match:
        year = int(year_match.group())
        return year < 2020
    
    # Check if major version is < 1.0
    version_parts = re.findall(r'\d+', version)
    if version_parts:
        try:
            major = int(version_parts[0])
            return major < 1
        except ValueError:
            pass
    
    return False


def sslscan_to_severity(finding_data: Dict[str, Any]) -> Severity:
    """
    Compute severity for SSLScan findings.
    
    Rules:
    - Deprecated protocols (SSLv2/v3, TLS1.0) => Medium
    - Weak ciphers (RC4, 3DES) => Medium/Low depending on context
    - Expired/self-signed in prod => Low/Medium (config dependent, default Low)
    
    Args:
        finding_data: SSLScan finding data
        
    Returns:
        Severity enum
    """
    title = str(finding_data.get("title", "")).lower()
    description = str(finding_data.get("description", "")).lower()
    
    # Deprecated protocols
    deprecated_protocols = ["sslv2", "sslv3", "tls1.0", "tls 1.0"]
    for protocol in deprecated_protocols:
        if protocol in title or protocol in description:
            return Severity.MEDIUM
    
    # Weak ciphers
    weak_ciphers = ["rc4", "3des", "des"]
    for cipher in weak_ciphers:
        if cipher in title or cipher in description:
            return Severity.MEDIUM
    
    # Expired/self-signed (default to Low)
    if "expired" in title or "expired" in description:
        return Severity.LOW
    if "self-signed" in title or "self-signed" in description or "self signed" in title:
        return Severity.LOW
    
    return Severity.INFO


def portfinding_to_severity(service: str, port: int, evidence: str = "", title: str = "") -> Severity:
    """
    Compute severity for port/service findings (Nmap, etc.).
    
    Rules:
    - Open port alone => Info
    - Exposed admin service (Tomcat manager, Redis unauth, etc.) => High (if confirmed by HTTP probe)
    - Known dangerous port + no auth (e.g., Redis 6379 open) => Critical/High based on evidence
    
    Args:
        service: Service name (e.g., "redis", "tomcat")
        port: Port number
        evidence: Evidence string (e.g., "authentication disabled")
        title: Finding title
        
    Returns:
        Severity enum
    """
    service_lower = (service or "").lower()
    evidence_lower = (evidence or "").lower()
    title_lower = (title or "").lower()
    
    # Critical: Unauthenticated dangerous services
    critical_services = ["redis", "mongodb", "memcached", "elasticsearch"]
    if any(svc in service_lower for svc in critical_services):
        if "auth" in evidence_lower and ("no" in evidence_lower or "disabled" in evidence_lower or "none" in evidence_lower):
            return Severity.CRITICAL
        if "unauth" in evidence_lower or "unauthenticated" in evidence_lower:
            return Severity.CRITICAL
    
    # High: Admin panels, management interfaces
    admin_patterns = ["manager", "admin", "console", "dashboard", "jenkins", "tomcat"]
    if any(pattern in service_lower or pattern in title_lower for pattern in admin_patterns):
        return Severity.HIGH
    
    # Default: Info for open ports
    return Severity.INFO


def httpx_wappalyzer_to_severity(finding_data: Dict[str, Any]) -> Severity:
    """
    Compute severity for HTTPX/Wappalyzer tech fingerprinting findings.
    
    Rules:
    - "Outdated/EOL component detected" => Medium (add needs_verification if only fingerprinted)
    - Pure "technology identified" => Info
    
    Args:
        finding_data: HTTPX/Wappalyzer finding data
        
    Returns:
        Severity enum
    """
    title = str(finding_data.get("title", "")).lower()
    description = str(finding_data.get("description", "")).lower()
    
    # Outdated/EOL components
    outdated_patterns = ["outdated", "eol", "end of life", "deprecated", "vulnerable version"]
    if any(pattern in title or pattern in description for pattern in outdated_patterns):
        return Severity.MEDIUM
    
    # Default: Info for technology identification
    return Severity.INFO


def header_finding_to_severity(header_name: str, finding_data: Dict[str, Any]) -> Severity:
    """
    Compute severity for security header findings.
    
    Rules:
    - Missing X-Content-Type-Options => Low
    - Missing X-Frame-Options / no frame-ancestors => Low (Medium if app has authenticated sensitive actions; keep Low by default)
    - Missing CSP => Low (Medium if auth site; keep Low default)
    - CORS misconfig:
      - ACAO=* + ACAC=true OR reflective origin + credentials => High
      - permissive ACAO=* without credentials => Low/Medium (default Low unless sensitive endpoints)
    
    Args:
        header_name: Header name (e.g., "X-Frame-Options")
        finding_data: Finding data with evidence (actual header values)
        
    Returns:
        Severity enum
    """
    header_lower = (header_name or "").lower()
    evidence = str(finding_data.get("evidence", "")).lower()
    title = str(finding_data.get("title", "")).lower()
    description = str(finding_data.get("description", "")).lower()
    
    # CORS misconfiguration (High severity)
    if "cors" in header_lower or "cors" in title or "cors" in description:
        # Check for dangerous CORS config
        if ("acao" in evidence or "access-control-allow-origin" in evidence):
            # ACAO=* + ACAC=true (credentials allowed with wildcard)
            if "*" in evidence and ("acac" in evidence or "credentials" in evidence or "true" in evidence):
                return Severity.HIGH
            # Reflective origin + credentials
            if "reflective" in evidence or "origin" in evidence:
                if "credentials" in evidence or "acac" in evidence:
                    return Severity.HIGH
        # Permissive ACAO=* without credentials -> Low/Medium (default Low)
        if "*" in evidence:
            return Severity.LOW
    
    # Missing headers (Low severity by default)
    missing_headers = [
        "x-content-type-options",
        "x-frame-options",
        "content-security-policy",
        "csp",
        "strict-transport-security",
        "hsts",
    ]
    
    for header in missing_headers:
        if header in header_lower or header in title:
            return Severity.LOW
    
    return Severity.INFO


def compute_overall_max_severity(findings: list) -> Severity:
    """
    Compute the maximum severity from a list of findings.
    
    Args:
        findings: List of Finding objects or dicts with severity field
        
    Returns:
        Maximum Severity enum (or INFO if empty)
    """
    if not findings:
        return Severity.INFO
    
    severities = []
    for finding in findings:
        if hasattr(finding, "severity"):
            severity = finding.severity
        elif isinstance(finding, dict):
            severity = finding.get("severity")
        else:
            continue
        
        normalized = normalize_severity(severity)
        severities.append(normalized)
    
    if not severities:
        return Severity.INFO
    
    # Order: CRITICAL > HIGH > MEDIUM > LOW > INFO
    severity_order = {
        Severity.CRITICAL: 5,
        Severity.HIGH: 4,
        Severity.MEDIUM: 3,
        Severity.LOW: 2,
        Severity.INFO: 1,
    }
    
    return max(severities, key=lambda s: severity_order.get(s, 0))

