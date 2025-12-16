#!/usr/bin/env python3
"""
Script to index existing findings into RAG store via API (no database access needed)
"""
import asyncio
import sys
import os
from pathlib import Path
import logging
from typing import Optional, List, Dict, Any

# Add app directory to path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

from app.rag.store import get_rag_store
from app.rag.ingestion import ingest_findings_batch
from app.core.config import settings
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch_findings_from_api(
    core_backend_url: str,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Fetch findings from core backend API.
    
    Args:
        core_backend_url: Core backend URL
        org_id: Filter by organization ID
        project_id: Filter by project ID
        limit: Maximum number of findings to fetch
        
    Returns:
        List of finding dicts
    """
    # Note: This requires an API endpoint that returns findings
    # For now, this is a placeholder - the actual endpoint may need to be created
    url = f"{core_backend_url}/api/v1/findings"
    
    params = {"limit": limit}
    if org_id:
        params["org_id"] = org_id
    if project_id:
        params["project_id"] = project_id
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Note: This endpoint may require authentication headers
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        findings = data.get("findings", [])
        logger.info(f"Fetched {len(findings)} findings from API")
        return findings


async def index_findings_via_api(
    core_backend_url: str = "http://localhost:8000",
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = 1000,
):
    """
    Index findings from core backend API into RAG store.
    
    Args:
        core_backend_url: Core backend URL
        org_id: Filter by organization ID
        project_id: Filter by project ID
        limit: Maximum number of findings to index
    """
    try:
        rag_store = get_rag_store()
        
        # Fetch findings from API
        logger.info(f"Fetching findings from {core_backend_url} (limit: {limit})...")
        findings = await fetch_findings_from_api(
            core_backend_url=core_backend_url,
            org_id=org_id,
            project_id=project_id,
            limit=limit,
        )
        
        if not findings:
            logger.info("No findings found to index")
            return
        
        # Index in batches
        batch_size = 100
        total_indexed = 0
        
        for i in range(0, len(findings), batch_size):
            batch = findings[i:i + batch_size]
            await ingest_findings_batch(rag_store, batch)
            total_indexed += len(batch)
            logger.info(f"Indexed {total_indexed}/{len(findings)} findings...")
        
        logger.info(f"Successfully indexed {total_indexed} findings into RAG store")
        
    except httpx.HTTPError as e:
        logger.error(f"API request failed: {e}")
        logger.error("Make sure core backend is running and accessible")
        raise
    except Exception as e:
        logger.error(f"Failed to index findings: {e}", exc_info=True)
        raise


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Index findings into RAG store via API")
    parser.add_argument("--core-backend-url", default="http://localhost:8000", help="Core backend URL")
    parser.add_argument("--org-id", help="Filter by organization ID")
    parser.add_argument("--project-id", help="Filter by project ID")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum findings to index")
    
    args = parser.parse_args()
    
    await index_findings_via_api(
        core_backend_url=args.core_backend_url,
        org_id=args.org_id,
        project_id=args.project_id,
        limit=args.limit,
    )


if __name__ == "__main__":
    asyncio.run(main())




