"""
Scan plan generation with RAG + rules
"""
import logging
import uuid
import json
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from urllib.parse import urlparse

from app.models import PlanScanResponse, PlanStep, Timeline
from app.catalog import load_catalog, get_tool_definition, get_mode_definition
from app.core.config import settings
from app.rag.store import get_rag_store
from app.rag.ingestion import query_rag_lanes

logger = logging.getLogger(__name__)


async def generate_plan(
    target_url: str,
    scan_level: str,
    org_id: str = None,
    project_id: str = None,
    stack_info: Dict[str, Any] = None,
) -> PlanScanResponse:
    """
    Generate a scan plan using RAG + rules.
    
    Process:
    1. Retrieve evidence from RAG (latest findings, tech fingerprint, CVE hints)
    2. Apply deterministic rules (TLS → sslyze, CVE signals → nuclei cve_fast, etc.)
    3. Build plan with steps, dependencies, timeline
    4. Validate plan (tool/mode exists, params validate, DAG acyclic, policy limits)
    
    Args:
        target_url: Target URL to scan
        scan_level: Scan level (basic, pro, advanced)
        org_id: Organization ID for RAG filtering
        project_id: Project ID for RAG filtering
        stack_info: Target stack information
        
    Returns:
        PlanScanResponse with steps, timeline, and reasoning
    """
    logger.info(f"Generating plan for {target_url} at level {scan_level}")
    
    if stack_info is None:
        stack_info = {}
    
    # Load catalog
    catalog = load_catalog()
    
    # Determine target type from URL
    parsed_url = urlparse(target_url)
    target_type = "https" if parsed_url.scheme == "https" else "http"
    is_tls = target_type == "https"
    
    # Step 1: Retrieve evidence from RAG
    rag_evidence = await _retrieve_rag_evidence(
        target_url=target_url,
        org_id=org_id,
        project_id=project_id,
        stack_info=stack_info,
    )
    
    # Step 2: Apply deterministic rules
    steps: List[PlanStep] = []
    step_counter = 1
    
    # Rule 1: Base tools based on scan level
    base_steps = await _get_base_tools_for_level(
        scan_level=scan_level,
        target_type=target_type,
        catalog=catalog,
        step_counter=step_counter,
    )
    steps.extend(base_steps)
    step_counter += len(base_steps)
    
    # Rule 2: TLS endpoint → add sslscan (only for pro/advanced; keep BASIC lightweight)
    if scan_level in {"pro", "advanced"} and is_tls and _tool_supports_target("sslscan", target_type, catalog):
        # Check if sslscan not already in plan
        if not any(s.tool_id == "sslscan" for s in steps):
            steps.append(PlanStep(
                step_id=f"step_{step_counter}",
                tool_id="sslscan",
                mode_id="standard",
                params={},
                depends_on=[],
                reason="TLS endpoint detected: SSL/TLS configuration analysis required",
                estimated_duration_sec=300,
            ))
            step_counter += 1
    
    # Rule 3: Prior CVE signals → nuclei cve_fast confirm mode
    if rag_evidence.get("has_cve_signals") and _tool_supports_target("nuclei", target_type, catalog):
        # Check if we should add a follow-up nuclei cve_fast step
        # Only if we already have a nuclei step (we'll add it as dependent)
        nuclei_steps = [s for s in steps if s.tool_id == "nuclei"]
        if nuclei_steps:
            # Add cve_fast as follow-up
            steps.append(PlanStep(
                step_id=f"step_{step_counter}",
                tool_id="nuclei",
                mode_id="cve_fast",
                params={},
                depends_on=[nuclei_steps[0].step_id],
                reason="Prior CVE signals detected: Quick CVE confirmation scan",
                estimated_duration_sec=300,
            ))
            step_counter += 1
    
    # Rule 4: Params-based app fingerprint → dalfox constrained mode
    if rag_evidence.get("has_params_fingerprint") and _tool_supports_target("dalfox", target_type, catalog):
        # Check if dalfox not already in plan
        if not any(s.tool_id == "dalfox" for s in steps):
            steps.append(PlanStep(
                step_id=f"step_{step_counter}",
                tool_id="dalfox",
                mode_id="constrained",
                params={},
                depends_on=[],
                reason="Params-based app fingerprint detected: Lightweight XSS scan for known parameters",
                estimated_duration_sec=600,
            ))
            step_counter += 1
    
    # Rule 5: Tech stack-based tool selection
    tech_fingerprint = rag_evidence.get("tech_fingerprint")
    tech_stack = {}
    if tech_fingerprint and isinstance(tech_fingerprint, dict):
        tech_stack = tech_fingerprint.get("tech_stack", {})
    
    if tech_stack:
        # If React/SPA detected, might want to adjust tools
        if "react" in str(tech_stack).lower() or "spa" in str(tech_stack).lower():
            # Ensure httpx is in plan for SPA detection
            if not any(s.tool_id == "httpx" for s in steps) and _tool_supports_target("httpx", target_type, catalog):
                steps.append(PlanStep(
                    step_id=f"step_{step_counter}",
                    tool_id="httpx",
                    mode_id="medium",
                    params={},
                    depends_on=[],
                    reason="SPA/React detected: HTTP probe for technology detection",
                    estimated_duration_sec=120,
                ))
                step_counter += 1
    
    # Rule 6: Server error (5xx) → skip heavy network tools
    http_status = None
    if stack_info and isinstance(stack_info, dict):
        http_info = stack_info.get("http", {})
        if isinstance(http_info, dict):
            http_status = http_info.get("status_code")
    
    if http_status and http_status >= 500:
        # Remove heavy tools (nmap, sslscan) but keep HTTP tools
        heavy_tools = {"nmap", "sslscan"}
        steps = [s for s in steps if s.tool_id not in heavy_tools]
        logger.info(f"Server error detected (status {http_status}), removed heavy network tools")
    
    # Step 3: Validate plan
    _validate_plan(steps, catalog)
    
    # Step 4: Calculate timeline
    timeline = _calculate_timeline(steps)
    
    plan_id = str(uuid.uuid4())
    
    return PlanScanResponse(
        plan_id=plan_id,
        steps=steps,
        timeline=timeline,
        metadata={
            "generated_at": datetime.utcnow().isoformat(),
            "scan_level": scan_level,
            "target_url": target_url,
            "rag_evidence_used": {
                "has_cve_signals": rag_evidence.get("has_cve_signals", False),
                "has_params_fingerprint": rag_evidence.get("has_params_fingerprint", False),
                "tech_fingerprint_detected": bool(rag_evidence.get("tech_fingerprint")),
            }
        }
    )


async def _retrieve_rag_evidence(
    target_url: str,
    org_id: Optional[str],
    project_id: Optional[str],
    stack_info: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Retrieve evidence from RAG across multiple lanes.
    
    Returns:
        Dict with:
        - latest_findings: List of recent findings
        - tech_fingerprint: Technology stack info
        - cve_templates: Relevant CVE templates
        - has_cve_signals: Boolean (prior CVE findings detected)
        - has_params_fingerprint: Boolean (params-based app detected)
    """
    try:
        rag_store = get_rag_store()
        
        # Query across all lanes
        query_text = f"security scan findings for {target_url}"
        lanes = await query_rag_lanes(
            rag_store=rag_store,
            query_text=query_text,
            org_id=org_id,
            project_id=project_id,
            target=target_url,
            top_k_per_lane=5,
        )
        
        # Analyze evidence
        latest_findings = lanes.get("latest_findings", [])
        tech_fingerprint_results = lanes.get("tech_fingerprint", [])
        cve_templates = lanes.get("cve_templates", [])
        
        # Check for CVE signals
        has_cve_signals = False
        if latest_findings:
            # Check if any findings have CVE IDs
            for finding in latest_findings:
                metadata = finding.get("metadata", {})
                if metadata.get("cve_id") or "cve" in str(metadata).lower():
                    has_cve_signals = True
                    break
        
        # Check for params fingerprint (dalfox, XSS findings suggest params-based app)
        has_params_fingerprint = False
        if latest_findings:
            for finding in latest_findings:
                metadata = finding.get("metadata", {})
                tool_id = metadata.get("tool_id", "")
                if tool_id in ("dalfox", "xss") or "xss" in str(metadata).lower():
                    has_params_fingerprint = True
                    break
        
        # Get tech fingerprint (most recent)
        tech_fingerprint = None
        if tech_fingerprint_results:
            # Get highest scoring result
            result = tech_fingerprint_results[0]
            if result and isinstance(result, dict):
                tech_fingerprint = result.get("metadata", {})
        
        logger.info(
            f"RAG evidence retrieved: {len(latest_findings)} findings, "
            f"CVE signals: {has_cve_signals}, params fingerprint: {has_params_fingerprint}"
        )
        
        return {
            "latest_findings": latest_findings,
            "tech_fingerprint": tech_fingerprint,
            "cve_templates": cve_templates,
            "has_cve_signals": has_cve_signals,
            "has_params_fingerprint": has_params_fingerprint,
        }
    except Exception as e:
        logger.warning(f"RAG retrieval failed: {e}, continuing with rule-based planning")
        return {
            "latest_findings": [],
            "tech_fingerprint": None,
            "cve_templates": [],
            "has_cve_signals": False,
            "has_params_fingerprint": False,
        }


async def _get_base_tools_for_level(
    scan_level: str,
    target_type: str,
    catalog: Dict[str, Any],
    step_counter: int,
) -> List[PlanStep]:
    """
    Get base tools for scan level (rule-based, no RAG).
    
    Returns:
        List of PlanStep objects
    """
    steps: List[PlanStep] = []
    current_step = step_counter
    
    if scan_level == "basic":
        # Basic: Just nuclei with basic_web mode
        if _tool_supports_target("nuclei", target_type, catalog):
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="nuclei",
                mode_id="basic_web",
                params={},
                depends_on=[],
                reason="Basic scan: Quick vulnerability detection with common templates",
                estimated_duration_sec=300,
            ))
            current_step += 1
        
        # Add httpx for tech detection
        if _tool_supports_target("httpx", target_type, catalog):
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="httpx",
                mode_id="low",
                params={},
                depends_on=[],
                reason="Basic scan: HTTP probe for technology detection",
                estimated_duration_sec=60,
            ))
    
    elif scan_level == "pro":
        # Pro: Multiple tools in parallel
        # Nuclei pro_web
        if _tool_supports_target("nuclei", target_type, catalog):
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="nuclei",
                mode_id="pro_web",
                params={},
                depends_on=[],
                reason="Pro scan: Comprehensive vulnerability detection",
                estimated_duration_sec=600,
            ))
            current_step += 1
        
        # Nmap top_ports (if target supports TCP)
        if _tool_supports_target("nmap", target_type, catalog):
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="nmap",
                mode_id="top_ports",
                params={},
                depends_on=[],
                reason="Pro scan: Port and service discovery",
                estimated_duration_sec=300,
            ))
            current_step += 1
        
        # HTTPx medium
        if _tool_supports_target("httpx", target_type, catalog):
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="httpx",
                mode_id="medium",
                params={},
                depends_on=[],
                reason="Pro scan: HTTP probe with extended tech detection",
                estimated_duration_sec=120,
            ))
            current_step += 1
        
        # FFuF pro (depends on httpx/nuclei finding endpoints)
        if _tool_supports_target("ffuf", target_type, catalog):
            nuclei_steps = [s for s in steps if s.tool_id == "nuclei"]
            depends_on = [nuclei_steps[0].step_id] if nuclei_steps else []
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="ffuf",
                mode_id="pro",
                params={},
                depends_on=depends_on,
                reason="Pro scan: Directory brute-forcing after endpoint discovery",
                estimated_duration_sec=900,
            ))
            current_step += 1
        
        # Dalfox standard
        if _tool_supports_target("dalfox", target_type, catalog):
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="dalfox",
                mode_id="standard",
                params={},
                depends_on=[],
                reason="Pro scan: XSS parameter analysis",
                estimated_duration_sec=900,
            ))
    
    elif scan_level == "advanced":
        # Advanced: Full tool suite
        # Nuclei advanced_web
        if _tool_supports_target("nuclei", target_type, catalog):
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="nuclei",
                mode_id="advanced_web",
                params={},
                depends_on=[],
                reason="Advanced scan: Full-depth vulnerability detection",
                estimated_duration_sec=1200,
            ))
            current_step += 1
        
        # Nmap full_ports_scripts
        if _tool_supports_target("nmap", target_type, catalog):
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="nmap",
                mode_id="full_ports_scripts",
                params={},
                depends_on=[],
                reason="Advanced scan: Comprehensive port and service analysis",
                estimated_duration_sec=900,
            ))
            current_step += 1
        
        # HTTPx high
        if _tool_supports_target("httpx", target_type, catalog):
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="httpx",
                mode_id="high",
                params={},
                depends_on=[],
                reason="Advanced scan: Comprehensive HTTP probe",
                estimated_duration_sec=180,
            ))
            current_step += 1
        
        # FFuF advanced (depends on initial tools)
        if _tool_supports_target("ffuf", target_type, catalog):
            nuclei_steps = [s for s in steps if s.tool_id == "nuclei"]
            depends_on = [nuclei_steps[0].step_id] if nuclei_steps else []
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="ffuf",
                mode_id="advanced",
                params={},
                depends_on=depends_on,
                reason="Advanced scan: Comprehensive directory brute-forcing",
                estimated_duration_sec=1800,
            ))
            current_step += 1
        
        # Dalfox standard
        if _tool_supports_target("dalfox", target_type, catalog):
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="dalfox",
                mode_id="standard",
                params={},
                depends_on=[],
                reason="Advanced scan: Comprehensive XSS analysis",
                estimated_duration_sec=1800,
            ))
            current_step += 1
        
        # SQLMap sqli_light
        if _tool_supports_target("sqlmap", target_type, catalog):
            steps.append(PlanStep(
                step_id=f"step_{current_step}",
                tool_id="sqlmap",
                mode_id="sqli_light",
                params={},
                depends_on=[],
                reason="Advanced scan: SQL injection detection",
                estimated_duration_sec=900,
            ))
    
    return steps


def _tool_supports_target(tool_id: str, target_type: str, catalog: Dict[str, Any]) -> bool:
    """Check if tool supports the target type"""
    try:
        tool = get_tool_definition(tool_id)
        allowed_types = tool.get("allowed_target_types", [])
        return target_type in allowed_types
    except ValueError:
        return False


def _validate_plan(steps: List[PlanStep], catalog: Dict[str, Any]) -> None:
    """
    Validate the plan:
    - Tool/mode must exist in catalog
    - Params must validate against params_schema
    - DAG must be acyclic
    - Enforce policy limits
    """
    if not steps:
        raise ValueError("Plan must contain at least one step")
    
    # Check tool/mode existence and validate params
    for step in steps:
        try:
            mode_def = get_mode_definition(step.tool_id, step.mode_id)
            
            # Validate params against params_schema
            params_schema = mode_def.get("params_schema", {})
            _validate_params(step.params, params_schema)
            
        except ValueError as e:
            raise ValueError(f"Invalid step {step.step_id}: {e}")
    
    # Check DAG is acyclic
    step_ids = {s.step_id for s in steps}
    for step in steps:
        for dep in step.depends_on:
            if dep not in step_ids:
                raise ValueError(f"Step {step.step_id} depends on unknown step {dep}")
    
    # Check for cycles (DFS)
    visited: Set[str] = set()
    rec_stack: Set[str] = set()
    
    def has_cycle(step_id: str) -> bool:
        if step_id in rec_stack:
            return True
        if step_id in visited:
            return False
        
        visited.add(step_id)
        rec_stack.add(step_id)
        
        step = next(s for s in steps if s.step_id == step_id)
        for dep in step.depends_on:
            if has_cycle(dep):
                return True
        
        rec_stack.remove(step_id)
        return False
    
    for step in steps:
        if has_cycle(step.step_id):
            raise ValueError(f"Cycle detected in plan dependencies")
    
    # Enforce policy limits
    if len(steps) > settings.BRAIN_MAX_STEPS:
        raise ValueError(
            f"Plan exceeds max steps limit: {len(steps)} > {settings.BRAIN_MAX_STEPS}"
        )
    
    # Calculate max parallelism (steps with no dependencies can run in parallel)
    parallel_steps = [s for s in steps if not s.depends_on]
    if len(parallel_steps) > settings.BRAIN_MAX_PARALLELISM:
        raise ValueError(
            f"Plan exceeds max parallelism: {len(parallel_steps)} > {settings.BRAIN_MAX_PARALLELISM}"
        )
    
    # Check total runtime
    total_runtime = _calculate_total_runtime(steps)
    if total_runtime > settings.BRAIN_MAX_TOTAL_RUNTIME_SEC:
        raise ValueError(
            f"Plan exceeds max runtime limit: {total_runtime} > {settings.BRAIN_MAX_TOTAL_RUNTIME_SEC}"
        )


def _validate_params(params: Dict[str, Any], params_schema: Dict[str, Any]) -> None:
    """
    Validate params against JSON Schema.
    
    Args:
        params: Parameters to validate
        params_schema: JSON Schema for parameters
        
    Raises:
        ValueError: If params don't match schema
    """
    try:
        import jsonschema
        jsonschema.validate(instance=params, schema=params_schema)
    except ImportError:
        logger.warning("jsonschema not installed, skipping param validation")
    except jsonschema.ValidationError as e:
        raise ValueError(f"Params validation failed: {e.message}")


def _calculate_timeline(steps: List[PlanStep]) -> Timeline:
    """
    Calculate timeline estimates for the plan.
    
    For parallel steps, use max duration.
    For sequential steps (with dependencies), sum durations.
    """
    if not steps:
        return Timeline(total_estimated_sec=0, phases=[])
    
    # Group steps by phase (parallel steps = same phase)
    phases: List[Dict[str, Any]] = []
    processed: Set[str] = set()
    
    # Phase 1: Steps with no dependencies (can run in parallel)
    phase_1_steps = [s for s in steps if not s.depends_on]
    if phase_1_steps:
        phase_1_duration = max([s.estimated_duration_sec for s in phase_1_steps], default=0)
        phases.append({
            "phase": 1,
            "steps": [s.step_id for s in phase_1_steps],
            "estimated_duration_sec": phase_1_duration,
            "parallel": True,
        })
        processed.update(s.step_id for s in phase_1_steps)
    
    # Phase 2+: Steps that depend on phase 1
    remaining_steps = [s for s in steps if s.step_id not in processed]
    phase_num = 2
    
    while remaining_steps:
        # Find steps whose dependencies are all processed
        ready_steps = [
            s for s in remaining_steps
            if all(dep in processed for dep in s.depends_on)
        ]
        
        if not ready_steps:
            # Circular dependency or missing dependency (shouldn't happen after validation)
            break
        
        phase_duration = max([s.estimated_duration_sec for s in ready_steps], default=0)
        phases.append({
            "phase": phase_num,
            "steps": [s.step_id for s in ready_steps],
            "estimated_duration_sec": phase_duration,
            "parallel": len(ready_steps) > 1,
        })
        
        processed.update(s.step_id for s in ready_steps)
        remaining_steps = [s for s in remaining_steps if s.step_id not in processed]
        phase_num += 1
    
    # Total duration is sum of phase durations (sequential phases)
    total_sec = sum(phase.get("estimated_duration_sec", 0) for phase in phases)
    
    return Timeline(
        total_estimated_sec=total_sec,
        phases=phases,
    )


def _calculate_total_runtime(steps: List[PlanStep]) -> int:
    """Calculate total runtime (sum of sequential phases, max of parallel)"""
    timeline = _calculate_timeline(steps)
    return timeline.total_estimated_sec
