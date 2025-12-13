"""
AI-powered scan planning service
Uses stack_info and scan_level to plan which tools to run in which waves
"""
import logging
import json
import os
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from collections import Counter, defaultdict
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
# This ensures .env is loaded even when running in Celery workers
# Try to find .env in the backend directory (where this file is located)
backend_dir = Path(__file__).parent.parent.parent.parent  # Go up from app/services/ai/planner.py to backend/
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fallback to default behavior (searches from current working directory)
    load_dotenv()

from app.services.scan_profiles import get_profile
from app.models.scan import ScanJob
from app.models.finding import Finding

logger = logging.getLogger(__name__)


def plan_scan(stack_info: Dict[str, Any], scan_level: str) -> Dict[str, Any]:
    """
    Plan a security scan based on stack_info and scan_level.
    
    This function analyzes the target's stack information (HTTP status, headers, etc.)
    to determine the optimal tool execution plan. Uses rule-based heuristics to adjust
    tool selection based on target characteristics while keeping it LLM-ready for
    future enhancements.
    
    Args:
        stack_info: Dictionary containing target metadata:
            - target_url: Target URL
            - scan_level: Scan level string
            - http: Optional HTTP response info (status_code, headers)
        scan_level: Scan level string ("basic", "pro", or "advanced")
        
    Returns:
        Dictionary with scan plan:
        {
            "meta": {
                "scan_level": scan_level,
                "is_html": bool,
                "is_json_api": bool,
                "is_errorish": bool,
                "api_target": bool (if applicable)
            },
            "waves": [
                {
                    "phase": "initial",
                    "tools": [
                        {"name": "nuclei", "config": {}},
                        ...
                    ]
                }
            ]
        }
        
    Example:
        >>> stack_info = {
        ...     "target_url": "https://example.com",
        ...     "scan_level": "basic",
        ...     "http": {"status_code": 200, "headers": {"content_type": "text/html"}}
        ... }
        >>> plan = plan_scan(stack_info, "basic")
        >>> # Returns plan with tools adjusted based on stack_info
    """
    logger.info(f"Planning scan for level '{scan_level}' with stack_info")
    
    # Extract information from stack_info
    target_url = stack_info.get("target_url", "")
    http_info = stack_info.get("http", {})
    status_code = http_info.get("status_code")
    headers = http_info.get("headers") or {}
    
    # Derive boolean flags from headers and status
    content_type = (headers.get("content_type") or "").lower()
    is_html = "text/html" in content_type
    is_json_api = "application/json" in content_type
    # Only treat 5xx (server errors) as truly problematic
    # 4xx errors (like 405 Method Not Allowed) are client errors and don't mean the target is unreachable
    is_server_error = status_code is not None and status_code >= 500
    is_errorish = status_code is not None and status_code >= 400
    
    logger.debug(
        f"Stack info analysis: status={status_code}, "
        f"is_html={is_html}, is_json_api={is_json_api}, "
        f"is_server_error={is_server_error}, is_errorish={is_errorish}"
    )
    
    # Get base tools from tool_matrix (single source of truth)
    from app.core.tool_matrix import get_tools_for_level
    from app.models.scan import ScanLevel
    
    try:
        level_enum = ScanLevel(scan_level.lower())
    except ValueError:
        # Fallback to legacy get_profile if level conversion fails
        profile = get_profile(scan_level)
        base_tools = profile["tools"]
    else:
        tool_configs = get_tools_for_level(level_enum)
        # Convert ToolConfig to legacy format for compatibility
        base_tools = [
            {
                "name": tool_cfg["key"],
                "config": {}
            }
            for tool_cfg in tool_configs
            if tool_cfg.get("enabled", True)
        ]
    
    # Apply rule-based heuristics to adjust tool selection
    tools_to_run = []
    
    if is_server_error:
        # If target returns 5xx (server error), skip heavy network tools
        # but still run HTTP-based tools since the server might be partially reachable
        logger.info(f"Target returns server error status {status_code}, skipping heavy network tools (nmap, sslscan)")
        # Skip heavy network tools (nmap, sslscan) but keep HTTP tools (httpx, ffuf, dalfox, nuclei)
        heavy_tools = {"nmap", "sslscan"}
        tools_to_run = [tool for tool in base_tools if tool["name"] not in heavy_tools]
        if not tools_to_run:
            # Fallback: if all tools were heavy, at least run nuclei
            tools_to_run = [tool for tool in base_tools if tool["name"] == "nuclei"]
            if not tools_to_run:
                # Last resort: use first tool
                tools_to_run = base_tools[:1] if base_tools else []
    else:
        # For 2xx, 3xx, and 4xx responses, use full tool list
        # 4xx errors (like 405 Method Not Allowed) don't mean the target is unreachable
        # HTTP tools can still work with different methods/endpoints
        tools_to_run = base_tools
    
    # Build meta information for LLM use
    meta = {
        "scan_level": scan_level,
        "is_html": is_html,
        "is_json_api": is_json_api,
        "is_errorish": is_errorish,
        "is_server_error": is_server_error,
    }
    
    # Add API target flag if detected
    if is_json_api:
        meta["api_target"] = True
        logger.debug("Detected JSON API target")
    
    # Build scan plan
    plan = {
        "meta": meta,
        "waves": [
            {
                "phase": "initial",
                "tools": tools_to_run
            }
        ]
    }
    
    logger.info(
        f"Generated scan plan with {len(plan['waves'])} wave(s), "
        f"{len(tools_to_run)} tool(s) in initial wave "
        f"(adjusted from {len(base_tools)} base tools)"
    )
    
    return plan


async def generate_scan_plan_for_job(
    db: Session,
    scan_job: ScanJob,
) -> Dict[str, Any]:
    """
    Use GPT-4o-mini to analyze scan findings and generate a plan for next tools to run.
    
    This function:
    1. Queries findings from the database for this scan
    2. Builds a compact JSON summary of findings (by severity, category, top URLs)
    3. Calls OpenAI API to get tool recommendations
    4. Returns a structured plan with next_tools and attack_paths
    
    Args:
        db: Database session
        scan_job: ScanJob instance (must have findings relationship loaded or accessible)
        
    Returns:
        Dictionary with scan plan:
        {
            "next_tools": [
                {"key": "dalfox", "reason": "...", "priority": "high"},
                {"key": "sqlmap", "reason": "...", "priority": "medium"},
            ],
            "attack_paths": [
                {
                    "goal": "Steal session via XSS on /vulnerable",
                    "steps": [
                        "enumerate params on that endpoint",
                        "run dalfox with chosen payload set",
                        "attempt cookie theft proof-of-concept"
                    ]
                }
            ]
        }
        
        Returns empty plan if planner fails or no findings exist.
    """
    logger.info(
        f"Generating AI scan plan for job {scan_job.id} "
        f"(target: {scan_job.project.target_url if scan_job.project else 'unknown'}, "
        f"level: {scan_job.scan_level.value})"
    )
    
    # Query findings for this scan
    findings = db.query(Finding).filter(Finding.scan_job_id == scan_job.id).all()
    
    if not findings:
        logger.info(f"No findings found for scan {scan_job.id}, returning empty plan")
        return {
            "next_tools": [],
            "attack_paths": []
        }
    
    logger.info(f"Found {len(findings)} findings for scan {scan_job.id}")
    
    # Build compact JSON summary of findings
    # Count by severity
    severity_counts = Counter(f.severity.value for f in findings)
    
    # Count by category (extract from raw_data)
    category_counts = Counter()
    category_urls = defaultdict(list)  # Top URLs per category
    
    for finding in findings:
        # Extract categories from raw_data
        categories = []
        if finding.raw_data:
            try:
                raw_data_dict = json.loads(finding.raw_data)
                if isinstance(raw_data_dict, dict) and "categories" in raw_data_dict:
                    categories = raw_data_dict["categories"]
                    if isinstance(categories, list):
                        categories = [c.lower() for c in categories if c]
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Count categories
        for cat in categories:
            category_counts[cat] += 1
            # Collect top URLs per category (max 3)
            if finding.url and len(category_urls[cat]) < 3:
                if finding.url not in category_urls[cat]:
                    category_urls[cat].append(finding.url)
    
    # Build findings summary (limit to top 20-30 findings to stay within token budget)
    findings_summary = {
        "total": len(findings),
        "by_severity": dict(severity_counts),
        "by_category": dict(category_counts),
        "top_urls_by_category": {
            cat: urls[:3] for cat, urls in category_urls.items()
        }
    }
    
    # Limit findings in summary if too many
    MAX_FINDINGS_IN_SUMMARY = 25
    if len(findings) > MAX_FINDINGS_IN_SUMMARY:
        # Include top findings by severity (critical/high first)
        top_findings = sorted(
            findings,
            key=lambda f: (
                0 if f.severity.value == "critical" else
                1 if f.severity.value == "high" else
                2 if f.severity.value == "medium" else 3
            )
        )[:MAX_FINDINGS_IN_SUMMARY]
        
        findings_summary["sample_findings"] = [
            {
                "title": f.title[:200],  # Truncate long titles
                "severity": f.severity.value,
                "url": f.url[:200] if f.url else None,
                "categories": json.loads(f.raw_data).get("categories", []) if f.raw_data else []
            }
            for f in top_findings
        ]
    else:
        findings_summary["sample_findings"] = [
            {
                "title": f.title[:200],
                "severity": f.severity.value,
                "url": f.url[:200] if f.url else None,
                "categories": json.loads(f.raw_data).get("categories", []) if f.raw_data else []
            }
            for f in findings
        ]
    
    # Get target URL and stack info
    target_url = scan_job.project.target_url if scan_job.project else "unknown"
    stack_info = scan_job.stack_info or {}
    
    # Build prompt
    prompt = f"""You are a security scan planning assistant. Analyze the current scan findings and recommend which tools to run next.

Target Information:
- URL: {target_url}
- Scan Level: {scan_job.scan_level.value}
- Scan Created: {scan_job.created_at.isoformat() if scan_job.created_at else 'unknown'}

Current Findings Summary:
{json.dumps(findings_summary, indent=2)}

Available Tools:
- nuclei: Vulnerability scanner (already run in base scan)
- httpx: HTTP probe (already run in base scan)
- nmap: Network port scanner (already run in base scan)
- ffuf: Directory/file brute-forcer (already run in base scan)
- dalfox: XSS parameter analyzer and scanner
- sqlmap: SQL injection scanner
- sslscan: SSL/TLS scanner (already run in base scan)

Task:
Based on the findings, recommend 2-4 tools to run next. Focus on tools that can:
1. Validate or exploit the vulnerabilities found
2. Discover related vulnerabilities
3. Test attack paths suggested by the findings

Output ONLY a valid JSON object with this exact structure:
{{
    "next_tools": [
        {{
            "key": "dalfox",
            "reason": "Brief explanation why this tool is recommended",
            "priority": "high|medium|low"
        }}
    ],
    "attack_paths": [
        {{
            "goal": "Attack goal description",
            "steps": ["step 1", "step 2", "step 3"]
        }}
    ]
}}

Important:
- Only include tools from the available list above
- Keep reasons concise (1-2 sentences)
- Limit to 2-4 tools total
- If no additional tools are needed, return empty arrays
- Output ONLY JSON, no markdown formatting or explanations"""
    
    # Check if OpenAI API key is available
    # Use Settings class which properly loads from .env via pydantic_settings
    from app.core.config import settings
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        logger.warning(
            f"OPENAI_API_KEY not set, skipping AI planner for scan {scan_job.id}. "
            "Set OPENAI_API_KEY environment variable in backend/.env to enable AI-powered scan planning."
        )
        return {
            "next_tools": [],
            "attack_paths": []
        }
    
    # Call OpenAI API
    try:
        from app.services.ai.openai_client import call_planner_llm
        
        response_text = await call_planner_llm(
            prompt,
            max_output_tokens=800,
            model="gpt-4o-mini",
            temperature=0.3,
            timeout=30.0
        )
        
        # Parse JSON response
        # Remove markdown code blocks if present
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        plan = json.loads(response_text)
        
        # Validate structure
        if not isinstance(plan, dict):
            raise ValueError("Plan is not a dictionary")
        
        # Ensure required fields exist
        if "next_tools" not in plan:
            plan["next_tools"] = []
        if "attack_paths" not in plan:
            plan["attack_paths"] = []
        
        # Validate next_tools structure
        validated_tools = []
        for tool in plan.get("next_tools", []):
            if isinstance(tool, dict) and "key" in tool:
                validated_tools.append({
                    "key": tool["key"],
                    "reason": tool.get("reason", ""),
                    "priority": tool.get("priority", "medium")
                })
        plan["next_tools"] = validated_tools
        
        logger.info(
            f"AI planner generated plan for scan {scan_job.id}: "
            f"{len(plan['next_tools'])} tools, {len(plan['attack_paths'])} attack paths"
        )
        
        return plan
        
    except json.JSONDecodeError as e:
        logger.error(
            f"Failed to parse JSON from AI planner response for scan {scan_job.id}: {e}",
            exc_info=True
        )
        logger.debug(f"Response text: {response_text[:500]}")
        return {
            "next_tools": [],
            "attack_paths": []
        }
    except ValueError as e:
        # Handle missing API key or other configuration errors gracefully
        if "OPENAI_API_KEY" in str(e):
            logger.warning(
                f"OpenAI API key not configured for scan {scan_job.id}. "
                "Skipping AI planner. Set OPENAI_API_KEY environment variable to enable AI-powered scan planning."
            )
        else:
            logger.warning(f"AI planner configuration error for scan {scan_job.id}: {e}")
        return {
            "next_tools": [],
            "attack_paths": []
        }
    except Exception as e:
        logger.error(
            f"AI planner failed for scan {scan_job.id}: {e}",
            exc_info=True
        )
        return {
            "next_tools": [],
            "attack_paths": []
        }
