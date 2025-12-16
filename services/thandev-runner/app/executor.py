"""
Tool execution adapter
Supports local subprocess execution (today) and remote job execution (future)
"""
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ToolExecutionAdapter(ABC):
    """Abstract base class for tool execution adapters"""
    
    @abstractmethod
    async def execute_step(
        self,
        tool_id: str,
        mode_id: str,
        params: Dict[str, Any],
        target_ref: str,
        job_dir: Path,
        scan_job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a tool step and return results.
        
        Args:
            tool_id: Tool identifier from catalog
            mode_id: Mode identifier from catalog
            params: Validated parameters for this mode
            target_ref: Target URL or reference
            job_dir: Directory for tool output files
            scan_job_id: Optional scan job ID for logging
            
        Returns:
            Dict with execution results:
            - tool_name: str
            - output: str (tool stdout)
            - exit_code: int
            - execution_time: float
            - success: bool
            - baseline: Optional[Dict] (for ffuf)
            - error: Optional[str]
        """
        pass


class LocalAdapter(ToolExecutionAdapter):
    """
    Local subprocess execution adapter.
    
    Uses ToolExecutor from backend/app/services/tools.py
    """
    
    def __init__(self):
        """Initialize local adapter"""
        # Use the centralized backend_imports utility
        from app.backend_imports import ensure_backend_in_path
        ensure_backend_in_path()
        
        try:
            # Now import ToolExecutor from backend
            from app.services.tools import ToolExecutor
            self.executor = ToolExecutor()
            logger.info("Initialized LocalAdapter with ToolExecutor")
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
    
    async def execute_step(
        self,
        tool_id: str,
        mode_id: str,
        params: Dict[str, Any],
        target_ref: str,
        job_dir: Path,
        scan_job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute tool step using local ToolExecutor.
        """
        logger.info(
            f"Executing step: tool_id={tool_id}, mode_id={mode_id}, "
            f"target={target_ref}, scan_job_id={scan_job_id}"
        )
        
        try:
            # Create job_dir if it doesn't exist
            job_dir.mkdir(parents=True, exist_ok=True)
            
            # Execute using ToolExecutor
            result = await self.executor.run_step(
                tool_id=tool_id,
                mode_id=mode_id,
                target_url=target_ref,
                params=params,
                scan_job_id=scan_job_id,
                job_dir=job_dir,
            )
            
            logger.info(
                f"Step completed: tool_id={tool_id}, mode_id={mode_id}, "
                f"success={result.get('success', False)}, "
                f"execution_time={result.get('execution_time', 0)}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Step execution failed: {e}", exc_info=True)
            return {
                "tool_name": tool_id,
                "output": "",
                "exit_code": -1,
                "execution_time": 0.0,
                "success": False,
                "error": str(e),
            }


class RemoteAdapter(ToolExecutionAdapter):
    """
    Remote job execution adapter (future).
    
    Will execute tools via remote job service/containers.
    """
    
    def __init__(self, job_service_url: str):
        """
        Initialize remote adapter.
        
        Args:
            job_service_url: URL of remote job service
        """
        self.job_service_url = job_service_url
        logger.info(f"Initialized RemoteAdapter with job_service_url={job_service_url}")
    
    async def execute_step(
        self,
        tool_id: str,
        mode_id: str,
        params: Dict[str, Any],
        target_ref: str,
        job_dir: Path,
        scan_job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute tool step via remote job service.
        
        TODO: Implement remote execution
        """
        raise NotImplementedError("RemoteAdapter not yet implemented")


def get_execution_adapter(adapter_type: str = "local", **kwargs) -> ToolExecutionAdapter:
    """
    Get execution adapter instance.
    
    Args:
        adapter_type: Adapter type ("local" or "remote")
        **kwargs: Additional arguments for adapter initialization
        
    Returns:
        ToolExecutionAdapter instance
    """
    if adapter_type == "local":
        return LocalAdapter()
    elif adapter_type == "remote":
        job_service_url = kwargs.get("job_service_url", "http://localhost:8002")
        return RemoteAdapter(job_service_url)
    else:
        raise ValueError(f"Unknown adapter type: {adapter_type}")



