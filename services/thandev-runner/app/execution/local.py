"""
Local subprocess execution backend
Executes tools as subprocesses on the local machine
"""
import logging
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from app.execution.base import ExecutionBackend, ExecutionResult

logger = logging.getLogger(__name__)


class LocalSubprocessBackend(ExecutionBackend):
    """
    Local subprocess execution backend.
    
    Uses ToolExecutor from app.services.tools (self-contained in runner).
    """
    
    def __init__(self):
        """Initialize local backend"""
        try:
            # Import ToolExecutor from local runner services (self-contained)
            from app.services.tools import ToolExecutor
            self.executor = ToolExecutor()
            logger.info("Initialized LocalSubprocessBackend with local ToolExecutor")
        except ImportError as e:
            logger.error(f"Failed to import ToolExecutor: {e}")
            logger.error(f"Python path (first 5): {sys.path[:5]}")
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
            # Create job directory - use configurable jobs directory (default: /tmp/jobs)
            from app.config import settings
            jobs_base = Path(settings.JOBS_DIR) if hasattr(settings, 'JOBS_DIR') and settings.JOBS_DIR else Path("/tmp/jobs")
            if scan_job_id:
                job_dir = jobs_base / scan_job_id
            else:
                job_dir = jobs_base / session_id
            job_dir.mkdir(parents=True, exist_ok=True)
            
            # Execute using ToolExecutor.
            #
            # IMPORTANT: ToolExecutor.run_step() is async but contains blocking subprocess calls.
            # We run it in a thread pool to prevent blocking the main event loop.
            # Use asyncio.run() in the thread to create a new event loop for the async function.
            def _run_step_sync() -> Dict[str, Any]:
                # Create a new event loop in this thread (asyncio.run() does this)
                # This is safe because we're in a separate thread via asyncio.to_thread()
                try:
                    return asyncio.run(
                        self.executor.run_step(
                            tool_id=tool_id,
                            mode_id=mode_id,
                            target_url=target,
                            params=params,
                            scan_job_id=scan_job_id,
                            job_dir=job_dir,
                        )
                    )
                except RuntimeError as e:
                    # Handle case where event loop already exists (shouldn't happen in thread)
                    if "asyncio.run() cannot be called from a running event loop" in str(e):
                        # Fallback: get or create event loop
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        try:
                            return loop.run_until_complete(
                                self.executor.run_step(
                                    tool_id=tool_id,
                                    mode_id=mode_id,
                                    target_url=target,
                                    params=params,
                                    scan_job_id=scan_job_id,
                                    job_dir=job_dir,
                                )
                            )
                        finally:
                            loop.close()
                    raise
                except Exception as e:
                    # Catch any other exceptions and log them
                    logger.error(f"Error in _run_step_sync for {tool_id}: {e}", exc_info=True)
                    # Return error result instead of raising
                    return {
                        "tool_name": tool_id,
                        "output": "",
                        "exit_code": -1,
                        "execution_time": 0.0,
                        "success": False,
                        "error": f"Tool execution failed: {str(e)}",
                    }

            result = await asyncio.to_thread(_run_step_sync)
            
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

