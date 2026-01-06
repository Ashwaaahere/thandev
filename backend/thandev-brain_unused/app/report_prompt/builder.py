"""
Report prompt package builder
Builds OpenAI prompt packages with RAG evidence for report generation
"""
import logging
from typing import Dict, Any, List, Optional

from app.models import BuildReportPromptResponse, ReportJsonSchema
from app.core.config import settings
from app.rag.store import get_rag_store
from app.rag.ingestion import query_rag_lanes

logger = logging.getLogger(__name__)


async def build_prompt_package(
    scan_job_id: str,
    finding_ids: List[str],
    artifact_refs: List[Dict[str, Any]] = None,
    org_id: str = None,
    project_id: str = None,
) -> BuildReportPromptResponse:
    """
    Build a prompt package for OpenAI report generation.
    
    Process:
    1. Load normalized findings from core-provided IDs (stub - core will provide)
    2. Retrieve supporting evidence from RAG
    3. Build artifact_index from artifact_refs
    4. Generate strict JSON schema for report structure
    5. Package system/user messages with evidence
    
    Args:
        scan_job_id: Scan job ID
        finding_ids: List of finding IDs to include
        artifact_refs: Artifact references (tool outputs, etc.)
        org_id: Organization ID for RAG filtering
        project_id: Project ID for RAG filtering
        
    Returns:
        BuildReportPromptResponse with OpenAI request payload
    """
    logger.info(f"Building report prompt for scan {scan_job_id} with {len(finding_ids)} findings")
    
    if artifact_refs is None:
        artifact_refs = []
    
    # Step 1: Load normalized findings
    # Note: In production, this would call core backend API or use shared DB
    # For now, we'll structure the findings from the IDs provided
    findings = await _load_findings(finding_ids, org_id, project_id)
    
    # Step 2: Retrieve supporting evidence from RAG
    rag_evidence = await _retrieve_report_evidence(
        finding_ids=finding_ids,
        findings=findings,
        org_id=org_id,
        project_id=project_id,
    )
    
    # Step 3: Build artifact_index
    artifact_index = _build_artifact_index(artifact_refs, findings)
    
    # Step 4: Generate strict JSON schema
    report_json_schema = _generate_report_schema()
    
    # Step 5: Build system and user messages
    system_message = _build_system_message()
    user_content = _build_user_content(
        scan_job_id=scan_job_id,
        findings=findings,
        evidence=rag_evidence,
        artifacts=artifact_refs,
    )
    
    return BuildReportPromptResponse(
        system_message=system_message,
        user_content=user_content,
        report_json_schema=report_json_schema,
        artifact_index=artifact_index,
        metadata={
            "scan_job_id": scan_job_id,
            "finding_count": len(findings),
            "evidence_count": len(rag_evidence.get("evidence_items", [])),
            "artifact_count": len(artifact_refs),
        }
    )


async def _load_findings(
    finding_ids: List[str],
    org_id: Optional[str],
    project_id: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Load normalized findings from core backend.
    
    Tries multiple methods:
    1. Direct database access (if DATABASE_URL shared)
    2. HTTP API call to core backend
    3. Stub findings as last resort
    """
    from app.report_prompt.finding_loader import load_findings_from_ids
    
    return await load_findings_from_ids(finding_ids, org_id, project_id)


async def _retrieve_report_evidence(
    finding_ids: List[str],
    findings: List[Dict[str, Any]],
    org_id: Optional[str],
    project_id: Optional[str],
) -> Dict[str, Any]:
    """
    Retrieve supporting evidence from RAG for report generation.
    
    Evidence includes:
    - Similar findings from prior scans
    - CVE/template metadata
    - Artifact summaries
    - Tech fingerprint context
    """
    try:
        rag_store = get_rag_store()
        
        # Build query from findings
        # Use titles and descriptions to find similar evidence
        query_texts = []
        for finding in findings:
            if finding.get("title"):
                query_texts.append(finding["title"])
            if finding.get("description"):
                query_texts.append(finding["description"])
        
        if not query_texts:
            query_texts = ["security findings"]
        
        # Query across lanes
        query_text = " ".join(query_texts[:3])  # Limit to first 3 for query
        
        lanes = await query_rag_lanes(
            rag_store=rag_store,
            query_text=query_text,
            org_id=org_id,
            project_id=project_id,
            top_k_per_lane=10,  # More evidence for reports
        )
        
        # Format evidence items
        evidence_items = []
        
        # Latest findings (similar findings)
        for finding_result in lanes.get("latest_findings", [])[:5]:
            evidence_items.append({
                "type": "similar_finding",
                "source": "rag",
                "metadata": finding_result.get("metadata", {}),
                "score": finding_result.get("score", 0.0),
            })
        
        # CVE templates
        for cve_result in lanes.get("cve_templates", [])[:5]:
            evidence_items.append({
                "type": "cve_template",
                "source": "rag",
                "metadata": cve_result.get("metadata", {}),
                "score": cve_result.get("score", 0.0),
            })
        
        # Tech fingerprint
        tech_results = lanes.get("tech_fingerprint", [])
        if tech_results:
            evidence_items.append({
                "type": "tech_fingerprint",
                "source": "rag",
                "metadata": tech_results[0].get("metadata", {}),
                "score": tech_results[0].get("score", 0.0),
            })
        
        # Artifact summaries
        for artifact_result in lanes.get("artifact_summaries", [])[:3]:
            evidence_items.append({
                "type": "artifact_summary",
                "source": "rag",
                "metadata": artifact_result.get("metadata", {}),
                "score": artifact_result.get("score", 0.0),
            })
        
        logger.info(f"Retrieved {len(evidence_items)} evidence items from RAG")
        
        return {
            "evidence_items": evidence_items,
            "lanes_queried": list(lanes.keys()),
        }
    except Exception as e:
        logger.warning(f"RAG evidence retrieval failed: {e}, continuing without evidence")
        return {
            "evidence_items": [],
            "lanes_queried": [],
        }


def _build_artifact_index(
    artifact_refs: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build artifact index mapping artifact IDs to metadata.
    
    Each finding should reference artifacts via evidence_refs.
    """
    artifact_index = {}
    
    for i, artifact_ref in enumerate(artifact_refs):
        artifact_id = artifact_ref.get("id") or f"artifact_{i}"
        artifact_index[artifact_id] = {
            "id": artifact_id,
            "tool_name": artifact_ref.get("tool_name", "unknown"),
            "file_path": artifact_ref.get("file_path"),
            "scan_job_id": artifact_ref.get("scan_job_id"),
            "created_at": artifact_ref.get("created_at"),
            "summary": artifact_ref.get("summary", ""),
        }
    
    # Also index findings as artifacts (they reference tool outputs)
    for finding in findings:
        tool_name = finding.get("tool_name", "unknown")
        finding_id = finding.get("id")
        
        if finding_id and tool_name:
            artifact_key = f"finding_{finding_id}"
            if artifact_key not in artifact_index:
                artifact_index[artifact_key] = {
                    "id": artifact_key,
                    "tool_name": tool_name,
                    "finding_id": finding_id,
                    "type": "finding_reference",
                }
    
    logger.info(f"Built artifact index with {len(artifact_index)} entries")
    return artifact_index


def _generate_report_schema() -> ReportJsonSchema:
    """
    Generate strict JSON schema for report structure.
    
    This schema will be used with OpenAI Structured Outputs.
    """
    return ReportJsonSchema(
        type="object",
        properties={
            "executive_summary": {
                "type": "string",
                "description": "High-level overview of the security scan results"
            },
            "top_risks": {
                "type": "array",
                "description": "Top 5-10 critical and high severity findings",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Finding title"
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low", "info"],
                            "description": "Finding severity"
                        },
                        "cve_id": {
                            "type": "string",
                            "description": "CVE ID if applicable"
                        },
                        "cvss_score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 10,
                            "description": "CVSS score if available"
                        },
                        "url": {
                            "type": "string",
                            "description": "URL where finding was detected"
                        },
                        "evidence_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "References to artifacts/evidence supporting this finding",
                            "minItems": 1
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description of the finding"
                        },
                        "recommendation": {
                            "type": "string",
                            "description": "Remediation recommendation"
                        }
                    },
                    "required": ["title", "severity", "evidence_refs"],
                    "additionalProperties": False
                },
                "minItems": 0,
                "maxItems": 10
            },
            "remediation_overview": {
                "type": "string",
                "description": "Prioritized remediation steps and recommendations"
            },
            "risk_score": {
                "type": "number",
                "minimum": 0,
                "maximum": 10,
                "description": "Overall risk score (0-10 scale)"
            },
            "findings_count": {
                "type": "integer",
                "minimum": 0,
                "description": "Total number of findings"
            },
            "severity_breakdown": {
                "type": "object",
                "properties": {
                    "critical": {"type": "integer", "minimum": 0},
                    "high": {"type": "integer", "minimum": 0},
                    "medium": {"type": "integer", "minimum": 0},
                    "low": {"type": "integer", "minimum": 0},
                    "info": {"type": "integer", "minimum": 0}
                },
                "required": ["critical", "high", "medium", "low", "info"],
                "additionalProperties": False
            },
            "scan_metadata": {
                "type": "object",
                "properties": {
                    "scan_level": {
                        "type": "string",
                        "enum": ["basic", "pro", "advanced"]
                    },
                    "tools_used": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "scan_duration_sec": {
                        "type": "number",
                        "minimum": 0
                    }
                },
                "additionalProperties": False
            }
        },
        required=[
            "executive_summary",
            "top_risks",
            "remediation_overview",
            "risk_score",
            "findings_count",
            "severity_breakdown"
        ],
        additionalProperties=False
    )


def _build_system_message() -> str:
    """Build system message for OpenAI."""
    return """You are a security report generator. Generate a comprehensive security scan report based on the provided findings and evidence.

CRITICAL RULES:
1. Do NOT invent findings. All findings must be based on the provided findings list.
2. All findings in top_risks MUST cite evidence_refs (references to artifacts/evidence).
3. Use the provided evidence objects to support your analysis.
4. Follow the strict JSON schema exactly - no additional fields allowed.
5. Risk score should be calculated based on severity and count of findings.
6. Remediation recommendations should be specific and actionable.
7. Executive summary should be concise (2-3 sentences) and highlight critical issues.

EVIDENCE REQUIREMENTS:
- Every finding in top_risks must have at least one evidence_ref
- Evidence refs should point to artifact IDs from the artifact_index
- Use evidence items to provide context and support findings

OUTPUT FORMAT:
- Return ONLY valid JSON matching the provided schema
- Do not include markdown formatting
- Do not include explanations outside the JSON structure"""


def _build_user_content(
    scan_job_id: str,
    findings: List[Dict[str, Any]],
    evidence: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build user message content with findings and evidence.
    """
    # Calculate severity breakdown
    severity_counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
    }
    
    for finding in findings:
        severity = finding.get("severity", "info").lower()
        if severity in severity_counts:
            severity_counts[severity] += 1
    
    # Sort findings by severity (critical > high > medium > low > info)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_findings = sorted(
        findings,
        key=lambda f: (
            severity_order.get(f.get("severity", "info").lower(), 99),
            f.get("cvss_score") or 0
        ),
        reverse=True
    )
    
    # Format findings for prompt
    formatted_findings = []
    for finding in sorted_findings:
        formatted_finding = {
            "id": finding.get("id"),
            "title": finding.get("title", "Unknown finding"),
            "description": finding.get("description"),
            "severity": finding.get("severity", "info"),
            "cve_id": finding.get("cve_id"),
            "cvss_score": finding.get("cvss_score"),
            "url": finding.get("url"),
            "tool_name": finding.get("tool_name"),
        }
        formatted_findings.append(formatted_finding)
    
    return {
        "scan_job_id": scan_job_id,
        "findings": formatted_findings,
        "findings_count": len(findings),
        "severity_breakdown": severity_counts,
        "evidence": evidence.get("evidence_items", []),
        "artifacts": artifacts,
        "instructions": (
            "Generate a comprehensive security report based on the findings above. "
            "Use the evidence items to provide context. "
            "Ensure every finding in top_risks has evidence_refs pointing to relevant artifacts. "
            "Calculate risk_score based on severity distribution (critical=10, high=8, medium=5, low=2, info=0)."
        )
    }
