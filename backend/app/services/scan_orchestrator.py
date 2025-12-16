"""
Scan orchestrator service
Handles queuing and coordination of security scans
"""
import logging
from typing import Optional, TYPE_CHECKING, Dict, Any, List
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import os
from pathlib import Path

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.scan import ScanJob
    from app.services.tools import ToolExecutor

logger = logging.getLogger(__name__)

# Maximum number of tools to run in parallel
MAX_PARALLEL_TOOLS = getattr(settings, "SCANNER_MAX_PARALLEL_TOOLS", 3)


class ScanOrchestrator:
    """Orchestrates security scan execution"""
    
    async def queue_scan(
        self,
        scan_job_id: str,
        target_url: str,
        scan_level: str,
        user_id: str = None
    ) -> str:
        """
        Queue a scan job using Celery with user-specific queue routing.
        
        Each user's scans are routed to a dedicated queue (user_{user_id}) to ensure
        scans run one at a time per user.
        
        Args:
            scan_job_id: ID of the scan job
            target_url: URL to scan
            scan_level: Scan level (basic, pro, advanced)
            user_id: User ID for queue routing (if None, uses default queue)
            
        Returns:
            Celery task ID
        """
        logger.info(f"Queueing scan job {scan_job_id} for {target_url} at level {scan_level}")
        
        # Import here to avoid circular imports
        from app.tasks.celery_app import run_scan_task
        
        # Route all tasks to default "celery" queue
        # Per-user concurrency is now handled by Redis-based queue_manager in the task itself
        logger.info(f"Routing scan {scan_job_id} to default celery queue (user: {user_id})")
        # Pass user_id to the task for concurrency control
        # Use apply_async to pass user_id as a keyword argument
        task = run_scan_task.apply_async(
            args=(scan_job_id, target_url, scan_level),
            kwargs={"user_id": user_id if user_id else None}
        )
        
        # ORIGINAL CODE (commented out until worker multi-queue support is fixed):
        # if user_id:
        #     queue_name = f"user_{user_id}"
        #     logger.info(f"Routing scan {scan_job_id} to user-specific queue: {queue_name}")
        #     task = run_scan_task.apply_async(
        #         args=(scan_job_id, target_url, scan_level),
        #         queue=queue_name
        #     )
        # else:
        #     logger.warning(f"No user_id provided for scan {scan_job_id}, using default queue")
        #     task = run_scan_task.delay(scan_job_id, target_url, scan_level)
        
        logger.info(f"Scan job {scan_job_id} queued with Celery task ID: {task.id} (user: {user_id or 'unknown'})")
        
        return task.id
    
    async def get_scan_status(self, celery_task_id: str) -> dict:
        """
        Get the status of a Celery task
        
        Args:
            celery_task_id: Celery task ID
            
        Returns:
            Task status information
        """
        from celery.result import AsyncResult
        
        task_result = AsyncResult(celery_task_id)
        
        return {
            "task_id": celery_task_id,
            "status": task_result.status,
            "ready": task_result.ready(),
            "successful": task_result.successful() if task_result.ready() else None,
            "result": task_result.result if task_result.ready() else None,
        }
    
    def run_basic_scan_for_job(self, job: "ScanJob") -> None:
        """
        Run the basic scan pipeline for this job.
        DEPRECATED: Use run_scan_for_job() instead.
        
        Args:
            job: ScanJob instance
        """
        logger.warning(f"run_basic_scan_for_job is deprecated, use run_scan_for_job instead")
        # Import here to avoid circular import
        from app.services.scan_orchestrator import run_scan_for_job
        return run_scan_for_job(job)


def _run_single_tool(
    db: Session,
    scan_job_id: str,
    executor: "ToolExecutor",
    tool_config: Dict[str, Any],
    target_url: str,
    job_dir: Path,
    loop: asyncio.AbstractEventLoop,
) -> str:
    """
    Execute a single tool, save results, and ingest findings.
    
    This is a helper function designed to run in parallel via ThreadPoolExecutor.
    Each tool execution is independent and can run concurrently with others.
    
    Args:
        db: Database session (thread-local, each thread gets its own)
        scan_job_id: ScanJob ID (will be loaded from this thread's DB session)
        executor: ToolExecutor instance
        tool_config: Tool configuration dict with "name" and "config" keys
        target_url: Target URL to scan
        job_dir: Directory for saving tool output files
        loop: Event loop for async tool execution
        
    Returns:
        Tool name (key) for tracking
        
    Raises:
        Exception: If tool execution fails (will be caught by caller)
    """
    from app.models.scan import ScanJob
    
    # Load scan_job from this thread's DB session
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_job_id).first()
    if not scan_job:
        raise ValueError(f"Scan job {scan_job_id} not found")
    
    # Support both old format (name/config) and new format (tool_id/mode_id)
    tool_name = tool_config.get("name")
    tool_id = tool_config.get("tool_id")
    mode_id = tool_config.get("mode_id")
    tool_config_dict = tool_config.get("config", {})
    
    # New format: tool_id/mode_id (from brain service plan)
    if tool_id and mode_id:
        logger.info(f"Running tool_id={tool_id}, mode_id={mode_id} for scan {scan_job.id}")
        try:
            params = tool_config_dict.copy()
            result = loop.run_until_complete(
                executor.run_step(
                    tool_id=tool_id,
                    mode_id=mode_id,
                    target_url=target_url,
                    params=params,
                    scan_job_id=scan_job.id,
                    job_dir=job_dir,
                )
            )
            # Ensure result has tool_name for backward compatibility
            if "tool_name" not in result:
                result["tool_name"] = tool_id
        except ValueError as e:
            logger.error(f"Invalid tool_id/mode_id: {e}")
            raise
    # Legacy format: tool name (for backward compatibility during migration)
    elif tool_name:
        logger.info(f"Running {tool_name} for scan {scan_job.id} (legacy format)")
        try:
            # Pass scan_job_id and scan_job_dir to tools for better logging and output paths
            tool_config_dict["scan_job_id"] = scan_job.id
            tool_config_dict["scan_job_dir"] = job_dir
            result = loop.run_until_complete(
                executor.run_tool(tool_name, target_url, scan_job.scan_level.value, **tool_config_dict)
            )
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}", exc_info=True)
            raise
    else:
        raise ValueError(f"Tool config must have either (tool_id, mode_id) or 'name': {tool_config}")
    
    # Save tool result to database
    from app.models.finding import ToolResult
    result_tool_name = result.get("tool_name") or tool_name or tool_id
    tool_result = ToolResult(
        scan_job_id=scan_job.id,
        tool_name=result_tool_name,
        output=result.get("output", ""),
        exit_code=result.get("exit_code", 0),
        execution_time=result.get("execution_time", 0),
        command=result.get("command", ""),
        error_message=result.get("error"),
        timed_out=1 if result.get("timed_out", False) else 0,  # Store as 0/1 (SQLite boolean)
    )
    db.add(tool_result)
    
    # Save tool output to file
    output_tool_name = tool_name or tool_id or result_tool_name
    output_file = job_dir / f"{output_tool_name}_output.json"
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_text = result.get("output", "") or ""
        
        # Write stdout as-is to file (no artificial [] fallback)
        # Empty string is valid and represents "no findings"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output_text)
        
        # Log file size after writing
        file_size = os.path.getsize(output_file)
        if tool_name == "nuclei":
            logger.info(
                "Nuclei output written for scan %s: %d bytes at %s",
                scan_job.id, file_size, output_file
            )
            # Log a preview of the output if it's not empty
            if file_size > 0:
                try:
                    with open(output_file, "r", encoding="utf-8") as preview_f:
                        first_line = preview_f.readline().strip()
                        if first_line:
                            logger.debug("Nuclei output first line preview: %s", first_line[:200])
                except Exception:
                    pass
            else:
                logger.info("Nuclei output file is empty (0 bytes) - no findings detected")
        else:
            logger.debug(f"Saved {tool_name} output to {output_file} ({file_size} bytes)")
    except Exception as e:
        logger.warning(f"Failed to save {tool_name} output to file {output_file}: {e}")
        if tool_result:
            tool_result.error_message = (tool_result.error_message or "") + f" File write error: {str(e)}"
    
    # Ingest tool-specific findings immediately after file is written
    from app.services.findings_ingestor import (
        parse_nmap_output,
        parse_sslscan_output,
        parse_httpx_output,
        parse_ffuf_output,
        parse_dalfox_output,
        parse_sqlmap_output,
        ingest_nmap_findings,
        ingest_sslscan_findings,
        ingest_httpx_findings,
        ingest_ffuf_findings,
        ingest_dalfox_findings,
        ingest_sqlmap_findings,
    )
    
    # Use tool_id if available, fallback to tool_name
    ingest_tool_name = tool_id or tool_name or result_tool_name
    
    if ingest_tool_name == "nmap" and result.get("success"):
        try:
            nmap_results = parse_nmap_output(output_file)
            logger.info("Parsed %d nmap findings for scan %s", len(nmap_results), scan_job.id)
            ingest_nmap_findings(db, scan_job.id, nmap_results)
        except Exception as e:
            logger.error("Failed to ingest nmap findings for scan %s: %s", scan_job.id, e, exc_info=True)
    
    elif ingest_tool_name == "sslscan" and result.get("success"):
        try:
            sslscan_results = parse_sslscan_output(output_file)
            logger.info("Parsed %d sslscan findings for scan %s", len(sslscan_results), scan_job.id)
            ingest_sslscan_findings(db, scan_job.id, sslscan_results)
        except Exception as e:
            logger.error("Failed to ingest sslscan findings for scan %s: %s", scan_job.id, e, exc_info=True)
    
    elif ingest_tool_name == "httpx" and result.get("success"):
        try:
            httpx_results = parse_httpx_output(output_file)
            logger.info("Parsed %d httpx findings for scan %s", len(httpx_results), scan_job.id)
            ingest_httpx_findings(db, scan_job.id, httpx_results)
        except Exception as e:
            logger.error("Failed to ingest httpx findings for scan %s: %s", scan_job.id, e, exc_info=True)
    
    elif ingest_tool_name == "ffuf" and result.get("success"):
        try:
            # PR-4C: Extract baseline from result for filtering 404/wildcard responses
            baseline_filter = result.get("baseline")
            ffuf_results = parse_ffuf_output(output_file, baseline_filter=baseline_filter)
            logger.info("Parsed %d ffuf findings for scan %s (baseline filter: %s)", 
                       len(ffuf_results), scan_job.id, "enabled" if baseline_filter else "disabled")
            ingest_ffuf_findings(db, scan_job.id, ffuf_results)
        except Exception as e:
            logger.error("Failed to ingest ffuf findings for scan %s: %s", scan_job.id, e, exc_info=True)
    
    elif ingest_tool_name == "dalfox" and result.get("success"):
        try:
            dalfox_results = parse_dalfox_output(output_file)
            if len(dalfox_results) > 0:
                logger.info("Parsed %d dalfox findings for scan %s", len(dalfox_results), scan_job.id)
            else:
                logger.info("Dalfox completed successfully for scan %s but found no XSS vulnerabilities", scan_job.id)
            ingest_dalfox_findings(db, scan_job.id, dalfox_results)
        except Exception as e:
            logger.error("Failed to ingest dalfox findings for scan %s: %s", scan_job.id, e, exc_info=True)
    
    elif ingest_tool_name == "sqlmap" and result.get("success"):
        try:
            # sqlmap outputs to a directory, not a single file
            output_dir = Path(result.get("output_dir", job_dir / "sqlmap"))
            sqlmap_results = parse_sqlmap_output(output_dir)
            logger.info("Parsed %d sqlmap findings for scan %s", len(sqlmap_results), scan_job.id)
            ingest_sqlmap_findings(db, scan_job.id, sqlmap_results)
        except Exception as e:
            logger.error("Failed to ingest sqlmap findings for scan %s: %s", scan_job.id, e, exc_info=True)
    
    # Commit this tool's results (each thread manages its own transaction)
    db.commit()
    
    # PR-3: Ingest findings into brain RAG after DB commit
    try:
        from app.services.brain_client import get_brain_client
        from app.core.config import settings
        
        if settings.BRAIN_SERVICE_ENABLED:
            # Get org_id and project_id for RAG filtering
            org_id = None
            project_id = scan_job.project_id
            if scan_job.project and scan_job.project.tenant:
                org_id = scan_job.project.tenant.id
            
            # Query findings that were just created for this tool
            from app.models.finding import Finding
            recent_findings = db.query(Finding).filter(
                Finding.scan_job_id == scan_job.id,
                Finding.tool_name == output_tool_name
            ).order_by(Finding.created_at.desc()).limit(100).all()
            
            if recent_findings:
                # Convert Finding models to dict format for brain
                findings_data = []
                for finding in recent_findings:
                    finding_dict = {
                        "id": str(finding.id),
                        "title": finding.title,
                        "description": finding.description,
                        "severity": finding.severity.value if hasattr(finding.severity, 'value') else str(finding.severity),
                        "url": finding.url,
                        "tool_id": finding.tool_name,
                        "tool_name": finding.tool_name,  # For compatibility
                        "org_id": org_id,
                        "project_id": project_id,
                        "target": target_url,
                    }
                    
                    # Parse raw_data if available
                    if finding.raw_data:
                        try:
                            import json
                            raw_data = json.loads(finding.raw_data)
                            finding_dict["raw_data"] = raw_data
                            
                            # Extract CVE ID if present
                            if isinstance(raw_data, dict):
                                cve_id = raw_data.get("cve_id") or raw_data.get("cve")
                                if cve_id:
                                    finding_dict["cve_id"] = cve_id
                        except (json.JSONDecodeError, TypeError):
                            pass
                    
                    findings_data.append(finding_dict)
                
                # Ingest to brain RAG (async, but we're in a sync context)
                # Use the existing event loop
                try:
                    brain_client = get_brain_client()
                    loop.run_until_complete(
                        brain_client.ingest_documents(
                            findings=findings_data,
                            org_id=org_id,
                            project_id=project_id,
                        )
                    )
                    logger.info(f"Ingested {len(findings_data)} findings from {output_tool_name} into brain RAG for scan {scan_job.id}")
                except Exception as e:
                    # Don't fail the scan if RAG ingestion fails
                    logger.warning(f"Failed to ingest findings into brain RAG: {e}", exc_info=True)
    except Exception as e:
        # Don't fail the scan if RAG ingestion fails
        logger.warning(f"RAG ingestion error (non-fatal): {e}", exc_info=True)
    
    return output_tool_name


def run_scan_for_job(job: "ScanJob") -> None:
    """
    Run the appropriate scan pipeline for this job based on job.scan_level.
    
    This function:
    1. Gets the scan profile for the job's scan level
    2. Runs each tool in the profile sequentially
    3. Parses findings from tool output
    4. Generates AI report
    
    Args:
        job: ScanJob instance with project relationship loaded
        
    Raises:
        ValueError: If scan level is invalid
        Exception: If scan execution fails
    """
    from app.core.database import SessionLocal
    from app.models.scan import ScanJob, ScanStatus
    from app.services.tools import ToolExecutor
    from app.models.finding import ToolResult
    from app.services.scan_profiles import get_profile
    from app.services.findings_ingestor import (
        parse_nuclei_output,
        ingest_nuclei_findings,
        parse_nmap_output,
        parse_sslscan_output,
        parse_httpx_output,
        parse_ffuf_output,
        parse_dalfox_output,
        parse_sqlmap_output,
        ingest_nmap_findings,
        ingest_sslscan_findings,
        ingest_http_header_findings,
        ingest_httpx_findings,
        ingest_ffuf_findings,
        ingest_dalfox_findings,
        ingest_sqlmap_findings,
    )
    from datetime import datetime
    import json
    import asyncio
    import os
    from pathlib import Path
    
    logger.info(f"Running scan pipeline for job {job.id} at level {job.scan_level.value}")
    
    # Get database session (job might be from a different session)
    db = SessionLocal()
    
    try:
        # Reload job from database to ensure we have latest state
        scan_job = db.query(ScanJob).filter(ScanJob.id == job.id).first()
        if not scan_job:
            raise ValueError(f"Scan job {job.id} not found in database")
        
        # Get target URL from project
        if not scan_job.project:
            db.refresh(scan_job, ["project"])
        if not scan_job.project:
            raise ValueError(f"Project not found for scan job {scan_job.id}")
        
        target_url = scan_job.project.target_url
        logger.info(f"Scanning target: {target_url}")
        
        # Build stack_info for future AI planning
        # This MUST be set before any tool execution or early returns
        from typing import Any, Dict
        import requests
        
        stack_info: Dict[str, Any] = {
            "target_url": target_url,
            "scan_level": getattr(scan_job.scan_level, "value", str(scan_job.scan_level)),
        }
        
        # Try a cheap HTTP HEAD/GET to enrich stack_info
        try:
            # Try HEAD first (cheaper, no body)
            try:
                resp = requests.head(target_url, timeout=5, allow_redirects=True)
            except requests.exceptions.RequestException:
                # Fallback to GET if HEAD fails (some servers don't support HEAD)
                resp = requests.get(target_url, timeout=5, allow_redirects=True, stream=True)
            
            stack_info["http"] = {
                "status_code": resp.status_code,
                "headers": {
                    "server": resp.headers.get("Server"),
                    "content_type": resp.headers.get("Content-Type"),
                    "x_powered_by": resp.headers.get("X-Powered-By"),
                },
            }
            logger.debug(f"Collected HTTP stack info for {target_url}: status={resp.status_code}")
        except Exception as e:
            # If HTTP request fails, log warning and continue with minimal stack_info
            logger.warning(f"Failed to fetch HTTP info for stack_info on job {scan_job.id}: {e}")
            # stack_info already has target_url and scan_level, which is sufficient
        
        # Persist stack_info to DB BEFORE running tools
        scan_job.stack_info = stack_info
        db.add(scan_job)
        db.commit()
        db.refresh(scan_job)
        logger.info(f"Saved stack_info for scan {scan_job.id}: {stack_info}")
        
        # Initialize event loop for async operations (brain client calls)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # PR-3: Ingest tech fingerprint into brain RAG
        try:
            from app.services.brain_client import get_brain_client
            from app.core.config import settings
            
            if settings.BRAIN_SERVICE_ENABLED:
                org_id = None
                project_id = scan_job.project_id
                if scan_job.project and scan_job.project.tenant:
                    org_id = scan_job.project.tenant.id
                
                brain_client = get_brain_client()
                loop.run_until_complete(
                    brain_client.ingest_documents(
                        tech_fingerprints=[{
                            "target": target_url,
                            "stack_info": stack_info,
                            "org_id": org_id,
                            "project_id": project_id,
                        }],
                        org_id=org_id,
                        project_id=project_id,
                    )
                )
                logger.info(f"Ingested tech fingerprint into brain RAG for scan {scan_job.id}")
        except Exception as e:
            # Don't fail the scan if RAG ingestion fails
            logger.warning(f"Failed to ingest tech fingerprint into brain RAG: {e}", exc_info=True)
        
        # Plan scan using brain service (PR-1: brain-only planning)
        plan = None
        from app.core.config import settings
        from app.services.ai.plan_validation import PlanExecutionValidator, PlanValidationError
        import sys
        from pathlib import Path
        
        # Add packages to path
        # Go up from: backend/app/services/scan_orchestrator.py
        # To: backend/../packages
        packages_path = Path(__file__).parent.parent.parent.parent.parent / "packages"
        if str(packages_path) not in sys.path:
            sys.path.insert(0, str(packages_path))
        
        from thandev_schemas.planning import PlanScanResponse
        
        # PR-1: Core must NOT decide which tools to run
        # Brain service is the only planner (unless explicitly disabled)
        if settings.BRAIN_SERVICE_ENABLED:
            try:
                from app.services.brain_client import get_brain_client
                brain_client = get_brain_client()
                
                # Get org_id and project_id for RAG filtering
                org_id = None
                project_id = scan_job.project_id
                if scan_job.project and scan_job.project.tenant:
                    org_id = scan_job.project.tenant.id
                
                # Call brain service (using existing event loop)
                brain_plan_dict = loop.run_until_complete(
                    brain_client.create_plan(
                        target_url=target_url,
                        scan_level=scan_job.scan_level.value,
                        org_id=org_id,
                        project_id=project_id,
                        stack_info=stack_info,
                    )
                )
                
                # Validate plan using PlanExecutionValidator (PR-1 requirement)
                try:
                    brain_plan = PlanScanResponse(**brain_plan_dict)
                    validator = PlanExecutionValidator()
                    
                    # Determine target type from URL
                    target_type = "https" if target_url.startswith("https://") else "http"
                    
                    # Validate plan
                    validator.validate_plan(
                        brain_plan,
                        target_type=target_type,
                        max_steps=50,
                        max_parallelism=10,
                        max_total_runtime_sec=3600,
                    )
                    
                    logger.info(
                        f"Plan validated: {len(brain_plan.steps)} steps, "
                        f"{brain_plan.timeline.total_estimated_sec}s estimated"
                    )
                    
                except PlanValidationError as e:
                    logger.error(f"Plan validation failed: {e}")
                    raise ValueError(f"Invalid plan from brain service: {e}")
                
                # Convert brain plan format to orchestrator format
                # Brain returns: {plan_id, steps: [{step_id, tool_id, mode_id, params, depends_on, reason, estimated_duration_sec}], timeline, metadata}
                # Orchestrator expects: {waves: [{phase, tools: [{tool_id, mode_id, params}]}]}
                
                # Group steps by phase based on dependencies (topological sort)
                steps_by_phase = {}
                step_phases = {}  # Map step_id -> phase number
                
                # Build dependency graph
                step_ids = {step.step_id for step in brain_plan.steps}
                graph: Dict[str, List[str]] = {step.step_id: [] for step in brain_plan.steps}
                in_degree: Dict[str, int] = {step_id: 0 for step_id in step_ids}
                
                for step in brain_plan.steps:
                    for dep in step.depends_on:
                        if dep in step_ids:
                            graph[step.step_id].append(dep)
                            in_degree[step.step_id] += 1
                
                # Topological sort to assign phases
                phase = 1
                queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
                
                while queue:
                    if phase not in steps_by_phase:
                        steps_by_phase[phase] = []
                    
                    next_queue = []
                    for node in queue:
                        step_phases[node] = phase
                        # Find step object
                        step_obj = next(s for s in brain_plan.steps if s.step_id == node)
                        
                        # Convert to orchestrator format (NEW: tool_id/mode_id format)
                        tool_config = {
                            "tool_id": step_obj.tool_id,
                            "mode_id": step_obj.mode_id,
                            "config": step_obj.params,  # Already validated params
                        }
                        steps_by_phase[phase].append(tool_config)
                        
                        # Update in_degree for dependent steps
                        for step in brain_plan.steps:
                            if node in step.depends_on:
                                in_degree[step.step_id] -= 1
                                if in_degree[step.step_id] == 0:
                                    next_queue.append(step.step_id)
                    
                    queue = next_queue
                    phase += 1
                
                # Build waves
                waves = []
                for phase_num in sorted(steps_by_phase.keys()):
                    waves.append({
                        "phase": f"phase_{phase_num}",
                        "tools": steps_by_phase[phase_num]
                    })
                
                plan = {"waves": waves}
                logger.info(
                    f"Generated scan plan from brain service: {len(waves)} wave(s), "
                    f"{len(brain_plan.steps)} step(s), validated and ready for execution"
                )
                
            except Exception as e:
                logger.error(f"Brain service planning failed: {e}", exc_info=True)
                if settings.BRAIN_REQUIRED:
                    # PR-1: If brain is required and fails, mark scan as failed
                    scan_job.status = ScanStatus.FAILED
                    scan_job.error_message = f"Brain service planning failed: {str(e)}. Brain service is required (BRAIN_REQUIRED=true)."
                    db.commit()
                    raise ValueError(f"Brain service required but failed: {e}")
                else:
                    # Brain not required, fall through to legacy planner
                    logger.warning("Brain service failed but BRAIN_REQUIRED=false, falling back to legacy planner")
                    plan = None
        
        # Fallback to legacy planner ONLY if brain is disabled or not required
        if plan is None:
            if not settings.BRAIN_SERVICE_ENABLED:
                logger.warning("Brain service disabled, using legacy planner (this violates PR-1 requirements)")
            else:
                logger.warning("Brain service not required, using legacy planner (this violates PR-1 requirements)")
            
            from app.services.ai.planner import plan_scan
            try:
                plan = plan_scan(stack_info, scan_job.scan_level.value)
                logger.info(f"Generated scan plan with {len(plan.get('waves', []))} wave(s) (legacy)")
            except Exception as e:
                logger.error(f"Failed to generate scan plan: {e}", exc_info=True)
                # PR-1: Do NOT fallback to tool_matrix in main path
                # If we get here, it's a critical error
                scan_job.status = ScanStatus.FAILED
                scan_job.error_message = f"All planning methods failed: {str(e)}"
                db.commit()
                raise ValueError(f"Planning failed: {e}")
        
        # Create job directory for artifacts
        job_dir = Path(f"data/jobs/{scan_job.id}")
        max_retries = 3
        dir_created = False
        for attempt in range(max_retries):
            try:
                job_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created job directory: {job_dir}")
                dir_created = True
                break
            except Exception as e:
                logger.warning(f"Failed to create job directory {job_dir} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(0.1)
        
        if not dir_created:
            logger.error(f"Failed to create job directory {job_dir} after {max_retries} attempts")
            # Continue anyway - file writes will handle directory creation as fallback
        
        # Initialize tool executor
        executor = ToolExecutor()
        tool_results = []
        
        # Event loop already initialized earlier (line 505-509)
        # Reuse the same loop for async tool execution
        
        # Run HTTP security header checks (for HTTP/HTTPS URLs only)
        # This runs before other tools to collect headers early
        from app.services.http_security import fetch_http_security, build_header_findings
        from app.services.findings_ingestor import ingest_http_header_findings
        
        logger.info(f"Starting HTTP header check for scan {scan_job.id} on {target_url}")
        try:
            http_result = loop.run_until_complete(
                fetch_http_security(target_url, timeout=10.0)
            )
            
            if http_result is not None:
                logger.info(f"HTTP header check successful for {target_url}: status={http_result.status_code}, headers={len(http_result.headers)}")
                header_findings = build_header_findings(http_result, scan_job)
                if header_findings:
                    ingest_http_header_findings(db, scan_job.id, header_findings)
                    logger.info(f"Created {len(header_findings)} HTTP header findings for scan {scan_job.id}")
                else:
                    logger.info(f"No missing headers detected for {target_url} (all security headers present)")
            else:
                logger.info(f"Skipping HTTP header checks for {target_url} (not HTTP/HTTPS or request failed)")
        except Exception as e:
            logger.error(f"HTTP header check failed for scan {scan_job.id}: {e}", exc_info=True)
            # Continue with scan - header checks are optional
        
        # Execute tools from all waves in the plan
        # We'll collect all Nuclei outputs and ingest them at the end for idempotency
        all_nuclei_outputs = []
        completed_tools: List[str] = []
        failed_tools: List[str] = []
        
        for wave_idx, wave in enumerate(plan.get("waves", [])):
            phase = wave.get("phase", f"wave_{wave_idx}")
            tools = wave.get("tools", [])
            
            if not tools:
                logger.warning(f"Wave {phase} has no tools, skipping")
                continue
            
            logger.info(f"Executing {phase} wave ({wave_idx + 1}/{len(plan.get('waves', []))}) with {len(tools)} tool(s)")
            
            # Run tools in parallel using ThreadPoolExecutor
            max_workers = min(len(tools), MAX_PARALLEL_TOOLS)
            logger.info(f"Running {len(tools)} tool(s) in parallel (max {max_workers} concurrent)")
            
            # Create a new event loop for each thread (ThreadPoolExecutor requirement)
            # Each thread will create its own loop for async tool execution
            def run_tool_with_loop(tool_cfg: Dict[str, Any]) -> str:
                """Wrapper that creates a thread-local event loop"""
                # Create a new event loop for this thread
                thread_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(thread_loop)
                try:
                    # Create a new DB session for this thread
                    from app.core.database import SessionLocal
                    thread_db = SessionLocal()
                    try:
                        return _run_single_tool(
                            thread_db, scan_job.id, executor, tool_cfg,
                            target_url, job_dir, thread_loop
                        )
                    finally:
                        thread_db.close()
                finally:
                    thread_loop.close()
            
            # Execute tools in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_workers) as executor_pool:
                future_map = {
                    executor_pool.submit(run_tool_with_loop, tool_config): (
                        tool_config.get("tool_id") or tool_config.get("name") or "unknown"
                    )
                    for tool_config in tools
                }
                
                for future in as_completed(future_map):
                    tool_key = future_map[future]
                    try:
                        completed_tool = future.result()
                        completed_tools.append(completed_tool)
                        logger.info(
                            "Tool %s completed for scan_job %s",
                            completed_tool,
                            scan_job.id,
                        )
                    except Exception as exc:
                        failed_tools.append(tool_key)
                        logger.exception(
                            "Tool %s failed for scan_job %s: %s",
                            tool_key,
                            scan_job.id,
                            exc,
                        )
        
        # Collect Nuclei outputs from files (after all tools complete)
        nuclei_output_path = job_dir / "nuclei_output.json"
        if nuclei_output_path.exists():
            try:
                with open(nuclei_output_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content:
                        all_nuclei_outputs.append(content)
            except Exception as e:
                logger.warning(f"Failed to read Nuclei output file: {e}")
        
        logger.info(f"Completed {len(completed_tools)} tool(s), {len(failed_tools)} failed")
        
        # Update scan status based on initial wave results
        # (Will be updated again at the end after follow-up waves)
        if failed_tools:
            if len(completed_tools) == 0:
                # All tools failed
                scan_job.status = ScanStatus.FAILED
                scan_job.error_message = f"All tools failed: {', '.join(failed_tools)}"
            else:
                # Some tools succeeded, some failed
                scan_job.status = ScanStatus.COMPLETED_WITH_ERRORS
                scan_job.error_message = f"Some tools failed: {', '.join(failed_tools)}"
            db.commit()
            db.refresh(scan_job)
        
        # Note: We'll ingest all Nuclei findings at the end after follow-up waves
        
        # Call AI planner after base tools finish
        # PR-1: This section should also use brain service, but keeping legacy for now
        # TODO: Refactor to use brain service for second wave planning
        from app.models.scan import AIStatus
        from app.services.ai.planner import generate_scan_plan_for_job
        
        logger.info(f"Calling AI planner for scan {scan_job.id} after base tools completion")
        try:
            # Refresh scan_job to get latest findings
            db.refresh(scan_job)
            
            # Generate AI plan (run async function in existing event loop)
            ai_plan = loop.run_until_complete(generate_scan_plan_for_job(db, scan_job))
            
            # Persist plan on scan_job
            scan_job.ai_plan = ai_plan
            scan_job.ai_status = AIStatus.PLANNED.value  # Store as string value
            db.commit()
            db.refresh(scan_job)
            
            logger.info(
                f"AI planner completed for scan {scan_job.id}: "
                f"{len(ai_plan.get('next_tools', []))} tools recommended, "
                f"{len(ai_plan.get('attack_paths', []))} attack paths"
            )
            
            # Log which tools the planner selected
            next_tools = ai_plan.get("next_tools", [])
            if next_tools:
                tool_keys = [tool.get("key") for tool in next_tools if tool.get("key")]
                logger.info(f"AI planner selected tools for scan {scan_job.id}: {', '.join(tool_keys)}")
            
        except Exception as e:
            logger.error(
                f"AI planner failed for scan {scan_job.id}: {e}",
                exc_info=True
            )
            # Set status to failed but continue with scan
            scan_job.ai_status = AIStatus.FAILED.value  # Store as string value
            scan_job.ai_plan = {"next_tools": [], "attack_paths": []}
            db.commit()
            db.refresh(scan_job)
        
        # Load findings for adaptive refinement
        db.refresh(scan_job)
        findings_list = list(scan_job.findings)
        logger.info(f"Current findings count before refinement: {len(findings_list)}")
        
        # Execute second wave of tools from AI plan if available
        # PR-1: This section should also use tool_id/mode_id format
        # Note: Legacy AI planner returns tool "key" format, we convert to tool_id/mode_id
        ai_plan = scan_job.ai_plan or {}
        next_tools = ai_plan.get("next_tools", [])
        
        if next_tools and scan_job.ai_status == AIStatus.PLANNED.value:
            logger.info(f"Executing AI-planned second wave for scan {scan_job.id}")
            
            # PR-1: Filter tools using catalog validation instead of tool_matrix
            executor = ToolExecutor()
            
            tools_to_run = []
            for tool_rec in next_tools:
                tool_key = tool_rec.get("key")
                if not tool_key:
                    continue
                
                # Check if tool is supported
                if tool_key not in executor.supported_tools:
                    logger.warning(
                        f"AI planner recommended unsupported tool '{tool_key}' for scan {scan_job.id}, skipping"
                    )
                    continue
                
                # PR-1: Use catalog to determine default mode instead of tool_matrix
                # For now, use a default mode based on tool_key (legacy compatibility)
                # TODO: AI planner should return tool_id/mode_id pairs
                default_mode_map = {
                    "nuclei": "pro_web",
                    "httpx": "medium",
                    "ffuf": "standard",
                    "dalfox": "constrained",
                    "sqlmap": "sqli_light",
                }
                mode_id = default_mode_map.get(tool_key, "standard")
                
                # Use new format: tool_id/mode_id
                tools_to_run.append({
                    "tool_id": tool_key,
                    "mode_id": mode_id,
                    "config": {}  # AI planner doesn't provide params yet
                })
            
            if tools_to_run:
                logger.info(
                    f"Executing {len(tools_to_run)} AI-planned tool(s) for scan {scan_job.id}"
                )
                
                # Run tools in parallel using ThreadPoolExecutor
                max_workers = min(len(tools_to_run), MAX_PARALLEL_TOOLS)
                
                def run_tool_with_loop(tool_cfg: Dict[str, Any]) -> str:
                    """Wrapper that creates a thread-local event loop"""
                    thread_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(thread_loop)
                    try:
                        from app.core.database import SessionLocal
                        thread_db = SessionLocal()
                        try:
                            return _run_single_tool(
                                thread_db, scan_job.id, executor, tool_cfg,
                                target_url, job_dir, thread_loop
                            )
                        finally:
                            thread_db.close()
                    finally:
                        thread_loop.close()
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor_pool:
                    future_map = {
                        executor_pool.submit(run_tool_with_loop, tool_config): (
                            tool_config.get("tool_id") or tool_config.get("name") or "unknown"
                        )
                        for tool_config in tools_to_run
                    }
                    
                    for future in as_completed(future_map):
                        tool_key = future_map[future]
                        try:
                            completed_tool = future.result()
                            completed_tools.append(completed_tool)
                            logger.info(
                                "AI-planned tool %s completed for scan_job %s",
                                completed_tool,
                                scan_job.id,
                            )
                        except Exception as exc:
                            failed_tools.append(tool_key)
                            logger.exception(
                                "AI-planned tool %s failed for scan_job %s: %s",
                                tool_key,
                                scan_job.id,
                                exc,
                            )
            else:
                logger.info(f"No valid tools to run from AI plan for scan {scan_job.id}")
        else:
            if not next_tools:
                logger.info(f"AI planner returned no tools for scan {scan_job.id}, skipping second wave")
            elif scan_job.ai_status != AIStatus.PLANNED.value:
                logger.info(f"AI planner status is {scan_job.ai_status} for scan {scan_job.id}, skipping second wave")
        
        # Refine scan plan based on findings
        from app.services.ai.adaptive import refine_scan
        try:
            refined_plan = refine_scan(stack_info, findings_list, scan_job.scan_level.value)
            follow_up_waves = refined_plan.get("waves", [])
            
            if follow_up_waves:
                logger.info(f"Adaptive refinement suggested {len(follow_up_waves)} follow-up wave(s)")
                
                # Execute follow-up waves
                for wave_idx, wave in enumerate(follow_up_waves):
                    phase = wave.get("phase", f"follow_up_{wave_idx}")
                    tools = wave.get("tools", [])
                    
                    logger.info(f"Executing {phase} wave with {len(tools)} tool(s)")
                    
                    for tool_config in tools:
                        # Support both old format (name/config) and new format (tool_id/mode_id)
                        tool_name = tool_config.get("name")
                        tool_id = tool_config.get("tool_id")
                        mode_id = tool_config.get("mode_id")
                        tool_config_dict = tool_config.get("config", {})
                        
                        tool_identifier = tool_name or f"{tool_id}/{mode_id}"
                        logger.info(f"Running {tool_identifier} for scan {scan_job.id} (follow-up)")
                        
                        # Run tool
                        try:
                            # New format: tool_id/mode_id
                            if tool_id and mode_id:
                                params = tool_config_dict.copy()
                                result = loop.run_until_complete(
                                    executor.run_step(
                                        tool_id=tool_id,
                                        mode_id=mode_id,
                                        target_url=target_url,
                                        params=params,
                                        scan_job_id=scan_job.id,
                                        job_dir=job_dir,
                                    )
                                )
                                if "tool_name" not in result:
                                    result["tool_name"] = tool_id
                            # Legacy format: tool name
                            elif tool_name:
                                tool_config_dict["scan_job_id"] = scan_job.id
                                result = loop.run_until_complete(
                                    executor.run_tool(tool_name, target_url, scan_job.scan_level.value, **tool_config_dict)
                                )
                            else:
                                raise ValueError(f"Tool config must have either (tool_id, mode_id) or 'name': {tool_config}")
                        except Exception as e:
                            logger.error(f"Tool {tool_name} execution failed: {e}", exc_info=True)
                            result = {
                                "tool_name": tool_name,
                                "success": False,
                                "error": str(e),
                                "output": "",
                                "exit_code": -1,
                                "execution_time": 0,
                            }
                        
                        # Save tool result
                        tool_result = ToolResult(
                            scan_job_id=scan_job.id,
                            tool_name=result.get("tool_name", tool_name),
                            output=result.get("output", ""),
                            exit_code=result.get("exit_code", 0),
                            execution_time=result.get("execution_time", 0),
                            command=result.get("command", ""),
                            error_message=result.get("error"),
                        )
                        db.add(tool_result)
                        db.commit()  # Commit tool result immediately
                        
                        # Save output to file
                        output_file = job_dir / f"{tool_name}_output.json"
                        try:
                            output_file.parent.mkdir(parents=True, exist_ok=True)
                            output_text = result.get("output", "") or ""
                            
                            # Write stdout as-is to file (no artificial [] fallback)
                            # Empty string is valid and represents "no findings"
                            with open(output_file, "w", encoding="utf-8") as f:
                                f.write(output_text)
                            
                            # Log file size after writing
                            file_size = os.path.getsize(output_file)
                            if tool_name == "nuclei":
                                logger.info(
                                    "Nuclei output written for scan %s: %d bytes at %s",
                                    scan_job.id, file_size, output_file
                                )
                            else:
                                logger.debug(f"Saved {tool_name} output to {output_file} ({file_size} bytes)")
                        except Exception as e:
                            logger.warning(f"Failed to save {tool_name} output to file: {e}")
                        
                        # Ingest tool-specific findings immediately after file is written
                        if tool_name == "nmap" and result.get("success"):
                            try:
                                nmap_results = parse_nmap_output(output_file)
                                logger.info("Parsed %d nmap findings for scan %s (follow-up)", len(nmap_results), scan_job.id)
                                ingest_nmap_findings(db, scan_job.id, nmap_results)
                            except Exception as e:
                                logger.error("Failed to ingest nmap findings for scan %s: %s", scan_job.id, e, exc_info=True)
                        
                        elif tool_name == "sslscan" and result.get("success"):
                            try:
                                sslscan_results = parse_sslscan_output(output_file)
                                logger.info("Parsed %d sslscan findings for scan %s (follow-up)", len(sslscan_results), scan_job.id)
                                ingest_sslscan_findings(db, scan_job.id, sslscan_results)
                            except Exception as e:
                                logger.error("Failed to ingest sslscan findings for scan %s: %s", scan_job.id, e, exc_info=True)
                        
                        elif tool_name == "httpx" and result.get("success"):
                            try:
                                httpx_results = parse_httpx_output(output_file)
                                logger.info("Parsed %d httpx findings for scan %s (follow-up)", len(httpx_results), scan_job.id)
                                ingest_httpx_findings(db, scan_job.id, httpx_results)
                            except Exception as e:
                                logger.error("Failed to ingest httpx findings for scan %s: %s", scan_job.id, e, exc_info=True)
                        
                        elif tool_name == "ffuf" and result.get("success"):
                            try:
                                # PR-4C: Extract baseline from result for filtering 404/wildcard responses
                                baseline_filter = result.get("baseline")
                                ffuf_results = parse_ffuf_output(output_file, baseline_filter=baseline_filter)
                                logger.info("Parsed %d ffuf findings for scan %s (follow-up, baseline filter: %s)", 
                                           len(ffuf_results), scan_job.id, "enabled" if baseline_filter else "disabled")
                                ingest_ffuf_findings(db, scan_job.id, ffuf_results)
                            except Exception as e:
                                logger.error("Failed to ingest ffuf findings for scan %s: %s", scan_job.id, e, exc_info=True)
                        
                        elif tool_name == "dalfox" and result.get("success"):
                            try:
                                dalfox_results = parse_dalfox_output(output_file)
                                logger.info("Parsed %d dalfox findings for scan %s (follow-up)", len(dalfox_results), scan_job.id)
                                ingest_dalfox_findings(db, scan_job.id, dalfox_results)
                            except Exception as e:
                                logger.error("Failed to ingest dalfox findings for scan %s: %s", scan_job.id, e, exc_info=True)
                        
                        # Collect Nuclei outputs from follow-up tools
                        if result.get("success") and result.get("output"):
                            if tool_name == "nuclei":
                                all_nuclei_outputs.append(result["output"])
            else:
                logger.info("No follow-up waves needed")
        except Exception as e:
            logger.error(f"Failed to refine scan plan: {e}", exc_info=True)
            # Continue without follow-up waves
        
        # Ingest all Nuclei findings at once (after all waves complete)
        # Read from the output file (not stdout) to get clean JSONL
        nuclei_output_path = job_dir / "nuclei_output.json"
        
        try:
            # Parse Nuclei output file (handles non-JSON lines, empty files gracefully)
            logger.info("Parsing Nuclei findings from %s", nuclei_output_path)
            all_nuclei_results = parse_nuclei_output(nuclei_output_path)
            
            logger.info("Parsed %d nuclei findings from file for scan %s", len(all_nuclei_results), scan_job.id)
            
            # Ingest findings (this deletes old ones and creates new ones - idempotent)
            # Call ingest_nuclei_findings even if results is empty (to ensure DB is clean)
            ingested_findings = ingest_nuclei_findings(db, scan_job.id, all_nuclei_results)
            logger.info("Finished nuclei ingestion for scan %s", scan_job.id)
            
            # PR-3: Ingest all findings into brain RAG after nuclei ingestion
            try:
                from app.services.brain_client import get_brain_client
                from app.core.config import settings
                from app.models.finding import Finding
                
                if settings.BRAIN_SERVICE_ENABLED:
                    # Get org_id and project_id
                    org_id = None
                    project_id = scan_job.project_id
                    if scan_job.project and scan_job.project.tenant:
                        org_id = scan_job.project.tenant.id
                    
                    # Get all findings for this scan
                    db.refresh(scan_job)
                    all_findings = db.query(Finding).filter(
                        Finding.scan_job_id == scan_job.id
                    ).all()
                    
                    if all_findings:
                        # Convert to dict format
                        findings_data = []
                        for finding in all_findings:
                            finding_dict = {
                                "id": str(finding.id),
                                "title": finding.title,
                                "description": finding.description,
                                "severity": finding.severity.value if hasattr(finding.severity, 'value') else str(finding.severity),
                                "url": finding.url,
                                "tool_id": finding.tool_name or "unknown",
                                "tool_name": finding.tool_name or "unknown",
                                "org_id": org_id,
                                "project_id": project_id,
                                "target": target_url,
                            }
                            
                            # Parse raw_data and extract CVE
                            if finding.raw_data:
                                try:
                                    import json
                                    raw_data = json.loads(finding.raw_data)
                                    finding_dict["raw_data"] = raw_data
                                    if isinstance(raw_data, dict):
                                        cve_id = raw_data.get("cve_id") or raw_data.get("cve") or finding.cve_id
                                        if cve_id:
                                            finding_dict["cve_id"] = cve_id
                                except (json.JSONDecodeError, TypeError):
                                    pass
                            
                            if finding.cve_id:
                                finding_dict["cve_id"] = finding.cve_id
                            
                            findings_data.append(finding_dict)
                        
                        # Ingest to brain RAG
                        brain_client = get_brain_client()
                        loop.run_until_complete(
                            brain_client.ingest_documents(
                                findings=findings_data,
                                org_id=org_id,
                                project_id=project_id,
                            )
                        )
                        logger.info(f"Ingested {len(findings_data)} total findings into brain RAG for scan {scan_job.id}")
            except Exception as e:
                # Don't fail the scan if RAG ingestion fails
                logger.warning(f"Failed to ingest findings into brain RAG: {e}", exc_info=True)
            
            # Verify findings count in DB
            db.refresh(scan_job)
            db_findings_count = len(scan_job.findings) if scan_job.findings else 0
            logger.info("Verified: %d findings in database for scan %s", db_findings_count, scan_job.id)
        except Exception as e:
            logger.error(
                "Failed to ingest Nuclei findings from %s: %s",
                nuclei_output_path, e, exc_info=True
            )
            # Continue - scan should complete even if finding ingestion fails
            # The scan will have 0 findings but status will be "completed"
        
        # Generate AI report (after all waves complete)
        # Use brain service for report prompt, then OpenAI for generation
        db.refresh(scan_job)
        final_findings_list = list(scan_job.findings)
        
        try:
            from app.core.config import settings
            
            if settings.BRAIN_SERVICE_ENABLED and settings.OPENAI_API_KEY:
                # Use brain service + OpenAI for report generation
                try:
                    from app.services.brain_client import get_brain_client
                    from app.services.ai.openai_client import get_openai_client
                    import json
                    
                    brain_client = get_brain_client()
                    
                    # Get org_id and project_id
                    org_id = None
                    project_id = scan_job.project_id
                    if scan_job.project and scan_job.project.tenant:
                        org_id = scan_job.project.tenant.id
                    
                    # Get finding IDs
                    finding_ids = [f.id for f in final_findings_list]
                    
                    # Build artifact refs from tool results
                    artifact_refs = []
                    for tool_result in scan_job.tool_results:
                        artifact_refs.append({
                            "id": f"artifact_{tool_result.id}",
                            "tool_name": tool_result.tool_name,
                            "file_path": f"data/jobs/{scan_job.id}/{tool_result.tool_name}_output.json",
                            "scan_job_id": scan_job.id,
                            "summary": f"{tool_result.tool_name} scan results",
                        })
                    
                    # Get prompt package from brain (using existing event loop)
                    prompt_package = loop.run_until_complete(
                        brain_client.build_report_prompt(
                            scan_job_id=scan_job.id,
                            finding_ids=finding_ids,
                            artifact_refs=artifact_refs,
                            org_id=org_id,
                            project_id=project_id,
                        )
                    )
                    
                    # Call OpenAI with structured outputs (using existing event loop)
                    openai_client = get_openai_client()
                    response = loop.run_until_complete(
                        openai_client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": prompt_package["system_message"]},
                                {"role": "user", "content": json.dumps(prompt_package["user_content"])},
                            ],
                            response_format={
                                "type": "json_schema",
                                "json_schema": {
                                    "name": "security_report",
                                    "schema": prompt_package["report_json_schema"],
                                }
                            },
                            temperature=0.3,
                            timeout=60.0,
                        )
                    )
                    
                    # Parse report JSON
                    report_json = json.loads(response.choices[0].message.content)
                    
                    # Validate report structure
                    # TODO: Add JSON Schema validation
                    
                    scan_job.summary = report_json
                    logger.info(f"Generated AI report via brain service for scan {scan_job.id} with {len(final_findings_list)} findings")
                    
                except Exception as e:
                    logger.warning(f"Brain service report generation failed: {e}, falling back to basic report", exc_info=True)
                    # Fall through to basic report
                    raise
            else:
                # Fallback to basic report (rule-based, no LLM)
                raise ValueError("Brain service or OpenAI not configured")
                
        except Exception as e:
            # Fallback to basic report
            try:
                from app.services.ai.reporter import generate_basic_report
                ai_report = generate_basic_report(scan_job, final_findings_list)
                scan_job.summary = ai_report
                logger.info(f"Generated basic report for scan {scan_job.id} with {len(final_findings_list)} findings")
            except Exception as e2:
                logger.error(f"Failed to generate AI report: {e2}", exc_info=True)
                from collections import Counter
                findings_list = list(scan_job.findings) if scan_job.findings else []
                scan_job.summary = {
                    "executive_summary": f"Scan completed with {len(findings_list)} findings. AI report generation encountered an error.",
                    "top_risks": [],
                    "remediation_overview": "Review findings and apply security best practices.",
                    "risk_score": 0,
                    "findings_count": len(findings_list),
                    "severity_breakdown": dict(Counter(f.severity.value for f in findings_list)) if findings_list else {},
                    "error": f"AI report generation failed: {str(e2)}"
                }
                logger.warning(f"Using fallback summary format for scan {scan_job.id}")
        
        # Update scan job status to completed (or completed_with_errors if some tools failed)
        db.refresh(scan_job)
        if scan_job.status != ScanStatus.COMPLETED_WITH_ERRORS:
            # Only set to COMPLETED if not already set to COMPLETED_WITH_ERRORS
            scan_job.status = ScanStatus.COMPLETED
        scan_job.completed_at = datetime.utcnow()
        db.commit()
        # Reload to get final findings count
        db.refresh(scan_job)
        final_findings_count = len(scan_job.findings) if scan_job.findings else 0
        logger.info(f"Scan {scan_job.id} completed with {final_findings_count} findings")
        
        # Create notification for scan completion
        try:
            create_scan_completed_notification(db, scan_job)
        except Exception as e:
            logger.warning(f"Failed to create scan completion notification: {e}", exc_info=True)
            # Don't fail the scan if notification creation fails
        
    except Exception as e:
        logger.error(f"Scan {job.id} failed: {str(e)}", exc_info=True)
        
        # Update scan job status to failed
        try:
            scan_job = db.query(ScanJob).filter(ScanJob.id == job.id).first()
            if scan_job:
                scan_job.status = ScanStatus.FAILED
                scan_job.error_message = str(e)
                scan_job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update scan job status: {db_error}")
            db.rollback()
        
        raise
    
    finally:
        db.close()


def create_scan_completed_notification(db: Session, scan_job: "ScanJob") -> None:
    """
    Create a notification when a scan completes successfully.
    
    Args:
        db: Database session
        scan_job: Completed ScanJob instance (must have project relationship loaded)
    """
    from app.models.notification import Notification
    from app.models.project import Project
    from app.models.user import User
    from app.models.tenant import Tenant
    
    # Ensure project is loaded
    if not scan_job.project:
        db.refresh(scan_job, ["project"])
    
    if not scan_job.project:
        logger.warning(f"Cannot create notification: project not found for scan {scan_job.id}")
        return
    
    project = scan_job.project
    
    # Get tenant and user from project
    if not project.tenant:
        db.refresh(project, ["tenant"])
    if not project.owner:
        db.refresh(project, ["owner"])
    
    tenant = project.tenant
    user = project.owner
    
    if not tenant or not user:
        logger.warning(f"Cannot create notification: tenant or user not found for scan {scan_job.id}")
        return
    
    # Build notification title and message
    title = f"Scan completed for {project.name}"
    
    risk_score = None
    if scan_job.summary and isinstance(scan_job.summary, dict):
        risk_score = scan_job.summary.get("risk_score")
    
    message_parts = [
        f"Security scan for {project.target_url} ({scan_job.scan_level.value}) completed."
    ]
    if risk_score is not None:
        message_parts.append(f"Risk score: {risk_score:.1f}")
    
    message = " ".join(message_parts)
    
    # Build link URL
    link_url = f"/projects/{project.id}/scans/{scan_job.id}"
    
    # Create notification
    notification = Notification(
        tenant_id=tenant.id,
        owner_id=user.id,
        type="scan_completed",
        title=title,
        message=message,
        link_url=link_url,
        is_read=False,
    )
    
    db.add(notification)
    db.commit()
    logger.info(f"Created scan completion notification for scan {scan_job.id}")
