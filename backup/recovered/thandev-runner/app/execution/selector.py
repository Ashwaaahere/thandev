"""
Backend selector - chooses execution backend per tool_id
"""
import logging
from typing import Dict, Optional

from app.execution.base import ExecutionBackend
from app.execution.local import LocalSubprocessBackend
from app.execution.remote import RemoteToolServiceBackend
from app.config import settings

logger = logging.getLogger(__name__)


# Default backend mapping: which tools use remote services
# Tools not in this map use local subprocess execution
DEFAULT_REMOTE_TOOLS: Dict[str, bool] = {
    # Set to True to use remote service, False for local
    # "nuclei": True,  # Example: use remote nuclei-service
    # "ffuf": True,    # Example: use remote ffuf-service
}


def get_backend_for_tool(tool_id: str) -> ExecutionBackend:
    """
    Get execution backend for a tool.
    
    Args:
        tool_id: Tool identifier (e.g., "nuclei", "ffuf")
        
    Returns:
        ExecutionBackend instance (LocalSubprocessBackend or RemoteToolServiceBackend)
    """
    # Check if tool should use remote service
    use_remote = DEFAULT_REMOTE_TOOLS.get(tool_id, False)
    
    # Also check environment variable override
    remote_tools_env = getattr(settings, "REMOTE_TOOLS", "")
    if remote_tools_env:
        remote_tools_list = [t.strip() for t in remote_tools_env.split(",")]
        use_remote = tool_id in remote_tools_list
    
    if use_remote:
        tool_service_url = getattr(settings, "TOOL_SERVICE_BASE_URL", "http://localhost:8003")
        logger.info(f"Using RemoteToolServiceBackend for {tool_id} (service: {tool_service_url})")
        return RemoteToolServiceBackend(tool_service_url)
    else:
        logger.debug(f"Using LocalSubprocessBackend for {tool_id}")
        return LocalSubprocessBackend()


def get_backend_for_tool_with_config(tool_id: str, backend_type: Optional[str] = None) -> ExecutionBackend:
    """
    Get execution backend for a tool with explicit configuration.
    
    Args:
        tool_id: Tool identifier
        backend_type: Explicit backend type ("local" or "remote"), or None to auto-select
        
    Returns:
        ExecutionBackend instance
    """
    if backend_type == "remote":
        tool_service_url = getattr(settings, "TOOL_SERVICE_BASE_URL", "http://localhost:8003")
        return RemoteToolServiceBackend(tool_service_url)
    elif backend_type == "local":
        return LocalSubprocessBackend()
    else:
        # Auto-select based on tool_id
        return get_backend_for_tool(tool_id)

