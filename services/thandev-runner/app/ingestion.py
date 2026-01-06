"""
Findings ingestion for runner service
DEPRECATED: This module is deprecated. Use app.backend_client.post_tool_result() instead.

This module previously supported direct DB writes, but runner now uses the backend API
to avoid backend Python import dependencies.
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def ingest_findings_direct_db(
    db: Session,
    scan_job_id: str,
    tool_name: str,
    findings: List[Dict[str, Any]],
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> int:
    """
    DEPRECATED: Ingest findings directly into database.
    
    This function is deprecated. Use app.backend_client.post_tool_result() instead.
    Runner now uses the backend API to avoid backend Python import dependencies.
    
    Args:
        db: Database session (unused, kept for compatibility)
        scan_job_id: Scan job ID
        tool_name: Tool name (e.g., "nuclei", "ffuf")
        findings: List of finding dicts
        org_id: Organization ID (unused, kept for compatibility)
        project_id: Project ID (unused, kept for compatibility)
        
    Returns:
        Number of findings (always 0, as this function is deprecated)
    """
    logger.warning(
        f"ingest_findings_direct_db is deprecated. Use app.backend_client.post_tool_result() instead. "
        f"Called for scan_job={scan_job_id}, tool={tool_name}"
    )
    return 0


async def ingest_findings_api(
    api_base_url: str,
    scan_job_id: str,
    tool_name: str,
    findings: List[Dict[str, Any]],
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> int:
    """
    Ingest findings via API call to core service.
    
    This is an alternative to direct DB writes, useful when:
    - Runner doesn't have direct DB access
    - Need to go through core's validation/processing
    
    Args:
        api_base_url: Base URL of core API
        scan_job_id: Scan job ID
        tool_name: Tool name
        findings: List of finding dicts
        org_id: Organization ID
        project_id: Project ID
        
    Returns:
        Number of findings ingested
    """
    import httpx
    
    endpoint = f"{api_base_url}/api/v1/findings/batch"
    
    payload = {
        "scan_job_id": scan_job_id,
        "tool_name": tool_name,
        "findings": findings,
    }
    if org_id:
        payload["org_id"] = org_id
    if project_id:
        payload["project_id"] = project_id
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            
            data = response.json()
            ingested_count = data.get("ingested_count", 0)
            
            logger.info(
                f"Ingested {ingested_count} findings via API for tool {tool_name} "
                f"in scan_job {scan_job_id}"
            )
            
            return ingested_count
            
    except Exception as e:
        logger.error(f"Failed to ingest findings via API: {e}", exc_info=True)
        raise



