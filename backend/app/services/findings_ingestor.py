"""
Findings ingestor service
Handles parsing tool output and creating Finding records
"""
import logging
import json
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from urllib.parse import urlparse

from app.models.finding import Finding, FindingInstance, Severity, FindingStatus
from app.models.scan import ScanJob
from app.utils.finding_utils import (
    generate_dedup_key,
    normalize_url,
    normalize_parameter,
    get_remediation_hint,
    extract_vuln_type_from_categories,
)
from app.services.tool_name_utils import canonical_tool_name
from app.core.severity import normalize_severity, nuclei_to_severity
from app.utils.finding_normalizer import (
    normalize_and_group_finding,
    is_static_asset_path,
)

logger = logging.getLogger(__name__)


def _create_finding_with_canonical_name(
    tool_name: str | None,
    tool_result_id: str | None = None,
    **kwargs
) -> Finding:
    """
    Factory function to create Finding objects with canonical tool_name.
    
    This ensures all Finding objects have normalized tool_name regardless of
    how the ingestion function calls it. This is a choke point for tool_name normalization.
    
    Args:
        tool_name: Tool name (will be normalized to canonical form)
        tool_result_id: Optional tool_result_id to link finding to specific tool run
        **kwargs: All other Finding constructor arguments
        
    Returns:
        Finding object with canonical tool_name
    """
    # Normalize tool_name to canonical form (choke point)
    canonical_name = canonical_tool_name(tool_name)
    
    # Set both tool_name and tool field for backward compatibility
    kwargs['tool_name'] = canonical_name
    kwargs['tool'] = canonical_name  # tool is alias for tool_name
    
    # Set tool_result_id if provided
    if tool_result_id:
        kwargs['tool_result_id'] = tool_result_id
    
    return Finding(**kwargs)


# Explicit tag-to-category mapping for Nuclei findings
# Maps Nuclei template tags to vulnerability categories
NUCLEI_TAG_TO_CATEGORY = {
    # XSS
    "xss": "xss",
    "cross-site-scripting": "xss",
    # SQL Injection
    "sqli": "sqli",
    "sql-injection": "sqli",
    "sql": "sqli",
    # SSRF
    "ssrf": "ssrf",
    "server-side-request-forgery": "ssrf",
    # SSTI
    "ssti": "ssti",
    "server-side-template-injection": "ssti",
    "template-injection": "ssti",
    # XXE
    "xxe": "xxe",
    "xml-external-entity": "xxe",
    # Directory Traversal / File Inclusion
    "path-traversal": "dir_traversal",
    "directory-traversal": "dir_traversal",
    "lfi": "dir_traversal",
    "rfi": "dir_traversal",
    "local-file-inclusion": "dir_traversal",
    "remote-file-inclusion": "dir_traversal",
    "file-inclusion": "dir_traversal",
    # CORS
    "cors-misconfig": "cors",
    "cors": "cors",
    "cross-origin-resource-sharing": "cors",
    # CSRF
    "csrf": "csrf",
    "cross-site-request-forgery": "csrf",
    # Command Injection / RCE
    "cmd-injection": "cmdi",
    "command-injection": "cmdi",
    "cmdi": "cmdi",
    "rce": "cmdi",
    "remote-code-execution": "cmdi",
    "code-execution": "cmdi",
    "os-commanding": "cmdi",
    # IDOR
    "idor": "idor",
    "insecure-direct-object-reference": "idor",
    "authorization": "idor",
}


def create_or_update_finding(
    db: Session,
    scan_job_id: str,
    project_id: str,
    finding_data: Dict[str, Any],
    tool_result_id: str | None = None,
) -> Finding:
    """
    Create a new finding or update an existing one based on dedup_key.
    
    This function implements cross-scan deduplication:
    - If a finding with the same dedup_key exists for this project, update it
    - Otherwise, create a new finding
    
    Args:
        db: Database session
        scan_job_id: Current scan job ID
        project_id: Project ID
        finding_data: Dict with finding fields:
            - tool: Tool name
            - template_id: Template/rule ID (optional)
            - rule_id: Alternative rule ID (optional)
            - url: URL (will be normalized)
            - parameter: Parameter name (optional)
            - vuln_type: Vulnerability type (optional)
            - category: Category (optional)
            - title, description, severity, etc. (standard finding fields)
            - http_method, evidence, etc. (optional location/evidence fields)
            - categories: List of categories (optional, used to extract vuln_type)
    
    Returns:
        Finding object (either newly created or updated)
    """
    now = datetime.now(timezone.utc)
    
    # Extract fields
    tool = finding_data.get("tool") or finding_data.get("tool_name", "")
    # Normalize tool name to canonical form (choke point)
    canonical_tool = canonical_tool_name(tool)
    template_id = finding_data.get("template_id")
    rule_id = finding_data.get("rule_id")
    url = finding_data.get("url", "")
    parameter = finding_data.get("parameter")
    vuln_type = finding_data.get("vuln_type")
    categories = finding_data.get("categories", [])
    
    # Extract vuln_type from categories if not provided
    if not vuln_type and categories:
        vuln_type = extract_vuln_type_from_categories(categories)
    
    # Normalize URL
    normalized_url = normalize_url(url) if url else ""
    
    # Generate dedup_key (use canonical tool name)
    dedup_key = generate_dedup_key(
        project_id=project_id,
        tool=canonical_tool,
        template_id=template_id,
        rule_id=rule_id,
        normalized_url=normalized_url,
        parameter=parameter,
        vuln_type=vuln_type,
    )
    
    # Check for existing finding
    existing_finding = db.query(Finding).filter(
        Finding.project_id == project_id,
        Finding.dedup_key == dedup_key
    ).first()
    
    if existing_finding:
        # Update existing finding
        existing_finding.last_seen_at = now
        existing_finding.last_seen_in_scan_id = scan_job_id
        existing_finding.found_count += 1
        existing_finding.not_seen_in_latest_scan = False
        
        # CRITICAL FIX: Update scan_job_id to current scan so findings show up in UI
        # This makes the finding appear in the current scan's results
        # The original scan is preserved in first_seen_at timestamp
        existing_finding.scan_job_id = scan_job_id
        
        # Update tool_name to canonical form if changed
        if existing_finding.tool_name != canonical_tool:
            existing_finding.tool_name = canonical_tool
            existing_finding.tool = canonical_tool
        
        # Update tool_result_id if provided (link to current tool run)
        if tool_result_id:
            existing_finding.tool_result_id = tool_result_id
        
        # Update fields that might have changed (but preserve first_seen_at)
        if "title" in finding_data:
            existing_finding.title = finding_data["title"][:500]
        if "description" in finding_data:
            existing_finding.description = finding_data.get("description")
        if "severity" in finding_data:
            # IMPORTANT: Preserve computed severity, do NOT overwrite with default INFO
            new_severity = normalize_severity(finding_data["severity"])
            # CRITICAL: For ZAP findings, do NOT allow overwriting computed severity back to INFO
            # unless riskcode is actually 0
            if existing_finding.tool_name == "zap" and hasattr(existing_finding, "zap_riskcode"):
                if existing_finding.zap_riskcode is not None and existing_finding.zap_riskcode != 0:
                    if new_severity == Severity.INFO:
                        logger.warning(
                            f"[SEVERITY-GUARD] Blocked overwrite of ZAP finding severity to INFO. "
                            f"Finding: {existing_finding.title[:50]}, riskcode={existing_finding.zap_riskcode}, "
                            f"keeping existing severity={existing_finding.severity.value}"
                        )
                        # Don't update severity if it would downgrade a non-zero riskcode to INFO
                        return existing_finding
            existing_finding.severity = new_severity
        if "needs_verification" in finding_data:
            existing_finding.needs_verification = finding_data.get("needs_verification", False)
        # Update ZAP metadata if provided
        if "wasc_id" in finding_data:
            existing_finding.wasc_id = finding_data.get("wasc_id")
        if "plugin_id" in finding_data:
            existing_finding.plugin_id = finding_data.get("plugin_id")
        if "alert_ref" in finding_data:
            existing_finding.alert_ref = finding_data.get("alert_ref")
        if "zap_confidence" in finding_data:
            existing_finding.zap_confidence = finding_data.get("zap_confidence")
        if "zap_riskcode" in finding_data:
            existing_finding.zap_riskcode = finding_data.get("zap_riskcode")
        if "url" in finding_data:
            existing_finding.url = (finding_data["url"][:2048] if finding_data["url"] else None)
        if "cve_id" in finding_data:
            existing_finding.cve_id = (finding_data["cve_id"][:50] if finding_data.get("cve_id") else None)
        if "cwe_id" in finding_data:
            existing_finding.cwe_id = (finding_data["cwe_id"][:50] if finding_data.get("cwe_id") else None)
        if "cvss_score" in finding_data:
            existing_finding.cvss_score = finding_data.get("cvss_score")
        if "raw_data" in finding_data:
            existing_finding.raw_data = finding_data.get("raw_data")
        
        # Update new fields
        if template_id:
            existing_finding.template_id = template_id
        if rule_id:
            existing_finding.rule_id = rule_id
        if vuln_type:
            existing_finding.vuln_type = vuln_type
        if categories:
            existing_finding.category = categories[0] if categories else None
        if "http_method" in finding_data:
            existing_finding.http_method = finding_data.get("http_method")
        if parameter:
            existing_finding.parameter = parameter
        if "evidence" in finding_data:
            existing_finding.evidence = finding_data.get("evidence")
        
        # Update remediation if not already set (don't overwrite user-provided remediation)
        if not existing_finding.remediation_summary and vuln_type:
            remediation = get_remediation_hint(vuln_type)
            if remediation:
                existing_finding.remediation_summary = remediation.get("summary")
                if remediation.get("steps"):
                    existing_finding.remediation_steps = "\n".join(remediation["steps"])
        
        return existing_finding
    else:
        # Create new finding
        # Get remediation hint - prefer provided remediation, fall back to hints
        remediation = {}
        if vuln_type:
            # Only use hint if remediation not explicitly provided
            if not finding_data.get("remediation_summary") and not finding_data.get("remediation_steps"):
                remediation = get_remediation_hint(vuln_type)
        
        # Normalize severity using severity engine
        # IMPORTANT: Do NOT default to INFO if severity is provided - preserve computed severity
        # If severity is already a Severity enum, use it directly; otherwise normalize
        provided_severity = finding_data.get("severity")
        if provided_severity is None:
            # Only default to INFO if severity is completely missing
            severity = Severity.INFO
            logger.warning(
                f"[SEVERITY-DEBUG] Finding '{finding_data.get('title', 'Unknown')[:50]}' has no severity, defaulting to INFO"
            )
        else:
            severity = normalize_severity(provided_severity)
            # DEBUG: Log severity assignment for first finding
            if hasattr(severity, 'value'):
                logger.debug(
                    f"[SEVERITY-DEBUG] Finding '{finding_data.get('title', 'Unknown')[:50]}': "
                    f"provided={provided_severity} (type={type(provided_severity).__name__}), "
                    f"normalized={severity.value}"
                )
        needs_verification = finding_data.get("needs_verification", False)
        
        # Use factory function to ensure canonical tool_name (choke point)
        finding = _create_finding_with_canonical_name(
            tool_name=canonical_tool,
            tool_result_id=tool_result_id,
            scan_job_id=scan_job_id,
            project_id=project_id,
            title=finding_data.get("title", "Security Finding")[:500],
            description=finding_data.get("description"),
            severity=severity,
            needs_verification=needs_verification,
            wasc_id=finding_data.get("wasc_id"),
            plugin_id=finding_data.get("plugin_id"),
            alert_ref=finding_data.get("alert_ref"),
            zap_confidence=finding_data.get("zap_confidence"),
            zap_riskcode=finding_data.get("zap_riskcode"),
            cve_id=(finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None),
            cwe_id=(finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None),
            cvss_score=finding_data.get("cvss_score"),
            url=(finding_data.get("url", "")[:2048] if finding_data.get("url") else None),
            path=finding_data.get("path"),
            line_number=finding_data.get("line_number"),
            template_id=template_id,
            rule_id=rule_id,
            vuln_type=vuln_type,
            category=(categories[0] if categories else None),
            http_method=finding_data.get("http_method"),
            parameter=parameter,
            header_name=finding_data.get("header_name"),
            cookie_name=finding_data.get("cookie_name"),
            evidence=finding_data.get("evidence"),
            raw_data=finding_data.get("raw_data"),
            dedup_key=dedup_key,
            first_seen_at=now,
            last_seen_at=now,
            last_seen_in_scan_id=scan_job_id,
            found_count=1,
            not_seen_in_latest_scan=False,
            remediation_summary=finding_data.get("remediation_summary") or remediation.get("summary"),
            remediation_steps=finding_data.get("remediation_steps") or ("\n".join(remediation["steps"]) if remediation.get("steps") else None),
            framework_hint=finding_data.get("framework_hint"),
            status=FindingStatus.OPEN,
        )
        
        db.add(finding)
        return finding


def create_or_update_finding_with_normalizer(
    db: Session,
    scan_job_id: str,
    project_id: str,
    finding_data: Dict[str, Any],
    tool_result_id: str | None = None,
) -> Tuple[Finding, FindingInstance]:
    """
    Create or update a finding using the new normalizer for deduplication and grouping.
    
    This function:
    - Normalizes the finding using finding_normalizer
    - Groups identical findings by finding_key
    - Creates/updates canonical Finding and appends FindingInstance
    - Handles severity normalization (de-noising)
    
    Args:
        db: Database session
        scan_job_id: Current scan job ID
        project_id: Project ID
        finding_data: Dict with finding fields
        tool_result_id: Optional tool_result_id
        
    Returns:
        Tuple of (Finding, FindingInstance)
    """
    now = datetime.now(timezone.utc)
    
    # Normalize and group finding
    canonical_data, instance_data = normalize_and_group_finding(
        finding_data,
        scan_job_id,
        project_id,
    )
    
    finding_key = canonical_data["finding_key"]
    canonical_tool = canonical_tool_name(canonical_data["tool"])
    
    # Check for existing finding by finding_key (within this scan)
    existing_finding = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.finding_key == finding_key
    ).first()
    
    if existing_finding:
        # Update existing finding
        existing_finding.last_seen_at = now
        existing_finding.affected_count += 1
        
        # Update severity if new one is higher
        new_severity = canonical_data["severity"]
        if isinstance(new_severity, str):
            new_severity = normalize_severity(new_severity)
        
        if new_severity.value != "info" and (
            existing_finding.severity == Severity.INFO or
            (existing_finding.severity == Severity.LOW and new_severity in [Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]) or
            (existing_finding.severity == Severity.MEDIUM and new_severity in [Severity.HIGH, Severity.CRITICAL]) or
            (existing_finding.severity == Severity.HIGH and new_severity == Severity.CRITICAL)
        ):
            existing_finding.severity = new_severity
        
        # Update rule_family if not set
        if not existing_finding.rule_family and canonical_data.get("rule_family"):
            existing_finding.rule_family = canonical_data["rule_family"]
        
        # Create new instance
        instance = FindingInstance(
            finding_id=existing_finding.id,
            url=instance_data.get("url"),
            path=instance_data.get("path"),
            http_method=instance_data.get("http_method"),
            parameter=instance_data.get("parameter"),
            evidence_snippet=instance_data.get("evidence_snippet"),
            is_static_asset=instance_data.get("is_static_asset", False),
        )
        db.add(instance)
        
        return existing_finding, instance
    else:
        # Create new finding
        # Get remediation hint
        vuln_type = canonical_data.get("vuln_type")
        remediation = {}
        if vuln_type:
            remediation = get_remediation_hint(vuln_type)
        
        finding = _create_finding_with_canonical_name(
            tool_name=canonical_tool,
            tool_result_id=tool_result_id,
            scan_job_id=scan_job_id,
            project_id=project_id,
            title=canonical_data.get("title", "Security Finding")[:500],
            description=canonical_data.get("description"),
            severity=canonical_data["severity"],
            needs_verification=finding_data.get("needs_verification", False),
            wasc_id=canonical_data.get("wasc_id"),
            plugin_id=canonical_data.get("plugin_id"),
            alert_ref=canonical_data.get("alert_ref"),
            zap_confidence=canonical_data.get("zap_confidence"),
            zap_riskcode=canonical_data.get("zap_riskcode"),
            cve_id=(canonical_data.get("cve_id")[:50] if canonical_data.get("cve_id") else None),
            cwe_id=(canonical_data.get("cwe_id")[:50] if canonical_data.get("cwe_id") else None),
            cvss_score=canonical_data.get("cvss_score"),
            url=None,  # No specific URL for canonical finding
            path=None,  # No specific path for canonical finding
            template_id=canonical_data.get("template_id"),
            rule_id=canonical_data.get("rule_id"),
            vuln_type=vuln_type,
            category=(canonical_data.get("categories", [])[0] if canonical_data.get("categories") else None),
            evidence=canonical_data.get("evidence"),
            raw_data=canonical_data.get("raw_data"),
            finding_key=finding_key,
            dedup_key=finding_key,  # Also set dedup_key for backward compatibility
            first_seen_at=now,
            last_seen_at=now,
            last_seen_in_scan_id=scan_job_id,
            found_count=1,
            not_seen_in_latest_scan=False,
            affected_count=1,
            rule_family=canonical_data.get("rule_family"),
            remediation_summary=canonical_data.get("remediation_summary") or remediation.get("summary"),
            remediation_steps=canonical_data.get("remediation_steps") or ("\n".join(remediation["steps"]) if remediation.get("steps") else None),
            status=FindingStatus.OPEN,
        )
        
        db.add(finding)
        db.flush()  # Flush to get finding.id
        
        # Create first instance
        instance = FindingInstance(
            finding_id=finding.id,
            url=instance_data.get("url"),
            path=instance_data.get("path"),
            http_method=instance_data.get("http_method"),
            parameter=instance_data.get("parameter"),
            evidence_snippet=instance_data.get("evidence_snippet"),
            is_static_asset=instance_data.get("is_static_asset", False),
        )
        db.add(instance)
        
        return finding, instance


def categorize_nuclei_finding(template_tags: list[str]) -> list[str]:
    """
    Categorize a Nuclei finding based on its template tags using explicit mapping.
    
    Returns lowercase category strings for attacker-relevant findings.
    
    Args:
        template_tags: List of template tags from Nuclei finding (e.g., ["xss", "sqli", "cve"])
        
    Returns:
        List of unique lowercase category strings (e.g., ["xss", "sqli"])
        
    Example:
        >>> categorize_nuclei_finding(["xss", "sqli", "cve"])
        ["xss", "sqli"]
        >>> categorize_nuclei_finding(["lfi", "rfi"])
        ["dir_traversal"]
    """
    if not template_tags:
        return []
    
    # Normalize tags to lowercase
    tags_lower = [tag.lower().strip() for tag in template_tags if tag]
    
    categories = []
    
    # Map tags to categories using explicit dictionary
    for tag in tags_lower:
        category = NUCLEI_TAG_TO_CATEGORY.get(tag)
        if category and category not in categories:
            categories.append(category)
    
    return categories


def ingest_nuclei_findings(
    db: Session,
    scan_job_id: str,
    nuclei_results: List[Dict[str, Any]],
    tool_result_id: str | None = None,
) -> List[Finding]:
    """
    Given a scan_job_id and a list of nuclei JSON objects, create or update Finding rows.
    
    This function implements cross-scan deduplication: same finding across multiple scans
    updates a single record instead of creating duplicates.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nuclei_results: List of Nuclei JSON objects (one per finding)
        
    Returns:
        List of Finding objects (created or updated)
    """
    # Get project_id from scan_job
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
    if not scan_job:
        logger.warning(f"Scan job {scan_job_id} not found, skipping nuclei findings ingestion")
        return []
    
    project_id = scan_job.project_id
    if not project_id:
        logger.warning(f"Project ID not found for scan job {scan_job_id}, skipping nuclei findings ingestion")
        return []
    
    findings = []
    
    for nuclei_data in nuclei_results:
        try:
            # Use severity engine for Nuclei findings
            severity = nuclei_to_severity(nuclei_data)
            
            # Extract title
            title = (
                nuclei_data.get("info", {}).get("name") or
                nuclei_data.get("template-id") or
                nuclei_data.get("matcher-name") or
                "Nuclei Finding"
            )
            
            # Extract description
            description = nuclei_data.get("info", {}).get("description", "")
            matched_at = nuclei_data.get("matched-at", "")
            if matched_at and description:
                description = f"{description}\n\nMatched at: {matched_at}"
            elif matched_at:
                description = f"Matched at: {matched_at}"
            
            # Extract CVE ID
            cve_id = None
            # Try multiple possible locations for CVE
            if "cve" in nuclei_data:
                cve_id = nuclei_data["cve"]
            elif "info" in nuclei_data and "classification" in nuclei_data["info"]:
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
            url = matched_at or nuclei_data.get("host", "") or nuclei_data.get("matched-at", "")
            
            # Extract template ID
            template_id = (
                nuclei_data.get("template-id") or
                nuclei_data.get("info", {}).get("id") or
                nuclei_data.get("id") or
                ""
            )
            
            # Extract template name for better identification
            template_name = (
                nuclei_data.get("info", {}).get("name") or
                nuclei_data.get("name") or
                template_id
            )
            
            # Extract template tags for categorization
            template_tags = []
            if "info" in nuclei_data and "tags" in nuclei_data["info"]:
                tags = nuclei_data["info"]["tags"]
                if isinstance(tags, list):
                    template_tags = tags
                elif isinstance(tags, str):
                    # Tags might be comma-separated string
                    template_tags = [t.strip() for t in tags.split(",")]
            
            # Categorize finding based on tags
            categories = categorize_nuclei_finding(template_tags)
            
            # Extract vuln_type from categories
            vuln_type = extract_vuln_type_from_categories(categories)
            
            # Extract HTTP method from request or method field
            http_method = None
            request_data = nuclei_data.get("request") or nuclei_data.get("curl-command") or ""
            if request_data:
                # Try to extract method from request (first word)
                if isinstance(request_data, str):
                    first_line = request_data.split('\n')[0] if '\n' in request_data else request_data
                    method_match = re.match(r'^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)', first_line.upper())
                    if method_match:
                        http_method = method_match.group(1)
            
            # Fallback to method field if available
            if not http_method:
                method_field = nuclei_data.get("method")
                if method_field and isinstance(method_field, str):
                    http_method = method_field.upper().split()[0] if " " in method_field else method_field.upper()
                    if http_method not in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
                        http_method = None
            
            # Extract parameter from URL or request
            parameter = None
            # Try to extract from URL query params
            if url:
                try:
                    parsed_url = urlparse(url)
                    if parsed_url.query:
                        # Extract first parameter name
                        from urllib.parse import parse_qs
                        params = parse_qs(parsed_url.query)
                        if params:
                            parameter = list(params.keys())[0]
                except:
                    pass
            
            # Try to extract from request body or extracted results
            if not parameter:
                extracted_results = nuclei_data.get("extracted-results") or nuclei_data.get("extracted_results")
                if extracted_results:
                    # Sometimes nuclei extracts parameter names
                    if isinstance(extracted_results, list) and extracted_results:
                        # Check if any extracted result looks like a parameter
                        for result in extracted_results[:3]:  # Check first few
                            if isinstance(result, str) and '=' in result:
                                # Might be a query param
                                param_match = re.search(r'([^=]+)=', result)
                                if param_match:
                                    parameter = param_match.group(1).strip()
                                    break
            
            # Build evidence string (human-readable summary)
            evidence_parts = []
            
            # Add template name/ID
            if template_name and template_name != template_id:
                evidence_parts.append(f"Template: {template_name}")
            
            # Add matched location
            if matched_at:
                evidence_parts.append(f"Matched at: {matched_at}")
            
            # Add extracted results if available
            extracted_results = nuclei_data.get("extracted-results") or nuclei_data.get("extracted_results")
            if extracted_results:
                if isinstance(extracted_results, list):
                    # Take first few results
                    results_str = ", ".join(str(r) for r in extracted_results[:3])
                    if len(extracted_results) > 3:
                        results_str += "..."
                    evidence_parts.append(f"Extracted: {results_str}")
                elif isinstance(extracted_results, str):
                    truncated = extracted_results[:200] + ('…' if len(extracted_results) > 200 else '')
                    evidence_parts.append(f"Extracted: {truncated}")
            
            # Add matcher name if available
            matcher_name = nuclei_data.get("matcher-name") or nuclei_data.get("matcher_name")
            if matcher_name:
                evidence_parts.append(f"Matcher: {matcher_name}")
            
            # Add request snippet if available (truncated)
            if request_data and isinstance(request_data, str):
                # Extract first line or first 150 chars
                request_snippet = request_data.split('\n')[0][:150] if '\n' in request_data else request_data[:150]
                if len(request_data) > 150:
                    request_snippet += '…'
                evidence_parts.append(f"Request: {request_snippet}")
            
            evidence = ". ".join(evidence_parts) if evidence_parts else None
            if evidence:
                evidence = evidence[:500]  # Limit total length
            
            # Store raw JSON as string, but add categories to the dict first
            raw_data_dict = nuclei_data.copy() if isinstance(nuclei_data, dict) else {}
            if categories:
                raw_data_dict["categories"] = categories
            
            raw_data = json.dumps(raw_data_dict) if isinstance(raw_data_dict, dict) else json.dumps(nuclei_data) if isinstance(nuclei_data, dict) else str(nuclei_data)
            
            # Use create_or_update_finding helper
            finding = create_or_update_finding(
                db=db,
                scan_job_id=scan_job_id,
                project_id=project_id,
                finding_data={
                    "tool": "nuclei",
                    "template_id": template_id,
                    "url": url,
                    "http_method": http_method,
                    "parameter": parameter,
                    "vuln_type": vuln_type,
                    "title": title,
                    "description": description,
                    "severity": severity,
                    "cve_id": cve_id,
                    "cwe_id": cwe_id,
                    "cvss_score": cvss_score,
                    "raw_data": raw_data,
                    "categories": categories,
                    "evidence": evidence,
                },
                tool_result_id=tool_result_id,
            )
            
            findings.append(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nuclei finding: {e}", exc_info=True)
            logger.debug(f"Problematic Nuclei data: {nuclei_data}")
            continue
    
    # Flush findings to make them visible to queries, then commit
    # This ensures counts computed after ingestion are accurate
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        created_count = sum(1 for f in findings if f.found_count == 1)
        updated_count = len(findings) - created_count
        logger.info(
            "Ingested %d nuclei findings into DB for scan %s (%d created, %d updated)",
            len(findings), scan_job_id, created_count, updated_count
        )
    except Exception as e:
        logger.error("Failed to commit findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    # Enrich findings with AI (non-blocking, runs in background)
    # Only enrich medium/high/critical findings that don't already have AI data
    if findings and scan_job:
        try:
            from app.services.finding_enrichment import enrich_findings_sync
            
            # Filter findings that need enrichment:
            # - severity in [medium, high, critical]
            # - impact_summary is NULL AND remediation_summary is NULL (avoid re-enriching)
            findings_to_enrich = [
                f for f in findings
                if f.severity in [Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
                and (not f.impact_summary or not f.remediation_summary)
            ]
            
            if findings_to_enrich:
                # Get org_id and target_url for enrichment
                org_id = None
                if scan_job.project and hasattr(scan_job.project, 'tenant') and scan_job.project.tenant:
                    org_id = scan_job.project.tenant.id
                
                target_url = None
                if scan_job.stack_info and isinstance(scan_job.stack_info, dict):
                    target_url = scan_job.stack_info.get("target_url")
                elif hasattr(scan_job, 'target_url'):
                    target_url = scan_job.target_url
                
                # Batch enrich findings (limit to 10 per batch to avoid timeouts)
                batch_size = 10
                for i in range(0, len(findings_to_enrich), batch_size):
                    batch = findings_to_enrich[i:i + batch_size]
                    enrich_findings_sync(db, batch, org_id, project_id, target_url)
        except Exception as e:
            # Don't fail ingestion if enrichment fails
            logger.warning(f"Failed to enrich nuclei findings: {e}", exc_info=True)
    
    return findings


def parse_nuclei_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nuclei JSONL output file (one JSON object per line) into a list of dicts.
    
    This function is robust to non-JSON lines (like ASCII tables, logs, etc.)
    and will skip them gracefully. Handles empty files and zero-byte files.
    
    Args:
        path: Path to the Nuclei output file (JSONL format)
        
    Returns:
        List of parsed Nuclei JSON objects (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    # Check if file is zero bytes
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                
                # Skip obvious non-JSON lines (tables, logs, etc.)
                # JSON objects/arrays start with { or [
                if not (line.startswith("{") or line.startswith("[")):
                    logger.debug(
                        "Skipping non-JSON line %d in nuclei output %s: %r",
                        line_no, path, line[:80]
                    )
                    continue
                
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        findings.append(obj)
                    else:
                        logger.debug("Skipping non-dict JSON on line %d in %s", line_no, path)
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
        
        logger.info("Parsed %d nuclei findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse Nuclei output file %s: %s", path, e, exc_info=True)
        return []


def parse_nmap_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nmap XML output file into a list of finding dicts.
    
    Each open port becomes a finding. Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the Nmap XML output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Extract host information
        for host in root.findall("host"):
            host_status = host.find("status")
            if host_status is None or host_status.get("state") != "up":
                continue
            
            # Get host address
            address_elem = host.find("address")
            host_ip = address_elem.get("addr") if address_elem is not None else "unknown"
            
            # Get hostname
            hostnames_elem = host.find("hostnames")
            hostname = host_ip
            if hostnames_elem is not None:
                hostname_elem = hostnames_elem.find("hostname")
                if hostname_elem is not None:
                    hostname = hostname_elem.get("name", host_ip)
            
            # Process ports
            ports_elem = host.find("ports")
            if ports_elem is None:
                continue
            
            for port_elem in ports_elem.findall("port"):
                port_state = port_elem.find("state")
                if port_state is None or port_state.get("state") != "open":
                    continue
                
                port_num = port_elem.get("portid")
                protocol = port_elem.get("protocol", "tcp")
                
                # Get service info
                service_elem = port_elem.find("service")
                service_name = service_elem.get("name", "unknown") if service_elem is not None else "unknown"
                service_product = service_elem.get("product", "") if service_elem is not None else ""
                service_version = service_elem.get("version", "") if service_elem is not None else ""
                
                # Build description
                description_parts = [
                    f"Host: {hostname} ({host_ip})",
                    f"Port: {port_num}/{protocol}",
                    f"Service: {service_name}",
                ]
                if service_product:
                    description_parts.append(f"Product: {service_product}")
                if service_version:
                    description_parts.append(f"Version: {service_version}")
                
                description = "\n".join(description_parts)
                
                # Determine severity based on port/service
                from app.core.config import settings
                severity = "info"
                high_risk_ports = [p.strip() for p in settings.HIGH_RISK_PORTS.split(",")]
                if port_num in high_risk_ports:  # SSH, RDP, VNC, etc.
                    severity = "medium"
                elif port_num in ["3306", "5432", "1433"]:  # MySQL, PostgreSQL, MSSQL
                    severity = "medium"
                elif port_num in ["21", "23", "25"]:  # FTP, Telnet, SMTP
                    severity = "low"
                elif port_num in ["80", "443", "8080", "8443"]:  # HTTP/HTTPS
                    severity = "info"
                
                # Build title
                title = f"Open port {port_num}/{protocol} ({service_name}) on {hostname}"
                
                # Build URL
                url = f"{hostname}:{port_num}"
                if port_num in ["80", "8080"]:
                    url = f"http://{hostname}:{port_num}"
                elif port_num in ["443", "8443"]:
                    url = f"https://{hostname}:{port_num}"
                
                # Store raw XML for this port as JSON
                raw_data = json.dumps({
                    "host": hostname,
                    "ip": host_ip,
                    "port": port_num,
                    "protocol": protocol,
                    "service": service_name,
                    "product": service_product,
                    "version": service_version,
                })
                
                findings.append({
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "cve_id": None,
                    "cwe_id": None,
                    "url": url,
                    "tool_name": "nmap",
                    "raw_data": raw_data,
                })
        
        logger.info("Parsed %d nmap findings from file for scan %s", len(findings), path)
        return findings
        
    except ET.ParseError as e:
        logger.warning("Failed to parse Nmap XML file %s: %s", path, e)
        return []
    except Exception as e:
        logger.error("Failed to read/parse Nmap output file %s: %s", path, e, exc_info=True)
        return []


def parse_sslscan_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse sslscan output file (JSON or text format) into a list of finding dicts.
    
    Handles both JSON output (when --json flag is used) and plain text output.
    Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the sslscan output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        # Try to parse as JSON first
        try:
            # Remove ANSI color codes if present
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            content_clean = ansi_escape.sub('', content)
            
            # Try to find JSON object/array
            json_start = content_clean.find('{')
            json_end = content_clean.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content_clean[json_start:json_end]
                data = json.loads(json_str)
                
                # Handle JSON format
                if isinstance(data, dict):
                    # Single JSON object
                    findings.extend(_parse_sslscan_json_object(data))
                elif isinstance(data, list):
                    # Array of JSON objects
                    for item in data:
                        if isinstance(item, dict):
                            findings.extend(_parse_sslscan_json_object(item))
        except (json.JSONDecodeError, ValueError):
            # Fall back to text parsing
            findings.extend(_parse_sslscan_text(content))
        
        logger.info("Parsed %d sslscan findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse sslscan output file %s: %s", path, e, exc_info=True)
        return []


def _parse_sslscan_json_object(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse a single sslscan JSON object into finding dicts"""
    findings = []
    
    host = data.get("host", "unknown")
    port = data.get("port", 443)
    target = f"{host}:{port}"
    
    # Check for weak protocols
    sslv2 = data.get("ssl_version", {}).get("SSLv2", {}).get("status", "").lower()
    sslv3 = data.get("ssl_version", {}).get("SSLv3", {}).get("status", "").lower()
    tls10 = data.get("ssl_version", {}).get("TLSv1.0", {}).get("status", "").lower()
    tls11 = data.get("ssl_version", {}).get("TLSv1.1", {}).get("status", "").lower()
    
    if sslv2 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if sslv3 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls10 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls11 == "enabled":
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    # Check for weak ciphers
    ciphers = data.get("cipher_suites", [])
    weak_ciphers = []
    for cipher in ciphers:
        cipher_name = cipher.get("cipher", "")
        key_length = cipher.get("key_length", 0)
        if key_length < 128 or "RC4" in cipher_name or "DES" in cipher_name or "MD5" in cipher_name:
            weak_ciphers.append(cipher_name)
    
    if weak_ciphers:
        findings.append({
            "severity": "medium",
            "title": f"Weak cipher suites detected on {target}",
            "description": f"Weak cipher suites found on {target}: {', '.join(weak_ciphers[:5])}",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    return findings


def _parse_sslscan_text(content: str) -> List[Dict[str, Any]]:
    """Parse sslscan plain text output into finding dicts"""
    findings = []
    
    # Remove ANSI color codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    content_clean = ansi_escape.sub('', content)
    
    # Extract host and port from content
    host_match = re.search(r'Testing SSL server\s+(\S+)\s+on port\s+(\d+)', content_clean)
    if not host_match:
        # Try alternative pattern
        host_match = re.search(r'Connected to\s+([\d.]+)', content_clean)
        port_match = re.search(r'port\s+(\d+)', content_clean)
        host = host_match.group(1) if host_match else "unknown"
        port = int(port_match.group(1)) if port_match else 443
    else:
        host = host_match.group(1)
        port = int(host_match.group(2))
    
    target = f"{host}:{port}"
    
    # Check for weak protocols in text
    if re.search(r'SSLv2\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],  # Store first 1000 chars
        })
    
    if re.search(r'SSLv3\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.0\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.1\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    # Check for weak ciphers
    weak_cipher_patterns = [
        (r'RC4', "high", "RC4 cipher is weak and should be disabled"),
        (r'DES', "high", "DES cipher is weak and should be disabled"),
        (r'3DES|Triple DES', "medium", "3DES cipher is deprecated and should be disabled"),
        (r'MD5', "high", "MD5 hash algorithm is weak and should not be used"),
        (r'SHA1', "medium", "SHA1 hash algorithm is deprecated and should be disabled"),
    ]
    
    for pattern, severity, description in weak_cipher_patterns:
        if re.search(pattern, content_clean, re.IGNORECASE):
            findings.append({
                "severity": severity,
                "title": f"Weak cipher/hash detected on {target}",
                "description": f"{description}",
                "cve_id": None,
                "cwe_id": "CWE-327",
                "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
                "tool_name": "sslscan",
                "raw_data": content_clean[:1000],
            })
    
    # Check for certificate issues
    cert_issues = [
        (r'Certificate.*expired', "high", "SSL certificate has expired"),
        (r'Certificate.*self.signed', "medium", "Self-signed certificate detected"),
        (r'Certificate.*invalid', "high", "Invalid SSL certificate detected"),
        (r'Certificate.*chain.*incomplete', "medium", "Incomplete certificate chain"),
    ]
    
    for pattern, severity, description in cert_issues:
        if re.search(pattern, content_clean, re.IGNORECASE):
            findings.append({
                "severity": severity,
                "title": f"Certificate issue on {target}",
                "description": f"{description}",
                "cve_id": None,
                "cwe_id": "CWE-295",
                "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
                "tool_name": "sslscan",
                "raw_data": content_clean[:1000],
            })
    
    # If we have output but no findings, create an informational finding
    # This helps users understand that SSLscan ran but found no issues
    if not findings and content_clean and len(content_clean) > 100:
        # Only create info finding if we have substantial output
        findings.append({
            "severity": "info",
            "title": f"SSL/TLS scan completed for {target}",
            "description": f"SSLscan completed successfully. No critical SSL/TLS issues detected. Review raw output for details.",
            "cve_id": None,
            "cwe_id": None,
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:2000],  # Store more data for info findings
        })
    
    return findings


def ingest_nmap_findings(
    db: Session,
    scan_job_id: str,
    nmap_results: List[Dict[str, Any]],
    tool_result_id: str | None = None,
) -> List[Finding]:
    """
    Ingest Nmap findings into the database.
    
    Per-tool idempotency: deletes existing nmap findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nmap_results: List of finding dicts from parse_nmap_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing nmap findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "nmap"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing nmap findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in nmap_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "Nmap Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="nmap",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nmap finding: {e}", exc_info=True)
            continue
    
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d nmap findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit nmap findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_sslscan_findings(
    db: Session,
    scan_job_id: str,
    sslscan_results: List[Dict[str, Any]],
    tool_result_id: str | None = None,
) -> List[Finding]:
    """
    Ingest sslscan findings into the database.
    
    Per-tool idempotency: deletes existing sslscan findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        sslscan_results: List of finding dicts from parse_sslscan_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing sslscan findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "sslscan"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing sslscan findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in sslscan_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "SSL/TLS Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="sslscan",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse sslscan finding: {e}", exc_info=True)
            continue
    
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d sslscan findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit sslscan findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_http_header_findings(
    db: Session,
    scan_job_id: str,
    header_findings: List[Finding],
) -> List[Finding]:
    """
    Ingest HTTP header findings into the database.
    
    Per-tool idempotency: deletes existing http_headers findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        header_findings: List of Finding objects for missing headers
        
    Returns:
        List of created Finding objects
    """
    # Delete existing http_headers findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "http_headers"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing http_headers findings for scan {scan_job_id}")
    
    # Add all findings to session
    for finding in header_findings:
        db.add(finding)
    
    # Flush findings to make them visible to queries, then commit
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d http_headers findings into DB for scan %s",
            len(header_findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit http_headers findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return header_findings


def parse_httpx_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse httpx JSONL output file into a list of finding dicts.
    
    Each line is a JSON object representing an HTTP response.
    Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the httpx JSONL output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("httpx output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("httpx output file is empty for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
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
                    
                    findings.append({
                        "title": finding_title[:500],
                        "description": description,
                        "severity": "info",
                        "url": url[:2048] if url else None,
                        "raw_data": json.dumps(data),
                    })
                    
                except json.JSONDecodeError:
                    logger.debug("Skipping non-JSON line %d in httpx output %s", line_no, path)
                    continue
                except Exception as e:
                    logger.warning(
                        "Unexpected error parsing line %d in %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d httpx findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse httpx output file %s: %s", path, e, exc_info=True)
        return []


def ingest_httpx_findings(
    db: Session,
    scan_job_id: str,
    httpx_results: List[Dict[str, Any]],
    tool_result_id: str | None = None,
) -> List[Finding]:
    """
    Ingest httpx findings into the database with aggregation to reduce noise.
    
    Implements aggregation to reduce noise:
    - Prioritizes URLs with interesting keywords (admin, login, debug, etc.)
    - Limits to max 200 individual findings per scan
    - Creates a summary finding for remaining endpoints
    
    Per-tool idempotency: deletes existing httpx findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        httpx_results: List of finding dicts from parse_httpx_output
        
    Returns:
        List of created Finding objects
    """
    # Early return if no results
    if not httpx_results:
        return []
    
    # Delete existing httpx findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "httpx"
    ).delete(synchronize_session=False)
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing httpx findings for scan {scan_job_id}")
    
    # Aggregation parameters
    MAX_INDIVIDUAL = 200
    
    # Interesting keywords to prioritize
    interesting_keywords = [
        "admin", "login", "auth", "debug", "backup", "test",
        "staging", "dev", "api", ".git", ".env", ".bak",
        "config", "console", "manage", "dashboard",
    ]
    
    def is_interesting(url: str) -> bool:
        """Check if URL contains interesting keywords"""
        if not url:
            return False
        url_lower = url.lower()
        return any(keyword in url_lower for keyword in interesting_keywords)
    
    # Separate prioritized and others
    prioritized = []
    others = []
    
    for finding_data in httpx_results:
        url = finding_data.get("url", "")
        if is_interesting(url):
            prioritized.append(finding_data)
        else:
            others.append(finding_data)
    
    # Sort prioritized by URL for consistency
    prioritized.sort(key=lambda x: x.get("url", ""))
    
    # Take up to MAX_INDIVIDUAL total (prioritize interesting)
    findings_to_create = prioritized[:MAX_INDIVIDUAL]
    remaining_slots = MAX_INDIVIDUAL - len(findings_to_create)
    if remaining_slots > 0:
        findings_to_create.extend(others[:remaining_slots])
        others = others[remaining_slots:]
    
    # CRITICAL FIX: If we have very few results (<= 10), always show them individually
    # This prevents single findings from being lost or only shown as summaries
    if len(httpx_results) <= 10 and len(findings_to_create) < len(httpx_results):
        # Add any remaining results that weren't included
        all_results = prioritized + others
        findings_to_create = all_results[:MAX_INDIVIDUAL]
        others = all_results[MAX_INDIVIDUAL:] if len(all_results) > MAX_INDIVIDUAL else []
    
    findings = []
    
    # Create individual findings for prioritized endpoints
    for finding_data in findings_to_create:
        try:
            url = finding_data.get("url", "")
            status_code = finding_data.get("status_code", 0)
            
            # Parse raw_data to extract additional info
            raw_data_str = finding_data.get("raw_data", "{}")
            try:
                raw_data_dict = json.loads(raw_data_str) if isinstance(raw_data_str, str) else raw_data_str
            except:
                raw_data_dict = {}
            if not isinstance(raw_data_dict, dict):
                raw_data_dict = {}
            
            # Build title
            title = f"HTTP surface: {url}"
            if status_code:
                title += f" (HTTP {status_code})"
            title = title[:500]
            
            # Build description from raw_data
            description_parts = []
            if status_code:
                description_parts.append(f"HTTP Status: {status_code}")
            
            title_page = raw_data_dict.get("title", "")
            if title_page:
                description_parts.append(f"Page Title: {title_page}")
            
            tech = raw_data_dict.get("tech", [])
            if tech:
                if isinstance(tech, list):
                    tech_str = ", ".join(tech[:5])  # Limit to 5 technologies
                else:
                    tech_str = str(tech)
                description_parts.append(f"Technologies: {tech_str}")
            
            tls_version = raw_data_dict.get("tls_version", "")
            if tls_version:
                description_parts.append(f"TLS Version: {tls_version}")
            
            description = "\n".join(description_parts) if description_parts else f"HTTP surface discovered at {url}"
            
            # Ensure categories in raw_data
            raw_data_dict["categories"] = ["HTTP Surface"]
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=title,
                description=description,
                severity=Severity.INFO,
                url=url[:2048] if url else None,
                tool_name="httpx",
                raw_data=json.dumps(raw_data_dict),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse httpx finding: {e}", exc_info=True)
            continue
    
    # Create summary finding if there are remaining endpoints
    if others:
        try:
            # Get scan job to extract target URL/domain
            scan_job = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
            root_domain = ""
            if scan_job and scan_job.project:
                target_url = getattr(scan_job.project, "target_url", "")
                if target_url:
                    parsed = urlparse(target_url)
                    root_domain = parsed.netloc or parsed.path.split("/")[0] if parsed.path else ""
            
            if not root_domain and httpx_results:
                # Fallback: extract from first URL
                first_url = httpx_results[0].get("url", "")
                if first_url:
                    parsed = urlparse(first_url)
                    root_domain = parsed.netloc or ""
            
            # Count by status code
            status_counts = {}
            for finding_data in others:
                raw_data_str = finding_data.get("raw_data", "{}")
                try:
                    raw_data_dict = json.loads(raw_data_str) if isinstance(raw_data_str, str) else raw_data_str
                except:
                    raw_data_dict = {}
                status = raw_data_dict.get("status_code", finding_data.get("status_code", "unknown"))
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Build summary description
            description_lines = [
                f"HTTP surface discovery identified {len(httpx_results)} total endpoints on {root_domain or 'target'}.",
                f"Of these, {len(findings_to_create)} are shown individually (prioritized by interesting keywords).",
                f"The remaining {len(others)} endpoints are summarized below.",
                "",
                "Status code breakdown for summarized endpoints:"
            ]
            for status, count in sorted(status_counts.items()):
                description_lines.append(f"  - HTTP {status}: {count} endpoints")
            
            description_lines.extend([
                "",
                "These endpoints were discovered but not individually reported to reduce noise.",
                "Review the full httpx output for complete endpoint list."
            ])
            
            raw_data_summary = {
                "summary": True,
                "total_endpoints": len(httpx_results),
                "summarized_endpoints": len(others),
                "status_breakdown": status_counts,
                "categories": ["HTTP Surface"]
            }
            
            summary_title = f"HTTP surface summary: {root_domain or 'target'} ({len(others)} additional endpoints)"
            if len(summary_title) > 500:
                summary_title = summary_title[:497] + "..."
            
            summary_finding = Finding(
                scan_job_id=scan_job_id,
                title=summary_title,
                description="\n".join(description_lines),
                severity=Severity.INFO,
                url=None,
                tool_name="httpx",
                raw_data=json.dumps(raw_data_summary),
                status=FindingStatus.OPEN,
            )
            
            findings.append(summary_finding)
            db.add(summary_finding)
            
        except Exception as e:
            logger.warning(f"Failed to create httpx summary finding: {e}", exc_info=True)
    
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d httpx findings into DB for scan %s (%d individual + %d summary)",
            len(findings), scan_job_id, len(findings_to_create), 1 if others else 0
        )
    except Exception as e:
        logger.error("Failed to commit httpx findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def parse_ffuf_output(path: Path, baseline_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Parse ffuf JSON output file into a list of finding dicts.
    
    ffuf with -json produces a JSON stream where each line contains a "result" object
    for discovered paths. We parse line by line and extract relevant information.
    
    PR-4C: Filters out 404/wildcard responses using baseline signature.
    
    Args:
        path: Path to the ffuf JSON output file
        baseline_filter: Optional baseline signature dict with:
            - status_code: Baseline status code
            - content_length: Baseline content length
            - word_count: Baseline word count
            - line_count: Baseline line count
            - content_hash: Baseline content hash (first 1000 chars)
        
    Returns:
        List of finding dicts (empty list if file is empty/missing or parsing fails)
    """
    if not path.exists():
        logger.info("ffuf output file is missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("ffuf output file is empty for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    # ffuf JSON output contains a "result" key with the actual finding
                    result = None
                    if "result" in data:
                        result = data["result"]
                    # Some ffuf versions may output the result directly
                    elif "url" in data or "status" in data:
                        result = data
                    
                    if result:
                        # Enhanced filtering to reduce noise
                        result_status = result.get("status", result.get("StatusCode", 0))
                        result_size = result.get("length", result.get("ContentLength", 0))
                        result_url = result.get("url", "")
                        
                        # Filter 1: Always skip 404s (even without baseline)
                        if result_status == 404:
                            continue
                        
                        # Filter 2: Skip very small responses (< 50 bytes) - likely empty or error pages
                        if result_size < 50:
                            logger.debug(f"Filtered ffuf result with very small size ({result_size} bytes): {result_url}")
                            continue
                        
                        # Filter 3: Enhanced baseline filtering if provided
                        if baseline_filter:
                            baseline_size = baseline_filter.get("content_length", 0)
                            baseline_words = baseline_filter.get("word_count", 0)
                            baseline_lines = baseline_filter.get("line_count", 0)
                            baseline_hash = baseline_filter.get("content_hash")
                            
                            # Filter 3a: Exact size match to baseline (likely wildcard 404)
                            if baseline_size > 0 and result_size == baseline_size:
                                logger.debug(f"Filtered ffuf result with exact baseline size match: {result_url}")
                                continue
                            
                            # Filter 3b: Size within tolerance (5% or 10 bytes, whichever is larger)
                            if baseline_size > 0:
                                tolerance = max(10, int(baseline_size * 0.05))
                                if abs(result_size - baseline_size) <= tolerance:
                                    # Size matches baseline - check additional signatures
                                    result_words = result.get("words", 0)
                                    result_lines = result.get("lines", 0)
                                    
                                    # Check word count match
                                    if baseline_words > 0 and abs(result_words - baseline_words) <= 2:
                                        # Check line count match
                                        if baseline_lines > 0 and abs(result_lines - baseline_lines) <= 2:
                                            logger.debug(f"Filtered ffuf result matching baseline signature (size/words/lines): {result_url}")
                                            continue
                            
                            # Filter 3c: Content hash comparison (if available)
                            # Note: ffuf doesn't provide content hash in JSON output, but we can check
                            # if the response body matches common wildcard patterns
                            if result_url:
                                # Filter out common wildcard response patterns
                                url_lower = result_url.lower()
                                # Common false positive patterns
                                false_positive_patterns = [
                                    "/FUZZ",  # Literal FUZZ in URL
                                    "not found",
                                    "404",
                                    "page not found",
                                    "file not found",
                                ]
                                # Check if URL contains false positive patterns
                                if any(pattern in url_lower for pattern in false_positive_patterns):
                                    logger.debug(f"Filtered ffuf result with false positive pattern in URL: {result_url}")
                                    continue
                        
                        # Filter 4: Filter out common low-value status codes that are often false positives
                        # Keep: 200, 204, 301, 302, 307, 401, 403, 500
                        # Filter: 400, 405, 406, 408, 429, 503 (often false positives or not interesting)
                        low_value_status_codes = [400, 405, 406, 408, 429, 503]
                        if result_status in low_value_status_codes:
                            # Only skip if size is also very small (likely error page)
                            if result_size < 500:
                                logger.debug(f"Filtered ffuf result with low-value status {result_status} and small size: {result_url}")
                                continue
                        
                        # Filter 5: Filter out responses that are too similar to common error pages
                        # This is a heuristic - if the response is very small and status is not 200, likely not interesting
                        if result_status not in [200, 204, 301, 302, 307] and result_size < 200:
                            logger.debug(f"Filtered ffuf result with non-success status {result_status} and small size: {result_url}")
                            continue
                        
                        # All filters passed - add to findings
                        findings.append(result)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON line %d in ffuf output %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
        
        logger.info("Parsed %d ffuf results from file %s", len(findings), path)
        return findings
    except Exception as e:
        logger.error("Failed to read/parse ffuf output file %s: %s", path, e, exc_info=True)
        return []


def ingest_ffuf_findings(
    db: Session,
    scan_job_id: str,
    ffuf_results: List[Dict[str, Any]],
    tool_result_id: str | None = None,
) -> List[Finding]:
    """
    Ingest ffuf findings into the database with aggregation to reduce noise.
    
    Implements aggregation to reduce noise:
    - Prioritizes URLs with interesting keywords and important status codes
    - Limits to max 300 individual findings per scan
    - Creates a summary finding for remaining endpoints
    
    Per-tool idempotency: deletes existing ffuf findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        ffuf_results: List of raw ffuf result objects
        
    Returns:
        List of created Finding objects
    """
    # Early return if no results
    if not ffuf_results:
        return []
    
    # Get project_id from scan_job
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
    if not scan_job:
        logger.warning(f"Scan job {scan_job_id} not found, skipping ffuf findings ingestion")
        return []
    
    project_id = scan_job.project_id
    if not project_id:
        logger.warning(f"Project ID not found for scan job {scan_job_id}, skipping ffuf findings ingestion")
        return []
    
    # Delete existing ffuf findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "ffuf"
    ).delete(synchronize_session=False)
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing ffuf findings for scan {scan_job_id}")
    
    # Aggregation parameters
    from app.core.config import settings
    MAX_INDIVIDUAL = settings.MAX_INDIVIDUAL_FINDINGS_PER_SCAN
    
    # Interesting keywords to prioritize (reuse from httpx plus file patterns)
    interesting_keywords = [
        "admin", "login", "auth", "debug", "backup", "test",
        "staging", "dev", "api", ".git", ".env", ".bak",
        "config", "console", "manage", "dashboard",
        ".php", ".jsp", ".aspx", ".old", ".zip",
    ]
    
    # Important status codes for ffuf
    interesting_status = {200, 204, 301, 302, 307, 401, 403, 500}
    
    def is_interesting(url: str, status_code: int) -> bool:
        """Check if URL/status should be prioritized"""
        if not url:
            return False
        url_lower = url.lower()
        has_keyword = any(keyword in url_lower for keyword in interesting_keywords)
        has_important_status = status_code in interesting_status
        return has_keyword or has_important_status
    
    # Separate prioritized and others
    prioritized = []
    others = []
    
    for ffuf_data in ffuf_results:
        url = ffuf_data.get("url", "") or ffuf_data.get("url_full", "")
        status_code = ffuf_data.get("status", 0)
        if is_interesting(url, status_code):
            prioritized.append(ffuf_data)
        else:
            others.append(ffuf_data)
    
    # Sort prioritized by status code (200/204 first) then URL
    prioritized.sort(key=lambda x: (
        0 if x.get("status", 0) in [200, 204] else 1,
        x.get("url", "") or x.get("url_full", "")
    ))
    
    # Take up to MAX_INDIVIDUAL total (prioritize interesting)
    findings_to_create = prioritized[:MAX_INDIVIDUAL]
    remaining_slots = MAX_INDIVIDUAL - len(findings_to_create)
    if remaining_slots > 0:
        findings_to_create.extend(others[:remaining_slots])
        others = others[remaining_slots:]
    
    findings = []
    
    # Track seen URLs within this scan to avoid duplicates
    seen_urls = set()
    
    # Create individual findings for prioritized endpoints using deduplication
    for ffuf_data in findings_to_create:
        try:
            # Extract URL and status code
            url = ffuf_data.get("url", "") or ffuf_data.get("url_full", "")
            url_full = ffuf_data.get("url_full", url)
            status_code = ffuf_data.get("status", 0)
            
            # Normalize URL for deduplication (within same scan)
            normalized_url = normalize_url(url) if url else ""
            url_key = f"{normalized_url}:{status_code}"
            
            # Skip if we've already seen this URL+status in this scan
            if url_key in seen_urls:
                logger.debug(
                    "Skipping duplicate ffuf finding within scan",
                    extra={
                        "scan_job_id": scan_job_id,
                        "url": url,
                        "status_code": status_code,
                        "url_key": url_key,
                    }
                )
                continue
            seen_urls.add(url_key)
            
            # Determine severity based on status code
            if status_code in [200, 204]:
                severity = Severity.MEDIUM
            elif status_code in [301, 302, 307, 401, 403, 500]:
                severity = Severity.LOW
            else:
                severity = Severity.LOW  # Default to LOW for other codes
            
            # Extract additional fields
            host = ffuf_data.get("host", "")
            length = ffuf_data.get("length", ffuf_data.get("size", 0))
            redirect_location = ffuf_data.get("redirectlocation", "")
            words = ffuf_data.get("words", 0)
            lines = ffuf_data.get("lines", 0)
            
            # Build title
            title = f"Discovered endpoint: {url_full or url} (HTTP {status_code})"
            if len(title) > 500:
                title = title[:497] + "..."
            
            # Build description
            description_lines = []
            
            if host:
                description_lines.append(
                    f"ffuf discovered a reachable path at `{url_full or url}` on `{host}`."
                )
            else:
                description_lines.append(
                    f"ffuf discovered a reachable path at `{url_full or url}`."
                )
            
            description_lines.append(f"HTTP status: {status_code}")
            
            if length > 0:
                description_lines.append(f"Response size: {length} bytes")
            
            if redirect_location:
                description_lines.append(f"Redirects to: {redirect_location}")
            
            if words > 0 or lines > 0:
                content_info = []
                if words > 0:
                    content_info.append(f"{words} words")
                if lines > 0:
                    content_info.append(f"{lines} lines")
                if content_info:
                    description_lines.append(f"Content analysis: {', '.join(content_info)}")
            
            # Contextual explanation
            if status_code in [200, 204]:
                description_lines.append(
                    "This endpoint was found via wordlist-based content discovery and may reveal "
                    "hidden functionality, admin panels, or debug paths."
                )
            elif status_code in [301, 302, 307]:
                description_lines.append(
                    "This endpoint redirects to another location. The redirect may reveal "
                    "internal paths or authentication flows."
                )
            elif status_code in [401, 403]:
                description_lines.append(
                    "This endpoint requires authentication or is protected. The presence of "
                    "this path may indicate hidden functionality or administrative interfaces."
                )
            elif status_code == 500:
                description_lines.append(
                    "This endpoint returned a server error, which may indicate misconfiguration "
                    "or reveal internal application structure."
                )
            else:
                description_lines.append(
                    "This endpoint was found via wordlist-based content discovery and may reveal "
                    "hidden functionality or additional attack surface."
                )
            
            description = "\n".join(description_lines)
            
            # Prepare raw_data with Content Discovery category
            raw_data_dict = ffuf_data.copy() if isinstance(ffuf_data, dict) else {}
            raw_data_dict["categories"] = ["Content Discovery"]
            
            # Use create_or_update_finding for deduplication across scans
            # For FFuF, use URL + status code as the deduplication key
            finding = create_or_update_finding(
                db=db,
                scan_job_id=scan_job_id,
                project_id=project_id,
                tool_result_id=tool_result_id,
                finding_data={
                    "tool": "ffuf",
                    "url": url,
                    "title": title,
                    "description": description,
                    "severity": severity,
                    "categories": ["Content Discovery"],
                    "vuln_type": "content_discovery",  # Use consistent vuln_type for deduplication
                    # Store status code in raw_data for reference
                    "raw_data": json.dumps(raw_data_dict),
                }
            )
            
            findings.append(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse ffuf finding: {e}", exc_info=True)
            continue
    
    # Create summary finding if there are remaining endpoints
    if others:
        try:
            # Get scan job to extract target URL/domain
            scan_job = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
            root_domain = ""
            if scan_job and scan_job.project:
                target_url = getattr(scan_job.project, "target_url", "")
                if target_url:
                    parsed = urlparse(target_url)
                    root_domain = parsed.netloc or parsed.path.split("/")[0] if parsed.path else ""
            
            if not root_domain and ffuf_results:
                # Fallback: extract from first URL
                first_url = ffuf_results[0].get("url", "") or ffuf_results[0].get("url_full", "")
                if first_url:
                    parsed = urlparse(first_url)
                    root_domain = parsed.netloc or ""
            
            # Count by status code
            status_counts = {}
            for ffuf_data in others:
                status = ffuf_data.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Build summary description
            description_lines = [
                f"Content discovery identified {len(ffuf_results)} total endpoints on {root_domain or 'target'}.",
                f"Of these, {len(findings_to_create)} are shown individually (prioritized by interesting keywords and status codes).",
                f"The remaining {len(others)} endpoints are summarized below.",
                "",
                "Status code breakdown for summarized endpoints:"
            ]
            for status, count in sorted(status_counts.items()):
                description_lines.append(f"  - HTTP {status}: {count} endpoints")
            
            description_lines.extend([
                "",
                "These endpoints were discovered but not individually reported to reduce noise.",
                "Review the full ffuf output for complete endpoint list."
            ])
            
            raw_data_summary = {
                "summary": True,
                "total_endpoints": len(ffuf_results),
                "summarized_endpoints": len(others),
                "status_breakdown": status_counts,
                "categories": ["Content Discovery"]
            }
            
            summary_title = f"Content discovery summary: {root_domain or 'target'} ({len(ffuf_results)} endpoints, {len(others)} summarized)"
            if len(summary_title) > 500:
                summary_title = summary_title[:497] + "..."
            
            # Create summary finding directly (it's a special summary, not a duplicate)
            # But ensure it has project_id and tool_result_id for proper linking
            summary_finding = _create_finding_with_canonical_name(
                tool_name="ffuf",
                tool_result_id=tool_result_id,
                scan_job_id=scan_job_id,
                project_id=project_id,
                title=summary_title,
                description="\n".join(description_lines),
                severity=Severity.INFO,
                url=None,
                raw_data=json.dumps(raw_data_summary),
                dedup_key=None,  # Summary findings don't deduplicate
                status=FindingStatus.OPEN,
            )
            
            findings.append(summary_finding)
            db.add(summary_finding)
            
        except Exception as e:
            logger.warning(f"Failed to create ffuf summary finding: {e}", exc_info=True)
    
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested ffuf findings into DB",
            extra={
                "scan_job_id": scan_job_id,
                "tool_result_id": tool_result_id,
                "total_findings": len(findings),
                "individual_findings": len(findings_to_create),
                "summary_findings": 1 if others else 0,
                "duplicates_skipped": len(findings_to_create) - len(findings) if len(findings_to_create) > len(findings) else 0,
            }
        )
    except Exception as e:
        logger.error("Failed to commit ffuf findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def parse_dalfox_output(path: Path) -> list[dict]:
    """
    Parse Dalfox JSON output file into a list of finding dicts.
    
    Dalfox with --format json produces JSON output that can be:
    - JSON array: `[{...}, {...}]` (starts with "[")
    - NDJSON (line-delimited): one JSON object per line
    - Single JSON object with "results" array
    
    This parser supports BOTH formats:
    - If output.strip().startswith("["): parse as JSON array
    - Else: parse line-by-line as NDJSON
    
    Args:
        path: Path to the Dalfox JSON output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing or parsing fails)
    """
    results: list[dict] = []
    
    # #region agent log
    import json
    from datetime import datetime, timezone
    with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"parse","hypothesisId":"PARSE","location":"findings_ingestor.py:1957","message":"parse_dalfox_output START","data":{"path":str(path),"exists":path.exists()},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
    # #endregion
    
    if not path.exists():
        logger.info(
            "Dalfox output file is missing",
            extra={
                "path": str(path),
                "file_exists": False,
            }
        )
        # #region agent log
        with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"parse","hypothesisId":"PARSE","location":"findings_ingestor.py:1978","message":"File missing","data":{"path":str(path)},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
        # #endregion
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info(
            "Dalfox output file is empty",
            extra={
                "path": str(path),
                "file_size": file_size,
            }
        )
        # #region agent log
        with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"parse","hypothesisId":"PARSE","location":"findings_ingestor.py:1983","message":"File empty","data":{"path":str(path),"file_size":file_size},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
        # #endregion
        return []
    
    try:
        raw = path.read_text().strip()
        # #region agent log
        with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"parse","hypothesisId":"PARSE","location":"findings_ingestor.py:2000","message":"Raw file content","data":{"raw_length":len(raw),"raw_preview":raw[:200],"raw_repr":repr(raw[:100])},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
        # #endregion
        
        # Normalize empty outputs: "", "{}", "[{}]" -> treat as empty
        # Also check for whitespace-normalized version like "[\n{}\n]"
        normalized_for_check = "".join(raw.split()) if raw else ""
        is_empty = (not raw or 
                   raw in ["", "{}", "[{}]", "[]"] or 
                   normalized_for_check in ["{}", "[{}]", "[]"])
        # #region agent log
        with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"parse","hypothesisId":"PARSE","location":"findings_ingestor.py:2006","message":"Empty check","data":{"raw":raw,"normalized_for_check":normalized_for_check,"is_empty":is_empty},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
        # #endregion
        if is_empty:
            logger.debug("Dalfox output is empty/placeholder: %r", raw)
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"parse","hypothesisId":"PARSE","location":"findings_ingestor.py:2011","message":"Empty/placeholder detected - returning empty","data":{"raw":raw},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
            # #endregion
            return []
        
        # Check if starts with "[" -> JSON array format
        if raw.startswith("["):
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    results.extend(data)
                elif isinstance(data, dict) and "results" in data:
                    # Wrapped in "results" key
                    results_list = data.get("results", [])
                    if isinstance(results_list, list):
                        results.extend(results_list)
                    else:
                        results.append(data)
                else:
                    # Single object in array format (unlikely but handle it)
                    results.append(data)
                logger.debug("Parsed Dalfox output as JSON array: %d items", len(results))
            except json.JSONDecodeError as e:
                logger.warning("Failed to parse Dalfox output as JSON array: %s, trying NDJSON", e)
                # Fall through to NDJSON parsing
                results = []
        
        # If not array or parsing failed, try NDJSON (line-by-line)
        if not results:
            for line_no, line in enumerate(raw.splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        results.append(data)
                    elif isinstance(data, list):
                        # Line contains an array
                        results.extend(data)
                    elif isinstance(data, dict) and "results" in data:
                        # Wrapped format
                        results.extend(data.get("results", []))
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON line %d in Dalfox output %s: %s | line=%r",
                        line_no, path, e, line[:120]
                    )
                    continue
            
            if results:
                logger.debug("Parsed Dalfox output as NDJSON: %d items", len(results))
        
        logger.info(
            "Parsed Dalfox output",
            extra={
                "path": str(path),
                "total_results": len(results),
                "file_size": file_size,
            }
        )
        
        # Filter out empty objects before returning
        # Note: "data" field contains the full URL with payload in dalfox output
        filtered_results = [
            r for r in results 
            if isinstance(r, dict) and r and any(key in r for key in ["url", "raw", "target", "data", "param", "parameter", "payload", "type"])
        ]
        
        if len(filtered_results) < len(results):
            logger.info(
                "Filtered out empty dalfox result objects",
                extra={
                    "path": str(path),
                    "filtered_count": len(filtered_results),
                    "total_count": len(results),
                    "removed_count": len(results) - len(filtered_results),
                }
            )
        
        # #region agent log
        with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"parse","hypothesisId":"PARSE","location":"findings_ingestor.py:2054","message":"parse_dalfox_output END","data":{"total_results":len(results),"filtered_results":len(filtered_results),"sample":filtered_results[0] if filtered_results else None},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
        # #endregion
        
        return filtered_results
    except Exception as e:
        logger.error("Failed to read/parse Dalfox output file %s: %s", path, e, exc_info=True)
        return []


def ingest_dalfox_findings(
    db: Session,
    scan_job_id: str,
    dalfox_results: list[dict],
    tool_result_id: str | None = None,
) -> List[Finding]:
    """
    Ingest Dalfox findings into the database.
    
    This function implements cross-scan deduplication: same finding across multiple scans
    updates a single record instead of creating duplicates.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        dalfox_results: List of raw Dalfox result objects
        
    Returns:
        List of Finding objects (created or updated)
    """
    # Get project_id from scan_job
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
    if not scan_job:
        logger.warning(f"Scan job {scan_job_id} not found, skipping Dalfox findings ingestion")
        return []
    
    project_id = scan_job.project_id
    if not project_id:
        logger.warning(f"Project ID not found for scan job {scan_job_id}, skipping Dalfox findings ingestion")
        return []
    
    # Delete existing dalfox findings for this scan job (per-tool idempotency)
    # This ensures we clean up old findings even when new results are empty
    # Use canonical name for consistency
    canonical_dalfox = canonical_tool_name("dalfox")
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == canonical_dalfox,
    ).delete(synchronize_session=False)
    if deleted_count > 0:
        logger.info(
            "Deleted existing dalfox findings for scan",
            extra={
                "scan_job_id": scan_job_id,
                "deleted_count": deleted_count,
                "tool_name": canonical_dalfox,
            }
        )
    # #region agent log
    with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"findings_ingestor.py:2108","message":"Dalfox findings deletion","data":{"scan_job_id":scan_job_id,"deleted_count":deleted_count,"canonical_tool_name":canonical_dalfox},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
    # #endregion
    
    # If no results, return early after deletion
    if not dalfox_results:
        db.commit()
        logger.info(
            "Dalfox ingestion completed: no findings",
            extra={
                "scan_job_id": scan_job_id,
                "tool_name": "dalfox",
                "parsed_items": 0,
                "stored_findings": 0,
            }
        )
        return []
    
    findings = []
    
    # #region agent log
    with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"ingest","hypothesisId":"INGEST","location":"findings_ingestor.py:2129","message":"ingest_dalfox_findings START","data":{"scan_job_id":scan_job_id,"dalfox_results_count":len(dalfox_results),"tool_result_id":tool_result_id},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
    # #endregion
    
    for item in dalfox_results:
        try:
            if not isinstance(item, dict):
                continue
            
            # Skip empty objects - require at least one meaningful field
            # An empty dict {} should not create a finding
            # Note: "data" field contains the full URL with payload in dalfox output
            if not item or not any(key in item for key in ["url", "raw", "target", "data", "param", "parameter", "payload", "type"]):
                logger.debug(f"Skipping empty dalfox result object: {item}")
                continue
            
            # Extract fields from Dalfox result
            # Dalfox uses "data" field for the full URL with payload, "url" for base URL
            url_raw = item.get("url") or item.get("raw") or item.get("target") or item.get("data")
            param_raw = item.get("param") or item.get("parameter")
            payload_raw = item.get("payload")
            itype_raw = item.get("type")
            evidence_raw = item.get("evidence")
            severity_raw = item.get("severity")
            data_raw = item.get("data")
            method_raw = item.get("method") or item.get("http_method")
            
            # Enhanced validation: require url AND at least one meaningful field
            # Rule: "Must be meaningful", not "must include payload"
            # This prevents dropping valid Dalfox results where only URL exists
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"findings_ingestor.py:2151","message":"Dalfox validation check start","data":{"item_keys":list(item.keys()) if isinstance(item,dict) else [],"url_raw":str(url_raw)[:100] if url_raw else None},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
            # #endregion
            if not url_raw:
                # #region agent log
                with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"findings_ingestor.py:2152","message":"Dalfox validation REJECTED: no URL","data":{"item":item},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
                # #endregion
                logger.debug(f"Skipping dalfox result with no URL: {item}")
                continue
            
            # Require at least ONE of: param, payload, type, evidence, severity, data
            meaningful_fields = [
                param_raw,
                payload_raw,
                itype_raw,
                evidence_raw,
                severity_raw,
                data_raw,
            ]
            meaningful_count = sum(1 for field in meaningful_fields if field and str(field).strip())
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"findings_ingestor.py:2164","message":"Dalfox validation meaningful fields check","data":{"meaningful_count":meaningful_count,"has_param":bool(param_raw),"has_payload":bool(payload_raw),"has_type":bool(itype_raw)},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
            # #endregion
            if not any(field for field in meaningful_fields if field and str(field).strip()):
                # #region agent log
                with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"findings_ingestor.py:2165","message":"Dalfox validation REJECTED: no meaningful fields","data":{"item":item},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
                # #endregion
                logger.debug(f"Skipping dalfox result with URL but no meaningful content: {item}")
                continue
            # Normalize for DB storage (strip and validate)
            url = url_raw.strip() if url_raw and url_raw.strip() else None
            param = param_raw.strip() if param_raw and param_raw.strip() else None
            
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"findings_ingestor.py:2166","message":"Dalfox validation PASSED","data":{"url":str(url)[:100] if url else None,"param":str(param)[:50] if param else None},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
            # #endregion
            payload = payload_raw.strip() if payload_raw and payload_raw.strip() else None
            itype = (itype_raw.lower() if itype_raw else "").strip()
            method = method_raw or "GET"
            
            # Severity based on XSS type
            if itype in {"stored", "blind"}:
                severity = Severity.HIGH
            else:  # reflected or unknown
                severity = Severity.MEDIUM
            
            # Build title
            if param:
                title = f"Cross-Site Scripting (XSS) in parameter '{param}'"
            else:
                title = "Cross-Site Scripting (XSS) detected"
            
            # Add XSS type to title if available
            if itype and itype != "reflected":
                title = f"{itype.capitalize()} {title}"
            
            # Build description
            description_lines = [
                "Dalfox identified a potential Cross-Site Scripting (XSS) issue.",
            ]
            if itype:
                description_lines.append(f"- XSS type: {itype.capitalize()}")
            if param:
                description_lines.append(f"- Parameter: `{param}`")
            if url:
                description_lines.append(f"- Location: `{url}`")
            if payload:
                truncated_payload = payload[:120] + ('…' if len(payload) > 120 else '')
                description_lines.append(f"- Example payload (truncated): `{truncated_payload}`")
            description_lines.append(
                "\nAn attacker could leverage this to execute arbitrary JavaScript "
                "in the victim's browser."
            )
            
            description = "\n".join(description_lines)
            
            # Build evidence string (human-readable summary)
            evidence_parts = []
            if itype:
                evidence_parts.append(f"{itype.capitalize()} XSS")
            if param:
                evidence_parts.append(f"parameter '{param}'")
            if payload:
                # Truncate payload for evidence
                truncated_payload = payload[:150] + ('…' if len(payload) > 150 else '')
                evidence_parts.append(f"payload: {truncated_payload}")
            
            evidence = ". ".join(evidence_parts) if evidence_parts else None
            if evidence:
                evidence = evidence[:500]  # Limit length
            
            # Prepare structured raw_data with ORIGINAL values from item (not normalized)
            # This ensures extract_location_from_raw_data can work properly
            raw_data_dict = {
                "url": item.get("url"),
                "target": item.get("target"),
                "raw": item.get("raw"),
                "data": item.get("data"),  # Dalfox uses "data" for full URL with payload
                "param": item.get("param"),
                "parameter": item.get("parameter"),
                "method": item.get("method"),
                "http_method": item.get("http_method"),
                "payload": item.get("payload"),
                "type": item.get("type"),
                "categories": ["xss"],
            }
            # Copy any other fields from item (excluding None values to keep JSON clean)
            for key, value in item.items():
                if key not in raw_data_dict and value is not None:
                    raw_data_dict[key] = value
            
            raw_data_json = json.dumps(raw_data_dict)
            
            # Determine template_id (use XSS type or rule ID if available)
            template_id = itype if itype else None
            rule_id = item.get("rule_id") or item.get("rule")
            if rule_id:
                template_id = rule_id
            
            # Normalize HTTP method for DB
            method_upper = None
            if method:
                method_upper = method.upper().strip()
                if method_upper not in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
                    method_upper = None
            # If we have a URL but no method, default to GET for DB
            if not method_upper and url:
                method_upper = "GET"
            
            # Use create_or_update_finding helper for deduplication
            finding = create_or_update_finding(
                db=db,
                scan_job_id=scan_job_id,
                project_id=project_id,
                finding_data={
                    "tool": "dalfox",
                    "template_id": template_id,  # Store XSS type or rule ID
                    "url": url,
                    "http_method": method_upper if method_upper else None,
                    "parameter": param,
                    "vuln_type": "xss",
                    "title": title,
                    "description": description,
                    "severity": severity,
                    "raw_data": raw_data_json,
                    "categories": ["xss"],
                    "evidence": evidence,
                },
                tool_result_id=tool_result_id,
            )
            
            findings.append(finding)
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"findings_ingestor.py:2313","message":"Dalfox finding created","data":{"finding_id":finding.id if hasattr(finding,'id') else None,"tool_result_id":finding.tool_result_id if hasattr(finding,'tool_result_id') else None,"tool_name":finding.tool_name if hasattr(finding,'tool_name') else None,"url":str(finding.url)[:100] if hasattr(finding,'url') and finding.url else None,"scan_job_id":finding.scan_job_id if hasattr(finding,'scan_job_id') else None},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
            # #endregion
            
        except Exception as e:
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"findings_ingestor.py:2310","message":"Dalfox finding creation FAILED","data":{"error":str(e),"error_type":type(e).__name__,"item_keys":list(item.keys()) if isinstance(item,dict) else None,"item_preview":str(item)[:200] if item else None},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
            # #endregion
            logger.error(
                "Failed to create Dalfox finding",
                extra={
                    "scan_job_id": scan_job_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "item_keys": list(item.keys()) if isinstance(item, dict) else None,
                    "item_preview": str(item)[:200] if item else None,
                },
                exc_info=True
            )
            continue
    
    # Flush findings to make them visible to queries, then commit
    # This ensures counts computed after ingestion are accurate
    try:
        # #region agent log
        with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"findings_ingestor.py:2315","message":"Dalfox ingestion before flush","data":{"findings_count":len(findings),"scan_job_id":scan_job_id},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
        # #endregion
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        created_count = sum(1 for f in findings if f.found_count == 1)
        updated_count = len(findings) - created_count
        # #region agent log
        with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"findings_ingestor.py:2321","message":"Dalfox ingestion after commit","data":{"created_count":created_count,"updated_count":updated_count,"total_findings":len(findings)},"timestamp":int(datetime.now(timezone.utc).timestamp()*1000)})+'\n')
        # #endregion
        # Structured logging for ingestion summary
        logger.info(
            "Dalfox ingestion completed",
            extra={
                "scan_job_id": scan_job_id,
                "tool_name": "dalfox",
                "parsed_items": len(dalfox_results),
                "stored_findings": len(findings),
                "created_count": created_count,
                "updated_count": updated_count,
            }
        )
        
        # Enrich findings with AI (non-blocking, runs in background)
        # Only enrich medium/high/critical findings that don't already have AI data
        if findings and scan_job:
            try:
                from app.services.finding_enrichment import enrich_findings_sync
                
                # Filter findings that need enrichment:
                # - severity in [medium, high, critical]
                # - impact_summary is NULL AND remediation_summary is NULL (avoid re-enriching)
                findings_to_enrich = [
                    f for f in findings
                    if f.severity in [Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
                    and (not f.impact_summary or not f.remediation_summary)
                ]
                
                if findings_to_enrich:
                    # Get org_id and target_url for enrichment
                    org_id = None
                    if scan_job.project and hasattr(scan_job.project, 'tenant') and scan_job.project.tenant:
                        org_id = scan_job.project.tenant.id
                    
                    target_url = None
                    if scan_job.stack_info and isinstance(scan_job.stack_info, dict):
                        target_url = scan_job.stack_info.get("target_url")
                    elif hasattr(scan_job, 'target_url'):
                        target_url = scan_job.target_url
                    
                    # Batch enrich findings (limit to 10 per batch to avoid timeouts)
                    batch_size = 10
                    for i in range(0, len(findings_to_enrich), batch_size):
                        batch = findings_to_enrich[i:i + batch_size]
                        enrich_findings_sync(db, batch, org_id, project_id, target_url)
            except Exception as e:
                # Don't fail ingestion if enrichment fails
                logger.warning(f"Failed to enrich Dalfox findings: {e}", exc_info=True)
    except Exception as e:
        logger.error("Failed to commit Dalfox findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings

def parse_sqlmap_output(output_dir: Path) -> List[Dict[str, Any]]:
    """
    Parse sqlmap output directory and stdout into a list of finding dicts.
    
    sqlmap outputs detection results to stdout and log files, not CSV files.
    CSV files are only created when using --dump for data extraction.
    We parse stdout/log files for SQL injection detection messages.
    
    Args:
        output_dir: Path to the sqlmap output directory (e.g., scan_job_dir/sqlmap)
        
    Returns:
        List of finding dicts (empty list if directory is empty/missing or parsing fails)
    """
    results: List[Dict[str, Any]] = []
    
    if not output_dir.exists() or not output_dir.is_dir():
        logger.debug("sqlmap output directory is missing for %s; will fallback to stdout parsing", output_dir)
        return []
    
    # Recursively search for log files in sqlmap output directory
    # SQLMap creates target-specific subdirectories: output_dir/<target_domain>/log
    # Also check for files directly in output_dir
    log_files = []
    
    # Search recursively for log files
    log_files.extend(output_dir.rglob("*.log"))
    log_files.extend(output_dir.rglob("*.txt"))
    log_files.extend(output_dir.rglob("target.txt"))
    # SQLMap also creates files named "log" without extension
    for log_path in output_dir.rglob("log"):
        if log_path.is_file():
            log_files.append(log_path)
    
    # Also check for CSV/JSON files (from --dump or other operations)
    csv_files = list(output_dir.rglob("*.csv"))
    json_files = list(output_dir.rglob("*.json"))
    
    # Parse log files for SQL injection detection messages
    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
                # Parse log content using stdout parser
                log_results = parse_sqlmap_stdout(log_content, "")
                if log_results:
                    logger.info(f"Parsed {len(log_results)} findings from sqlmap log file: {log_file}")
                    results.extend(log_results)
        except Exception as e:
            logger.debug(f"Failed to parse sqlmap log file {log_file}: {e}")
            continue
    
    # Also check for CSV/JSON files (from --dump or other operations)
    csv_files = list(output_dir.rglob("*.csv"))
    import csv
    
    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                # Try to detect delimiter
                sample = f.read(1024)
                f.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    # Extract relevant fields from CSV row
                    # sqlmap CSV format: "Target URL,Place,Parameter,Technique(s),Note(s)"
                    # Also check for alternative formats
                    url = (
                        row.get("Target URL", "") or 
                        row.get("target url", "") or 
                        row.get("url", "") or 
                        row.get("target", "") or
                        row.get("Target", "")
                    )
                    parameter = (
                        row.get("Parameter", "") or 
                        row.get("parameter", "") or
                        row.get("Parameter(s)", "")
                    )
                    place = (
                        row.get("Place", "") or 
                        row.get("place", "")
                    )  # GET, POST, etc.
                    technique = (
                        row.get("Technique(s)", "") or 
                        row.get("technique(s)", "") or
                        row.get("Technique", "") or
                        row.get("technique", "")
                    )
                    note = (
                        row.get("Note(s)", "") or 
                        row.get("note(s)", "") or
                        row.get("Note", "") or
                        row.get("note", "")
                    )
                    
                    # Build title from technique if available
                    title = technique or note or ""
                    
                    # Only add if we have at least URL or parameter
                    if url or parameter:
                        results.append({
                            "url": url,
                            "parameter": parameter,
                            "place": place,  # GET/POST
                            "title": title,
                            "technique": technique,
                            "note": note,
                            "payload": "",  # Not in CSV, will be empty
                            "dbms": "",  # Not in CSV, will be empty (we can get from stdout)
                            "raw_row": row,  # Keep full row for reference
                        })
        except Exception as e:
            logger.warning(
                "Failed to parse sqlmap CSV file %s: %s",
                csv_file, e
            )
            continue
    
    # Also check for JSON files if available
    json_files = list(output_dir.rglob("*.json"))
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # sqlmap JSON structure varies, try to extract findings
                if isinstance(data, dict):
                    # Look for common keys
                    if "target" in data:
                        target = data["target"]
                        if isinstance(target, dict):
                            url = target.get("url", "")
                            parameters = target.get("parameters", [])
                            for param in parameters:
                                if isinstance(param, dict):
                                    results.append({
                                        "url": url,
                                        "parameter": param.get("name", ""),
                                        "title": param.get("title", ""),
                                        "payload": param.get("payload", ""),
                                        "dbms": param.get("dbms", ""),
                                        "raw_data": param,
                                    })
        except Exception as e:
            logger.warning(
                "Failed to parse sqlmap JSON file %s: %s",
                json_file, e
            )
            continue
    
    if results:
        logger.info(
            "Parsed %d sqlmap findings from directory %s (searched %d log files, %d CSV files, %d JSON files)",
            len(results), output_dir, len(log_files), len(csv_files), len(json_files)
        )
    else:
        logger.debug(
            "No sqlmap findings parsed from directory %s (searched %d log files, %d CSV files, %d JSON files)",
            output_dir, len(log_files), len(csv_files), len(json_files)
        )
    return results


def parse_sqlmap_stdout(stdout: str, default_url: str = "") -> List[Dict[str, Any]]:
    """
    Parse sqlmap stdout for SQL injection detection messages.
    
    sqlmap outputs detection results to stdout with patterns like:
    - "GET parameter 'id' is vulnerable"
    - "sqlmap identified the following injection point(s)"
    - "Parameter: cat (GET)" followed by multiple "Type:" entries
    
    Args:
        stdout: sqlmap stdout text
        default_url: Default URL to use if not found in stdout
        
    Returns:
        List of finding dicts (one per technique found per parameter)
    """
    results: List[Dict[str, Any]] = []
    
    if not stdout:
        return results
    
    import re
    
    # Extract base URL
    url = default_url
    url_patterns = [
        r"Target:\s*([^\n]+)",
        r"URL:\s*([^\n]+)",
        r"testing\s+URL\s+'([^']+)'",
        r"starting\s+crawler\s+for\s+target\s+URL\s+'([^']+)'",
    ]
    for pattern in url_patterns:
        url_match = re.search(pattern, stdout, re.IGNORECASE)
        if url_match:
            url = url_match.group(1).strip()
            break
    
    # Extract DBMS
    dbms_match = re.search(r"back-end DBMS:\s*([^\n]+)", stdout, re.IGNORECASE)
    dbms = dbms_match.group(1).strip() if dbms_match else ""
    
    # Pattern 1: Parse the detailed injection point section
    # Format: "Parameter: cat (GET)" followed by multiple "Type:" blocks
    injection_section_pattern = r"sqlmap identified the following injection point\(s\)[^\n]*\n(.*?)(?=\n---|\n\[|$)"
    injection_section_match = re.search(injection_section_pattern, stdout, re.IGNORECASE | re.DOTALL)
    
    if injection_section_match:
        injection_section = injection_section_match.group(1)
        
        # Extract parameter name and place (GET/POST)
        param_header_match = re.search(r"Parameter:\s*([^\s(]+)\s*\(([^)]+)\)", injection_section, re.IGNORECASE)
        if param_header_match:
            parameter = param_header_match.group(1).strip()
            place = param_header_match.group(2).strip().upper()
            
            # Extract all Type blocks (each represents a different injection technique)
            type_blocks = re.split(r'\n\s*Type:\s*', injection_section)[1:]  # Skip first empty part
            
            for type_block in type_blocks:
                # Extract technique type
                technique_match = re.search(r'^([^\n]+)', type_block, re.IGNORECASE)
                technique = technique_match.group(1).strip() if technique_match else ""
                
                # Extract title
                title_match = re.search(r'Title:\s*([^\n]+)', type_block, re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else technique
                
                # Extract payload
                payload_match = re.search(r'Payload:\s*([^\n]+)', type_block, re.IGNORECASE)
                payload = payload_match.group(1).strip() if payload_match else ""
                
                # Extract vector
                vector_match = re.search(r'Vector:\s*([^\n]+)', type_block, re.IGNORECASE)
                vector = vector_match.group(1).strip() if vector_match else ""
                
                if technique or title:
                    results.append({
                        "url": url,
                        "parameter": parameter,
                        "place": place,
                        "technique": technique,
                        "note": title or "",
                        "title": title or technique or f"SQL Injection on {parameter}",
                        "payload": payload or vector,
                        "dbms": dbms,
                    })
    
    # Pattern 2: Catch "parameter 'X' is 'technique' injectable" or "appears to be 'technique' injectable"
    # This is the most common format sqlmap uses when it finds SQL injection
    # Examples:
    #   "POST parameter 'uname' appears to be 'AND boolean-based blind - WHERE or HAVING clause (subquery - comment)' injectable"
    #   "POST parameter 'uname' is 'MySQL >= 5.6 AND error-based - WHERE, HAVING, ORDER BY or GROUP BY clause (GTID_SUBSET)' injectable"
    injectable_patterns = [
        # Pattern: "POST parameter 'uname' appears to be 'technique' injectable"
        r"(?:GET|POST|Cookie|User-Agent|Referer|Header)\s+parameter\s+['\"]([^'\"]+)['\"]\s+appears\s+to\s+be\s+['\"]([^'\"]+)['\"]\s+injectable",
        # Pattern: "POST parameter 'uname' is 'technique' injectable"
        r"(?:GET|POST|Cookie|User-Agent|Referer|Header)\s+parameter\s+['\"]([^'\"]+)['\"]\s+is\s+['\"]([^'\"]+)['\"]\s+injectable",
        # Fallback: "parameter 'X' is vulnerable" (less common)
        r"(?:GET|POST|Cookie|User-Agent|Referer|Header)\s+parameter\s+['\"]([^'\"]+)['\"]\s+is\s+vulnerable",
    ]
    
    # Check if we already have results for these parameters from the detailed section
    existing_params = {(r.get("parameter", ""), r.get("technique", "")) for r in results}
    
    for pattern in injectable_patterns:
        matches = list(re.finditer(pattern, stdout, re.IGNORECASE))
        for match in matches:
            parameter = match.group(1)
            # For patterns with technique in the match, extract it
            if len(match.groups()) >= 2 and match.group(2):
                technique = match.group(2).strip()
            else:
                # For "is vulnerable" pattern, extract technique from context
                technique = ""
                match_start = match.start()
                context_start = max(0, match_start - 1000)
                context_end = min(len(stdout), match.end() + 1000)
                context = stdout[context_start:context_end]
                
                # Look for technique in context
                technique_patterns = [
                    r"is\s+['\"]([^'\"]+)\s+injectable",
                    r"appears\s+to\s+be\s+['\"]([^'\"]+)\s+injectable",
                    r"Type:\s*([^\n]+)",
                ]
                for tech_pattern in technique_patterns:
                    tech_match = re.search(tech_pattern, context, re.IGNORECASE)
                    if tech_match:
                        technique = tech_match.group(1).strip()
                        break
            
            # Extract place (GET/POST) from the match or context
            place_match = re.search(r"(GET|POST|Cookie|Header)", match.group(0), re.IGNORECASE)
            if not place_match:
                # Try context
                match_start = match.start()
                context_start = max(0, match_start - 200)
                context_end = min(len(stdout), match.end() + 200)
                context = stdout[context_start:context_end]
                place_match = re.search(r"(GET|POST|Cookie|Header)", context, re.IGNORECASE)
            place = place_match.group(1).upper() if place_match else ""
            
            # Extract payload if available from context
            match_start = match.start()
            context_start = max(0, match_start - 1000)
            context_end = min(len(stdout), match.end() + 1000)
            context = stdout[context_start:context_end]
            payload_match = re.search(r"Payload:\s*([^\n]+)", context, re.IGNORECASE)
            payload = payload_match.group(1).strip() if payload_match else ""
            
            # Only add if we don't already have this parameter+technique combination
            if (parameter, technique) not in existing_params:
                results.append({
                    "url": url,
                    "parameter": parameter,
                    "place": place,
                    "technique": technique,
                    "note": technique or "",
                    "title": technique or f"SQL Injection on {parameter}",
                    "payload": payload,
                    "dbms": dbms,
                })
                existing_params.add((parameter, technique))
    
    if results:
        logger.info(
            "Parsed %d sqlmap findings from stdout (url: %s, parameters: %s)",
            len(results), url or "unknown", ", ".join(set(r.get("parameter", "") for r in results if r.get("parameter")))
        )
    else:
        logger.debug("No sqlmap findings parsed from stdout")
    
    return results


def ingest_sqlmap_findings(
    db: Session,
    scan_job_id: str,
    sqlmap_results: List[Dict[str, Any]],
) -> List[Finding]:
    """
    Ingest sqlmap findings into the database.
    
    This function implements cross-scan deduplication: same finding across multiple scans
    updates a single record instead of creating duplicates.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        sqlmap_results: List of finding dicts from parse_sqlmap_output
        
    Returns:
        List of Finding objects (created or updated)
    """
    if not sqlmap_results:
        return []
    
    # Get project_id from scan_job
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
    if not scan_job:
        logger.warning(f"Scan job {scan_job_id} not found, skipping sqlmap findings ingestion")
        return []
    
    project_id = scan_job.project_id
    if not project_id:
        logger.warning(f"Project ID not found for scan job {scan_job_id}, skipping sqlmap findings ingestion")
        return []
    
    findings = []
    
    for result_data in sqlmap_results:
        try:
            url = result_data.get("url", "")
            parameter = result_data.get("parameter", "")
            place = result_data.get("place", "")  # GET, POST, etc.
            technique = result_data.get("technique", "")
            note = result_data.get("note", "")
            title = result_data.get("title", "")
            payload = result_data.get("payload", "")
            dbms = result_data.get("dbms", "")
            
            # Extract HTTP method from place (GET, POST, etc.)
            http_method = None
            if place:
                # Normalize to uppercase (GET, POST, etc.)
                http_method = place.upper().split()[0] if place else None
                # Map common variations
                if http_method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    pass  # Keep as is
                elif http_method in ["COOKIE", "HEADER", "USER-AGENT", "REFERER"]:
                    # These are parameter locations, not HTTP methods
                    # Default to GET for cookie/header-based injections
                    http_method = "GET"
                else:
                    http_method = None
            
            # Determine severity - sqlmap only reports confirmed SQLi, so always CRITICAL
            severity = Severity.CRITICAL
            
            # Build title from technique or parameter
            if technique:
                finding_title = f"SQL Injection ({technique})"
                if parameter:
                    finding_title += f" on parameter '{parameter}'"
            elif parameter:
                finding_title = f"SQL Injection on parameter '{parameter}'"
            else:
                finding_title = "SQL Injection detected"
            
            if url:
                # Extract path from URL for brevity
                try:
                    parsed = urlparse(url)
                    path = parsed.path[:50]  # Truncate long paths
                    finding_title += f" at {path}"
                except:
                    pass
            
            finding_title = finding_title[:500]
            
            # Build description
            description_lines = [
                "sqlmap identified a SQL injection vulnerability.",
            ]
            
            if technique:
                description_lines.append(f"- Injection technique: {technique}")
            
            if parameter:
                description_lines.append(f"- Vulnerable parameter: `{parameter}`")
                if place:
                    description_lines.append(f"- Parameter location: {place} (GET/POST)")
            
            if url:
                description_lines.append(f"- Location: `{url}`")
            
            if note:
                description_lines.append(f"- Additional notes: {note}")
            
            if dbms and dbms.lower() not in ["", "none", "unknown"]:
                description_lines.append(f"- Database management system: {dbms}")
            
            if payload:
                # Sanitize payload (truncate and escape)
                sanitized_payload = payload[:200].replace('\n', ' ').replace('\r', ' ')
                description_lines.append(f"- Example payload (truncated): `{sanitized_payload}...`")
            
            description_lines.append(
                "\nAn attacker could leverage this vulnerability to:"
            )
            description_lines.append("- Access and manipulate database contents")
            description_lines.append("- Extract sensitive information (user credentials, personal data)")
            description_lines.append("- Potentially gain unauthorized access to the application")
            
            if dbms:
                description_lines.append(f"\nConfirmed database system: {dbms}")
            
            description = "\n".join(description_lines)
            
            # Build evidence string (human-readable summary)
            evidence_parts = []
            if technique:
                evidence_parts.append(f"{technique}")
            if parameter:
                evidence_parts.append(f"parameter '{parameter}'")
            if dbms and dbms.lower() not in ["", "none", "unknown"]:
                evidence_parts.append(f"DBMS: {dbms}")
            if payload:
                # Truncate payload for evidence
                truncated_payload = payload[:150] + ('…' if len(payload) > 150 else '')
                evidence_parts.append(f"payload: {truncated_payload}")
            
            evidence = ". ".join(evidence_parts) if evidence_parts else None
            if evidence:
                evidence = evidence[:500]  # Limit length
            
            # Prepare raw_data with categories
            raw_data_dict = result_data.copy()
            raw_data_dict["categories"] = ["sqli"]
            raw_data = json.dumps(raw_data_dict)
            
            # Use create_or_update_finding helper for deduplication
            finding = create_or_update_finding(
                db=db,
                scan_job_id=scan_job_id,
                project_id=project_id,
                finding_data={
                    "tool": "sqlmap",
                    "template_id": technique,  # Store technique as template_id
                    "url": url,
                    "http_method": http_method,
                    "parameter": parameter,
                    "vuln_type": "sqli",
                    "title": finding_title,
                    "description": description,
                    "severity": severity,
                    "raw_data": raw_data,
                    "categories": ["sqli"],
                    "evidence": evidence,
                }
            )
            
            findings.append(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse sqlmap finding: {e}", exc_info=True)
            continue
    
    # Flush findings to make them visible to queries, then commit
    # This ensures counts computed after ingestion are accurate
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        created_count = sum(1 for f in findings if f.found_count == 1)
        updated_count = len(findings) - created_count
        logger.info(
            "Ingested %d sqlmap findings into DB for scan %s (%d created, %d updated)",
            len(findings), scan_job_id, created_count, updated_count
        )
    except Exception as e:
        logger.error("Failed to commit sqlmap findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    # Enrich findings with AI (non-blocking, runs in background)
    # Only enrich medium/high/critical findings that don't already have AI data
    if findings and scan_job:
        try:
            from app.services.finding_enrichment import enrich_findings_sync
            
            # Filter findings that need enrichment:
            # - severity in [medium, high, critical]
            # - impact_summary is NULL AND remediation_summary is NULL (avoid re-enriching)
            findings_to_enrich = [
                f for f in findings
                if f.severity in [Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
                and (not f.impact_summary or not f.remediation_summary)
            ]
            
            if findings_to_enrich:
                # Get org_id and target_url for enrichment
                org_id = None
                if scan_job.project and hasattr(scan_job.project, 'tenant') and scan_job.project.tenant:
                    org_id = scan_job.project.tenant.id
                
                target_url = None
                if scan_job.stack_info and isinstance(scan_job.stack_info, dict):
                    target_url = scan_job.stack_info.get("target_url")
                elif hasattr(scan_job, 'target_url'):
                    target_url = scan_job.target_url
                
                # Batch enrich findings (limit to 10 per batch to avoid timeouts)
                batch_size = 10
                for i in range(0, len(findings_to_enrich), batch_size):
                    batch = findings_to_enrich[i:i + batch_size]
                    enrich_findings_sync(db, batch, org_id, project_id, target_url)
        except Exception as e:
            # Don't fail ingestion if enrichment fails
            logger.warning(f"Failed to enrich sqlmap findings: {e}", exc_info=True)
    
    return findings

import logging
import json
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from urllib.parse import urlparse

from app.models.finding import Finding, Severity, FindingStatus

logger = logging.getLogger(__name__)


def categorize_nuclei_finding(template_tags: list[str]) -> list[str]:
    """
    Categorize a Nuclei finding based on its template tags.
    
    Normalizes tags to lowercase and returns a list of category strings
    based on the presence of common vulnerability tags.
    
    Args:
        template_tags: List of template tags from Nuclei finding (e.g., ["xss", "sqli", "cve"])
        
    Returns:
        List of category strings (e.g., ["xss", "sqli"])
        
    Example:
        >>> categorize_nuclei_finding(["xss", "sqli", "cve"])
        ["xss", "sqli"]
        >>> categorize_nuclei_finding(["lfi", "rfi"])
        ["dir_traversal"]
    """
    if not template_tags:
        return []
    
    # Normalize tags to lowercase
    tags_lower = [tag.lower() for tag in template_tags if tag]
    
    categories = []
    
    # Map tags to simple lowercase category names (attacker-relevant findings)
    # XSS
    if any(tag in tags_lower for tag in ["xss", "cross-site-scripting"]):
        categories.append("xss")
    
    # SQL Injection
    if any(tag in tags_lower for tag in ["sqli", "sql-injection", "sql"]):
        categories.append("sqli")
    
    # SSRF
    if any(tag in tags_lower for tag in ["ssrf", "server-side-request-forgery"]):
        categories.append("ssrf")
    
    # SSTI
    if any(tag in tags_lower for tag in ["ssti", "server-side-template-injection", "template-injection"]):
        categories.append("ssti")
    
    # XXE
    if any(tag in tags_lower for tag in ["xxe", "xml-external-entity"]):
        categories.append("xxe")
    
    # Directory Traversal (LFI/RFI)
    if any(tag in tags_lower for tag in ["lfi", "rfi", "local-file-inclusion", "remote-file-inclusion", "path-traversal", "directory-traversal", "file-inclusion"]):
        categories.append("directory_traversal")
    
    # CSRF
    if any(tag in tags_lower for tag in ["csrf", "cross-site-request-forgery"]):
        categories.append("csrf")
    
    # CORS
    if any(tag in tags_lower for tag in ["cors", "cross-origin-resource-sharing", "cors-misconfig"]):
        categories.append("cors_misconfig")
    
    # Command Injection
    if any(tag in tags_lower for tag in ["cmdi", "command-injection", "rce", "remote-code-execution", "code-execution", "os-commanding"]):
        categories.append("command_injection")
    
    # IDOR
    if any(tag in tags_lower for tag in ["idor", "insecure-direct-object-reference", "authorization"]):
        categories.append("idor")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_categories = []
    for cat in categories:
        if cat not in seen:
            seen.add(cat)
            unique_categories.append(cat)
    
    return unique_categories


def parse_nuclei_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nuclei JSONL output file (one JSON object per line) into a list of dicts.
    
    This function is robust to non-JSON lines (like ASCII tables, logs, etc.)
    and will skip them gracefully. Handles empty files and zero-byte files.
    
    Args:
        path: Path to the Nuclei output file (JSONL format)
        
    Returns:
        List of parsed Nuclei JSON objects (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    # Check if file is zero bytes
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                
                # Skip obvious non-JSON lines (tables, logs, etc.)
                # JSON objects/arrays start with { or [
                if not (line.startswith("{") or line.startswith("[")):
                    logger.debug(
                        "Skipping non-JSON line %d in nuclei output %s: %r",
                        line_no, path, line[:80]
                    )
                    continue
                
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        findings.append(obj)
                    else:
                        logger.debug("Skipping non-dict JSON on line %d in %s", line_no, path)
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
        
        logger.info("Parsed %d nuclei findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse Nuclei output file %s: %s", path, e, exc_info=True)
        return []


def parse_nmap_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nmap XML output file into a list of finding dicts.
    
    Each open port becomes a finding. Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the Nmap XML output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Extract host information
        for host in root.findall("host"):
            host_status = host.find("status")
            if host_status is None or host_status.get("state") != "up":
                continue
            
            # Get host address
            address_elem = host.find("address")
            host_ip = address_elem.get("addr") if address_elem is not None else "unknown"
            
            # Get hostname
            hostnames_elem = host.find("hostnames")
            hostname = host_ip
            if hostnames_elem is not None:
                hostname_elem = hostnames_elem.find("hostname")
                if hostname_elem is not None:
                    hostname = hostname_elem.get("name", host_ip)
            
            # Process ports
            ports_elem = host.find("ports")
            if ports_elem is None:
                continue
            
            for port_elem in ports_elem.findall("port"):
                port_state = port_elem.find("state")
                if port_state is None or port_state.get("state") != "open":
                    continue
                
                port_num = port_elem.get("portid")
                protocol = port_elem.get("protocol", "tcp")
                
                # Get service info
                service_elem = port_elem.find("service")
                service_name = service_elem.get("name", "unknown") if service_elem is not None else "unknown"
                service_product = service_elem.get("product", "") if service_elem is not None else ""
                service_version = service_elem.get("version", "") if service_elem is not None else ""
                
                # Build description
                description_parts = [
                    f"Host: {hostname} ({host_ip})",
                    f"Port: {port_num}/{protocol}",
                    f"Service: {service_name}",
                ]
                if service_product:
                    description_parts.append(f"Product: {service_product}")
                if service_version:
                    description_parts.append(f"Version: {service_version}")
                
                description = "\n".join(description_parts)
                
                # Determine severity based on port/service
                from app.core.config import settings
                severity = "info"
                high_risk_ports = [p.strip() for p in settings.HIGH_RISK_PORTS.split(",")]
                if port_num in high_risk_ports:  # SSH, RDP, VNC, etc.
                    severity = "medium"
                elif port_num in ["3306", "5432", "1433"]:  # MySQL, PostgreSQL, MSSQL
                    severity = "medium"
                elif port_num in ["21", "23", "25"]:  # FTP, Telnet, SMTP
                    severity = "low"
                elif port_num in ["80", "443", "8080", "8443"]:  # HTTP/HTTPS
                    severity = "info"
                
                # Build title
                title = f"Open port {port_num}/{protocol} ({service_name}) on {hostname}"
                
                # Build URL
                url = f"{hostname}:{port_num}"
                if port_num in ["80", "8080"]:
                    url = f"http://{hostname}:{port_num}"
                elif port_num in ["443", "8443"]:
                    url = f"https://{hostname}:{port_num}"
                
                # Store raw XML for this port as JSON
                raw_data = json.dumps({
                    "host": hostname,
                    "ip": host_ip,
                    "port": port_num,
                    "protocol": protocol,
                    "service": service_name,
                    "product": service_product,
                    "version": service_version,
                })
                
                findings.append({
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "cve_id": None,
                    "cwe_id": None,
                    "url": url,
                    "tool_name": "nmap",
                    "raw_data": raw_data,
                })
        
        logger.info("Parsed %d nmap findings from file for scan %s", len(findings), path)
        return findings
        
    except ET.ParseError as e:
        logger.warning("Failed to parse Nmap XML file %s: %s", path, e)
        return []
    except Exception as e:
        logger.error("Failed to read/parse Nmap output file %s: %s", path, e, exc_info=True)
        return []


def parse_sslscan_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse sslscan output file (JSON or text format) into a list of finding dicts.
    
    Handles both JSON output (when --json flag is used) and plain text output.
    Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the sslscan output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        # Try to parse as JSON first
        try:
            # Remove ANSI color codes if present
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            content_clean = ansi_escape.sub('', content)
            
            # Try to find JSON object/array
            json_start = content_clean.find('{')
            json_end = content_clean.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content_clean[json_start:json_end]
                data = json.loads(json_str)
                
                # Handle JSON format
                if isinstance(data, dict):
                    # Single JSON object
                    findings.extend(_parse_sslscan_json_object(data))
                elif isinstance(data, list):
                    # Array of JSON objects
                    for item in data:
                        if isinstance(item, dict):
                            findings.extend(_parse_sslscan_json_object(item))
        except (json.JSONDecodeError, ValueError):
            # Fall back to text parsing
            findings.extend(_parse_sslscan_text(content))
        
        logger.info("Parsed %d sslscan findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse sslscan output file %s: %s", path, e, exc_info=True)
        return []


def _parse_sslscan_json_object(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse a single sslscan JSON object into finding dicts"""
    findings = []
    
    host = data.get("host", "unknown")
    port = data.get("port", 443)
    target = f"{host}:{port}"
    
    # Check for weak protocols
    sslv2 = data.get("ssl_version", {}).get("SSLv2", {}).get("status", "").lower()
    sslv3 = data.get("ssl_version", {}).get("SSLv3", {}).get("status", "").lower()
    tls10 = data.get("ssl_version", {}).get("TLSv1.0", {}).get("status", "").lower()
    tls11 = data.get("ssl_version", {}).get("TLSv1.1", {}).get("status", "").lower()
    
    if sslv2 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if sslv3 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls10 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls11 == "enabled":
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    # Check for weak ciphers
    ciphers = data.get("cipher_suites", [])
    weak_ciphers = []
    for cipher in ciphers:
        cipher_name = cipher.get("cipher", "")
        key_length = cipher.get("key_length", 0)
        if key_length < 128 or "RC4" in cipher_name or "DES" in cipher_name or "MD5" in cipher_name:
            weak_ciphers.append(cipher_name)
    
    if weak_ciphers:
        findings.append({
            "severity": "medium",
            "title": f"Weak cipher suites detected on {target}",
            "description": f"Weak cipher suites found on {target}: {', '.join(weak_ciphers[:5])}",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    return findings


def _parse_sslscan_text(content: str) -> List[Dict[str, Any]]:
    """Parse sslscan plain text output into finding dicts"""
    findings = []
    
    # Remove ANSI color codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    content_clean = ansi_escape.sub('', content)
    
    # Extract host and port from content
    host_match = re.search(r'Testing SSL server\s+(\S+)\s+on port\s+(\d+)', content_clean)
    if not host_match:
        # Try alternative pattern
        host_match = re.search(r'Connected to\s+([\d.]+)', content_clean)
        port_match = re.search(r'port\s+(\d+)', content_clean)
        host = host_match.group(1) if host_match else "unknown"
        port = int(port_match.group(1)) if port_match else 443
    else:
        host = host_match.group(1)
        port = int(host_match.group(2))
    
    target = f"{host}:{port}"
    
    # Check for weak protocols in text
    if re.search(r'SSLv2\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],  # Store first 1000 chars
        })
    
    if re.search(r'SSLv3\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.0\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.1\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    # Check for weak ciphers
    weak_cipher_patterns = [
        (r'RC4', "high", "RC4 cipher is weak and should be disabled"),
        (r'DES', "high", "DES cipher is weak and should be disabled"),
        (r'3DES|Triple DES', "medium", "3DES cipher is deprecated and should be disabled"),
        (r'MD5', "high", "MD5 hash algorithm is weak and should not be used"),
        (r'SHA1', "medium", "SHA1 hash algorithm is deprecated and should be disabled"),
    ]
    
    for pattern, severity, description in weak_cipher_patterns:
        if re.search(pattern, content_clean, re.IGNORECASE):
            findings.append({
                "severity": severity,
                "title": f"Weak cipher/hash detected on {target}",
                "description": f"{description}",
                "cve_id": None,
                "cwe_id": "CWE-327",
                "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
                "tool_name": "sslscan",
                "raw_data": content_clean[:1000],
            })
    
    # Check for certificate issues
    cert_issues = [
        (r'Certificate.*expired', "high", "SSL certificate has expired"),
        (r'Certificate.*self.signed', "medium", "Self-signed certificate detected"),
        (r'Certificate.*invalid', "high", "Invalid SSL certificate detected"),
        (r'Certificate.*chain.*incomplete', "medium", "Incomplete certificate chain"),
    ]
    
    for pattern, severity, description in cert_issues:
        if re.search(pattern, content_clean, re.IGNORECASE):
            findings.append({
                "severity": severity,
                "title": f"Certificate issue on {target}",
                "description": f"{description}",
                "cve_id": None,
                "cwe_id": "CWE-295",
                "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
                "tool_name": "sslscan",
                "raw_data": content_clean[:1000],
            })
    
    # If we have output but no findings, create an informational finding
    # This helps users understand that SSLscan ran but found no issues
    if not findings and content_clean and len(content_clean) > 100:
        # Only create info finding if we have substantial output
        findings.append({
            "severity": "info",
            "title": f"SSL/TLS scan completed for {target}",
            "description": f"SSLscan completed successfully. No critical SSL/TLS issues detected. Review raw output for details.",
            "cve_id": None,
            "cwe_id": None,
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:2000],  # Store more data for info findings
        })
    
    return findings


def ingest_nmap_findings(
    db: Session,
    scan_job_id: str,
    nmap_results: List[Dict[str, Any]],
    tool_result_id: str | None = None,
) -> List[Finding]:
    """
    Ingest Nmap findings into the database.
    
    Per-tool idempotency: deletes existing nmap findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nmap_results: List of finding dicts from parse_nmap_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing nmap findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "nmap"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing nmap findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in nmap_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "Nmap Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="nmap",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nmap finding: {e}", exc_info=True)
            continue
    
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d nmap findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit nmap findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_sslscan_findings(
    db: Session,
    scan_job_id: str,
    sslscan_results: List[Dict[str, Any]],
    tool_result_id: str | None = None,
) -> List[Finding]:
    """
    Ingest sslscan findings into the database.
    
    Per-tool idempotency: deletes existing sslscan findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        sslscan_results: List of finding dicts from parse_sslscan_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing sslscan findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "sslscan"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing sslscan findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in sslscan_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "SSL/TLS Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="sslscan",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse sslscan finding: {e}", exc_info=True)
            continue
    
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d sslscan findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit sslscan findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_http_header_findings(
    db: Session,
    scan_job_id: str,
    header_findings: List[Finding],
) -> List[Finding]:
    """
    Ingest HTTP header findings into the database.
    
    Per-tool idempotency: deletes existing http_headers findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        header_findings: List of Finding objects for missing headers
        
    Returns:
        List of created Finding objects
    """
    # Delete existing http_headers findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "http_headers"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing http_headers findings for scan {scan_job_id}")
    
    # Add all findings to session
    for finding in header_findings:
        db.add(finding)
    
    # Flush findings to make them visible to queries, then commit
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d http_headers findings into DB for scan %s",
            len(header_findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit http_headers findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return header_findings


def categorize_nuclei_finding(template_tags: list[str]) -> list[str]:
    """
    Categorize a Nuclei finding based on its template tags.
    
    Normalizes tags to lowercase and returns a list of category strings
    based on the presence of common vulnerability tags.
    
    Args:
        template_tags: List of template tags from Nuclei finding (e.g., ["xss", "sqli", "cve"])
        
    Returns:
        List of category strings (e.g., ["xss", "sqli"])
        
    Example:
        >>> categorize_nuclei_finding(["xss", "sqli", "cve"])
        ["xss", "sqli"]
        >>> categorize_nuclei_finding(["lfi", "rfi"])
        ["dir_traversal"]
    """
    if not template_tags:
        return []
    
    # Normalize tags to lowercase
    tags_lower = [tag.lower() for tag in template_tags if tag]
    
    categories = []
    
    # Map tags to simple lowercase category names (attacker-relevant findings)
    # XSS
    if any(tag in tags_lower for tag in ["xss", "cross-site-scripting"]):
        categories.append("xss")
    
    # SQL Injection
    if any(tag in tags_lower for tag in ["sqli", "sql-injection", "sql"]):
        categories.append("sqli")
    
    # SSRF
    if any(tag in tags_lower for tag in ["ssrf", "server-side-request-forgery"]):
        categories.append("ssrf")
    
    # SSTI
    if any(tag in tags_lower for tag in ["ssti", "server-side-template-injection", "template-injection"]):
        categories.append("ssti")
    
    # XXE
    if any(tag in tags_lower for tag in ["xxe", "xml-external-entity"]):
        categories.append("xxe")
    
    # Directory Traversal (LFI/RFI)
    if any(tag in tags_lower for tag in ["lfi", "rfi", "local-file-inclusion", "remote-file-inclusion", "path-traversal", "directory-traversal", "file-inclusion"]):
        categories.append("directory_traversal")
    
    # CSRF
    if any(tag in tags_lower for tag in ["csrf", "cross-site-request-forgery"]):
        categories.append("csrf")
    
    # CORS
    if any(tag in tags_lower for tag in ["cors", "cross-origin-resource-sharing", "cors-misconfig"]):
        categories.append("cors_misconfig")
    
    # Command Injection
    if any(tag in tags_lower for tag in ["cmdi", "command-injection", "rce", "remote-code-execution", "code-execution", "os-commanding"]):
        categories.append("command_injection")
    
    # IDOR
    if any(tag in tags_lower for tag in ["idor", "insecure-direct-object-reference", "authorization"]):
        categories.append("idor")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_categories = []
    for cat in categories:
        if cat not in seen:
            seen.add(cat)
            unique_categories.append(cat)
    
    return unique_categories


def parse_nuclei_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nuclei JSONL output file (one JSON object per line) into a list of dicts.
    
    This function is robust to non-JSON lines (like ASCII tables, logs, etc.)
    and will skip them gracefully. Handles empty files and zero-byte files.
    
    Args:
        path: Path to the Nuclei output file (JSONL format)
        
    Returns:
        List of parsed Nuclei JSON objects (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    # Check if file is zero bytes
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                
                # Skip obvious non-JSON lines (tables, logs, etc.)
                # JSON objects/arrays start with { or [
                if not (line.startswith("{") or line.startswith("[")):
                    logger.debug(
                        "Skipping non-JSON line %d in nuclei output %s: %r",
                        line_no, path, line[:80]
                    )
                    continue
                
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        findings.append(obj)
                    else:
                        logger.debug("Skipping non-dict JSON on line %d in %s", line_no, path)
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
        
        logger.info("Parsed %d nuclei findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse Nuclei output file %s: %s", path, e, exc_info=True)
        return []


def parse_nmap_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nmap XML output file into a list of finding dicts.
    
    Each open port becomes a finding. Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the Nmap XML output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Extract host information
        for host in root.findall("host"):
            host_status = host.find("status")
            if host_status is None or host_status.get("state") != "up":
                continue
            
            # Get host address
            address_elem = host.find("address")
            host_ip = address_elem.get("addr") if address_elem is not None else "unknown"
            
            # Get hostname
            hostnames_elem = host.find("hostnames")
            hostname = host_ip
            if hostnames_elem is not None:
                hostname_elem = hostnames_elem.find("hostname")
                if hostname_elem is not None:
                    hostname = hostname_elem.get("name", host_ip)
            
            # Process ports
            ports_elem = host.find("ports")
            if ports_elem is None:
                continue
            
            for port_elem in ports_elem.findall("port"):
                port_state = port_elem.find("state")
                if port_state is None or port_state.get("state") != "open":
                    continue
                
                port_num = port_elem.get("portid")
                protocol = port_elem.get("protocol", "tcp")
                
                # Get service info
                service_elem = port_elem.find("service")
                service_name = service_elem.get("name", "unknown") if service_elem is not None else "unknown"
                service_product = service_elem.get("product", "") if service_elem is not None else ""
                service_version = service_elem.get("version", "") if service_elem is not None else ""
                
                # Build description
                description_parts = [
                    f"Host: {hostname} ({host_ip})",
                    f"Port: {port_num}/{protocol}",
                    f"Service: {service_name}",
                ]
                if service_product:
                    description_parts.append(f"Product: {service_product}")
                if service_version:
                    description_parts.append(f"Version: {service_version}")
                
                description = "\n".join(description_parts)
                
                # Determine severity based on port/service
                from app.core.config import settings
                severity = "info"
                high_risk_ports = [p.strip() for p in settings.HIGH_RISK_PORTS.split(",")]
                if port_num in high_risk_ports:  # SSH, RDP, VNC, etc.
                    severity = "medium"
                elif port_num in ["3306", "5432", "1433"]:  # MySQL, PostgreSQL, MSSQL
                    severity = "medium"
                elif port_num in ["21", "23", "25"]:  # FTP, Telnet, SMTP
                    severity = "low"
                elif port_num in ["80", "443", "8080", "8443"]:  # HTTP/HTTPS
                    severity = "info"
                
                # Build title
                title = f"Open port {port_num}/{protocol} ({service_name}) on {hostname}"
                
                # Build URL
                url = f"{hostname}:{port_num}"
                if port_num in ["80", "8080"]:
                    url = f"http://{hostname}:{port_num}"
                elif port_num in ["443", "8443"]:
                    url = f"https://{hostname}:{port_num}"
                
                # Store raw XML for this port as JSON
                raw_data = json.dumps({
                    "host": hostname,
                    "ip": host_ip,
                    "port": port_num,
                    "protocol": protocol,
                    "service": service_name,
                    "product": service_product,
                    "version": service_version,
                })
                
                findings.append({
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "cve_id": None,
                    "cwe_id": None,
                    "url": url,
                    "tool_name": "nmap",
                    "raw_data": raw_data,
                })
        
        logger.info("Parsed %d nmap findings from file for scan %s", len(findings), path)
        return findings
        
    except ET.ParseError as e:
        logger.warning("Failed to parse Nmap XML file %s: %s", path, e)
        return []
    except Exception as e:
        logger.error("Failed to read/parse Nmap output file %s: %s", path, e, exc_info=True)
        return []


def parse_sslscan_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse sslscan output file (JSON or text format) into a list of finding dicts.
    
    Handles both JSON output (when --json flag is used) and plain text output.
    Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the sslscan output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        # Try to parse as JSON first
        try:
            # Remove ANSI color codes if present
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            content_clean = ansi_escape.sub('', content)
            
            # Try to find JSON object/array
            json_start = content_clean.find('{')
            json_end = content_clean.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content_clean[json_start:json_end]
                data = json.loads(json_str)
                
                # Handle JSON format
                if isinstance(data, dict):
                    # Single JSON object
                    findings.extend(_parse_sslscan_json_object(data))
                elif isinstance(data, list):
                    # Array of JSON objects
                    for item in data:
                        if isinstance(item, dict):
                            findings.extend(_parse_sslscan_json_object(item))
        except (json.JSONDecodeError, ValueError):
            # Fall back to text parsing
            findings.extend(_parse_sslscan_text(content))
        
        logger.info("Parsed %d sslscan findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse sslscan output file %s: %s", path, e, exc_info=True)
        return []


def _parse_sslscan_json_object(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse a single sslscan JSON object into finding dicts"""
    findings = []
    
    host = data.get("host", "unknown")
    port = data.get("port", 443)
    target = f"{host}:{port}"
    
    # Check for weak protocols
    sslv2 = data.get("ssl_version", {}).get("SSLv2", {}).get("status", "").lower()
    sslv3 = data.get("ssl_version", {}).get("SSLv3", {}).get("status", "").lower()
    tls10 = data.get("ssl_version", {}).get("TLSv1.0", {}).get("status", "").lower()
    tls11 = data.get("ssl_version", {}).get("TLSv1.1", {}).get("status", "").lower()
    
    if sslv2 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if sslv3 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls10 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls11 == "enabled":
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    # Check for weak ciphers
    ciphers = data.get("cipher_suites", [])
    weak_ciphers = []
    for cipher in ciphers:
        cipher_name = cipher.get("cipher", "")
        key_length = cipher.get("key_length", 0)
        if key_length < 128 or "RC4" in cipher_name or "DES" in cipher_name or "MD5" in cipher_name:
            weak_ciphers.append(cipher_name)
    
    if weak_ciphers:
        findings.append({
            "severity": "medium",
            "title": f"Weak cipher suites detected on {target}",
            "description": f"Weak cipher suites found on {target}: {', '.join(weak_ciphers[:5])}",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    return findings


def _parse_sslscan_text(content: str) -> List[Dict[str, Any]]:
    """Parse sslscan plain text output into finding dicts"""
    findings = []
    
    # Remove ANSI color codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    content_clean = ansi_escape.sub('', content)
    
    # Extract host and port from content
    host_match = re.search(r'Testing SSL server\s+(\S+)\s+on port\s+(\d+)', content_clean)
    if not host_match:
        # Try alternative pattern
        host_match = re.search(r'Connected to\s+([\d.]+)', content_clean)
        port_match = re.search(r'port\s+(\d+)', content_clean)
        host = host_match.group(1) if host_match else "unknown"
        port = int(port_match.group(1)) if port_match else 443
    else:
        host = host_match.group(1)
        port = int(host_match.group(2))
    
    target = f"{host}:{port}"
    
    # Check for weak protocols in text
    if re.search(r'SSLv2\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],  # Store first 1000 chars
        })
    
    if re.search(r'SSLv3\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.0\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.1\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    # Check for weak ciphers
    weak_cipher_patterns = [
        (r'RC4', "high", "RC4 cipher is weak and should be disabled"),
        (r'DES', "high", "DES cipher is weak and should be disabled"),
        (r'3DES|Triple DES', "medium", "3DES cipher is deprecated and should be disabled"),
        (r'MD5', "high", "MD5 hash algorithm is weak and should not be used"),
        (r'SHA1', "medium", "SHA1 hash algorithm is deprecated and should be disabled"),
    ]
    
    for pattern, severity, description in weak_cipher_patterns:
        if re.search(pattern, content_clean, re.IGNORECASE):
            findings.append({
                "severity": severity,
                "title": f"Weak cipher/hash detected on {target}",
                "description": f"{description}",
                "cve_id": None,
                "cwe_id": "CWE-327",
                "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
                "tool_name": "sslscan",
                "raw_data": content_clean[:1000],
            })
    
    # Check for certificate issues
    cert_issues = [
        (r'Certificate.*expired', "high", "SSL certificate has expired"),
        (r'Certificate.*self.signed', "medium", "Self-signed certificate detected"),
        (r'Certificate.*invalid', "high", "Invalid SSL certificate detected"),
        (r'Certificate.*chain.*incomplete', "medium", "Incomplete certificate chain"),
    ]
    
    for pattern, severity, description in cert_issues:
        if re.search(pattern, content_clean, re.IGNORECASE):
            findings.append({
                "severity": severity,
                "title": f"Certificate issue on {target}",
                "description": f"{description}",
                "cve_id": None,
                "cwe_id": "CWE-295",
                "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
                "tool_name": "sslscan",
                "raw_data": content_clean[:1000],
            })
    
    # If we have output but no findings, create an informational finding
    # This helps users understand that SSLscan ran but found no issues
    if not findings and content_clean and len(content_clean) > 100:
        # Only create info finding if we have substantial output
        findings.append({
            "severity": "info",
            "title": f"SSL/TLS scan completed for {target}",
            "description": f"SSLscan completed successfully. No critical SSL/TLS issues detected. Review raw output for details.",
            "cve_id": None,
            "cwe_id": None,
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:2000],  # Store more data for info findings
        })
    
    return findings


def ingest_nmap_findings(
    db: Session,
    scan_job_id: str,
    nmap_results: List[Dict[str, Any]],
    tool_result_id: str | None = None,
) -> List[Finding]:
    """
    Ingest Nmap findings into the database.
    
    Per-tool idempotency: deletes existing nmap findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nmap_results: List of finding dicts from parse_nmap_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing nmap findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "nmap"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing nmap findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in nmap_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "Nmap Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="nmap",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nmap finding: {e}", exc_info=True)
            continue
    
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d nmap findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit nmap findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_sslscan_findings(
    db: Session,
    scan_job_id: str,
    sslscan_results: List[Dict[str, Any]],
    tool_result_id: str | None = None,
) -> List[Finding]:
    """
    Ingest sslscan findings into the database.
    
    Per-tool idempotency: deletes existing sslscan findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        sslscan_results: List of finding dicts from parse_sslscan_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing sslscan findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "sslscan"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing sslscan findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in sslscan_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "SSL/TLS Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="sslscan",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse sslscan finding: {e}", exc_info=True)
            continue
    
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d sslscan findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit sslscan findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_http_header_findings(
    db: Session,
    scan_job_id: str,
    header_findings: List[Finding],
) -> List[Finding]:
    """
    Ingest HTTP header findings into the database.
    
    Per-tool idempotency: deletes existing http_headers findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        header_findings: List of Finding objects for missing headers
        
    Returns:
        List of created Finding objects
    """
    # Delete existing http_headers findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "http_headers"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing http_headers findings for scan {scan_job_id}")
    
    # Add all findings to session
    for finding in header_findings:
        db.add(finding)
    
    # Flush findings to make them visible to queries, then commit
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d http_headers findings into DB for scan %s",
            len(header_findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit http_headers findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return header_findings





def categorize_nuclei_finding(template_tags: list[str]) -> list[str]:
    """
    Categorize a Nuclei finding based on its template tags.
    
    Normalizes tags to lowercase and returns a list of category strings
    based on the presence of common vulnerability tags.
    
    Args:
        template_tags: List of template tags from Nuclei finding (e.g., ["xss", "sqli", "cve"])
        
    Returns:
        List of category strings (e.g., ["xss", "sqli"])
        
    Example:
        >>> categorize_nuclei_finding(["xss", "sqli", "cve"])
        ["xss", "sqli"]
        >>> categorize_nuclei_finding(["lfi", "rfi"])
        ["dir_traversal"]
    """
    if not template_tags:
        return []
    
    # Normalize tags to lowercase
    tags_lower = [tag.lower() for tag in template_tags if tag]
    
    categories = []
    
    # Map tags to simple lowercase category names (attacker-relevant findings)
    # XSS
    if any(tag in tags_lower for tag in ["xss", "cross-site-scripting"]):
        categories.append("xss")
    
    # SQL Injection
    if any(tag in tags_lower for tag in ["sqli", "sql-injection", "sql"]):
        categories.append("sqli")
    
    # SSRF
    if any(tag in tags_lower for tag in ["ssrf", "server-side-request-forgery"]):
        categories.append("ssrf")
    
    # SSTI
    if any(tag in tags_lower for tag in ["ssti", "server-side-template-injection", "template-injection"]):
        categories.append("ssti")
    
    # XXE
    if any(tag in tags_lower for tag in ["xxe", "xml-external-entity"]):
        categories.append("xxe")
    
    # Directory Traversal (LFI/RFI)
    if any(tag in tags_lower for tag in ["lfi", "rfi", "local-file-inclusion", "remote-file-inclusion", "path-traversal", "directory-traversal", "file-inclusion"]):
        categories.append("directory_traversal")
    
    # CSRF
    if any(tag in tags_lower for tag in ["csrf", "cross-site-request-forgery"]):
        categories.append("csrf")
    
    # CORS
    if any(tag in tags_lower for tag in ["cors", "cross-origin-resource-sharing", "cors-misconfig"]):
        categories.append("cors_misconfig")
    
    # Command Injection
    if any(tag in tags_lower for tag in ["cmdi", "command-injection", "rce", "remote-code-execution", "code-execution", "os-commanding"]):
        categories.append("command_injection")
    
    # IDOR
    if any(tag in tags_lower for tag in ["idor", "insecure-direct-object-reference", "authorization"]):
        categories.append("idor")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_categories = []
    for cat in categories:
        if cat not in seen:
            seen.add(cat)
            unique_categories.append(cat)
    
    return unique_categories


def parse_nuclei_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nuclei JSONL output file (one JSON object per line) into a list of dicts.
    
    This function is robust to non-JSON lines (like ASCII tables, logs, etc.)
    and will skip them gracefully. Handles empty files and zero-byte files.
    
    Args:
        path: Path to the Nuclei output file (JSONL format)
        
    Returns:
        List of parsed Nuclei JSON objects (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    # Check if file is zero bytes
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nuclei output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                
                # Skip obvious non-JSON lines (tables, logs, etc.)
                # JSON objects/arrays start with { or [
                if not (line.startswith("{") or line.startswith("[")):
                    logger.debug(
                        "Skipping non-JSON line %d in nuclei output %s: %r",
                        line_no, path, line[:80]
                    )
                    continue
                
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        findings.append(obj)
                    else:
                        logger.debug("Skipping non-dict JSON on line %d in %s", line_no, path)
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
        
        logger.info("Parsed %d nuclei findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse Nuclei output file %s: %s", path, e, exc_info=True)
        return []


def parse_nmap_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nmap XML output file into a list of finding dicts.
    
    Each open port becomes a finding. Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the Nmap XML output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Extract host information
        for host in root.findall("host"):
            host_status = host.find("status")
            if host_status is None or host_status.get("state") != "up":
                continue
            
            # Get host address
            address_elem = host.find("address")
            host_ip = address_elem.get("addr") if address_elem is not None else "unknown"
            
            # Get hostname
            hostnames_elem = host.find("hostnames")
            hostname = host_ip
            if hostnames_elem is not None:
                hostname_elem = hostnames_elem.find("hostname")
                if hostname_elem is not None:
                    hostname = hostname_elem.get("name", host_ip)
            
            # Process ports
            ports_elem = host.find("ports")
            if ports_elem is None:
                continue
            
            for port_elem in ports_elem.findall("port"):
                port_state = port_elem.find("state")
                if port_state is None or port_state.get("state") != "open":
                    continue
                
                port_num = port_elem.get("portid")
                protocol = port_elem.get("protocol", "tcp")
                
                # Get service info
                service_elem = port_elem.find("service")
                service_name = service_elem.get("name", "unknown") if service_elem is not None else "unknown"
                service_product = service_elem.get("product", "") if service_elem is not None else ""
                service_version = service_elem.get("version", "") if service_elem is not None else ""
                
                # Build description
                description_parts = [
                    f"Host: {hostname} ({host_ip})",
                    f"Port: {port_num}/{protocol}",
                    f"Service: {service_name}",
                ]
                if service_product:
                    description_parts.append(f"Product: {service_product}")
                if service_version:
                    description_parts.append(f"Version: {service_version}")
                
                description = "\n".join(description_parts)
                
                # Determine severity based on port/service
                from app.core.config import settings
                severity = "info"
                high_risk_ports = [p.strip() for p in settings.HIGH_RISK_PORTS.split(",")]
                if port_num in high_risk_ports:  # SSH, RDP, VNC, etc.
                    severity = "medium"
                elif port_num in ["3306", "5432", "1433"]:  # MySQL, PostgreSQL, MSSQL
                    severity = "medium"
                elif port_num in ["21", "23", "25"]:  # FTP, Telnet, SMTP
                    severity = "low"
                elif port_num in ["80", "443", "8080", "8443"]:  # HTTP/HTTPS
                    severity = "info"
                
                # Build title
                title = f"Open port {port_num}/{protocol} ({service_name}) on {hostname}"
                
                # Build URL
                url = f"{hostname}:{port_num}"
                if port_num in ["80", "8080"]:
                    url = f"http://{hostname}:{port_num}"
                elif port_num in ["443", "8443"]:
                    url = f"https://{hostname}:{port_num}"
                
                # Store raw XML for this port as JSON
                raw_data = json.dumps({
                    "host": hostname,
                    "ip": host_ip,
                    "port": port_num,
                    "protocol": protocol,
                    "service": service_name,
                    "product": service_product,
                    "version": service_version,
                })
                
                findings.append({
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "cve_id": None,
                    "cwe_id": None,
                    "url": url,
                    "tool_name": "nmap",
                    "raw_data": raw_data,
                })
        
        logger.info("Parsed %d nmap findings from file for scan %s", len(findings), path)
        return findings
        
    except ET.ParseError as e:
        logger.warning("Failed to parse Nmap XML file %s: %s", path, e)
        return []
    except Exception as e:
        logger.error("Failed to read/parse Nmap output file %s: %s", path, e, exc_info=True)
        return []


def parse_sslscan_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse sslscan output file (JSON or text format) into a list of finding dicts.
    
    Handles both JSON output (when --json flag is used) and plain text output.
    Handles empty files and missing files gracefully.
    
    Args:
        path: Path to the sslscan output file
        
    Returns:
        List of finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("sslscan output file is empty or missing for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        # Try to parse as JSON first
        try:
            # Remove ANSI color codes if present
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            content_clean = ansi_escape.sub('', content)
            
            # Try to find JSON object/array
            json_start = content_clean.find('{')
            json_end = content_clean.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content_clean[json_start:json_end]
                data = json.loads(json_str)
                
                # Handle JSON format
                if isinstance(data, dict):
                    # Single JSON object
                    findings.extend(_parse_sslscan_json_object(data))
                elif isinstance(data, list):
                    # Array of JSON objects
                    for item in data:
                        if isinstance(item, dict):
                            findings.extend(_parse_sslscan_json_object(item))
        except (json.JSONDecodeError, ValueError):
            # Fall back to text parsing
            findings.extend(_parse_sslscan_text(content))
        
        logger.info("Parsed %d sslscan findings from file for scan %s", len(findings), path)
        return findings
        
    except Exception as e:
        logger.error("Failed to read/parse sslscan output file %s: %s", path, e, exc_info=True)
        return []


def _parse_sslscan_json_object(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse a single sslscan JSON object into finding dicts"""
    findings = []
    
    host = data.get("host", "unknown")
    port = data.get("port", 443)
    target = f"{host}:{port}"
    
    # Check for weak protocols
    sslv2 = data.get("ssl_version", {}).get("SSLv2", {}).get("status", "").lower()
    sslv3 = data.get("ssl_version", {}).get("SSLv3", {}).get("status", "").lower()
    tls10 = data.get("ssl_version", {}).get("TLSv1.0", {}).get("status", "").lower()
    tls11 = data.get("ssl_version", {}).get("TLSv1.1", {}).get("status", "").lower()
    
    if sslv2 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if sslv3 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls10 == "enabled":
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    if tls11 == "enabled":
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    # Check for weak ciphers
    ciphers = data.get("cipher_suites", [])
    weak_ciphers = []
    for cipher in ciphers:
        cipher_name = cipher.get("cipher", "")
        key_length = cipher.get("key_length", 0)
        if key_length < 128 or "RC4" in cipher_name or "DES" in cipher_name or "MD5" in cipher_name:
            weak_ciphers.append(cipher_name)
    
    if weak_ciphers:
        findings.append({
            "severity": "medium",
            "title": f"Weak cipher suites detected on {target}",
            "description": f"Weak cipher suites found on {target}: {', '.join(weak_ciphers[:5])}",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": json.dumps(data),
        })
    
    return findings


def _parse_sslscan_text(content: str) -> List[Dict[str, Any]]:
    """Parse sslscan plain text output into finding dicts"""
    findings = []
    
    # Remove ANSI color codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    content_clean = ansi_escape.sub('', content)
    
    # Extract host and port from content
    host_match = re.search(r'Testing SSL server\s+(\S+)\s+on port\s+(\d+)', content_clean)
    if not host_match:
        # Try alternative pattern
        host_match = re.search(r'Connected to\s+([\d.]+)', content_clean)
        port_match = re.search(r'port\s+(\d+)', content_clean)
        host = host_match.group(1) if host_match else "unknown"
        port = int(port_match.group(1)) if port_match else 443
    else:
        host = host_match.group(1)
        port = int(host_match.group(2))
    
    target = f"{host}:{port}"
    
    # Check for weak protocols in text
    if re.search(r'SSLv2\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv2) on {target}",
            "description": f"SSLv2 is enabled on {target}. SSLv2 is deprecated and vulnerable.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],  # Store first 1000 chars
        })
    
    if re.search(r'SSLv3\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak SSL protocol enabled (SSLv3) on {target}",
            "description": f"SSLv3 is enabled on {target}. SSLv3 is vulnerable to POODLE attack.",
            "cve_id": "CVE-2014-3566",
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.0\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "high",
            "title": f"Weak TLS protocol enabled (TLSv1.0) on {target}",
            "description": f"TLSv1.0 is enabled on {target}. TLSv1.0 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    if re.search(r'TLSv1\.1\s+enabled', content_clean, re.IGNORECASE):
        findings.append({
            "severity": "medium",
            "title": f"Deprecated TLS protocol enabled (TLSv1.1) on {target}",
            "description": f"TLSv1.1 is enabled on {target}. TLSv1.1 is deprecated and should be disabled.",
            "cve_id": None,
            "cwe_id": "CWE-327",
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:1000],
        })
    
    # Check for weak ciphers
    weak_cipher_patterns = [
        (r'RC4', "high", "RC4 cipher is weak and should be disabled"),
        (r'DES', "high", "DES cipher is weak and should be disabled"),
        (r'3DES|Triple DES', "medium", "3DES cipher is deprecated and should be disabled"),
        (r'MD5', "high", "MD5 hash algorithm is weak and should not be used"),
        (r'SHA1', "medium", "SHA1 hash algorithm is deprecated and should be disabled"),
    ]
    
    for pattern, severity, description in weak_cipher_patterns:
        if re.search(pattern, content_clean, re.IGNORECASE):
            findings.append({
                "severity": severity,
                "title": f"Weak cipher/hash detected on {target}",
                "description": f"{description}",
                "cve_id": None,
                "cwe_id": "CWE-327",
                "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
                "tool_name": "sslscan",
                "raw_data": content_clean[:1000],
            })
    
    # Check for certificate issues
    cert_issues = [
        (r'Certificate.*expired', "high", "SSL certificate has expired"),
        (r'Certificate.*self.signed', "medium", "Self-signed certificate detected"),
        (r'Certificate.*invalid', "high", "Invalid SSL certificate detected"),
        (r'Certificate.*chain.*incomplete', "medium", "Incomplete certificate chain"),
    ]
    
    for pattern, severity, description in cert_issues:
        if re.search(pattern, content_clean, re.IGNORECASE):
            findings.append({
                "severity": severity,
                "title": f"Certificate issue on {target}",
                "description": f"{description}",
                "cve_id": None,
                "cwe_id": "CWE-295",
                "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
                "tool_name": "sslscan",
                "raw_data": content_clean[:1000],
            })
    
    # If we have output but no findings, create an informational finding
    # This helps users understand that SSLscan ran but found no issues
    if not findings and content_clean and len(content_clean) > 100:
        # Only create info finding if we have substantial output
        findings.append({
            "severity": "info",
            "title": f"SSL/TLS scan completed for {target}",
            "description": f"SSLscan completed successfully. No critical SSL/TLS issues detected. Review raw output for details.",
            "cve_id": None,
            "cwe_id": None,
            "url": f"https://{host}:{port}" if port == 443 else f"{host}:{port}",
            "tool_name": "sslscan",
            "raw_data": content_clean[:2000],  # Store more data for info findings
        })
    
    return findings


def ingest_nmap_findings(
    db: Session,
    scan_job_id: str,
    nmap_results: List[Dict[str, Any]],
    tool_result_id: str | None = None,
) -> List[Finding]:
    """
    Ingest Nmap findings into the database.
    
    Per-tool idempotency: deletes existing nmap findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        nmap_results: List of finding dicts from parse_nmap_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing nmap findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "nmap"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing nmap findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in nmap_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "Nmap Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="nmap",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse Nmap finding: {e}", exc_info=True)
            continue
    
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d nmap findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit nmap findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_sslscan_findings(
    db: Session,
    scan_job_id: str,
    sslscan_results: List[Dict[str, Any]],
    tool_result_id: str | None = None,
) -> List[Finding]:
    """
    Ingest sslscan findings into the database.
    
    Per-tool idempotency: deletes existing sslscan findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        sslscan_results: List of finding dicts from parse_sslscan_output
        
    Returns:
        List of created Finding objects
    """
    # Delete existing sslscan findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "sslscan"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing sslscan findings for scan {scan_job_id}")
    
    findings = []
    
    for finding_data in sslscan_results:
        try:
            # Normalize severity
            severity_str = finding_data.get("severity", "info").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.INFO)
            
            finding = Finding(
                scan_job_id=scan_job_id,
                title=finding_data.get("title", "SSL/TLS Finding")[:500],
                description=finding_data.get("description"),
                severity=severity,
                cve_id=finding_data.get("cve_id")[:50] if finding_data.get("cve_id") else None,
                cwe_id=finding_data.get("cwe_id")[:50] if finding_data.get("cwe_id") else None,
                url=finding_data.get("url")[:2048] if finding_data.get("url") else None,
                tool_name="sslscan",
                raw_data=finding_data.get("raw_data"),
                status=FindingStatus.OPEN,
            )
            
            findings.append(finding)
            db.add(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse sslscan finding: {e}", exc_info=True)
            continue
    
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d sslscan findings into DB for scan %s",
            len(findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit sslscan findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return findings


def ingest_http_header_findings(
    db: Session,
    scan_job_id: str,
    header_findings: List[Finding],
) -> List[Finding]:
    """
    Ingest HTTP header findings into the database.
    
    Per-tool idempotency: deletes existing http_headers findings for this scan_job before inserting.
    
    Args:
        db: Database session
        scan_job_id: ID of the scan job
        header_findings: List of Finding objects for missing headers
        
    Returns:
        List of created Finding objects
    """
    # Delete existing http_headers findings for this scan job (per-tool idempotency)
    deleted_count = db.query(Finding).filter(
        Finding.scan_job_id == scan_job_id,
        Finding.tool_name == "http_headers"
    ).delete()
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} existing http_headers findings for scan {scan_job_id}")
    
    # Add all findings to session
    for finding in header_findings:
        db.add(finding)
    
    # Flush findings to make them visible to queries, then commit
    try:
        db.flush()  # Make findings visible to queries before commit
        db.commit()
        logger.info(
            "Ingested %d http_headers findings into DB for scan %s",
            len(header_findings), scan_job_id
        )
    except Exception as e:
        logger.error("Failed to commit http_headers findings for scan %s: %s", scan_job_id, e, exc_info=True)
        db.rollback()
        raise
    
    return header_findings



