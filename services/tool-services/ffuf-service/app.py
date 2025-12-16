"""
FFuF tool microservice
Executes FFuF directory brute forcing in isolation
"""
import logging
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import tool execution logic
import sys
from pathlib import Path as PathLib
backend_path = PathLib(__file__).resolve().parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.tools import ToolExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FFuF Tool Service")


class RunRequest(BaseModel):
    """Request to run a tool step"""
    session_id: str
    step_id: str
    tool_id: str
    mode_id: str
    target: str
    params: Dict[str, Any]
    org_id: Optional[str] = None
    project_id: Optional[str] = None
    scan_job_id: Optional[str] = None
    scope: Optional[Dict[str, Any]] = None


class RunResponse(BaseModel):
    """Response from tool execution"""
    success: bool
    tool_name: str
    output: str
    exit_code: int
    execution_time: float
    artifact_refs: list
    findings: Optional[list] = None
    error: Optional[str] = None
    baseline: Optional[Dict[str, Any]] = None


@app.post("/run", response_model=RunResponse)
async def run_tool(request: RunRequest):
    """
    Execute a FFuF directory brute forcing step.
    """
    logger.info(
        f"Executing FFuF step: step_id={request.step_id}, "
        f"mode_id={request.mode_id}, target={request.target}"
    )
    
    # Validate tool_id
    if request.tool_id != "ffuf":
        raise HTTPException(status_code=400, detail=f"This service only handles 'ffuf', got '{request.tool_id}'")
    
    # Create job directory
    if request.scan_job_id:
        job_dir = Path(f"data/jobs/{request.scan_job_id}")
    else:
        job_dir = Path(f"data/jobs/{request.session_id}")
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Execute tool
    executor = ToolExecutor()
    
    try:
        result = await executor.run_step(
            tool_id=request.tool_id,
            mode_id=request.mode_id,
            target_url=request.target,
            params=request.params,
            scan_job_id=request.scan_job_id,
            job_dir=job_dir,
        )
        
        # Get artifact refs
        artifact_refs = []
        if result.get("success"):
            tool_name = result.get("tool_name", "ffuf")
            output_file = job_dir / f"{tool_name}_output.json"
            if output_file.exists():
                # In production, upload to S3/GCS and return URL
                # For now, return local path
                artifact_refs.append(str(output_file))
        
        return RunResponse(
            success=result.get("success", False),
            tool_name=result.get("tool_name", "ffuf"),
            output=result.get("output", ""),
            exit_code=result.get("exit_code", 0),
            execution_time=result.get("execution_time", 0.0),
            artifact_refs=artifact_refs,
            error=result.get("error"),
            baseline=result.get("baseline"),  # FFuF baseline filter data
        )
    
    except Exception as e:
        logger.error(f"FFuF execution failed: {e}", exc_info=True)
        return RunResponse(
            success=False,
            tool_name="ffuf",
            output="",
            exit_code=-1,
            execution_time=0.0,
            artifact_refs=[],
            error=str(e),
        )


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ffuf-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

