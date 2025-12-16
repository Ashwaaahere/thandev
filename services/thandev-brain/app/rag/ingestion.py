"""
Document ingestion utilities for RAG
"""
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def create_finding_document(
    finding_id: str,
    title: str,
    description: Optional[str],
    severity: str,
    url: Optional[str],
    tool_id: str,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    target: Optional[str] = None,
    cve_id: Optional[str] = None,
    raw_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a RAG document from a normalized finding.
    
    Args:
        finding_id: Finding ID
        title: Finding title
        description: Finding description
        severity: Finding severity (critical, high, medium, low, info)
        url: Finding URL
        tool_id: Tool that found this (nuclei, nmap, etc.)
        org_id: Organization ID
        project_id: Project ID
        target: Target URL
        cve_id: CVE ID if applicable
        raw_data: Raw finding data
        
    Returns:
        Document dict for RAG storage
    """
    # Combine title and description for content
    content_parts = [title]
    if description:
        content_parts.append(description)
    if cve_id:
        content_parts.append(f"CVE: {cve_id}")
    if url:
        content_parts.append(f"URL: {url}")
    
    content = "\n".join(content_parts)
    
    # Qdrant requires point IDs to be UUID or integer
    # If finding_id is already a UUID, use it directly; otherwise generate UUID5
    try:
        # Try to parse as UUID (finding_id should be a UUID string)
        point_id = uuid.UUID(str(finding_id))
    except (ValueError, TypeError):
        # Generate deterministic UUID5 from finding_id
        point_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"finding_{finding_id}")
    
    doc = {
        "id": point_id,  # Store UUID object (will be converted to string in store if needed)
        "title": title,
        "description": description or "",
        "content": content,
        "doc_type": "finding",
        "org_id": org_id,
        "project_id": project_id,
        "target": target,
        "tool_id": tool_id,
        "severity": severity,
        "cve_id": cve_id,
        "url": url,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    # Add raw_data as JSON string if provided
    if raw_data:
        import json
        doc["raw_data"] = json.dumps(raw_data)
    
    return doc


def create_artifact_summary_document(
    artifact_id: str,
    tool_id: str,
    scan_job_id: str,
    summary: str,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    target: Optional[str] = None,
    finding_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a RAG document from a tool artifact summary.
    
    Args:
        artifact_id: Artifact ID
        tool_id: Tool that generated this artifact
        scan_job_id: Scan job ID
        summary: Summary of artifact contents (NOT huge raw logs)
        org_id: Organization ID
        project_id: Project ID
        target: Target URL
        finding_count: Number of findings in this artifact
        
    Returns:
        Document dict for RAG storage
    """
    # Generate deterministic UUID5 for artifact
    point_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"artifact_{artifact_id}")
    
    doc = {
        "id": point_id,  # Store UUID object
        "title": f"{tool_id} scan results",
        "description": f"Artifact from {tool_id} scan on {target or 'unknown target'}",
        "content": summary,
        "doc_type": "artifact_summary",
        "org_id": org_id,
        "project_id": project_id,
        "target": target,
        "tool_id": tool_id,
        "scan_job_id": scan_job_id,
        "finding_count": finding_count,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    return doc


def create_tech_fingerprint_document(
    target: str,
    tech_stack: Dict[str, Any],
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a RAG document from technology fingerprint.
    
    Args:
        target: Target URL
        tech_stack: Technology stack information (server, framework, etc.)
        org_id: Organization ID
        project_id: Project ID
        
    Returns:
        Document dict for RAG storage
    """
    # Build content from tech stack
    content_parts = [f"Technology fingerprint for {target}"]
    if tech_stack.get("server"):
        content_parts.append(f"Server: {tech_stack['server']}")
    if tech_stack.get("framework"):
        content_parts.append(f"Framework: {tech_stack['framework']}")
    if tech_stack.get("cms"):
        content_parts.append(f"CMS: {tech_stack['cms']}")
    if tech_stack.get("languages"):
        content_parts.append(f"Languages: {', '.join(tech_stack['languages'])}")
    
    content = "\n".join(content_parts)
    
    # Generate deterministic UUID5 for tech fingerprint
    point_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"tech_{target}")
    
    doc = {
        "id": point_id,  # Store UUID object
        "title": f"Technology fingerprint: {target}",
        "description": f"Detected technologies for {target}",
        "content": content,
        "doc_type": "tech_fingerprint",
        "org_id": org_id,
        "project_id": project_id,
        "target": target,
        "tech_stack": tech_stack,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    return doc


def create_cve_template_document(
    cve_id: str,
    template_info: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a RAG document from CVE/template metadata.
    
    Args:
        cve_id: CVE ID
        template_info: Template information (name, description, severity, tags)
        
    Returns:
        Document dict for RAG storage
    """
    content_parts = [
        f"CVE: {cve_id}",
        template_info.get("name", ""),
        template_info.get("description", ""),
    ]
    if template_info.get("tags"):
        content_parts.append(f"Tags: {', '.join(template_info['tags'])}")
    
    content = "\n".join(content_parts)
    
    # Generate deterministic UUID5 for CVE template
    point_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"cve_{cve_id}")
    
    doc = {
        "id": point_id,  # Store UUID object
        "title": f"{cve_id}: {template_info.get('name', 'Unknown')}",
        "description": template_info.get("description", ""),
        "content": content,
        "doc_type": "cve_template",
        "cve_id": cve_id,
        "severity": template_info.get("severity", "unknown"),
        "tags": template_info.get("tags", []),
        "created_at": datetime.utcnow().isoformat(),
    }
    
    return doc


async def ingest_findings_batch(
    rag_store: "RagStore",
    findings: List[Dict[str, Any]],
) -> None:
    """
    Ingest a batch of findings into RAG store.
    
    Args:
        rag_store: RAG store instance
        findings: List of finding dicts with fields: id, title, description, severity, url, tool_id, etc.
    """
    if not findings:
        return
    
    docs = []
    for finding in findings:
        doc = create_finding_document(
            finding_id=finding.get("id"),
            title=finding.get("title", ""),
            description=finding.get("description"),
            severity=finding.get("severity", "info"),
            url=finding.get("url"),
            tool_id=finding.get("tool_id") or finding.get("tool_name", "unknown"),
            org_id=finding.get("org_id"),
            project_id=finding.get("project_id"),
            target=finding.get("target"),
            cve_id=finding.get("cve_id"),
            raw_data=finding.get("raw_data"),
        )
        docs.append(doc)
    
    await rag_store.upsert_documents(docs)
    logger.info(f"Ingested {len(docs)} findings into RAG store")


async def query_rag_lanes(
    rag_store: "RagStore",
    query_text: str,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    target: Optional[str] = None,
    doc_types: Optional[List[str]] = None,
    top_k_per_lane: int = 5,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Query RAG store across multiple "lanes" (document types).
    
    Retrieval lanes:
    - latest_findings: Recent findings for this project/target
    - tech_fingerprint: Technology stack information
    - cve_templates: CVE/template metadata
    - artifact_summaries: Tool artifact summaries
    
    Args:
        rag_store: RAG store instance
        query_text: Query text
        org_id: Organization ID filter
        project_id: Project ID filter
        target: Target URL filter
        doc_types: Specific doc types to query (None = all)
        top_k_per_lane: Number of results per lane
        
    Returns:
        Dict mapping lane names to result lists
    """
    lanes = {}
    
    # Lane 1: Latest findings
    if not doc_types or "finding" in doc_types:
        filters = {"doc_type": "finding"}
        if org_id:
            filters["org_id"] = org_id
        if project_id:
            filters["project_id"] = project_id
        if target:
            filters["target"] = target
        
        findings = await rag_store.query(
            query_text=query_text,
            filters=filters,
            top_k=top_k_per_lane,
        )
        lanes["latest_findings"] = findings
    
    # Lane 2: Tech fingerprint
    if not doc_types or "tech_fingerprint" in doc_types:
        filters = {"doc_type": "tech_fingerprint"}
        if target:
            filters["target"] = target
        
        tech = await rag_store.query(
            query_text=query_text,
            filters=filters,
            top_k=top_k_per_lane,
        )
        lanes["tech_fingerprint"] = tech
    
    # Lane 3: CVE templates
    if not doc_types or "cve_template" in doc_types:
        filters = {"doc_type": "cve_template"}
        
        cves = await rag_store.query(
            query_text=query_text,
            filters=filters,
            top_k=top_k_per_lane,
        )
        lanes["cve_templates"] = cves
    
    # Lane 4: Artifact summaries
    if not doc_types or "artifact_summary" in doc_types:
        filters = {"doc_type": "artifact_summary"}
        if org_id:
            filters["org_id"] = org_id
        if project_id:
            filters["project_id"] = project_id
        if target:
            filters["target"] = target
        
        artifacts = await rag_store.query(
            query_text=query_text,
            filters=filters,
            top_k=top_k_per_lane,
        )
        lanes["artifact_summaries"] = artifacts
    
    return lanes

