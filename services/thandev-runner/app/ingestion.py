"""
Findings ingestion for runner service
Supports direct DB writes (recommended) or API calls
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.backend_imports import ensure_backend_in_path

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
    Ingest findings directly into database.
    
    This is the recommended approach for performance and reliability.
    
    Args:
        db: Database session
        scan_job_id: Scan job ID
        tool_name: Tool name (e.g., "nuclei", "ffuf")
        findings: List of finding dicts
        org_id: Organization ID (for tenant context)
        project_id: Project ID (for tenant context)
        
    Returns:
        Number of findings ingested
    """
    # Ensure backend is in path and cached modules are cleared
    ensure_backend_in_path()
    
    try:
        from app.services.findings_ingestor import (
            parse_nuclei_output,
            parse_nmap_output,
            parse_httpx_output,
            parse_ffuf_output,
            parse_dalfox_output,
            parse_sqlmap_output,
            ingest_nuclei_findings,
            ingest_nmap_findings,
            ingest_httpx_findings,
            ingest_ffuf_findings,
            ingest_dalfox_findings,
            ingest_sqlmap_findings,
        )
        
        # Map tool_name to parser and ingestor
        tool_parsers = {
            "nuclei": (parse_nuclei_output, ingest_nuclei_findings),
            "nmap": (parse_nmap_output, ingest_nmap_findings),
            "httpx": (parse_httpx_output, ingest_httpx_findings),
            "ffuf": (parse_ffuf_output, ingest_ffuf_findings),
            "dalfox": (parse_dalfox_output, ingest_dalfox_findings),
            "sqlmap": (parse_sqlmap_output, ingest_sqlmap_findings),
        }
        
        if tool_name not in tool_parsers:
            logger.warning(f"Unknown tool_name {tool_name}, skipping ingestion")
            return 0
        
        parser_func, ingestor_func = tool_parsers[tool_name]
        
        # For tools that output to files, we need to write findings to a temp file first
        # For now, assume findings are already parsed dicts
        # TODO: Handle file-based parsing if needed
        
        # Ingest findings
        ingested = ingestor_func(db, scan_job_id, findings)
        
        logger.info(
            f"Ingested {len(ingested)} findings for tool {tool_name} "
            f"in scan_job {scan_job_id}"
        )
        
        return len(ingested)
        
    except ImportError as e:
        logger.error(f"Failed to import findings_ingestor: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Failed to ingest findings: {e}", exc_info=True)
        raise


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



