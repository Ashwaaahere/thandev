"""
Finding enrichment service
Uses RAG + OpenAI to generate impact summaries and remediation guidance for findings
"""
import logging
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI

from app.core.config import settings
from app.rag.store import get_rag_store
from app.rag.ingestion import query_rag_lanes
from app.models import BrainFindingInput, EnrichedFindingItem

logger = logging.getLogger(__name__)


async def enrich_findings_batch(
    findings: List[BrainFindingInput],
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    target_url: Optional[str] = None,
) -> List[EnrichedFindingItem]:
    """
    Enrich a batch of findings with AI-generated impact summaries and remediation guidance.
    
    Process:
    1. Build context for each finding (title, description, severity, tool, vuln_type, url, parameter)
    2. Query RAG store for relevant evidence (latest findings, tech fingerprint, CVE templates)
    3. Call OpenAI with structured outputs to generate impact_summary, remediation_summary, remediation_steps
    4. Return enriched findings
    
    Args:
        findings: List of findings to enrich
        org_id: Organization ID for RAG filtering
        project_id: Project ID for RAG filtering
        target_url: Target URL for RAG filtering
        
    Returns:
        List of EnrichedFindingItem with AI-generated content
    """
    if not findings:
        return []
    
    # Check if enrichment is enabled and OpenAI is configured
    if not settings.ENRICH_FINDINGS_ENABLED:
        logger.info("Finding enrichment is disabled, returning generic fallbacks")
        return _generate_fallback_enrichments(findings)
    
    if not settings.OPENAI_API_KEY:
        logger.warning("OpenAI API key not configured, returning generic fallbacks")
        return _generate_fallback_enrichments(findings)
    
    try:
        # Step 1: Build context strings for each finding
        finding_contexts = []
        for finding in findings:
            context_parts = []
            if finding.title:
                context_parts.append(f"Title: {finding.title}")
            if finding.description:
                context_parts.append(f"Description: {finding.description[:500]}")  # Truncate long descriptions
            if finding.severity:
                context_parts.append(f"Severity: {finding.severity}")
            if finding.tool_name:
                context_parts.append(f"Tool: {finding.tool_name}")
            if finding.vuln_type:
                context_parts.append(f"Vulnerability Type: {finding.vuln_type}")
            if finding.url:
                context_parts.append(f"URL: {finding.url}")
            if finding.parameter:
                context_parts.append(f"Parameter: {finding.parameter}")
            if finding.raw_data:
                # Include relevant raw_data fields (payload, type, etc.)
                raw_str = json.dumps(finding.raw_data, indent=2)[:300]  # Truncate
                context_parts.append(f"Raw Data: {raw_str}")
            
            context = "\n".join(context_parts)
            finding_contexts.append({
                "finding_id": finding.id,
                "context": context,
                "vuln_type": finding.vuln_type,
            })
        
        # Step 2: Retrieve RAG evidence for the batch
        # Build a combined query from all findings
        query_texts = []
        for finding in findings:
            if finding.title:
                query_texts.append(finding.title)
            if finding.vuln_type:
                query_texts.append(finding.vuln_type)
        
        query_text = " ".join(query_texts[:5]) or "security findings"
        
        rag_evidence = {}
        try:
            rag_store = get_rag_store()
            lanes = await query_rag_lanes(
                rag_store=rag_store,
                query_text=query_text,
                org_id=org_id,
                project_id=project_id,
                target=target_url,
                top_k_per_lane=5,  # Fewer results per lane for enrichment
            )
            
            # Format evidence for prompt
            evidence_items = []
            for finding_result in lanes.get("latest_findings", [])[:3]:
                evidence_items.append(f"Similar finding: {finding_result.get('title', 'N/A')}")
            for cve_result in lanes.get("cve_templates", [])[:3]:
                evidence_items.append(f"CVE template: {cve_result.get('title', 'N/A')}")
            for tech_result in lanes.get("tech_fingerprint", [])[:2]:
                evidence_items.append(f"Tech stack: {tech_result.get('title', 'N/A')}")
            
            rag_evidence["evidence_text"] = "\n".join(evidence_items) if evidence_items else "No similar findings or CVE templates found."
        except Exception as e:
            logger.warning(f"RAG evidence retrieval failed: {e}, continuing without evidence")
            rag_evidence["evidence_text"] = "No additional evidence available."
        
        # Step 3: Call OpenAI with structured outputs
        enriched_items = await _call_openai_for_enrichment(
            finding_contexts=finding_contexts,
            rag_evidence=rag_evidence,
        )
        
        return enriched_items
        
    except Exception as e:
        logger.error(f"Failed to enrich findings: {e}", exc_info=True)
        # Return fallbacks on error
        return _generate_fallback_enrichments(findings)


async def _call_openai_for_enrichment(
    finding_contexts: List[Dict[str, Any]],
    rag_evidence: Dict[str, Any],
) -> List[EnrichedFindingItem]:
    """
    Call OpenAI API to generate enrichment for findings.
    
    Uses structured outputs (JSON schema) to ensure consistent format.
    """
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Build system message
        system_message = """You are a security expert specializing in vulnerability analysis and remediation guidance.

Your task is to analyze security findings and provide:
1. **Impact Summary**: A clear, concise explanation of why this vulnerability matters and what an attacker could do.
2. **Remediation Summary**: A brief overview of how to fix this issue.
3. **Remediation Steps**: A numbered list of specific, actionable steps to remediate the vulnerability.

CRITICAL RULES:
- Be specific and actionable. Avoid generic statements.
- Focus on the actual vulnerability type and context provided.
- Use the evidence from similar findings or CVE templates to inform your guidance.
- Keep impact_summary to 1-2 sentences.
- Keep remediation_summary to 1 sentence.
- Provide 3-5 concrete remediation steps.
- If the vulnerability type is unclear, provide general security best practices.

OUTPUT FORMAT:
- Return a JSON array where each object has: finding_id, impact_summary, remediation_summary, remediation_steps (array of strings).
- All fields are required except where explicitly noted as optional."""
        
        # Build user message with findings and evidence
        findings_text = "\n\n---\n\n".join([
            f"Finding ID: {ctx['finding_id']}\n{ctx['context']}"
            for ctx in finding_contexts
        ])
        
        user_message = f"""Analyze the following security findings and provide impact summaries and remediation guidance for each.

EVIDENCE FROM SIMILAR FINDINGS:
{rag_evidence.get('evidence_text', 'No additional evidence available.')}

FINDINGS TO ANALYZE:
{findings_text}

For each finding, provide:
- impact_summary: Why this vulnerability matters (1-2 sentences)
- remediation_summary: How to fix it (1 sentence)
- remediation_steps: Specific steps to remediate (3-5 steps as array of strings)"""
        
        # Define JSON schema for structured output
        response_schema = {
            "type": "object",
            "properties": {
                "enriched_findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "finding_id": {"type": "string"},
                            "impact_summary": {"type": "string"},
                            "remediation_summary": {"type": "string"},
                            "remediation_steps": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["finding_id", "impact_summary", "remediation_summary", "remediation_steps"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["enriched_findings"],
            "additionalProperties": False
        }
        
        # Call OpenAI with structured outputs
        logger.info(f"Calling OpenAI to enrich {len(finding_contexts)} findings")
        
        # Note: OpenAI structured outputs requires response_format with JSON schema
        # For now, use json_object and parse manually (structured outputs API may vary by model)
        response = client.chat.completions.create(
            model=settings.ENRICH_FINDINGS_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,  # Lower temperature for more consistent, factual output
            timeout=settings.ENRICH_FINDINGS_TIMEOUT_SEC,
        )
        
        # Parse response
        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI returned empty response")
        
        result_data = json.loads(content)
        enriched_findings = result_data.get("enriched_findings", [])
        
        # Convert to EnrichedFindingItem
        enriched_items = []
        for item in enriched_findings:
            enriched_items.append(
                EnrichedFindingItem(
                    finding_id=item["finding_id"],
                    impact_summary=item.get("impact_summary"),
                    remediation_summary=item.get("remediation_summary"),
                    remediation_steps=item.get("remediation_steps", []),
                    ai_source="brain_v1",
                    ai_model=settings.ENRICH_FINDINGS_MODEL,
                    confidence=0.85,  # Default confidence for AI-generated content
                )
            )
        
        logger.info(f"Successfully enriched {len(enriched_items)} findings")
        return enriched_items
        
    except ImportError:
        logger.error("openai package not installed")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI response as JSON: {e}")
        raise
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}", exc_info=True)
        raise


def _generate_fallback_enrichments(
    findings: List[BrainFindingInput]
) -> List[EnrichedFindingItem]:
    """
    Generate fallback enrichment when AI is not available.
    
    Uses simple vuln_type-based mappings as emergency fallback.
    """
    fallback_impact_map = {
        "xss": "An attacker can run JavaScript in the user's browser and steal sessions or act as the user.",
        "sqli": "An attacker can read or modify application data in the database.",
        "open_port": "Exposed services can be attacked or misconfigured, potentially allowing unauthorized access.",
        "insecure_http": "Unencrypted HTTP traffic can be intercepted or modified by attackers.",
    }
    
    fallback_remediation_map = {
        "xss": {
            "summary": "Encode user input before rendering it in HTML and avoid inserting raw user input directly into the page.",
            "steps": [
                "Use your framework's output encoding (e.g., htmlspecialchars in PHP, html.escape in Python)",
                "Do not insert untrusted data into HTML, JavaScript, or attributes",
                "Validate and constrain input to expected characters or patterns",
            ]
        },
        "sqli": {
            "summary": "Use parameterized queries instead of building SQL statements with string concatenation.",
            "steps": [
                "Use prepared statements / ORM parameter binding for all database queries",
                "Never concatenate raw user input directly into SQL strings",
                "Apply server-side validation to limit input values to expected formats",
            ]
        },
        "open_port": {
            "summary": "Close or restrict unnecessary exposed services so they cannot be abused.",
            "steps": [
                "Close unused ports or services on the server",
                "Restrict access to required services using firewall rules or security groups",
                "Keep exposed services patched and monitored",
            ]
        },
        "insecure_http": {
            "summary": "Migrate traffic to HTTPS to protect data from interception and tampering.",
            "steps": [
                "Obtain and install a valid TLS certificate",
                "Redirect all HTTP requests to HTTPS",
                "Consider enabling HSTS once HTTPS is stable",
            ]
        },
    }
    
    enriched_items = []
    for finding in findings:
        vuln_type = (finding.vuln_type or "").lower()
        
        impact_summary = fallback_impact_map.get(vuln_type)
        remediation = fallback_remediation_map.get(vuln_type)
        
        if not impact_summary:
            impact_summary = "This issue could pose a security risk to your application."
        
        if not remediation:
            remediation = {
                "summary": "Review the technical details and consult your security team for remediation guidance.",
                "steps": ["Review the finding details", "Consult security documentation", "Apply appropriate security controls"]
            }
        
        enriched_items.append(
            EnrichedFindingItem(
                finding_id=finding.id,
                impact_summary=impact_summary,
                remediation_summary=remediation["summary"],
                remediation_steps=remediation["steps"],
                ai_source="fallback",
                ai_model=None,
                confidence=0.5,  # Lower confidence for fallback
            )
        )
    
    return enriched_items

