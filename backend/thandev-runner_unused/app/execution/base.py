"""
Execution backend interface for tool execution
Supports local subprocess and remote tool service execution
"""
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Result from tool execution"""
    def __init__(
        self,
        tool_name: str,
        output: str,
        exit_code: int,
        execution_time: float,
        success: bool,
        error: Optional[str] = None,
        baseline: Optional[Dict[str, Any]] = None,
        artifact_refs: Optional[list] = None,
    ):
        self.tool_name = tool_name
        self.output = output
        self.exit_code = exit_code
        self.execution_time = execution_time
        self.success = success
        self.error = error
        self.baseline = baseline
        self.artifact_refs = artifact_refs or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "tool_name": self.tool_name,
            "output": self.output,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "success": self.success,
            "error": self.error,
            "baseline": self.baseline,
            "artifact_refs": self.artifact_refs,
        }


class ExecutionBackend(ABC):
    """Abstract base class for execution backends"""
    
    @abstractmethod
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
        Execute a tool step.
        
        Args:
            tool_id: Tool identifier from catalog
            mode_id: Mode identifier from catalog
            params: Validated parameters for this mode
            target: Target URL or reference
            session_id: Session ID
            step_id: Step ID
            org_id: Organization ID
            project_id: Project ID
            scan_job_id: Scan job ID
            scope: Additional scope information
            
        Returns:
            ExecutionResult instance
        """
        pass

