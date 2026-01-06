"""
Plan Execution Validator

Validates scan plans from the brain service to ensure:
- tool_id/mode_id exist in catalog
- params validate against mode's params_schema (strict: additionalProperties:false)
- dependencies form a DAG (no cycles)
- policy limits are respected
- target types are allowed
"""
import logging
import json
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from jsonschema import validate, ValidationError, Draft202012Validator

import sys
from pathlib import Path

# Add packages to path
# Go up from: backend/app/services/ai/plan_validation.py
# To: backend/../packages
packages_path = Path(__file__).parent.parent.parent.parent.parent / "packages"
if str(packages_path) not in sys.path:
    sys.path.insert(0, str(packages_path))

from thandev_schemas.planning import PlanScanResponse, PlanStep

logger = logging.getLogger(__name__)


class PlanValidationError(Exception):
    """Raised when plan validation fails"""
    pass


class PlanExecutionValidator:
    """Validates scan plans from brain service"""
    
    def __init__(self, catalog_path: Optional[Path] = None):
        """
        Initialize validator with catalog.
        
        Args:
            catalog_path: Path to catalog.json file. If None, uses default location.
        """
        if catalog_path is None:
            # Default: look for catalog in brain service
            # Go up from: backend/app/services/ai/plan_validation.py
            # To: repo root, then services/thandev-brain/catalog/catalog.json
            # File is at: backend/app/services/ai/plan_validation.py
            # Need to go up 5 levels: ai -> services -> app -> backend -> repo_root
            repo_root = Path(__file__).parent.parent.parent.parent.parent
            catalog_path = repo_root / "services" / "thandev-brain" / "catalog" / "catalog.json"
            
            # If not found, try alternative: load from brain service via API
            if not catalog_path.exists():
                # Fallback: try to get catalog from brain service
                try:
                    from app.services.brain_client import get_brain_client
                    import asyncio
                    brain_client = get_brain_client()
                    catalog_data = asyncio.run(brain_client.get_catalog())
                    # Use a temporary path or in-memory catalog
                    # For now, raise error with helpful message
                    raise PlanValidationError(
                        f"Catalog file not found at {catalog_path}. "
                        f"Please ensure the catalog exists or use brain service API."
                    )
                except Exception:
                    raise PlanValidationError(f"Catalog file not found: {catalog_path}")
        
        self.catalog_path = catalog_path
        self.catalog = self._load_catalog()
        self._tool_index = self._build_tool_index()
        self._mode_index = self._build_mode_index()
    
    def _load_catalog(self) -> Dict[str, Any]:
        """Load catalog from JSON file"""
        if not self.catalog_path.exists():
            raise PlanValidationError(f"Catalog file not found: {self.catalog_path}")
        
        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            
            if not isinstance(catalog, dict) or "tools" not in catalog:
                raise PlanValidationError("Invalid catalog structure: missing 'tools'")
            
            logger.info(f"Loaded catalog with {len(catalog.get('tools', []))} tools")
            return catalog
        except json.JSONDecodeError as e:
            raise PlanValidationError(f"Failed to parse catalog JSON: {e}")
        except Exception as e:
            raise PlanValidationError(f"Failed to load catalog: {e}")
    
    def _build_tool_index(self) -> Dict[str, Dict[str, Any]]:
        """Build index of tools by tool_id"""
        index = {}
        for tool in self.catalog.get("tools", []):
            tool_id = tool.get("tool_id")
            if tool_id:
                index[tool_id] = tool
        return index
    
    def _build_mode_index(self) -> Dict[str, Dict[str, Any]]:
        """Build index of modes by (tool_id, mode_id)"""
        index = {}
        for tool in self.catalog.get("tools", []):
            tool_id = tool.get("tool_id")
            if not tool_id:
                continue
            
            for mode in tool.get("modes", []):
                mode_id = mode.get("mode_id")
                if mode_id:
                    key = (tool_id, mode_id)
                    index[key] = mode
        return index
    
    def validate_plan(
        self,
        plan: PlanScanResponse,
        target_type: str = "http",
        max_steps: int = 50,
        max_parallelism: int = 10,
        max_total_runtime_sec: int = 3600,
    ) -> None:
        """
        Validate a complete scan plan.
        
        Args:
            plan: PlanScanResponse from brain service
            target_type: Target type (http, https, tcp, etc.)
            max_steps: Maximum number of steps allowed
            max_parallelism: Maximum parallel steps allowed
            max_total_runtime_sec: Maximum total runtime in seconds
            
        Raises:
            PlanValidationError: If validation fails
        """
        if not plan.steps:
            raise PlanValidationError("Plan has no steps")
        
        if len(plan.steps) > max_steps:
            raise PlanValidationError(
                f"Plan has {len(plan.steps)} steps, exceeds maximum of {max_steps}"
            )
        
        # Validate each step
        step_ids = set()
        for step in plan.steps:
            self.validate_step(step, target_type)
            if step.step_id in step_ids:
                raise PlanValidationError(f"Duplicate step_id: {step.step_id}")
            step_ids.add(step.step_id)
        
        # Validate dependencies form a DAG
        self._validate_dag(plan.steps)
        
        # Validate timeline
        if plan.timeline.total_estimated_sec > max_total_runtime_sec:
            raise PlanValidationError(
                f"Plan estimated runtime {plan.timeline.total_estimated_sec}s "
                f"exceeds maximum of {max_total_runtime_sec}s"
            )
        
        # Validate parallelism (check max concurrent steps based on dependencies)
        max_concurrent = self._calculate_max_parallelism(plan.steps)
        if max_concurrent > max_parallelism:
            raise PlanValidationError(
                f"Plan requires {max_concurrent} concurrent steps, "
                f"exceeds maximum of {max_parallelism}"
            )
        
        logger.info(f"Plan validation passed: {len(plan.steps)} steps, "
                   f"{plan.timeline.total_estimated_sec}s estimated")
    
    def validate_step(
        self,
        step: PlanStep,
        target_type: str = "http",
    ) -> None:
        """
        Validate a single plan step.
        
        Args:
            step: PlanStep to validate
            target_type: Target type (http, https, tcp, etc.)
            
        Raises:
            PlanValidationError: If validation fails
        """
        # Validate tool_id exists
        if step.tool_id not in self._tool_index:
            raise PlanValidationError(
                f"Invalid tool_id '{step.tool_id}' in step '{step.step_id}'. "
                f"Available tools: {list(self._tool_index.keys())}"
            )
        
        tool_def = self._tool_index[step.tool_id]
        
        # Validate target type is allowed
        allowed_types = tool_def.get("allowed_target_types", [])
        if target_type not in allowed_types:
            raise PlanValidationError(
                f"Tool '{step.tool_id}' does not support target type '{target_type}'. "
                f"Allowed types: {allowed_types}"
            )
        
        # Validate mode_id exists for this tool
        mode_key = (step.tool_id, step.mode_id)
        if mode_key not in self._mode_index:
            available_modes = [
                m.get("mode_id") for m in tool_def.get("modes", [])
            ]
            raise PlanValidationError(
                f"Invalid mode_id '{step.mode_id}' for tool '{step.tool_id}' in step '{step.step_id}'. "
                f"Available modes: {available_modes}"
            )
        
        mode_def = self._mode_index[mode_key]
        
        # Validate params against mode's params_schema (strict: additionalProperties:false)
        params_schema = mode_def.get("params_schema", {})
        if params_schema:
            # Ensure additionalProperties is false for strict validation
            strict_schema = dict(params_schema)
            if "additionalProperties" not in strict_schema:
                strict_schema["additionalProperties"] = False
            
            try:
                # Use Draft202012Validator for better error messages
                validator = Draft202012Validator(strict_schema)
                validator.validate(step.params)
            except ValidationError as e:
                raise PlanValidationError(
                    f"Invalid params for step '{step.step_id}': {e.message}. "
                    f"Path: {'.'.join(str(p) for p in e.path)}"
                )
        
        # Validate dependencies reference existing step_ids
        # (We'll validate DAG separately)
        if step.depends_on:
            if not isinstance(step.depends_on, list):
                raise PlanValidationError(
                    f"depends_on must be a list in step '{step.step_id}'"
                )
            for dep in step.depends_on:
                if not isinstance(dep, str):
                    raise PlanValidationError(
                        f"depends_on must contain strings in step '{step.step_id}'"
                    )
    
    def _validate_dag(self, steps: List[PlanStep]) -> None:
        """
        Validate that dependencies form a DAG (no cycles).
        
        Uses DFS to detect cycles.
        
        Args:
            steps: List of PlanStep objects
            
        Raises:
            PlanValidationError: If cycle detected
        """
        step_ids = {step.step_id for step in steps}
        
        # Build adjacency list
        graph: Dict[str, List[str]] = {step.step_id: [] for step in steps}
        for step in steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    raise PlanValidationError(
                        f"Step '{step.step_id}' depends on non-existent step '{dep}'"
                    )
                graph[step.step_id].append(dep)
        
        # DFS to detect cycles
        WHITE = 0  # Unvisited
        GRAY = 1   # Visiting
        BLACK = 2  # Visited
        
        color: Dict[str, int] = {step_id: WHITE for step_id in step_ids}
        
        def dfs(node: str, path: List[str]) -> None:
            if color[node] == GRAY:
                # Cycle detected
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                raise PlanValidationError(
                    f"Cycle detected in dependencies: {' -> '.join(cycle)}"
                )
            
            if color[node] == BLACK:
                return
            
            color[node] = GRAY
            path.append(node)
            
            for neighbor in graph[node]:
                dfs(neighbor, path)
            
            path.pop()
            color[node] = BLACK
        
        # Check all nodes
        for step_id in step_ids:
            if color[step_id] == WHITE:
                dfs(step_id, [])
    
    def _calculate_max_parallelism(self, steps: List[PlanStep]) -> int:
        """
        Calculate maximum parallelism required by plan.
        
        This is the maximum number of steps that can run concurrently
        based on their dependencies.
        
        Args:
            steps: List of PlanStep objects
            
        Returns:
            Maximum parallelism required
        """
        if not steps:
            return 0
        
        step_ids = {step.step_id for step in steps}
        
        # Build dependency graph
        graph: Dict[str, List[str]] = {step.step_id: [] for step in steps}
        for step in steps:
            for dep in step.depends_on:
                if dep in step_ids:
                    graph[step.step_id].append(dep)
        
        # Topological sort to find levels
        in_degree: Dict[str, int] = {step_id: 0 for step_id in step_ids}
        for step in steps:
            for dep in step.depends_on:
                if dep in step_ids:
                    in_degree[step.step_id] += 1
        
        max_level_size = 0
        queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
        
        while queue:
            level_size = len(queue)
            max_level_size = max(max_level_size, level_size)
            
            next_queue = []
            for node in queue:
                for step in steps:
                    if node in step.depends_on:
                        in_degree[step.step_id] -= 1
                        if in_degree[step.step_id] == 0:
                            next_queue.append(step.step_id)
            
            queue = next_queue
        
        return max_level_size


def get_validator(catalog_path: Optional[Path] = None) -> PlanExecutionValidator:
    """
    Get a PlanExecutionValidator instance.
    
    Args:
        catalog_path: Optional path to catalog.json
        
    Returns:
        PlanExecutionValidator instance
    """
    return PlanExecutionValidator(catalog_path)

