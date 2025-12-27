"""
Finding enrichment service
Calls thandev-brain to enrich findings with AI-generated impact summaries and remediation guidance
"""
import logging
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC
from sqlalchemy.orm import Session

from app.models.finding import Finding
from app.services.brain_client import get_brain_client
from app.core.config import settings

logger = logging.getLogger(__name__)


async def enrich_findings_async(
    findings: List[Finding],
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    target_url: Optional[str] = None,
) -> None:
    """
    Asynchronously enrich findings with AI-generated content.
    
    This function:
    1. Builds payload for brain service
    2. Calls brain.enrich_findings()
    3. Updates Finding objects with AI data
    
    Args:
        findings: List of Finding ORM objects to enrich
        org_id: Organization ID (optional)
        project_id: Project ID (optional)
        target_url: Target URL (optional)
    """
    if not findings:
        return
    
    if not settings.BRAIN_SERVICE_ENABLED:
        logger.debug("Brain service is disabled, skipping enrichment")
        return
    
    try:
        # Build payload for brain service
        brain_payload = []
        for finding in findings:
            # Parse raw_data if available
            raw_data_dict = None
            if finding.raw_data:
                try:
                    raw_data_dict = json.loads(finding.raw_data) if isinstance(finding.raw_data, str) else finding.raw_data
                except (json.JSONDecodeError, TypeError):
                    pass
            
            brain_payload.append({
                "id": finding.id,
                "title": finding.title or "",
                "description": finding.description,
                "severity": finding.severity.value if finding.severity else None,
                "tool_name": finding.tool_name or finding.tool,
                "vuln_type": finding.vuln_type,
                "url": finding.url,
                "parameter": finding.parameter,
                "target_url": target_url,
                "project_id": project_id,
                "org_id": org_id,
                "raw_data": raw_data_dict,
            })
        
        # Call brain service
        brain_client = get_brain_client()
        enriched_dict = await brain_client.enrich_findings(
            findings=brain_payload,
            org_id=org_id,
            project_id=project_id,
            target_url=target_url,
        )
        
        if not enriched_dict:
            logger.debug(f"No enrichment data returned from brain for {len(findings)} findings")
            return
        
        # Update findings with AI data
        # Note: This requires a new DB session since we're async
        # We'll need to update findings in a sync context
        logger.info(f"Received enrichment for {len(enriched_dict)} findings")
        
        # Return enriched data for caller to apply
        return enriched_dict
        
    except Exception as e:
        logger.warning(f"Failed to enrich findings: {e}", exc_info=True)
        return None


def enrich_findings_sync(
    db: Session,
    findings: List[Finding],
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    target_url: Optional[str] = None,
) -> None:
    """
    Synchronously enrich findings with AI-generated content.
    
    This is a wrapper that runs the async enrichment in a new event loop.
    Use this when called from synchronous code (like ingestion functions).
    
    Args:
        db: Database session
        findings: List of Finding ORM objects to enrich
        org_id: Organization ID (optional)
        project_id: Project ID (optional)
        target_url: Target URL (optional)
    """
    if not findings:
        return
    
    if not settings.BRAIN_SERVICE_ENABLED:
        logger.debug("Brain service is disabled, skipping enrichment")
        return
    
    try:
        # Run async enrichment in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            enriched_dict = loop.run_until_complete(
                enrich_findings_async(findings, org_id, project_id, target_url)
            )
        finally:
            loop.close()
        
        if not enriched_dict:
            return
        
        # Update findings with AI data
        updated_count = 0
        for finding in findings:
            enriched_data = enriched_dict.get(finding.id)
            if not enriched_data:
                continue
            
            # Update finding with AI data
            if enriched_data.get("impact_summary"):
                finding.impact_summary = enriched_data["impact_summary"]
            
            if enriched_data.get("remediation_summary"):
                finding.remediation_summary = enriched_data["remediation_summary"]
            
            if enriched_data.get("remediation_steps"):
                # Join steps with newlines
                steps = enriched_data["remediation_steps"]
                if isinstance(steps, list):
                    finding.remediation_steps = "\n".join(steps)
                elif isinstance(steps, str):
                    finding.remediation_steps = steps
            
            # Store AI metadata
            finding.ai_source = enriched_data.get("ai_source") or "brain_v1"
            finding.ai_model = enriched_data.get("ai_model")
            finding.ai_confidence = enriched_data.get("confidence")
            finding.ai_last_updated_at = datetime.now(UTC)
            
            updated_count += 1
        
        if updated_count > 0:
            db.commit()
            logger.info(f"Updated {updated_count} findings with AI enrichment")
        
    except Exception as e:
        logger.warning(f"Failed to enrich findings synchronously: {e}", exc_info=True)
        # Don't raise - enrichment failure shouldn't break ingestion
        db.rollback()


def enrich_findings_batch_background(
    finding_ids: List[str],
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    target_url: Optional[str] = None,
) -> None:
    """
    Background task to enrich findings by ID.
    
    This can be called from Celery or other background task systems.
    It loads findings from DB, enriches them, and saves results.
    
    Args:
        finding_ids: List of finding IDs to enrich
        org_id: Organization ID (optional)
        project_id: Project ID (optional)
        target_url: Target URL (optional)
    """
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        findings = db.query(Finding).filter(Finding.id.in_(finding_ids)).all()
        if findings:
            enrich_findings_sync(db, findings, org_id, project_id, target_url)
    finally:
        db.close()

