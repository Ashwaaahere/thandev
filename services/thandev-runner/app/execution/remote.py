"""
Remote tool service execution backend
Executes tools via HTTP calls to tool microservices
"""
import logging
import httpx
from typing import Dict, Any, Optional

from app.execution.base import ExecutionBackend, ExecutionResult
from app.config import settings

logger = logging.getLogger(__name__)


class RemoteToolServiceBackend(ExecutionBackend):
    """
    Remote tool service execution backend.
    
    Calls tool microservices over HTTP (e.g., POST http://tool-nuclei/run)
    """
    
    def __init__(self, tool_service_base_url: Optional[str] = None):
        """
        Initialize remote backend.
        
        Args:
            tool_service_base_url: Base URL for tool services (e.g., "http://tool-nuclei")
        """
        self.tool_service_base_url = tool_service_base_url or getattr(
            settings, "TOOL_SERVICE_BASE_URL", "http://localhost:8003"
        )
        logger.info(f"Initialized RemoteToolServiceBackend with base_url={self.tool_service_base_url}")
    
    def _get_tool_service_url(self, tool_id: str) -> str:
        """
        Get the service URL for a tool.
        
        Args:
            tool_id: Tool identifier (e.g., "nuclei", "ffuf")
            
        Returns:
            Service URL (e.g., "http://tool-nuclei/run" or "http://localhost:8003/nuclei/run")
        """
        # Map tool_id to service name
        # For now, assume service naming: tool-{tool_id} or {tool_id}-service
        service_name = f"tool-{tool_id}"
        
        # If base_url is a pattern, use it; otherwise construct from tool_id
        if "{tool_id}" in self.tool_service_base_url:
            return self.tool_service_base_url.format(tool_id=tool_id) + "/run"
        else:
            return f"{self.tool_service_base_url}/{tool_id}/run"
    
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
        Execute tool step via remote tool service.
        """
        service_url = self._get_tool_service_url(tool_id)
        
        logger.info(
            f"Executing step remotely: tool_id={tool_id}, mode_id={mode_id}, "
            f"target={target}, session={session_id}, step={step_id}, "
            f"service_url={service_url}"
        )
        
        # Prepare request payload
        payload = {
            "session_id": session_id,
            "step_id": step_id,
            "tool_id": tool_id,
            "mode_id": mode_id,
            "target": target,
            "params": params,
            "org_id": org_id,
            "project_id": project_id,
            "scan_job_id": scan_job_id,
            "scope": scope or {},
        }
        
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3600.0)) as client:
                response = await client.post(
                    service_url,
                    json=payload,
                )
                
                if response.status_code == 200:
                    result_data = response.json()
                    
                    # Parse response from tool service
                    # Expected format:
                    # {
                    #   "success": bool,
                    #   "tool_name": str,
                    #   "output": str,
                    #   "exit_code": int,
                    #   "execution_time": float,
                    #   "artifact_refs": [str],  # URLs or artifact IDs
                    #   "findings": [dict],  # Normalized findings (optional)
                    #   "error": str (optional),
                    #   "baseline": dict (optional, for ffuf),
                    # }
                    
                    return ExecutionResult(
                        tool_name=result_data.get("tool_name", tool_id),
                        output=result_data.get("output", ""),
                        exit_code=result_data.get("exit_code", 0),
                        execution_time=result_data.get("execution_time", 0.0),
                        success=result_data.get("success", False),
                        error=result_data.get("error"),
                        baseline=result_data.get("baseline"),
                        artifact_refs=result_data.get("artifact_refs", []),
                    )
                else:
                    error_text = response.text
                    logger.error(
                        f"Tool service returned error status {response.status_code}: {error_text}"
                    )
                    return ExecutionResult(
                        tool_name=tool_id,
                        output="",
                        exit_code=-1,
                        execution_time=0.0,
                        success=False,
                        error=f"Tool service error: {response.status_code} - {error_text}",
                    )
        
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling tool service {service_url}: {e}", exc_info=True)
            return ExecutionResult(
                tool_name=tool_id,
                output="",
                exit_code=-1,
                execution_time=0.0,
                success=False,
                error=f"HTTP error: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error calling tool service: {e}", exc_info=True)
            return ExecutionResult(
                tool_name=tool_id,
                output="",
                exit_code=-1,
                execution_time=0.0,
                success=False,
                error=f"Unexpected error: {str(e)}",
            )

