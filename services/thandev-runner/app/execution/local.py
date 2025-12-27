"""
Local subprocess execution backend
Executes tools as subprocesses on the local machine
"""
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from app.execution.base import ExecutionBackend, ExecutionResult

logger = logging.getLogger(__name__)


class LocalSubprocessBackend(ExecutionBackend):
    """
    Local subprocess execution backend.
    
    Uses ToolExecutor from backend/app/services/tools.py
    """
    
    def __init__(self):
        """Initialize local backend"""
        # Use the centralized backend_imports utility
        from app.backend_imports import ensure_backend_in_path
        ensure_backend_in_path()
        
        try:
            # Now import ToolExecutor from backend
            from app.services.tools import ToolExecutor
            self.executor = ToolExecutor()
            logger.info("Initialized LocalSubprocessBackend with ToolExecutor")
        except ImportError as e:
            logger.error(f"Failed to import ToolExecutor: {e}")
            logger.error(f"Python path (first 5): {sys.path[:5]}")
            backend_path = Path(__file__).resolve().parent.parent.parent.parent / "backend"
            logger.error(f"Backend path: {backend_path}")
            logger.error(f"Backend path exists: {backend_path.exists()}")
            if backend_path.exists():
                app_path = backend_path / "app"
                services_path = app_path / "services"
                tools_file_check = services_path / "tools.py"
                logger.error(f"App path exists: {app_path.exists()}")
                logger.error(f"Services path exists: {services_path.exists()}")
                logger.error(f"Tools file exists: {tools_file_check.exists()}")
            raise
    
    async def execute(
        self,
        tool_id: str,
        mode_id: str,
        params: Dict[str, Any],
        target: str,
        session_id: str,
        step_id: str,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        scan_job_id: Optional[str] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Execute tool step using local ToolExecutor.
        """
        logger.info(
            f"Executing step locally: tool_id={tool_id}, mode_id={mode_id}, "
            f"target={target}, session={session_id}, step={step_id}"
        )
        
        try:
            # Create job directory - use backend's data/jobs directory
            repo_root = Path(__file__).parent.parent.parent.parent
            if scan_job_id:
                job_dir = repo_root / "backend" / "data" / "jobs" / scan_job_id
            else:
                job_dir = repo_root / "backend" / "data" / "jobs" / session_id
            job_dir.mkdir(parents=True, exist_ok=True)
            
            # Execute using ToolExecutor
            result = await self.executor.run_step(
                tool_id=tool_id,
                mode_id=mode_id,
                target_url=target,
                params=params,
                scan_job_id=scan_job_id,
                job_dir=job_dir,
            )
            
            # Get artifact refs
            artifact_refs = []
            if result.get("success"):
                tool_name = result.get("tool_name", tool_id)
                output_file = job_dir / f"{tool_name}_output.json"
                if output_file.exists():
                    artifact_refs.append(str(output_file))
            
            logger.info(
                f"Step completed locally: tool_id={tool_id}, mode_id={mode_id}, "
                f"success={result.get('success', False)}, "
                f"execution_time={result.get('execution_time', 0)}s"
            )
            
            return ExecutionResult(
                tool_name=result.get("tool_name", tool_id),
                output=result.get("output", ""),
                exit_code=result.get("exit_code", 0),
                execution_time=result.get("execution_time", 0.0),
                success=result.get("success", False),
                error=result.get("error"),
                baseline=result.get("baseline"),
                artifact_refs=artifact_refs,
            )
            
        except Exception as e:
            logger.error(f"Step execution failed: {e}", exc_info=True)
            return ExecutionResult(
                tool_name=tool_id,
                output="",
                exit_code=-1,
                execution_time=0.0,
                success=False,
                error=str(e),
            )

