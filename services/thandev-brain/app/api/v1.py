"""
API v1 endpoints for Thandev Brain Service
"""
import logging
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, Optional

from app.models import (
    PlanScanRequest,
    PlanScanResponse,
    BuildReportPromptRequest,
    BuildReportPromptResponse,
    CatalogResponse,
    StartSessionRequest,
    StartSessionResponse,
    GetSessionResponse,
    StopSessionResponse,
    SessionStatus,
    StopReasonCode,
    EnrichFindingsRequest,
    EnrichFindingsResponse,
)
from app.catalog import load_catalog
from app.api.rag import router as rag_router

logger = logging.getLogger(__name__)

router = APIRouter(tags=["brain"])


@router.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "thandev-brain"}


@router.get("/healthz")
async def healthz():
    """Health check endpoint for Fly.io (Kubernetes-style naming)"""
    return {"status": "ok", "service": "thandev-brain"}


@router.get("/catalog", response_model=CatalogResponse)
async def get_catalog():
    """
    Get the tool catalog with all available tools and modes.
    
    Returns:
        CatalogResponse with tools, modes, and metadata
    """
    try:
        catalog = load_catalog()
        return CatalogResponse(**catalog)
    except Exception as e:
        logger.error(f"Failed to load catalog: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load catalog: {str(e)}"
        )


@router.post("/plan-scan", response_model=PlanScanResponse)
async def plan_scan(request: PlanScanRequest) -> PlanScanResponse:
    """
    Generate a scan plan based on target information and scan level.
    
    The brain uses RAG + rules to determine which tools and modes to run,
    in what order, with dependencies and timeline estimates.
    
    Returns:
        PlanScanResponse with steps, timeline, and reasoning
    """
    try:
        from app.planner.plan import generate_plan
        
        plan = await generate_plan(
            target_url=request.target_url,
            scan_level=request.scan_level,
            org_id=request.org_id,
            project_id=request.project_id,
            stack_info=request.stack_info or {},
        )
        
        return plan
    except ValueError as e:
        logger.warning(f"Invalid plan request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to generate plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate plan: {str(e)}"
        )


@router.post("/build-report-prompt", response_model=BuildReportPromptResponse)
async def build_report_prompt(request: BuildReportPromptRequest) -> BuildReportPromptResponse:
    """
    Build a prompt package for OpenAI report generation.
    
    The brain does NOT generate the report JSON itself. Instead, it:
    1. Loads normalized findings from core-provided IDs
    2. Retrieves supporting evidence from RAG
    3. Returns a prompt package with system/user messages and schema
    
    Returns:
        BuildReportPromptResponse with OpenAI request payload
    """
    try:
        from app.report_prompt.builder import build_prompt_package
        
        prompt_package = await build_prompt_package(
            scan_job_id=request.scan_job_id,
            finding_ids=request.finding_ids,
            artifact_refs=request.artifact_refs or [],
            org_id=request.org_id,
            project_id=request.project_id,
        )
        
        return prompt_package
    except ValueError as e:
        logger.warning(f"Invalid report prompt request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to build report prompt: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build report prompt: {str(e)}"
        )


# Include RAG router
router.include_router(rag_router, prefix="/rag")


# Session endpoints (PR-4A)
@router.post("/sessions/start", response_model=StartSessionResponse)
async def start_session(request: StartSessionRequest) -> StartSessionResponse:
    """
    Start a new scan session.
    
    The brain will own the closed-loop scanning process:
    1. Create session state in Redis
    2. Start controller worker (if not already running)
    3. Controller will decide steps, enqueue them, wait for results, and adapt
    
    Returns:
        StartSessionResponse with session_id
    """
    try:
        from app.session.state import create_session
        from app.controller.session_controller import trigger_session_loop
        
        # Create session state
        session_state = await create_session(
            scan_job_id=request.scan_job_id,
            target_url=request.target_url,
            scan_level=request.scan_level,
            org_id=request.org_id,
            project_id=request.project_id,
            stack_info=request.stack_info,
            policy=request.policy,
        )
        
        # Trigger controller loop (non-blocking - don't await, just schedule)
        # Use asyncio.create_task to ensure it runs in background
        import asyncio as _asyncio
        _asyncio.create_task(trigger_session_loop(
            session_state.session_id,
            org_id=request.org_id,
            project_id=request.project_id,
        ))
        
        return StartSessionResponse(
            session_id=session_state.session_id,
            status=session_state.status,
            message=f"Session {session_state.session_id} started successfully",
        )
    except ValueError as e:
        logger.warning(f"Invalid session request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to start session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start session: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=GetSessionResponse)
async def get_session(
    session_id: str,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> GetSessionResponse:
    """
    Get session status.
    
    Args:
        session_id: Session ID
        org_id: Organization ID (optional, for filtering)
        project_id: Project ID (optional, for filtering)
        
    Returns:
        GetSessionResponse with current session state
    """
    try:
        from app.session.state import get_session
        
        session_state = await get_session(org_id, project_id, session_id)
        
        if not session_state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        # Extract error message if session failed
        error_message = None
        if session_state.status == SessionStatus.FAILED:
            # Try to get error_message from session state
            session_dict = session_state.model_dump() if hasattr(session_state, 'model_dump') else {}
            error_message = session_dict.get("error_message") or getattr(session_state, "error_message", None)
        
        return GetSessionResponse(
            session_id=session_state.session_id,
            status=session_state.status,
            stop_reason_code=session_state.stop_reason_code,
            current_step_count=session_state.current_step_count,
            total_runtime_sec=session_state.total_runtime_sec,
            created_at=session_state.created_at,
            last_updated=session_state.last_updated,
            error_message=error_message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session: {str(e)}"
        )


@router.post("/sessions/{session_id}/stop", response_model=StopSessionResponse)
async def stop_session(
    session_id: str,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> StopSessionResponse:
    """
    Stop a running session gracefully.
    
    Args:
        session_id: Session ID
        org_id: Organization ID (optional)
        project_id: Project ID (optional)
        
    Returns:
        StopSessionResponse with final status
    """
    try:
        from app.session.state import get_session, stop_session
        
        session_state = await get_session(org_id, project_id, session_id)
        
        if not session_state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        if session_state.status != SessionStatus.RUNNING:
            return StopSessionResponse(
                session_id=session_id,
                status=session_state.status,
                message=f"Session is already {session_state.status.value}",
            )
        
        # Stop the session
        await stop_session(
            org_id,
            project_id,
            session_id,
            SessionStatus.STOPPED,
            StopReasonCode.USER_STOPPED,
        )
        
        return StopSessionResponse(
            session_id=session_id,
            status=SessionStatus.STOPPED,
            message=f"Session {session_id} stopped successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop session: {str(e)}"
        )


@router.post("/enrich-findings", response_model=EnrichFindingsResponse)
async def enrich_findings(request: EnrichFindingsRequest) -> EnrichFindingsResponse:
    """
    Enrich findings with AI-generated impact summaries and remediation guidance.
    
    The brain uses RAG + OpenAI to:
    1. Query relevant evidence from RAG store (similar findings, CVE templates, tech fingerprint)
    2. Generate structured impact summaries and remediation steps using OpenAI
    3. Return enriched findings with AI-generated content
    
    This endpoint does NOT modify the core backend database. The core backend
    should call this endpoint and then store the returned enrichment data.
    
    Returns:
        EnrichFindingsResponse with enriched findings
    """
    try:
        from app.finding_enrichment.enricher import enrich_findings_batch
        
        logger.info(f"Enriching {len(request.findings)} findings")
        
        enriched_items = await enrich_findings_batch(
            findings=request.findings,
            org_id=request.org_id,
            project_id=request.project_id,
            target_url=request.target_url,
        )
        
        return EnrichFindingsResponse(
            items=enriched_items,
            metadata={
                "count": len(enriched_items),
                "org_id": request.org_id,
                "project_id": request.project_id,
                "target_url": request.target_url,
            }
        )
    except ValueError as e:
        logger.warning(f"Invalid enrichment request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to enrich findings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enrich findings: {str(e)}"
        )


@router.post("/scans/{scan_id}/explain")
async def explain_scan_artifacts(
    scan_id: str,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate AI explanation of dependency scanning artifacts.
    
    Fetches scan artifacts from backend and generates structured explanation
    strictly based on artifacts (no hallucinations).
    
    Returns:
        Explanation with summary, key points, prioritized actions, and limitations
    """
    try:
        import httpx
        import os
        
        # Get backend URL
        backend_url = os.getenv("CORE_BACKEND_URL", "http://localhost:8000")
        
        # Fetch artifacts from backend
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{backend_url}/api/scans/{scan_id}/artifacts",
                headers={"X-Thandev-Org-Id": org_id} if org_id else {},
            )
            response.raise_for_status()
            artifacts_data = response.json()
        
        artifacts = artifacts_data.get("items", [])
        
        if not artifacts:
            return {
                "summary": "No dependency scanning artifacts found for this scan.",
                "key_points": [],
                "prioritized_actions": [],
                "limitations": ["No artifacts available to analyze."],
            }
        
        # Generate explanation from artifacts
        explanation = await _generate_explanation_from_artifacts(artifacts)
        
        return explanation
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scan not found: {scan_id}"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch artifacts: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to explain artifacts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to explain artifacts: {str(e)}"
        )


async def _generate_explanation_from_artifacts(artifacts: list) -> Dict[str, Any]:
    """
    Generate explanation from scan artifacts using OpenAI.
    
    Strictly grounded in artifacts - no hallucinations.
    """
    from app.core.config import settings
    
    # Extract data from artifacts
    url_sca = None
    repo_sca = None
    
    for artifact in artifacts:
        if artifact.get("type") == "url_sca":
            url_sca = artifact.get("payload", {})
        elif artifact.get("type") == "repo_sca":
            repo_sca = artifact.get("payload", {})
    
    # Build context from artifacts
    context_parts = []
    
    if url_sca:
        fingerprint = url_sca.get("fingerprint", {})
        techs = fingerprint.get("technologies", [])
        deps = url_sca.get("client_dependencies", [])
        findings = url_sca.get("findings", [])
        
        context_parts.append("URL-Based Dependency Scan Results:")
        if techs:
            context_parts.append(f"- Technologies detected: {', '.join([t.get('name', '') for t in techs[:5]])}")
        if deps:
            context_parts.append(f"- Client-side dependencies: {len(deps)}")
        if findings:
            context_parts.append(f"- Vulnerabilities found: {len(findings)}")
    
    if repo_sca:
        packages = repo_sca.get("packages", [])
        findings = repo_sca.get("findings", [])
        
        context_parts.append("Repository-Based Dependency Scan Results:")
        context_parts.append(f"- Packages analyzed: {len(packages)}")
        if findings:
            context_parts.append(f"- Vulnerabilities found: {len(findings)}")
    
    context = "\n".join(context_parts)
    
    # Generate explanation using OpenAI
    if settings.OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
            prompt = f"""Analyze the following dependency scanning results and provide a structured explanation.

{context}

Provide:
1. A brief summary of what was detected
2. Key points about the findings
3. Prioritized actions (most critical first)
4. Limitations and confidence notes

Be specific and only reference what is actually in the scan results. Do not invent vulnerabilities or findings."""

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a security analyst explaining dependency scan results. Only reference findings that are explicitly in the scan data."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            
            explanation_text = response.choices[0].message.content
            
            # Parse explanation into structured format
            return _parse_explanation(explanation_text, url_sca, repo_sca)
            
        except Exception as e:
            logger.warning(f"OpenAI explanation failed: {e}, using fallback")
    
    # Fallback: generate basic explanation from artifacts
    return _generate_fallback_explanation(url_sca, repo_sca)


def _parse_explanation(text: str, url_sca: Optional[Dict], repo_sca: Optional[Dict]) -> Dict[str, Any]:
    """Parse OpenAI response into structured format."""
    # Simple parsing - in production, use more sophisticated parsing
    lines = text.split("\n")
    
    summary = ""
    key_points = []
    actions = []
    limitations = []
    
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if "summary" in line.lower() or "overview" in line.lower():
            current_section = "summary"
        elif "key point" in line.lower() or "finding" in line.lower():
            current_section = "key_points"
        elif "action" in line.lower() or "recommend" in line.lower():
            current_section = "actions"
        elif "limit" in line.lower() or "note" in line.lower():
            current_section = "limitations"
        
        if line.startswith("-") or line.startswith("*"):
            content = line[1:].strip()
            if current_section == "key_points":
                key_points.append(content)
            elif current_section == "actions":
                actions.append({"title": content, "reason": "", "references": []})
            elif current_section == "limitations":
                limitations.append(content)
        elif current_section == "summary" and not summary:
            summary = line
    
    if not summary:
        summary = "Dependency scan completed. Review findings below."
    
    return {
        "summary": summary,
        "key_points": key_points[:10],
        "prioritized_actions": actions[:10],
        "limitations": limitations + ["Analysis based on scan artifacts only. Manual verification recommended."],
    }


def _generate_fallback_explanation(url_sca: Optional[Dict], repo_sca: Optional[Dict]) -> Dict[str, Any]:
    """Generate basic explanation without OpenAI."""
    summary_parts = []
    key_points = []
    actions = []
    
    if url_sca:
        findings = url_sca.get("findings", [])
        if findings:
            summary_parts.append(f"Found {len(findings)} client-side dependency vulnerabilities")
            key_points.append(f"{len(findings)} vulnerabilities detected in client-side JavaScript")
            
            # Group by severity
            by_severity = {}
            for f in findings:
                sev = f.get("severity", "unknown")
                by_severity[sev] = by_severity.get(sev, 0) + 1
            
            for sev, count in sorted(by_severity.items(), key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x[0], 4)):
                actions.append({
                    "title": f"Review {count} {sev} severity vulnerabilities",
                    "reason": f"Found {count} {sev} severity issues in client-side dependencies",
                    "references": [],
                })
    
    if repo_sca:
        findings = repo_sca.get("findings", [])
        packages = repo_sca.get("packages", [])
        if findings:
            summary_parts.append(f"Found {len(findings)} repository dependency vulnerabilities across {len(packages)} packages")
            key_points.append(f"{len(findings)} vulnerabilities in {len(packages)} packages")
            
            # Group by ecosystem
            by_ecosystem = {}
            for f in findings:
                eco = f.get("ecosystem", "unknown")
                by_ecosystem[eco] = by_ecosystem.get(eco, 0) + 1
            
            for eco, count in sorted(by_ecosystem.items()):
                actions.append({
                    "title": f"Update {eco} dependencies ({count} vulnerabilities)",
                    "reason": f"Found {count} vulnerabilities in {eco} packages",
                    "references": [],
                })
    
    if not summary_parts:
        summary = "Dependency scan completed with no vulnerabilities detected."
    else:
        summary = ". ".join(summary_parts) + "."
    
    return {
        "summary": summary,
        "key_points": key_points[:10],
        "prioritized_actions": actions[:10],
        "limitations": [
            "Analysis based on scan artifacts only.",
            "Manual verification of findings recommended.",
            "Some vulnerabilities may have been fixed in newer versions.",
        ],
    }

