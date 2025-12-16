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
)
from app.catalog import load_catalog
from app.api.rag import router as rag_router

logger = logging.getLogger(__name__)

router = APIRouter(tags=["brain"])


@router.get("/health")
async def health():
    """Health check endpoint"""
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
        
        return GetSessionResponse(
            session_id=session_state.session_id,
            status=session_state.status,
            stop_reason_code=session_state.stop_reason_code,
            current_step_count=session_state.current_step_count,
            total_runtime_sec=session_state.total_runtime_sec,
            created_at=session_state.created_at,
            last_updated=session_state.last_updated,
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

