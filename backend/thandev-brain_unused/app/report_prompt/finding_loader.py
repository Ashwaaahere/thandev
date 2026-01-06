"""
Finding loader for report prompt generation
Loads normalized findings from core backend database
"""
import logging
from typing import List, Dict, Any, Optional
import os

logger = logging.getLogger(__name__)


async def load_findings_from_ids(
    finding_ids: List[str],
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Load normalized findings from core backend.
    
    This function can work in two modes:
    1. Direct database access (if DATABASE_URL is shared)
    2. HTTP API call to core backend (if separate services)
    
    Args:
        finding_ids: List of finding IDs to load
        org_id: Organization ID for validation
        project_id: Project ID for validation
        
    Returns:
        List of finding dicts with normalized fields
    """
    if not finding_ids:
        return []
    
    # Try direct database access first (if DATABASE_URL is available)
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgresql"):
        try:
            return await _load_from_database(finding_ids, org_id, project_id)
        except Exception as e:
            logger.warning(f"Database load failed: {e}, trying API fallback")
    
    # Fallback to HTTP API call
    try:
        return await _load_from_api(finding_ids, org_id, project_id)
    except Exception as e:
        logger.error(f"API load failed: {e}", exc_info=True)
        # Return stub findings as last resort
        return _create_stub_findings(finding_ids)


async def _load_from_database(
    finding_ids: List[str],
    org_id: Optional[str],
    project_id: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Load findings directly from shared database.
    
    This assumes brain service has access to the same database.
    """
    try:
        from sqlalchemy import create_engine, text
        from app.core.config import settings
        
        engine = create_engine(settings.DATABASE_URL)
        
        # Build query with filters
        query = """
            SELECT 
                f.id, f.title, f.description, f.severity, f.cve_id, f.cvss_score,
                f.url, f.path, f.recommendation, f.tool_name, f.raw_data,
                f.created_at, f.scan_job_id
            FROM findings f
            WHERE f.id = ANY(:finding_ids)
        """
        
        params = {"finding_ids": finding_ids}
        
        # Add project filter if provided
        if project_id:
            query += " AND f.scan_job_id IN (SELECT id FROM scan_jobs WHERE project_id = :project_id)"
            params["project_id"] = project_id
        
        with engine.connect() as conn:
            result = conn.execute(text(query), params)
            rows = result.fetchall()
            
            findings = []
            for row in rows:
                finding = {
                    "id": row[0],
                    "title": row[1] or "",
                    "description": row[2],
                    "severity": row[3] if row[3] else "info",
                    "cve_id": row[4],
                    "cvss_score": float(row[5]) if row[5] is not None else None,
                    "url": row[6],
                    "path": row[7],
                    "recommendation": row[8],
                    "tool_name": row[9] or "unknown",
                    "raw_data": row[10],
                    "created_at": row[11].isoformat() if row[11] else None,
                    "scan_job_id": row[12],
                }
                findings.append(finding)
            
            logger.info(f"Loaded {len(findings)} findings from database")
            return findings
            
    except ImportError:
        raise ValueError("sqlalchemy not available for database access")
    except Exception as e:
        logger.error(f"Database query failed: {e}", exc_info=True)
        raise


async def _load_from_api(
    finding_ids: List[str],
    org_id: Optional[str],
    project_id: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Load findings via HTTP API call to core backend.
    
    This is the preferred method when services are separate.
    """
    try:
        import httpx
        
        # Get core backend URL from environment
        core_backend_url = os.getenv("CORE_BACKEND_URL", "http://localhost:8000")
        
        # Call core backend API
        url = f"{core_backend_url}/api/v1/findings/batch"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json={
                    "finding_ids": finding_ids,
                    "org_id": org_id,
                    "project_id": project_id,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            findings = data.get("findings", [])
            logger.info(f"Loaded {len(findings)} findings from core backend API")
            return findings
            
    except ImportError:
        raise ValueError("httpx not available for API calls")
    except Exception as e:
        logger.error(f"API call failed: {e}", exc_info=True)
        raise


def _create_stub_findings(finding_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Create stub findings as last resort.
    
    This should only be used when both database and API access fail.
    """
    logger.warning(f"Using stub findings for {len(finding_ids)} IDs")
    return [
        {
            "id": fid,
            "title": f"Finding {fid}",
            "description": None,
            "severity": "info",
            "cve_id": None,
            "cvss_score": None,
            "url": None,
            "tool_name": "unknown",
        }
        for fid in finding_ids
    ]

