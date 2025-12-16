"""
RAG ingestion endpoints
"""
import logging
from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any

from app.rag.store import get_rag_store
from app.rag.ingestion import (
    ingest_findings_batch,
    create_artifact_summary_document,
    create_tech_fingerprint_document,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rag"])


@router.post("/ingest")
async def ingest_documents(
    findings: List[Dict[str, Any]] = None,
    artifact_summaries: List[Dict[str, Any]] = None,
    tech_fingerprints: List[Dict[str, Any]] = None,
    org_id: str = None,
    project_id: str = None,
) -> Dict[str, Any]:
    """
    Ingest documents into RAG store.
    
    This endpoint accepts findings, artifact summaries, and tech fingerprints
    from the core backend and stores them in the RAG store for later retrieval.
    
    Args:
        findings: List of finding dicts (id, title, description, severity, url, tool_id, etc.)
        artifact_summaries: List of artifact summary dicts (artifact_id, tool_id, summary, etc.)
        tech_fingerprints: List of tech fingerprint dicts (target, stack_info, etc.)
        org_id: Organization ID (optional, for filtering)
        project_id: Project ID (optional, for filtering)
        
    Returns:
        Dict with ingestion results
    """
    try:
        rag_store = get_rag_store()
        
        total_ingested = 0
        results = {
            "findings_ingested": 0,
            "artifacts_ingested": 0,
            "tech_fingerprints_ingested": 0,
        }
        
        # Ingest findings
        if findings:
            # Add org_id and project_id to findings if provided
            for finding in findings:
                if org_id and "org_id" not in finding:
                    finding["org_id"] = org_id
                if project_id and "project_id" not in finding:
                    finding["project_id"] = project_id
            
            await ingest_findings_batch(rag_store, findings)
            results["findings_ingested"] = len(findings)
            total_ingested += len(findings)
            logger.info(f"Ingested {len(findings)} findings into RAG")
        
        # Ingest artifact summaries
        if artifact_summaries:
            docs = []
            for artifact in artifact_summaries:
                doc = create_artifact_summary_document(
                    artifact_id=artifact.get("artifact_id", ""),
                    tool_id=artifact.get("tool_id", ""),
                    scan_job_id=artifact.get("scan_job_id", ""),
                    summary=artifact.get("summary", ""),
                    org_id=artifact.get("org_id") or org_id,
                    project_id=artifact.get("project_id") or project_id,
                    target=artifact.get("target"),
                    finding_count=artifact.get("finding_count"),
                )
                docs.append(doc)
            
            if docs:
                await rag_store.upsert_documents(docs)
                results["artifacts_ingested"] = len(docs)
                total_ingested += len(docs)
                logger.info(f"Ingested {len(docs)} artifact summaries into RAG")
        
        # Ingest tech fingerprints
        if tech_fingerprints:
            docs = []
            for fingerprint in tech_fingerprints:
                # Extract tech_stack from stack_info
                stack_info = fingerprint.get("stack_info", {})
                tech_stack = stack_info if isinstance(stack_info, dict) else {}
                
                doc = create_tech_fingerprint_document(
                    target=fingerprint.get("target", ""),
                    tech_stack=tech_stack,
                    org_id=fingerprint.get("org_id") or org_id,
                    project_id=fingerprint.get("project_id") or project_id,
                )
                docs.append(doc)
            
            if docs:
                await rag_store.upsert_documents(docs)
                results["tech_fingerprints_ingested"] = len(docs)
                total_ingested += len(docs)
                logger.info(f"Ingested {len(docs)} tech fingerprints into RAG")
        
        if total_ingested == 0:
            logger.warning("No documents provided for ingestion")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No documents provided for ingestion"
            )
        
        results["total_ingested"] = total_ingested
        logger.info(f"Total documents ingested: {total_ingested}")
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to ingest documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest documents: {str(e)}"
        )


