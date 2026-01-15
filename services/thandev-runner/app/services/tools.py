"""
Security scanning tools service
Handles execution of various security scanning tools
"""
import asyncio
import logging
import subprocess
import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import tempfile
from app.utils.crawler import SmartCrawler

# Ensure PATH includes common tool locations when module loads
# This helps subprocess.find_executable() and await asyncio.to_thread(subprocess.run,) find tools
_home_dir = os.path.expanduser("~")
_go_bin = os.path.join(_home_dir, "go", "bin")
_local_tools = os.path.join(_home_dir, ".local", "thandev-tools", "bin")
# Base directory: project root (services/thandev-runner/app/services/tools.py -> project root)
# parents[0] = services/thandev-runner/app/services, parents[1] = services/thandev-runner/app, 
# parents[2] = services/thandev-runner, parents[3] = services, parents[4] = project root
# Try to get project root, fallback if path structure is different
try:
    _BASE_DIR = Path(__file__).resolve().parents[4]
except IndexError:
    # Fallback: try fewer parents if structure is different
    try:
        _BASE_DIR = Path(__file__).resolve().parents[3]
    except IndexError:
        _BASE_DIR = Path(__file__).resolve().parents[2]
_current_path = os.environ.get("PATH", "")
if _go_bin not in _current_path or _local_tools not in _current_path:
    _new_path = f"{_local_tools}:{_go_bin}:{_current_path}"
    os.environ["PATH"] = _new_path
    logger = logging.getLogger(__name__)
    logger.debug(f"Updated PATH to include tool directories: {_go_bin}, {_local_tools}")

# Base directory: project root (services/thandev-runner/app/services/tools.py -> project root)
# parents[0] = services/thandev-runner/app/services, parents[1] = services/thandev-runner/app,
# parents[2] = services/thandev-runner, parents[3] = services, parents[4] = project root
# Use the same _BASE_DIR calculated above
BASE_DIR = _BASE_DIR

# Initialize logger after PATH setup
if 'logger' not in locals():
    logger = logging.getLogger(__name__)

# Nuclei profile to tags mapping
# Maps profile names from tool_matrix to Nuclei -tags CLI argument
# IMPORTANT: Tags must match exactly what Nuclei templates use
# Use "cve" (singular) not "cves" - Nuclei templates use "cve" tag
# NOTE: "headless" tag is VERY slow (Chrome-based DOM XSS tests), only use for advanced scans
NUCLEI_PROFILE_TAGS = {
    "basic_web": ["cve", "vulnerability", "exposure", "misconfig", "xss"],  # Fast for basic
    "pro_web": [
        "cve", "vulnerability", "exposure", "misconfig", "exposed-panels",
        "xss", "sqli", "ssrf", "ssti", "xxe", "lfi", "rfi", "path-traversal",
        "cmdi", "idor", "csrf", "cors", "cors-misconfig"  # Removed headless - too slow (20+ min)
    ],
    "advanced_web": [
        "cve", "vulnerability", "exposure", "misconfig", "exposed-panels",
        "xss", "sqli", "ssrf", "ssti", "xxe", "lfi", "rfi", "path-traversal",
        "cmdi", "idor", "csrf", "cors", "cors-misconfig", "tech", "ssl"  # Removed headless due to Chrome timeout issues
    ],
}


def run_nuclei_basic(job: "ScanJob") -> None:
    """
    Run a basic Nuclei scan for the given ScanJob.
    
    This function will later run the actual nuclei command, but for now
    it just logs a placeholder.
    
    Args:
        job: ScanJob instance with project relationship loaded
    """
    logger.info(f"run_nuclei_basic: Placeholder for running Nuclei scan on job {job.id}")
    logger.info(f"  Job ID: {job.id}")
    logger.info(f"  Scan Level: {job.scan_level}")
    logger.info(f"  Project ID: {job.project_id}")
    
    # TODO: Get target URL from job.project.target_url
    # TODO: Run actual nuclei command: nuclei -u <target_url> -severity critical,high -json -silent
    # TODO: Parse JSON output and create Finding records
    # TODO: Save findings to database
    
    logger.info(f"  Placeholder: Would run Nuclei on target URL from project")


def _normalize_dalfox_output(output_text: str) -> str:
    """
    Normalize dalfox output to prevent placeholder outputs from creating fake findings.
    
    Converts:
    - "" -> "[]"
    - "{}" -> "[]"
    - "[{}]" -> "[]"
    - List of empty dicts -> "[]"
    
    Args:
        output_text: Raw dalfox stdout output
        
    Returns:
        Normalized JSON string (always a valid JSON array)
    """
    if not output_text or not output_text.strip():
        return "[]"
    
    output_stripped = output_text.strip()
    
    # Handle common placeholder patterns (exact matches)
    # Note: Also check normalized version (remove all whitespace) for cases like "[\n{}\n]"
    normalized_for_check = "".join(output_stripped.split())
    if normalized_for_check in ["{}", "[]"] or output_stripped in ["{}", "[]"]:
        return "[]"
    
    # Try parsing as JSON to check for empty objects
    # This handles cases like "[\n{}\n]" where newlines are inside brackets
    try:
        parsed = json.loads(output_stripped)
        
        # If it's a list, filter out empty dicts BUT KEEP NON-EMPTY ONES
        if isinstance(parsed, list):
            # Filter out empty dicts (dicts with no keys or all None/empty values)
            filtered = []
            for item in parsed:
                if isinstance(item, dict):
                    # Check if dict has any non-empty values
                    # CRITICAL FIX: Only filter if dict is COMPLETELY empty or has only None/empty string values
                    # Do NOT filter dicts that have actual data
                    if item:  # Dict is not empty
                        # Check if it has any meaningful values (not just None or empty strings)
                        has_meaningful_data = any(
                            v is not None and str(v).strip() 
                            for v in item.values()
                        )
                        if has_meaningful_data:
                            filtered.append(item)
                        # Empty dict {} or dict with only None/empty values is skipped
                    # Completely empty dict {} is skipped
                else:
                    # Non-dict items are kept (shouldn't happen in Dalfox output, but be safe)
                    filtered.append(item)
            
            if not filtered:
                # All items were empty dicts or empty
                return "[]"
            # Return filtered list as JSON
            return json.dumps(filtered)
        
        # If it's a single empty dict, return []
        if isinstance(parsed, dict) and not parsed:
            return "[]"
        
        # Valid output with data, return as-is (re-serialize to ensure clean formatting)
        return json.dumps(parsed) if not isinstance(parsed, str) else output_stripped
        
    except json.JSONDecodeError:
        # Not valid JSON - could be actual findings in non-JSON format
        # DO NOT FILTER - return as-is to preserve findings
        logger.warning(f"Dalfox output is not valid JSON, preserving as-is: {output_stripped[:100]}")
        return output_stripped


class ToolExecutor:
    """Executes security scanning tools"""
    
    # Map tool_id to binary name (some tools have different binary names)
    TOOL_BINARY_MAP = {
        "nuclei": "nuclei",
        "nmap": "nmap",
        "sslscan": "sslscan",
        "httpx": "httpx",
        "ffuf": "ffuf",
        "dalfox": "dalfox",
        "sqlmap": "sqlmap",  # sqlmap is in venv, checked separately
        "zap": "zap",  # ZAP is accessed via API, not binary
    }
    
    def __init__(self, catalog_path: Optional[Path] = None):
        """
        Initialize ToolExecutor with catalog for tool_id/mode_id mapping.
        
        Args:
            catalog_path: Path to catalog.json. If None, uses default location.
        """
        self.supported_tools = {
            "nuclei": self._run_nuclei,
            "nmap": self._run_nmap,
            "sslscan": self._run_sslscan,
            "httpx": self._run_httpx,
            # "ffuf": self._run_ffuf,  # Removed - no longer used
            "dalfox": self._run_dalfox,
            "sqlmap": self._run_sqlmap,
            "zap": self._run_zap,
        }
        
        # Load catalog for tool_id/mode_id mapping
        if catalog_path is None:
                # Try multiple possible catalog paths
                possible_paths = [
                    BASE_DIR / "services" / "thandev-brain" / "catalog" / "catalog.json",
                    Path("/services/thandev-brain/catalog/catalog.json"),
                    Path("/app/services/thandev-brain/catalog/catalog.json"),
                    BASE_DIR / "catalog" / "catalog.json",
                # Docker image path (runner Dockerfile copies to /app/catalog/catalog.json)
                Path("/app/catalog/catalog.json"),
                ]
                catalog_path = None
                for path in possible_paths:
                    if path.exists():
                        catalog_path = path
                        break
                if catalog_path is None:
                    # Use first path as default (will log warning if not found)
                    catalog_path = possible_paths[0]
        
        self.catalog_path = catalog_path
        self._catalog = self._load_catalog()
        self._tool_mode_map = self._build_tool_mode_map()
        self._crawl_cache = {}  # Cache crawl results per scan_job_id (simple in-memory cache)

    async def _crawl_target(self, target_url: str, scan_job_id: str, scan_level: str) -> Tuple[List[str], List[str]]:
        """
        Crawl the target URL to discover endpoints and parameters.
        Returns: (all_urls, parameterized_urls)
        """
        # Return cached result if available for this scan job
        if scan_job_id and scan_job_id in self._crawl_cache:
            logger.info(f"Using cached crawl results for scan {scan_job_id}")
            return self._crawl_cache[scan_job_id]

        # Determine limits based on scan level
        # Reduced limits to prevent nuclei timeouts
        if scan_level == "advanced":
            depth = 3
            limit = 50  # Reduced from 100 to prevent timeouts
        elif scan_level == "pro":
            depth = 2
            limit = 25  # Reduced from 50 to prevent timeouts (was finding 117 URLs)
        else:
            depth = 2
            limit = 15  # Reduced from 20 for faster basic scans
        
        crawler = SmartCrawler(target_url, depth=depth, limit=limit)
        try:
            logger.info(f"Starting crawl for scan {scan_job_id}: {target_url} (depth={depth}, limit={limit})")
            all_urls, parameterized_urls = await crawler.crawl()
            
            # Always include the root target_url
            if target_url not in all_urls:
                all_urls.insert(0, target_url)
            
            # Cache the result
            if scan_job_id:
                self._crawl_cache[scan_job_id] = (all_urls, parameterized_urls)
                
            return all_urls, parameterized_urls
        except Exception as e:
            logger.error(f"Crawl failed for scan {scan_job_id}: {e}")
            # Return empty lists so tools know crawling failed completely
            return [], []
    
    def check_tool_dependencies(self, tool_ids: List[str]) -> Tuple[bool, List[str]]:
        """
        Check if all required tool binaries are available.
        
        Uses the same binary detection logic as individual tool methods to ensure consistency.
        Checks common installation locations (e.g., ~/go/bin for Go tools) in addition to PATH.
        
        Args:
            tool_ids: List of tool_id strings to check (e.g., ["nuclei", "nmap", "httpx"])
            
        Returns:
            Tuple of (all_available: bool, missing_tools: List[str])
            - all_available: True if all tools are available, False otherwise
            - missing_tools: List of tool_ids that are missing
        """
        missing_tools = []
        
        for tool_id in tool_ids:
            if tool_id not in self.TOOL_BINARY_MAP:
                logger.warning(f"Unknown tool_id '{tool_id}' in dependency check, skipping")
                continue
            
            binary_name = self.TOOL_BINARY_MAP[tool_id]
            found = False
            
            # Special handling for sqlmap (check container installation first, then PATH)
            if tool_id == "sqlmap":
                sqlmap_path = "/opt/sqlmap/sqlmap.py"
                if os.path.exists(sqlmap_path) and os.access(sqlmap_path, os.X_OK):
                    found = True
                    logger.debug(f"sqlmap found at {sqlmap_path}")
                else:
                    # Check PATH as fallback
                    import shutil
                    path_binary = shutil.which("sqlmap")
                    if path_binary:
                        found = True
                        logger.debug(f"sqlmap found in PATH at {path_binary}")
                    else:
                        logger.error(f"sqlmap not found at {sqlmap_path} or in PATH")
            else:
                # Check common locations (same as individual tool methods)
                possible_paths = []
                
                # Go tools (nuclei, httpx, dalfox) are typically in ~/go/bin
                if tool_id in ["nuclei", "httpx", "dalfox"]:
                    possible_paths.extend([
                        os.path.expanduser("~/go/bin/" + binary_name),
                        os.path.expanduser("~/.local/thandev-tools/bin/" + binary_name),
                        "/usr/local/bin/" + binary_name,
                    ])
                
                # Standard system tools (nmap, sslscan) are typically in standard locations
                if tool_id in ["nmap", "sslscan"]:
                    possible_paths.extend([
                        "/usr/bin/" + binary_name,
                        "/usr/local/bin/" + binary_name,
                    ])
                
                # Always check PATH last
                import shutil
                path_binary = shutil.which(binary_name)
                if path_binary:
                    possible_paths.append(path_binary)
                
                # Check each possible path
                for binary_path in possible_paths:
                    try:
                        expanded_path = os.path.expanduser(binary_path) if binary_path.startswith("~") else binary_path
                        
                        # For absolute paths, check if file exists and is executable
                        if os.path.isabs(expanded_path) or expanded_path.startswith("/"):
                            if os.path.exists(expanded_path) and os.access(expanded_path, os.X_OK):
                                found = True
                                logger.debug(f"Tool '{tool_id}' (binary: {binary_name}) found at {expanded_path}")
                                break
                        else:
                            # For commands in PATH, use 'which' to find them
                            # Note: This is in a non-async function, so we use subprocess.run directly
                            check_result = subprocess.run(
                                ["which", binary_path],
                                capture_output=True,
                                timeout=2,
                                text=True
                            )
                            if check_result.returncode == 0:
                                found = True
                                logger.debug(f"Tool '{tool_id}' (binary: {binary_name}) found in PATH at {check_result.stdout.strip()}")
                                break
                    except Exception as e:
                        logger.debug(f"Tool dependency check failed for {binary_path}: {e}")
                        continue
            
            if not found:
                missing_tools.append(tool_id)
                logger.error(f"Tool '{tool_id}' (binary: {binary_name}) not found in any expected location")
        
        all_available = len(missing_tools) == 0
        if all_available:
            logger.info(f"All required tools are available: {', '.join(tool_ids)}")
        else:
            logger.error(f"Missing tools: {', '.join(missing_tools)}")
        return (all_available, missing_tools)
    
    def _load_catalog(self) -> Dict:
        """Load catalog from JSON file"""
        if not self.catalog_path.exists():
            logger.warning(f"Catalog file not found at {self.catalog_path}, tool_id/mode_id execution will be limited")
            return {"tools": []}
        
        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            logger.debug(f"Loaded catalog with {len(catalog.get('tools', []))} tools")
            return catalog
        except Exception as e:
            logger.warning(f"Failed to load catalog: {e}, tool_id/mode_id execution will be limited")
            return {"tools": []}
    
    def _build_tool_mode_map(self) -> Dict[Tuple[str, str], Dict]:
        """
        Build mapping from (tool_id, mode_id) to mode configuration.
        
        Returns:
            Dict mapping (tool_id, mode_id) -> mode config dict
        """
        mapping = {}
        for tool in self._catalog.get("tools", []):
            tool_id = tool.get("tool_id")
            if not tool_id:
                continue
            
            for mode in tool.get("modes", []):
                mode_id = mode.get("mode_id")
                if mode_id:
                    mapping[(tool_id, mode_id)] = {
                        "tool_id": tool_id,
                        "mode_id": mode_id,
                        "params_schema": mode.get("params_schema", {}),
                        "constraints": mode.get("constraints", {}),
                    }
        
        logger.debug(f"Built tool_mode_map with {len(mapping)} entries")
        return mapping
    
    async def run_step(
        self,
        tool_id: str,
        mode_id: str,
        target_url: str,
        params: Optional[Dict[str, Any]] = None,
        scan_job_id: Optional[str] = None,
        job_dir: Optional[Path] = None,
    ) -> Dict:
        """
        Execute a tool step using tool_id/mode_id (catalog-based execution).
        
        This is the new interface that accepts only allowlisted tool_id/mode_id
        combinations. Commands are built internally from the catalog.
        
        Args:
            tool_id: Tool identifier from catalog (e.g., "nuclei", "nmap")
            mode_id: Mode identifier from catalog (e.g., "basic_web", "pro_web")
            target_url: Target URL to scan
            params: Validated parameters for this mode (from plan step)
            scan_job_id: Optional scan job ID for logging
            job_dir: Optional job directory for output files
            
        Returns:
            Tool execution results dict
            
        Raises:
            ValueError: If tool_id/mode_id not found in catalog or not supported
        """
        # Validate tool_id/mode_id exists in catalog
        mode_key = (tool_id, mode_id)
        if mode_key not in self._tool_mode_map:
            available = list(self._tool_mode_map.keys())
            raise ValueError(
                f"Invalid tool_id/mode_id combination: ({tool_id}, {mode_id}). "
                f"Available combinations: {available}"
            )
        
        # Validate tool is supported
        if tool_id not in self.supported_tools:
            raise ValueError(
                f"Tool '{tool_id}' is not supported. Supported tools: {list(self.supported_tools.keys())}"
            )
        
        mode_config = self._tool_mode_map[mode_key]
        params = params or {}
        
        # Defense-in-depth: Validate params against mode's params_schema
        # (Plan validation already does this, but we validate again here for security)
        params_schema = mode_config.get("params_schema", {})
        if params_schema:
            try:
                from jsonschema import Draft202012Validator, ValidationError as SchemaValidationError
                
                # Filter out system properties (timeout_seconds, scan_level) before validation
                # These are added by the planner but may not be in the schema
                system_props = {"timeout_seconds", "scan_level", "timeout_sec"}
                filtered_params = {k: v for k, v in params.items() if k not in system_props}
                
                # Ensure additionalProperties is false for strict validation
                strict_schema = dict(params_schema)
                if "additionalProperties" not in strict_schema:
                    strict_schema["additionalProperties"] = False
                
                validator = Draft202012Validator(strict_schema)
                validator.validate(filtered_params)
            except SchemaValidationError as e:
                raise ValueError(
                    f"Invalid params for {tool_id}/{mode_id}: {e.message}. "
                    f"Params must match schema with additionalProperties=false"
                )
            except ImportError:
                # jsonschema not available, skip validation (should not happen in production)
                logger.warning(f"jsonschema not available, skipping param validation for {tool_id}/{mode_id}")
        
        # Map mode_id to internal parameters based on catalog
        # This is where we convert catalog modes to internal tool parameters
        internal_kwargs = self._map_mode_to_internal_params(tool_id, mode_id, params, mode_config)
        
        # CRITICAL: Extract timeout_seconds and scan_level from params if provided
        # These are passed from backend via runner_client.py
        # IMPORTANT: Extract AFTER mode mapping to override any defaults from mode mapping
        # This ensures backend-provided timeouts take precedence
        if "timeout_seconds" in params:
            timeout_val = params["timeout_seconds"]
            internal_kwargs["timeout_seconds"] = timeout_val
            logger.info(f"Using timeout_seconds={timeout_val} from params for {tool_id}/{mode_id} (override mode default)")
        elif "timeout_seconds" not in internal_kwargs:
            logger.warning(
                f"timeout_seconds NOT found in params or mode config for {tool_id}/{mode_id}. "
                f"Available params keys: {list(params.keys())}. "
                f"Available internal_kwargs keys: {list(internal_kwargs.keys())}. "
                f"This may cause tools to use default timeouts which may be too short."
            )

        if "scan_level" in params:
            # Use scan_level from params (more accurate than inferring from mode_id)
            scan_level = params["scan_level"]
            logger.info(f"Using scan_level={scan_level} from params for {tool_id}/{mode_id}")
        else:
            # Fallback: Determine scan_level from mode_id (for backward compatibility)
            scan_level = self._infer_scan_level_from_mode(mode_id)
        
        # CRITICAL: Do NOT add scan_level to internal_kwargs - it's passed as positional argument
        # Adding it to kwargs would cause "got multiple values for argument 'scan_level'" error
        
        # Add metadata
        if scan_job_id:
            internal_kwargs["scan_job_id"] = scan_job_id
        if job_dir:
            internal_kwargs["scan_job_dir"] = job_dir
        
        logger.info(f"Executing tool_id={tool_id}, mode_id={mode_id} on {target_url} (scan_level={scan_level})")
        
        # Track execution time (like run_tool does)
        start_time = datetime.utcnow()
        
        try:
            # Call internal tool runner
            # scan_level is passed as positional argument, NOT in kwargs
            tool_runner = self.supported_tools[tool_id]
            result = await tool_runner(target_url, scan_level, **internal_kwargs)
            
            # Calculate and add execution time ONLY if tool didn't provide it
            # This prevents overwriting accurate subprocess-only timing with wall-clock time that includes setup overhead
            if "execution_time" not in result:
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                result["execution_time"] = execution_time
                logger.debug(f"Tool {tool_id} did not provide execution_time, using wall-clock: {execution_time:.2f}s")
            
            result["success"] = result.get("success", True)  # Default to True if not set
            
            return result
        except Exception as e:
            logger.error(f"Tool {tool_id}/{mode_id} failed: {str(e)}", exc_info=True)
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "tool_name": tool_id,
                "success": False,
                "error": str(e),
                "output": "",
                "exit_code": -1,
                "execution_time": execution_time,
            }
    
    def _map_mode_to_internal_params(
        self,
        tool_id: str,
        mode_id: str,
        params: Dict[str, Any],
        mode_config: Dict,
    ) -> Dict[str, Any]:
        """
        Map catalog mode parameters to internal tool parameters.
        
        This is where we convert catalog-defined params to the internal
        format expected by _run_* methods.
        """
        internal = {}
        
        if tool_id == "nuclei":
            # Map mode_id to profile (for backward compatibility)
            if mode_id in ["basic_web", "pro_web", "advanced_web"]:
                internal["profile"] = mode_id
            
            # Map params
            if "tags" in params:
                internal["tags"] = params["tags"]
            if "severity" in params:
                internal["severity"] = params["severity"]
        
        elif tool_id == "httpx":
            # Map intensity from mode_id
            if mode_id == "low":
                internal["intensity"] = "low"
            elif mode_id == "medium":
                internal["intensity"] = "medium"
            elif mode_id == "high":
                internal["intensity"] = "high"
        
        elif tool_id == "ffuf":
            # Map wordlist from params
            if "wordlist" in params:
                internal["wordlist"] = params["wordlist"]
        
        elif tool_id == "nmap":
            # Map profile from mode_id
            if mode_id == "top_ports":
                internal["profile"] = "top_ports"
            elif mode_id == "full_ports_scripts":
                internal["profile"] = "full_ports_scripts"
        
        elif tool_id == "sqlmap":
            # Map level and risk from params
            if "level" in params:
                internal["level"] = params["level"]
            if "risk" in params:
                internal["risk"] = params["risk"]
            if "timeout_sec" in params:
                internal["timeout_seconds"] = params["timeout_sec"]
            
            # Map mode_id to execution mode
            internal["mode_id"] = mode_id
            
            # Map mode-specific params
            if mode_id == "sqli_post_data":
                if "data" in params:
                    internal["post_data"] = params["data"]
                if "param_names" in params:
                    internal["param_names"] = params["param_names"]
                if "cookie" in params:
                    internal["cookie"] = params["cookie"]
            elif mode_id == "sqli_raw_request":
                if "raw_request_ref" in params:
                    internal["raw_request_ref"] = params["raw_request_ref"]
            elif mode_id == "sqli_forms_login":
                if "use_raw_request" in params:
                    internal["use_raw_request"] = params["use_raw_request"]
            elif mode_id == "sqli_get_basic":
                if "param_names" in params:
                    internal["param_names"] = params["param_names"]
            elif mode_id == "sqli_light":
                internal["profile"] = "sqli_light"
        
        elif tool_id == "dalfox":
            # Map aggressiveness from mode_id
            if mode_id == "constrained":
                internal["aggressiveness"] = "low"
            elif mode_id == "standard":
                internal["aggressiveness"] = "medium"
            elif mode_id == "aggressive":
                internal["aggressiveness"] = "high"
        
        elif tool_id == "zap":
            # Map mode_id and params
            internal["mode_id"] = mode_id
            if "max_depth" in params:
                internal["max_depth"] = params["max_depth"]
            if "max_children" in params:
                internal["max_children"] = params["max_children"]
            if "policy" in params:
                internal["policy"] = params["policy"]
            if "max_duration" in params:
                internal["max_duration"] = params["max_duration"]
        
        # CRITICAL: Pass through timeout from params (set by backend via runner_client)
        # This takes precedence over constraints since it's based on actual scan level
        if "timeout_seconds" in params:
            internal["timeout_seconds"] = params["timeout_seconds"]
            logger.debug(f"Using timeout_seconds={params['timeout_seconds']} from params for {tool_id}/{mode_id}")
        elif "timeout_sec" in params:
            # Also check for timeout_sec (alternative naming)
            internal["timeout_seconds"] = params["timeout_sec"]
            logger.debug(f"Using timeout_seconds={params['timeout_sec']} from params (timeout_sec) for {tool_id}/{mode_id}")
        else:
            # Fallback: Pass through timeout if specified in constraints
            constraints = mode_config.get("constraints", {})
            if "max_timeout_sec" in constraints:
                internal["timeout_seconds"] = constraints["max_timeout_sec"]
                logger.debug(f"Using timeout_seconds={constraints['max_timeout_sec']} from constraints for {tool_id}/{mode_id}")
        
        return internal
    
    def _infer_scan_level_from_mode(self, mode_id: str) -> str:
        """
        Infer scan_level from mode_id (temporary for backward compatibility).
        
        This will be removed once we fully migrate away from scan_level.
        """
        if "basic" in mode_id.lower():
            return "basic"
        elif "pro" in mode_id.lower() or "standard" in mode_id.lower():
            return "pro"
        elif "advanced" in mode_id.lower() or "aggressive" in mode_id.lower():
            return "advanced"
        else:
            return "basic"  # Default
    
    async def run_tool(
        self,
        tool_name: str,
        target_url: str,
        scan_level: str,
        **kwargs
    ) -> Dict:
        """
        Run a security scanning tool
        
        Args:
            tool_name: Name of the tool to run
            target_url: Target URL to scan
            scan_level: Scan level (basic, pro, advanced)
            **kwargs: Additional tool-specific arguments
            
        Returns:
            Tool execution results
        """
        if tool_name not in self.supported_tools:
            raise ValueError(f"Unsupported tool: {tool_name}")
        
        logger.info(f"Running {tool_name} on {target_url} at level {scan_level}")
        
        start_time = datetime.utcnow()
        
        try:
            result = await self.supported_tools[tool_name](target_url, scan_level, **kwargs)
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            result["execution_time"] = execution_time
            result["success"] = True
            
            return result
            
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {str(e)}")
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "success": False,
                "error": str(e),
                "execution_time": execution_time,
            }
    
    # TODO: Vulnerability classes covered by Nuclei:
    # - XSS (via xss templates)
    # - SQLi (via sqli templates)
    # - SSRF (via ssrf templates)
    # - SSTI (via ssti templates)
    # - XXE (via xxe templates)
    # - Directory Traversal / File Inclusion (via lfi/rfi/path-traversal templates)
    # - Command Injection (via cmdi/rce templates)
    # - IDOR (via idor templates)
    # - CSRF (via csrf templates)
    # - CORS Misconfiguration (via cors templates)
    # - HTTP Headers, TLS/Certificate, Network Exposure (via misc templates)
    async def _run_nuclei(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run Nuclei vulnerability scanner
        
        Optional kwargs:
            profile: profile name from tool config (e.g., "basic_web", "pro_web", "advanced_web")
                    If provided, uses NUCLEI_PROFILE_TAGS to determine which tags to use
        """
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        
        # 1. Crawl first to get all endpoints
        logger.info(f"Crawling target for Nuclei scan {scan_job_id}...")
        all_urls, _ = await self._crawl_target(target_url, scan_job_id, scan_level)
        logger.info(f"Nuclei will scan {len(all_urls)} URLs found by crawler")
        
        if not all_urls:
            logger.warning(f"No URLs found for Nuclei scan {scan_job_id} (crawler failed or returned nothing). Skipping Nuclei.")
            return {
                "tool_name": "nuclei",
                "output": "[]",
                "exit_code": 0,
                "command": "skipped",
                "timed_out": False,
                "error": "Crawler found no URLs (target likely unreachable)",
                "success": False # Mark as failure to alert user, but cleanly
            }
        
        # Check if nuclei is installed
        # Try common locations for nuclei (in order of preference)
        nuclei_binary = None
        # Check /usr/local/bin first (where Dockerfile installs it)
        possible_paths = [
            "/usr/local/bin/nuclei",  # Dockerfile installs here (check first)
            "/usr/local/go/bin/nuclei",  # Go bin directory (if GOBIN is set)
            os.path.expanduser("~/go/bin/nuclei"),  # Go bin directory
            os.path.expanduser("~/.local/thandev-tools/bin/nuclei"),  # Local tools directory
            "nuclei",  # In PATH
        ]
        
        for binary_path in possible_paths:
            try:
                expanded_path = os.path.expanduser(binary_path) if binary_path.startswith("~") else binary_path
                if os.path.isabs(expanded_path) or expanded_path.startswith("/"):
                    if os.path.exists(expanded_path) and os.access(expanded_path, os.X_OK):
                        nuclei_binary = expanded_path
                        logger.info(f"Found nuclei binary at: {nuclei_binary}")
                        break
                else:
                    # Check if command exists in PATH using shutil.which (more reliable)
                    found_path = shutil.which(binary_path)
                    if found_path:
                        nuclei_binary = found_path
                        logger.info(f"Found nuclei binary in PATH at: {nuclei_binary}")
                        break
            except Exception as e:
                logger.debug(f"Error checking nuclei path {binary_path}: {e}")
                continue
        
        # CRITICAL: If still not found, check if Go is installed and try to install nuclei
        if not nuclei_binary:
            # Check if Go is available
            go_binary = shutil.which("go") or "/usr/local/go/bin/go"
            if os.path.exists(go_binary) and os.access(go_binary, os.X_OK):
                logger.warning(f"nuclei binary not found, but Go is available. Attempting to install nuclei...")
                try:
                    # Try to install nuclei using Go
                    install_result = await asyncio.to_thread(
                        subprocess.run,
                        [go_binary, "install", "-v", "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"],
                        capture_output=True,
                        text=True,
                        timeout=120,  # 2 minutes for installation
                        env={**os.environ, "GOBIN": "/usr/local/bin", "GOPATH": "/tmp/go"}
                    )
                    if install_result.returncode == 0 and os.path.exists("/usr/local/bin/nuclei"):
                        nuclei_binary = "/usr/local/bin/nuclei"
                        logger.info(f"Successfully installed and found nuclei binary at: {nuclei_binary}")
                    else:
                        logger.error(f"Failed to install nuclei: {install_result.stderr}")
                except Exception as install_error:
                    logger.error(f"Error installing nuclei: {install_error}")
        
        if not nuclei_binary:
            error_msg = "Nuclei binary not found or not executable. Please install nuclei: go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest (ensure ~/go/bin is in PATH)"
            logger.error(f"nuclei binary not found: {error_msg}")
            return {
                "tool_name": "nuclei",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "nuclei -version",
                "success": False,
            }
        
        try:
            # Verify binary is actually executable by running version check
            # CRITICAL: Some versions of nuclei may exit with non-zero even on success
            # So we check stdout for version info, not just exit code
            check_result = await asyncio.to_thread(subprocess.run,
                [nuclei_binary, "-version"],
                capture_output=True,
                timeout=10,  # Increased timeout to 10s
                text=True
            )
            
            # Check if we got version output (this is the real indicator of success)
            has_version_output = check_result.stdout and "nuclei" in check_result.stdout.lower()
            
            if not has_version_output:
                # No version output - check stderr for errors
                if check_result.stderr:
                    stderr_lower = check_result.stderr.lower()
                    if any(keyword in stderr_lower for keyword in ["not found", "cannot execute", "permission denied", "no such file"]):
                        raise FileNotFoundError(f"nuclei binary not executable: {check_result.stderr}")
                    # Log stderr but don't fail if it's just a warning
                    logger.warning(f"nuclei version check stderr: {check_result.stderr[:200]}")
                
                # If no stdout and no clear error in stderr, check if binary exists and is executable
                if not check_result.stdout:
                    # Check if binary file actually exists and is executable
                    if os.path.exists(nuclei_binary) and os.access(nuclei_binary, os.X_OK):
                        # Binary exists and is executable, but version check failed
                        # This might be a version display issue - log warning but continue
                        logger.warning(f"nuclei version check returned no output, but binary exists and is executable. Continuing anyway.")
                    else:
                        raise FileNotFoundError("nuclei version check returned no output and binary may not be executable")
            
            # If we have version output, log it and continue (even if exit code is non-zero)
            if has_version_output:
                logger.info(f"nuclei version check successful: {check_result.stdout.strip()[:100]}")
            else:
                # This shouldn't happen due to check above, but be safe
                logger.warning(f"nuclei version check ambiguous: exit_code={check_result.returncode}, stdout={check_result.stdout[:100] if check_result.stdout else 'None'}, stderr={check_result.stderr[:100] if check_result.stderr else 'None'}")
                
        except subprocess.TimeoutExpired:
            logger.error(f"nuclei version check timed out after 10s - binary may be slow or unresponsive")
            return {
                "tool_name": "nuclei",
                "output": "",
                "exit_code": -1,
                "error": "Nuclei binary version check timed out. The binary may be corrupted or incompatible.",
                "command": "nuclei -version",
                "success": False,
            }
        except FileNotFoundError as e:
            logger.error(f"nuclei binary verification failed: {e}")
            return {
                "tool_name": "nuclei",
                "output": "",
                "exit_code": -1,
                "error": f"Nuclei binary not found or not executable: {str(e)}. Please ensure nuclei is installed correctly.",
                "command": "nuclei -version",
                "success": False,
            }
        except Exception as e:
            logger.error(f"Unexpected error during nuclei version check: {e}", exc_info=True)
            # Don't fail completely - try to continue if binary exists
            logger.warning(f"Continuing despite version check error - will attempt to run nuclei anyway")
        
        # Determine severity levels based on scan level
        # Using only flags supported by Nuclei v3.4.10
        severity_map = {
            "basic": "low,medium",
            "pro": "low,medium,high",
            "advanced": "low,medium,high,critical,info",
        }
        
        severity_levels = severity_map.get(scan_level, severity_map["basic"])
        
        # Get profile from kwargs and look up tags
        profile = kwargs.get("profile")
        template_tags = None
        
        if profile and profile in NUCLEI_PROFILE_TAGS:
            tags_list = NUCLEI_PROFILE_TAGS[profile]
            template_tags = ",".join(tags_list)
            logger.info(f"Using Nuclei profile '{profile}' with tags: {tags_list}")
        else:
            # Fallback to scan_level-based tags if profile not provided or not found
            # CRITICAL: Always include "xss" tag to ensure XSS detection works
            # NOTE: "headless" removed from both pro and advanced due to Chrome timeout issues
            tags_map = {
                "basic": "cve,vulnerability,exposure,xss",  # Fast for basic
                "pro": "cve,vulnerability,exposure,misconfig,xss,sqli,ssrf,ssti,xxe,lfi,rfi,path-traversal,cmdi",  # Removed headless - completes in ~5-10 min
                "advanced": "cve,vulnerability,exposure,misconfig,xss,sqli,ssrf,ssti,xxe,lfi,rfi,path-traversal,cmdi,idor,csrf,cors,tech,ssl",  # Removed headless due to Chrome timeout issues
            }
            template_tags = tags_map.get(scan_level, tags_map["basic"])
            
            # Log the tags being used
            logger.info(f"Using fallback tags for {scan_level} scan: {template_tags}")
        
        # Nuclei v3.4.10 command flags:
        # -severity: filter by severity levels
        # -tags: filter by template tags (cve, vulnerability, etc.)
        # -jsonl: output JSON Lines format
        # -silent: suppress non-JSON output
        # -rate-limit: limit requests per second (lower for basic scans)
        # -timeout: timeout per request in seconds
        # -retries: number of retries for failed requests
        # NOTE: WE DO NOT USE -u HERE, we use STDIN to feed multiple URLs
        
        # Adjust rate limit based on scan level (basic = low rate, pro/advanced = higher)
        rate_limit = "30" if scan_level == "basic" else "50"
        
        cmd = [
            nuclei_binary,  # Use the found binary path
            "-severity", severity_levels,
            "-jsonl",
            "-silent",
            "-rate-limit", rate_limit,  # Lower rate for basic scans
            "-timeout", "10",  # 10 second timeout per request
            "-retries", "1",  # Retry once on failure
            "-bulk-size", "25",  # Reduce bulk size to lower memory usage (default is 25, but explicit helps)
            "-c", "50",  # Reduce concurrency to 50 (default is 25, but we want to be conservative for memory)
        ]
        
        # Add -tags argument only if we have tags
        if template_tags:
            cmd.extend(["-tags", template_tags])
        
        logger.info("Nuclei v3.4.10 command for scan %s: %s (targets: %d)", 
                   scan_job_id, " ".join(cmd), len(all_urls))
        
        # Get timeout from kwargs (set by backend via runner_client from scan_timeouts.py)
        # CRITICAL: This MUST come from kwargs which is set by backend via runner_client
        # If not provided, fall back to default but log a warning
        base_timeout = kwargs.get("timeout_seconds")
        if base_timeout is None:
            # CRITICAL: Use scan-level appropriate defaults instead of generic 300s
            scan_level_lower = scan_level.lower() if scan_level else "basic"
            if scan_level_lower == "advanced":
                default_timeout = 1800  # 30 minutes for advanced
            elif scan_level_lower == "pro":
                default_timeout = 1800  # 30 minutes for pro
            else:
                default_timeout = 300  # 5 minutes for basic
            logger.warning(
                f"Nuclei scan {scan_job_id}: timeout_seconds not provided in kwargs! "
                f"Using scan-level default {default_timeout}s for {scan_level}. "
                f"This may cause premature timeouts. "
                f"Available kwargs keys: {list(kwargs.keys())}, scan_level: {scan_level}"
            )
            base_timeout = default_timeout
        
        # Adjust timeout for multiple URLs if needed
        # CRITICAL: Nuclei needs more time per URL when scanning with multiple templates
        # Use at least 30 seconds per URL (was 10s, too short for comprehensive scanning)
        timeout_seconds = max(base_timeout, min(3600, len(all_urls) * 30)) # Ensure at least 30s per URL, max 1h
        logger.info(
            f"Nuclei timeout for {len(all_urls)} URLs: {timeout_seconds}s "
            f"(base from kwargs: {base_timeout}s, scan_level: {scan_level})"
        )
        
        try:
            # Feed URLs via stdin
            urls_input = "\n".join(all_urls)
            
            # CRITICAL: Log what we're about to send to nuclei
            logger.info(
                f"Nuclei scan {scan_job_id}: About to execute with {len(all_urls)} URLs, timeout={timeout_seconds}s"
            )
            if len(all_urls) > 0:
                logger.info(
                    f"Nuclei scan {scan_job_id}: URLs to scan (first 10): {all_urls[:10]}"
                )
            logger.debug(
                f"Nuclei scan {scan_job_id}: Full command: {' '.join(cmd)}"
            )
            
            # Track execution start time
            import time
            exec_start_time = time.time()

            # Use asyncio.to_thread to prevent blocking event loop
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                input=urls_input,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )

            exec_duration = time.time() - exec_start_time
            logger.info(
                f"Nuclei scan {scan_job_id}: Execution completed in {exec_duration:.2f}s "
                f"(timeout was {timeout_seconds}s, exit_code={result.returncode})"
            )
            
            # CRITICAL: If execution was suspiciously fast, log warning
            if exec_duration < 5.0 and len(all_urls) > 5:
                logger.warning(
                    f"Nuclei scan {scan_job_id}: Execution completed in {exec_duration:.2f}s which is "
                    f"suspiciously fast for {len(all_urls)} URLs. This might indicate an error."
            )
            
            # Calculate sizes
            stdout_bytes = len(result.stdout.encode("utf-8")) if result.stdout else 0
            stderr_bytes = len(result.stderr.encode("utf-8")) if result.stderr else 0
            exit_code = result.returncode
            
            # Log execution summary - clear distinction between success and failure
            logger.info(
                "Nuclei completed for scan %s: exit_code=%s, stdout_bytes=%d, stderr_bytes=%d",
                scan_job_id, exit_code, stdout_bytes, stderr_bytes
            )
            
            # Handle non-zero exit codes
            # Nuclei may exit with non-zero even when scan completes successfully (e.g., no findings)
            # Only treat as error if exit_code is non-zero AND we have no output AND stderr indicates failure
            is_error = False
            error_msg = None
            
            if exit_code != 0:
                # Check if we have useful output despite non-zero exit
                if stdout_bytes > 0:
                    # We have output, so the scan found vulnerabilities (this is success)
                    logger.info(
                        "Nuclei scan %s completed with exit_code=%s but found %d bytes of output (vulnerabilities detected, treating as success)",
                        scan_job_id, exit_code, stdout_bytes
                    )
                elif result.stderr:
                    # Check stderr for actual errors vs normal "no results" messages
                    stderr_lower = result.stderr.lower()
                    # These are normal messages, not errors
                    normal_messages = ["no results found", "scan completed", "no templates found", "target is not reachable"]
                    if any(msg in stderr_lower for msg in normal_messages):
                        logger.info(
                            "Nuclei scan %s completed with exit_code=%s: %s (treating as success - no vulnerabilities found)",
                            scan_job_id, exit_code, stderr_lower[:100]
                        )
                    elif any(keyword in stderr_lower for keyword in ["error", "failed", "fatal", "cannot", "invalid"]):
                        is_error = True
                        error_msg = f"Nuclei exited with code {exit_code}: {result.stderr[:200]}"
                        logger.warning("Nuclei scan %s failed: %s", scan_job_id, error_msg)
                    else:
                        # Unknown stderr message, but no output - likely just informational
                        logger.info(
                            "Nuclei scan %s completed with exit_code=%s (stderr: %s, treating as success)",
                            scan_job_id, exit_code, result.stderr[:100]
                        )
                else:
                    # No output and no stderr - might be unreachable target or no findings
                    logger.info(
                        "Nuclei scan %s completed with exit_code=%s and no output (no vulnerabilities found or target unreachable, treating as success)",
                        scan_job_id, exit_code
                    )
            
            if is_error:
                # Return error in result structure
                return {
                    "tool_name": "nuclei",
                    "output": result.stdout,  # Still return stdout in case there's partial output
                    "exit_code": exit_code,
                    "command": " ".join(cmd),
                    "error": error_msg,
                }
            
            # Success case: distinguish between "found vulnerabilities" and "no findings"
            if stdout_bytes > 0:
                stdout_preview = result.stdout[:500]
                logger.debug("Nuclei stdout preview for scan %s: %s", scan_job_id, stdout_preview)
                logger.info(
                    "Nuclei scan %s successful: found %d bytes of output (vulnerabilities detected)",
                    scan_job_id, stdout_bytes
                )
            else:
                # No output = no findings (this is a valid, successful outcome)
                if result.stderr:
                    # Check if stderr indicates "no results found" (normal) vs actual error
                    stderr_lower = result.stderr.lower()
                    if "no results found" in stderr_lower or "scan completed" in stderr_lower:
                        logger.info(
                            "Nuclei scan %s successful: no vulnerabilities found (target is clean)",
                            scan_job_id
                        )
                    else:
                        logger.debug("Nuclei stderr for scan %s: %s", scan_job_id, result.stderr[:500])
                else:
                    logger.info(
                        "Nuclei scan %s successful: no vulnerabilities found (target is clean)",
                        scan_job_id
                    )
            
            return {
                "tool_name": "nuclei",
                "output": result.stdout,
                "exit_code": exit_code,
                "command": " ".join(cmd),
                "success": True,  # Explicitly mark as successful
                "execution_time": exec_duration,  # Accurate subprocess-only execution time
            }
        except subprocess.TimeoutExpired:
            # Calculate execution time even on timeout
            exec_duration = time.time() - exec_start_time
            logger.warning(f"Nuclei scan {scan_job_id} timed out after {timeout_seconds} seconds ({timeout_seconds // 60} minutes, actual: {exec_duration:.2f}s)")
            return {
                "tool_name": "nuclei",
                "output": "",
                "exit_code": -1,
                "error": f"Tool execution timed out after {timeout_seconds} seconds ({timeout_seconds // 60} minutes)",
                "command": " ".join(cmd),
                "timed_out": True,
                "execution_time": exec_duration,  # Actual time before timeout
            }
        except Exception as e:
            logger.error(f"Nuclei execution error: {e}")
            return {
                "tool_name": "nuclei",
                "output": "",
                "exit_code": -1,
                "error": f"Nuclei execution failed: {str(e)}",
                "command": " ".join(cmd),
            }
    
    async def _run_nmap(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run Nmap port scanner
        
        Optional kwargs:
            profile: profile name from tool config (e.g., "top_ports", "full_ports_scripts")
                    Currently not used but available for future implementation
        """
        """Run Nmap port scanner"""
        from urllib.parse import urlparse
        
        parsed = urlparse(target_url)
        hostname = parsed.hostname
        
        if not hostname:
            raise ValueError(f"Invalid URL: {target_url}")
        
        # Determine scan intensity based on level
        # OPTIMIZED: Reduced port counts to prevent timeouts while maintaining good coverage
        # - Basic: Top 50 ports (fast, covers ~80% of common services)
        # - Pro: Top 100 ports (balanced, covers ~95% of common services)
        # - Advanced: Top 500 ports (comprehensive, covers ~99% of services)
        scan_map = {
            "basic": [
                "-sT",              # TCP connect scan (no root needed)
                "-Pn",              # Skip host discovery
                "--top-ports", "50",  # Reduced from 100 for speed
                "-sV",              # Version detection
                "--version-intensity", "2",  # Light version probing
                "-T4",              # Aggressive timing (faster)
            ],
            "pro": [
                "-sT",              # TCP connect scan
                "-Pn",              # Skip host discovery
                "--top-ports", "100",  # Reduced from 1000 (critical fix!)
                "-sV",              # Version detection
                "--version-intensity", "3",  # Medium version probing
                "-sC",              # Default scripts
                "-T4",              # Aggressive timing
            ],
            "advanced": [
                "-sT",              # TCP connect scan
                "-Pn",              # Skip host discovery
                "--top-ports", "500",  # Reduced from 10000
                "-sV",              # Version detection
                "--version-intensity", "5",  # Thorough version probing
                "-sC",              # Default scripts
                "-A",               # Enable OS detection, traceroute
                "-T4",              # Aggressive timing
            ],
        }
        
        scan_args = scan_map.get(scan_level, scan_map["basic"])
        
        cmd = ["nmap", "-oX", "-"] + scan_args + [hostname]
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            # Track execution start time
            import time
            exec_start_time = time.time()
            
            # Use asyncio.to_thread to prevent blocking event loop
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            
            exec_duration = time.time() - exec_start_time
            logger.info(f"nmap execution completed in {exec_duration:.2f}s for {hostname}")
            
            return {
                "tool_name": "nmap",
                "output": result.stdout or "",
                "exit_code": result.returncode,
                "command": " ".join(cmd),
                "success": result.returncode == 0,
                "execution_time": exec_duration,  # Accurate subprocess-only execution time
            }
        except subprocess.TimeoutExpired:
            # Calculate execution time even on timeout
            exec_duration = time.time() - exec_start_time
            logger.warning(f"nmap execution timed out after {timeout_seconds} seconds for {hostname} (actual: {exec_duration:.2f}s)")
            return {
                "tool_name": "nmap",
                "output": "",
                "exit_code": -1,
                "error": f"Tool execution timed out after {timeout_seconds} seconds",
                "command": " ".join(cmd),
                "timed_out": True,
                "success": False,
                "execution_time": exec_duration,  # Actual time before timeout
            }
        except FileNotFoundError:
            logger.error("nmap binary not found in PATH")
            return {
                "tool_name": "nmap",
                "output": "",
                "exit_code": -1,
                "error": "nmap binary not found. Please install nmap: sudo apt-get install nmap (or brew install nmap on macOS)",
                "command": " ".join(cmd),
                "success": False,
            }
        except Exception as e:
            logger.error(f"nmap execution failed: {e}", exc_info=True)
            return {
                "tool_name": "nmap",
                "output": "",
                "exit_code": -1,
                "error": f"nmap execution failed: {str(e)}",
                "command": " ".join(cmd),
                "success": False,
            }
    
    async def _run_sslscan(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """Run SSL/TLS scanner"""
        from urllib.parse import urlparse
        
        parsed = urlparse(target_url)
        hostname = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        
        if not hostname:
            raise ValueError(f"Invalid URL: {target_url}")
        
        target = f"{hostname}:{port}"
        
        # Note: sslscan doesn't support --json flag, it outputs text with ANSI colors
        cmd = ["sslscan", target]
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            
            return {
                "tool_name": "sslscan",
                "output": result.stdout,
                "exit_code": result.returncode,
                "command": " ".join(cmd),
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "sslscan",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out",
            }
        except FileNotFoundError:
            # Fallback to openssl if sslscan not available
            logger.warning("sslscan not found, using openssl fallback")
            return await self._run_openssl_fallback(hostname, port)
    
    async def _run_openssl_fallback(self, hostname: str, port: int) -> Dict:
        """Fallback SSL check using openssl"""
        cmd = [
            "openssl", "s_client",
            "-connect", f"{hostname}:{port}",
            "-showcerts",
        ]
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                input="",  # Close connection immediately
            )
            
            return {
                "tool_name": "openssl",
                "output": result.stdout,
                "exit_code": result.returncode,
                "command": " ".join(cmd),
            }
        except Exception as e:
            return {
                "tool_name": "openssl",
                "output": "",
                "exit_code": -1,
                "error": str(e),
            }
    
    # TODO: Vulnerability classes covered by httpx:
    # - HTTP Surface Discovery (identifies endpoints, status codes, technologies)
    # - Content Discovery (via response analysis)
    # Note: httpx is primarily a reconnaissance tool, not a vulnerability scanner
    async def _run_httpx(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run httpx HTTP surface scanner (ProjectDiscovery httpx)
        
        Optional kwargs:
            intensity: "low", "medium", "high" (from tool config, currently not used but available)
        """
        # Check if ProjectDiscovery httpx is installed
        # Note: Python httpx library also has a CLI, so we need to verify it's the right one
        # Python httpx errors on -u flag, ProjectDiscovery httpx supports it
        httpx_binary = None
        
        # Try common locations for ProjectDiscovery httpx
        # Check ~/go/bin first (most common location) before PATH to avoid Python httpx
        # Also check ~/.local/bin which is common in user installations
        possible_paths = [
            os.path.expanduser("~/go/bin/httpx"),  # Go bin directory (check first!)
            os.path.expanduser("~/.local/bin/httpx"),  # User local bin (common location)
            "/usr/local/bin/httpx",
            "/usr/local/bin/httpx-projectdiscovery",
            "/usr/bin/httpx",  # System bin
            "httpx",  # In PATH (check last to avoid Python httpx)
        ]
        
        for binary_path in possible_paths:
            try:
                test_cmd = [binary_path, "-u", "https://example.com", "-silent", "-json"]
                test_result = await asyncio.to_thread(subprocess.run,
                    test_cmd,
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                # Python httpx will error with "No such option: -u" or "required dependencies"
                # ProjectDiscovery httpx will either succeed or fail with different error
                stderr_lower = test_result.stderr.lower()
                if ("no such option" not in stderr_lower and 
                    "error: no such option" not in stderr_lower and
                    "required dependencies" not in stderr_lower and
                    "could not run" not in stderr_lower):
                    httpx_binary = binary_path
                    logger.info(f"Detected ProjectDiscovery httpx binary at: {binary_path}")
                    break
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.debug(f"httpx detection test failed for {binary_path}: {e}")
                continue
        
        if not httpx_binary:
            error_msg = "ProjectDiscovery httpx binary not found. The system has Python httpx (HTTP client) installed, but we need ProjectDiscovery httpx (security scanner). Install with: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest (or download from https://github.com/projectdiscovery/httpx/releases). After installation, ensure ~/go/bin is in your PATH."
            logger.error(f"httpx binary not found: {error_msg}")
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "httpx -u <url> -json",
                "success": False,
            }
        
        # httpx (ProjectDiscovery) command flags:
        # -u: target URL (required)
        # -json: output JSON format (one JSON object per line)
        # -follow-redirects: follow HTTP redirects
        # -status-code: include HTTP status code in output
        # -title: extract page title
        # -tech-detect: detect web technologies
        # -tls-probe: probe TLS/SSL information
        # -silent: suppress non-JSON output
        cmd = [
            httpx_binary,
            "-u", target_url,
            "-json",
            "-follow-redirects",
            "-status-code",
            "-title",
            "-tech-detect",
            "-tls-probe",
            "-silent",
        ]
        
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        logger.info("httpx command for scan %s: %s", scan_job_id, " ".join(cmd))
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            
            exit_code = result.returncode
            stdout_bytes = len(result.stdout.encode("utf-8")) if result.stdout else 0
            stderr_bytes = len(result.stderr.encode("utf-8")) if result.stderr else 0
            
            logger.info(
                "httpx completed for scan %s: exit_code=%s, stdout_bytes=%d, stderr_bytes=%d",
                scan_job_id, exit_code, stdout_bytes, stderr_bytes
            )
            
            # httpx may exit with non-zero even when it successfully probes URLs
            # Consider it successful if we have output OR if exit code is just a warning
            # Only treat as error if exit_code is non-zero AND we have no output AND stderr indicates failure
            is_error = False
            error_msg = None
            
            if exit_code != 0:
                # Check if we have useful output despite non-zero exit
                if stdout_bytes > 0:
                    # We have output, so the scan was partially successful
                    logger.info(
                        "httpx scan %s completed with exit_code=%s but produced %d bytes of output (treating as success)",
                        scan_job_id, exit_code, stdout_bytes
                    )
                elif result.stderr:
                    # Check stderr for actual errors vs warnings
                    stderr_lower = result.stderr.lower()
                    if any(keyword in stderr_lower for keyword in ["error", "failed", "fatal", "cannot"]):
                        is_error = True
                        error_msg = f"httpx exited with code {exit_code}: {result.stderr[:200]}"
                        logger.warning("httpx scan %s failed: %s", scan_job_id, error_msg)
                    else:
                        # Likely just a warning, not a fatal error
                        logger.info(
                            "httpx scan %s completed with exit_code=%s (likely no reachable URLs, treating as success)",
                            scan_job_id, exit_code
                        )
                else:
                    # No output and no stderr - might be unreachable target
                    logger.info(
                        "httpx scan %s completed with exit_code=%s and no output (target may be unreachable, treating as success)",
                        scan_job_id, exit_code
                    )
            
            if is_error:
                return {
                    "tool_name": "httpx",
                    "output": result.stdout,  # Still return any partial output
                    "exit_code": exit_code,
                    "error": error_msg,
                    "command": " ".join(cmd),
                    "success": False,
                }
            
            # Success case (even with non-zero exit if we have output)
            if stdout_bytes > 0:
                logger.info(
                    "httpx scan %s successful: found %d bytes of output",
                    scan_job_id, stdout_bytes
                )
            else:
                logger.info("httpx scan %s completed: no output (target may be unreachable or no URLs found)", scan_job_id)
            
            return {
                "tool_name": "httpx",
                "output": result.stdout,
                "exit_code": exit_code,  # Return actual exit code even if we treat as success
                "command": " ".join(cmd),
                "success": True,  # Explicitly mark as successful
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out after 10 minutes",
                "command": " ".join(cmd),
                "success": False,
                "timed_out": True,
            }
        except Exception as e:
            logger.error(f"httpx execution error: {e}", exc_info=True)
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": f"httpx execution failed: {str(e)}",
                "command": " ".join(cmd),
                "success": False,
            }
    
    # TODO: Vulnerability classes covered by ffuf:
    # - Content Discovery (finds hidden files, directories, endpoints)
    # - Information Disclosure (via discovered paths like .git, .env, backup files)
    # Note: ffuf is a content discovery tool, findings may reveal attack surface for other vulnerability classes
    async def _run_ffuf(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run ffuf content discovery scanner
        
        Optional kwargs:
            wordlist: wordlist filename from tool config (e.g., "ffuf-pro.txt", "ffuf-advanced.txt")
                     If provided, will use wordlists/{wordlist} instead of default
            timeout_seconds: timeout in seconds (default: 900 for 15 minutes)
        """
        # Check if ffuf is installed
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        logger.info(f"Checking ffuf availability for scan {scan_job_id}")
        
        # Try common locations for ffuf (in order of preference)
        ffuf_binary = None
        possible_paths = [
            os.path.expanduser("~/go/bin/ffuf"),  # Go bin directory (most common)
            os.path.expanduser("~/.local/thandev-tools/bin/ffuf"),  # Local tools directory
            "/usr/local/bin/ffuf",
            "ffuf",  # In PATH
        ]
        
        for binary_path in possible_paths:
            try:
                expanded_path = os.path.expanduser(binary_path) if binary_path.startswith("~") else binary_path
                if os.path.isabs(expanded_path) or expanded_path.startswith("/"):
                    if os.path.exists(expanded_path) and os.access(expanded_path, os.X_OK):
                        ffuf_binary = expanded_path
                        logger.info(f"Found ffuf binary at: {ffuf_binary}")
                        break
                else:
                    # Check if command exists in PATH
                    check_result = await asyncio.to_thread(subprocess.run,
                        ["which", binary_path],
                        capture_output=True,
                        timeout=2,
                        text=True
                    )
                    if check_result.returncode == 0:
                        ffuf_binary = check_result.stdout.strip()
                        logger.info(f"Found ffuf binary at: {ffuf_binary}")
                        break
            except Exception:
                continue
        
        if not ffuf_binary:
            error_msg = "ffuf binary not found. Please install ffuf: go install -v github.com/ffuf/ffuf/v2@latest (ensure ~/go/bin is in PATH)"
            logger.error(f"ffuf binary not found for scan {scan_job_id}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "ffuf -V",
                "timed_out": False,
            }
        
        # Verify ffuf works
        try:
            check_result = await asyncio.to_thread(subprocess.run,
                [ffuf_binary, "-V"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if check_result.returncode != 0:
                error_msg = f"ffuf command failed with exit code {check_result.returncode}: {check_result.stderr}"
                logger.error(f"ffuf binary check failed for scan {scan_job_id}: {error_msg}")
                raise FileNotFoundError("ffuf command failed")
            logger.info(f"ffuf binary verified for scan {scan_job_id}: {check_result.stdout.strip()}")
        except FileNotFoundError:
            error_msg = "ffuf binary not found in PATH. Please install ffuf: go install -v github.com/ffuf/ffuf/v2@latest"
            logger.error(f"ffuf binary not found for scan {scan_job_id}. Check PATH or install ffuf.")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "ffuf -V",
                "timed_out": False,
            }
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            error_msg = f"ffuf binary check failed: {str(e)}"
            logger.error(f"ffuf binary check error for scan {scan_job_id}: {error_msg}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "ffuf -V",
                "timed_out": False,
            }
        
        # ffuf command flags:
        # -u: target URL with FUZZ placeholder
        # -w: wordlist file path
        # -mc: match status codes (200, 204, 301, 302, 307, 401, 403)
        # -json: output JSON format
        # 
        # Wordlist path configuration:
        # - Can be specified via tool config (kwargs["wordlist"]) or env var
        # - Default: repo_root/wordlists/ffuf-small.txt
        # - Priority: tool config > env var > default
        wordlist_filename = kwargs.get("wordlist", None)
        if wordlist_filename:
            # Use wordlist from tool config (e.g., "ffuf-pro.txt" -> wordlists/ffuf-pro.txt)
            wordlist_path = os.path.join(os.getenv("WORDLISTS_DIR", "/opt/thandev/wordlists"), wordlist_filename)
            logger.info(f"Using wordlist from tool config: {wordlist_filename}")
        else:
            # Fall back to env var or default
            wordlist_path = os.getenv(
                "THANDEV_FFUF_WORDLIST",
                os.path.join(os.getenv("WORDLISTS_DIR", "/opt/thandev/wordlists"), "ffuf-small.txt"),
            )
        
        # Verify wordlist exists before running ffuf
        if not os.path.exists(wordlist_path):
            error_msg = f"Wordlist not found: {wordlist_path}. Please ensure the wordlist exists or set THANDEV_FFUF_WORDLIST environment variable."
            logger.error(f"ffuf wordlist not found for scan {scan_job_id}: {wordlist_path}")
            logger.error(f"  Expected location: {wordlist_path}")
            logger.error(f"  BASE_DIR: {BASE_DIR}")
            logger.error(f"  Wordlist filename from config: {wordlist_filename}")
            logger.error(f"  THANDEV_FFUF_WORDLIST env var: {os.getenv('THANDEV_FFUF_WORDLIST', 'not set')}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": f"ffuf -u {target_url}/FUZZ -w <wordlist>",
                "timed_out": False,
            }
        
        logger.info(f"ffuf wordlist verified for scan {scan_job_id}: {wordlist_path} ({os.path.getsize(wordlist_path)} bytes)")
        
        # PR-4C: Baseline detection to filter out 404/wildcard responses
        baseline = None
        try:
            import random
            import string
            import requests
            
            # Generate random baseline path
            random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            baseline_path = f"/THANDEV-BASELINE-{random_suffix}"
            baseline_url = f"{target_url.rstrip('/')}{baseline_path}"
            
            logger.info(f"Performing baseline request for ffuf: {baseline_url}")
            
            # Make baseline request
            baseline_resp = requests.get(
                baseline_url,
                timeout=10,
                allow_redirects=True,
                headers={"User-Agent": "Thandev-Baseline/1.0"},
            )
            
            # Calculate baseline signature
            response_text = baseline_resp.text
            baseline = {
                "status_code": baseline_resp.status_code,
                "content_length": len(baseline_resp.content),
                "word_count": len(response_text.split()),
                "line_count": len(response_text.splitlines()),
                "content_hash": hash(response_text[:1000]),  # Hash first 1000 chars
            }
            
            logger.info(
                f"Baseline signature for {target_url}: status={baseline['status_code']}, "
                f"size={baseline['content_length']}, words={baseline['word_count']}, "
                f"lines={baseline['line_count']}"
            )
        except Exception as e:
            logger.warning(f"Failed to establish baseline for ffuf: {e}. Will filter by status code only.")
            baseline = None
        
        # Get timeout from config (default: 5 minutes)
        default_timeout = 300  # 5 minutes
        timeout = kwargs.get("timeout_seconds", default_timeout)
        
        # PR-4C: Add filters to exclude baseline and 404
        cmd = [
            ffuf_binary,  # Use the found binary path
            "-u", f"{target_url}/FUZZ",
            "-w", wordlist_path,
            "-mc", "200,204,301,302,307,401,403",  # Only allow relevant status codes
            "-json",
        ]
        
        # Add size filter if baseline available
        if baseline:
            # Exclude responses matching baseline size (with small tolerance)
            baseline_size = baseline["content_length"]
            if baseline_size > 0:
                # Exclude responses within 5% of baseline size
                tolerance = max(10, int(baseline_size * 0.05))
                min_size = baseline_size - tolerance
                max_size = baseline_size + tolerance
                cmd.extend(["-fs", f"{min_size}-{max_size}"])  # Filter by size
                logger.info(f"Added size filter to exclude baseline: {min_size}-{max_size} bytes")
        
        logger.info("ffuf command for scan %s: %s (timeout: %d seconds, wordlist: %s)", 
                   scan_job_id, " ".join(cmd), timeout, wordlist_path)
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            exit_code = result.returncode
            stdout_bytes = len(result.stdout.encode("utf-8")) if result.stdout else 0
            stderr_bytes = len(result.stderr.encode("utf-8")) if result.stderr else 0
            
            logger.info(
                "ffuf completed for scan %s: exit_code=%s, stdout_bytes=%d, stderr_bytes=%d",
                scan_job_id, exit_code, stdout_bytes, stderr_bytes
            )
            
            # ffuf may exit with non-zero even when it finds paths
            # Consider it successful if we have output
            is_error = False
            error_msg = None
            
            if exit_code != 0:
                if stdout_bytes > 0:
                    # We have output, so the scan found some paths
                    logger.info(
                        "ffuf scan %s completed with exit_code=%s but produced %d bytes of output (treating as success)",
                        scan_job_id, exit_code, stdout_bytes
                    )
                elif result.stderr:
                    stderr_lower = result.stderr.lower()
                    if any(keyword in stderr_lower for keyword in ["error", "failed", "fatal", "cannot", "not found"]):
                        is_error = True
                        error_msg = f"ffuf exited with code {exit_code}: {result.stderr[:200]}"
                        logger.warning("ffuf scan %s failed: %s", scan_job_id, error_msg)
                    else:
                        logger.info(
                            "ffuf scan %s completed with exit_code=%s (no paths found, treating as success)",
                            scan_job_id, exit_code
                        )
                else:
                    logger.info(
                        "ffuf scan %s completed with exit_code=%s and no output (no paths found, treating as success)",
                        scan_job_id, exit_code
                    )
            
            if is_error:
                return {
                    "tool_name": "ffuf",
                    "output": result.stdout,  # Still return any partial output
                    "exit_code": exit_code,
                    "error": error_msg,
                    "command": " ".join(cmd),
                    "timed_out": False,
                }
            
            # Success case
            if stdout_bytes > 0:
                logger.info(
                    "ffuf scan %s successful: found %d bytes of output (paths discovered)",
                    scan_job_id, stdout_bytes
                )
            else:
                logger.info("ffuf scan %s completed: no paths discovered (exit_code=%s, stderr_bytes=%d)", 
                           scan_job_id, exit_code, stderr_bytes)
            
            # PR-4C: Store baseline in result for filtering during parsing
            result_dict = {
                "tool_name": "ffuf",
                "output": result.stdout,
                "exit_code": exit_code,
                "command": " ".join(cmd),
                "timed_out": False,
            }
            
            if baseline:
                result_dict["baseline"] = baseline
                logger.info(f"Stored baseline signature in ffuf result for filtering")
            
            return result_dict
        except subprocess.TimeoutExpired as exc:
            logger.warning("ffuf scan %s timed out after %d seconds (%d minutes). Results may be partial.", 
                          scan_job_id, timeout, timeout // 60)
            logger.warning("  Command: %s", " ".join(cmd))
            logger.warning("  Wordlist: %s", wordlist_path)
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": None,  # None indicates timeout (not a normal exit code)
                "error": f"Tool execution timed out after {timeout} seconds ({timeout // 60} minutes)",
                "command": " ".join(cmd),
                "timed_out": True,
            }
        except Exception as e:
            logger.error(f"ffuf execution error for scan {scan_job_id}: {e}", exc_info=True)
            logger.error(f"  Command: {' '.join(cmd)}")
            logger.error(f"  Wordlist: {wordlist_path}")
            logger.error(f"  Target URL: {target_url}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": f"ffuf execution failed: {str(e)}",
                "command": " ".join(cmd),
                "timed_out": False,
            }
    
    # TODO: Vulnerability classes covered by dalfox:
    # - XSS (Cross-Site Scripting) - primary focus
    # - DOM XSS (via deep-domxss flag)
    # Note: dalfox is specifically designed for XSS detection and exploitation
    async def _run_dalfox(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run Dalfox XSS scanner
        
        Optional kwargs:
            timeout_seconds: timeout in seconds (default: 900 for Pro, 1800 for Advanced)
        """
        from app.utils.param_harvester import ParamHarvester, create_fallback_targets
        
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        scan_job_dir = kwargs.get("scan_job_dir")
        
        # 1. Harvest parameterized requests from ZAP/crawler outputs first
        logger.info(f"Harvesting parameterized endpoints for Dalfox scan {scan_job_id}: {target_url}")
        harvester = ParamHarvester(job_dir=scan_job_dir)
        
        # Try to harvest from job directory (ZAP output, etc.)
        if scan_job_dir:
            harvested_count = harvester.harvest_from_job_dir()
            logger.info(f"Dalfox scan {scan_job_id}: Harvested {harvested_count} parameterized requests from job dir")
        
        # 2. Also crawl to get additional endpoints
        logger.info(f"Crawling target for Dalfox scan {scan_job_id}: {target_url} (scan_level: {scan_level})")
        all_urls, parameterized_urls = await self._crawl_target(target_url, scan_job_id, scan_level)
        
        # Add crawler results to harvester
        if parameterized_urls:
            crawler_count = harvester.harvest_from_crawler_output(parameterized_urls)
            logger.info(f"Dalfox scan {scan_job_id}: Added {crawler_count} URLs from crawler")
        
        # Get all harvested parameterized URLs
        harvested_param_urls = harvester.get_parameterized_urls()
        
        # Combine harvested URLs with crawler results
        combined_urls = set(all_urls)
        combined_urls.update(harvested_param_urls)
        
        # CRITICAL: If no parameterized URLs were found, create fallback targets
        if not harvested_param_urls and not parameterized_urls:
            logger.warning(
                f"Dalfox scan {scan_job_id}: No parameterized URLs found from harvester or crawler! "
                f"Creating fallback test parameters."
            )
            fallback_urls = create_fallback_targets(target_url)
            combined_urls.update(fallback_urls)
            logger.info(f"Dalfox scan {scan_job_id}: Added {len(fallback_urls)} fallback parameterized URLs")
        
        # Convert back to list and ensure target URL is included
        all_urls = list(combined_urls)
        
        # CRITICAL: Always ensure we have at least the target URL
        if not all_urls:
            logger.warning(
                f"Dalfox scan {scan_job_id}: No URLs found at all! "
                f"Will test target URL directly: {target_url}"
            )
            all_urls = [target_url]
        
        # Ensure target URL is in the list
        if target_url not in all_urls:
            all_urls.append(target_url)
            logger.info(f"Dalfox scan {scan_job_id}: Added target URL to scan list: {target_url}")
        
        # Get stats
        harvester_stats = harvester.get_stats()
        logger.info(
            f"Dalfox scan {scan_job_id}: Will scan {len(all_urls)} URLs total "
            f"({harvester_stats['total_requests']} from harvester with {harvester_stats['total_parameters']} params, "
            f"{len(parameterized_urls)} from crawler)."
        )
        
        # Check if dalfox is installed
        logger.info(f"Checking dalfox availability for scan {scan_job_id}")
        
        # Try common locations for dalfox
        possible_paths = [
            os.path.expanduser("~/go/bin/dalfox"),  # Go bin directory (most common)
            "/usr/local/bin/dalfox",
            "dalfox",  # In PATH
        ]
        
        dalfox_binary = None
        for binary_path in possible_paths:
            try:
                # Expand ~ to home directory for absolute paths
                expanded_path = os.path.expanduser(binary_path) if binary_path.startswith("~") else binary_path
                
                # For absolute paths, check if file exists and is executable
                if os.path.isabs(expanded_path) or expanded_path.startswith("/"):
                    if os.path.exists(expanded_path) and os.access(expanded_path, os.X_OK):
                        dalfox_binary = expanded_path
                        logger.info(f"dalfox binary found for scan {scan_job_id}: {expanded_path}")
                        break
                else:
                    # For commands in PATH, use 'which' to find them
                    check_result = await asyncio.to_thread(subprocess.run,
                        ["which", binary_path],
                        capture_output=True,
                        timeout=5,
                        text=True
                    )
                    if check_result.returncode == 0:
                        dalfox_binary = check_result.stdout.strip()
                        logger.info(f"dalfox binary found for scan {scan_job_id}: {dalfox_binary}")
                        break
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.debug(f"dalfox detection test failed for {binary_path}: {e}")
                continue
        
        if not dalfox_binary:
            error_msg = "dalfox binary not found in PATH. Please install dalfox: go install github.com/hahwul/dalfox/v2@latest (ensure ~/go/bin is in PATH)"
            logger.error(f"dalfox binary not found for scan {scan_job_id}")
            return {
                "tool_name": "dalfox",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "dalfox --version",
                "timed_out": False,
            }
        
        # Determine aggressiveness level (default: medium)
        aggressiveness = kwargs.get("aggressiveness", "medium")
        
        # Determine timeout based on scan level and number of URLs
        # CRITICAL: Use timeout from kwargs (set by backend via runner_client from scan_timeouts.py)
        # If not provided, calculate based on URLs and scan level but log a warning
        timeout = kwargs.get("timeout_seconds")
        if timeout is None:
            # CRITICAL: Use scan-level appropriate defaults instead of generic calculation
            scan_level_lower = scan_level.lower() if scan_level else "basic"
            if scan_level_lower == "advanced":
                default_timeout = 1500  # 25 minutes for advanced
            elif scan_level_lower == "pro":
                default_timeout = 1500  # 25 minutes for pro
            else:
                default_timeout = 300  # 5 minutes for basic
            base_timeout_per_url = 30  # 30 seconds per URL
            # Calculate dynamic timeout based on number of URLs, but use scan-level default as minimum
            timeout = min(3600, max(default_timeout, len(all_urls) * base_timeout_per_url))
            logger.warning(
                f"Dalfox scan {scan_job_id}: timeout_seconds not provided in kwargs! "
                f"Using calculated default {timeout}s (scan_level: {scan_level}, URLs: {len(all_urls)}). "
                f"This may cause premature timeouts. "
                f"Available kwargs keys: {list(kwargs.keys())}"
            )
        else:
            logger.info(
                f"Dalfox scan {scan_job_id}: Using timeout_seconds={timeout}s from kwargs "
                f"(scan_level: {scan_level}, URLs: {len(all_urls)})"
            ) 
            
        # Enforce minimums for high-intensity scans with headless browser
        # Always apply this check to override any low default passed in kwargs
        # Ensure case-insensitive comparison
        scan_level_lower = scan_level.lower() if scan_level else "standard"
        
        # Check if deep-domxss is enabled (adds browser overhead)
        has_deep_domxss = scan_level_lower in ("pro", "advanced")
        
        if scan_level_lower == "advanced":
            timeout = max(timeout, 900)  # Min 15m for advanced with headless browser
        elif scan_level_lower == "pro":
            timeout = max(timeout, 600)  # Min 10m for pro with headless browser
            
        logger.info(f"Dalfox timeout calculated: {timeout} seconds (level: {scan_level})")
        
        # Build dalfox command
        # Use PIPE mode to scan multiple URLs found by crawler
        # CRITICAL: Include all XSS detection flags for maximum coverage
        # Note: Dalfox has built-in grepping that detects XSS indicators automatically
        # Note: --mining-all flag doesn't exist, use --mining-dict and --mining-dom instead
        cmd = [
            dalfox_binary,
            "pipe",
            "--silence",  # Suppress banner/progress
            "--format", "json",  # JSON output for parsing
            "--follow-redirects",  # Follow redirects to find XSS
            "--mining-dict",  # Parameter mining from dictionaries
            "--mining-dom",  # DOM-based parameter mining (lightweight)
            # Note: --mining-all doesn't exist in dalfox, removed
            "--only-poc", "g,v",  # Only show findings with proof-of-concept (grep + verified)
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",  # Realistic UA to avoid blocking
        ]
        
        # Add scan-level specific options
        if scan_level_lower == "advanced":
            cmd.extend([
                "--worker", "100",  # More workers for aggressive mode
                "--waf-evasion",  # WAF evasion techniques
                "--remote-payloads", "portswigger,payloadbox",  # Use remote payload lists
                # NOTE: --deep-domxss removed due to headless Chrome timeout issues
                # Headless browsers spawn child processes that don't respect subprocess timeout
                # causing orphaned Chrome processes and early termination
                "--context-aware",  # Context-aware payload selection
            ])
            logger.info(f"Dalfox Advanced scan without headless (timeout: {timeout}s)")
        elif scan_level_lower == "pro":
            cmd.extend([
                "--worker", "50",  # Moderate workers
                "--waf-evasion",  # WAF evasion techniques
                # NOTE: --deep-domxss removed due to headless Chrome timeout issues
            ])
            logger.info(f"Dalfox Pro scan without headless (timeout: {timeout}s)")
        else:  # basic
            cmd.extend([
                "--worker", "25",  # Fewer workers for basic scan
            ])
            # Basic scans don't use headless (faster, but won't detect DOM XSS)
        
        # Add custom payload file if it exists
        payload_file = Path(os.getenv("PAYLOADS_DIR", "/opt/thandev/payloads")) / "xss-payloads.txt"
        if payload_file.exists():
            cmd.extend(["--custom-payload", str(payload_file)])
            logger.debug(
                "Using custom XSS payload file",
                extra={"scan_job_id": scan_job_id, "payload_file": str(payload_file)}
            )
        
        logger.info("dalfox command for scan %s: %s (timeout: %d seconds, targets: %d)", 
                   scan_job_id, " ".join(cmd), timeout, len(all_urls))
        
        try:
            # Join URLs with newlines for pipe input
            urls_input = "\n".join(all_urls)
            
            # CRITICAL: Log what we're about to send to dalfox
            logger.info(
                f"Dalfox scan {scan_job_id}: About to execute with {len(all_urls)} URLs, timeout={timeout}s"
            )
            logger.debug(
                f"Dalfox scan {scan_job_id}: URLs to scan (first 5): {all_urls[:5]}"
            )
            logger.debug(
                f"Dalfox scan {scan_job_id}: Full command: {' '.join(cmd)}"
            )
            
            # Track execution start time
            import time
            exec_start_time = time.time()

            # Use asyncio.to_thread to prevent blocking event loop
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                input=urls_input,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            exec_duration = time.time() - exec_start_time
            logger.info(
                f"Dalfox scan {scan_job_id}: Execution completed in {exec_duration:.2f}s "
                f"(timeout was {timeout}s, exit_code={result.returncode})"
            )
            
            exit_code = result.returncode
            stdout_bytes = len(result.stdout.encode("utf-8")) if result.stdout else 0
            stderr_bytes = len(result.stderr.encode("utf-8")) if result.stderr else 0
            
            # CRITICAL: If execution was suspiciously fast (< 1 second), log warning
            if exec_duration < 1.0 and len(all_urls) > 0:
                logger.warning(
                    f"Dalfox scan {scan_job_id}: Execution completed in {exec_duration:.2f}s which is "
                    f"suspiciously fast for {len(all_urls)} URLs. This might indicate an error or that "
                    f"dalfox didn't actually scan. stdout_length={stdout_bytes}, stderr_length={stderr_bytes}, "
                    f"exit_code={exit_code}"
                )
            
            # Check for suspiciously fast completion (might indicate an error or no actual scanning)
            if stdout_bytes == 0 and stderr_bytes == 0 and exit_code == 0:
                logger.warning(
                    f"Dalfox scan {scan_job_id} completed with no output (stdout/stderr empty). "
                    f"This might indicate the scan didn't actually run or URLs were invalid. "
                    f"URLs scanned: {len(all_urls)}"
                )
            
            logger.info(
                "Dalfox scan completed",
                extra={
                    "scan_job_id": scan_job_id,
                    "exit_code": exit_code,
                    "stdout_bytes": stdout_bytes,
                    "stderr_bytes": stderr_bytes,
                    "target_url": target_url,
                    "crawled_urls": len(all_urls),
                    "stdout_preview": result.stdout[:500] if result.stdout else None,
                    "stderr_preview": result.stderr[:500] if result.stderr else None,
                }
            )
            
            # Rest of the processing logic remains the same...
            is_error = False
            error_msg = None
            
            # Normalize Dalfox output BEFORE checking exit code
            # This ensures we can properly detect if there are findings even with non-zero exit codes
            normalized_output = _normalize_dalfox_output(result.stdout) if result.stdout else "[]"
            has_findings = normalized_output and normalized_output.strip() not in ["[]", "[{}]", ""]
            
            if exit_code != 0:
                stdout_lower = (result.stdout or "").lower()
                # Treat CLI/flag/config errors as real failures even if they were printed to stdout.
                if any(s in stdout_lower for s in ["unknown flag", "invalid", "usage:"]):
                    is_error = True
                    error_msg = f"dalfox exited with code {exit_code}: {result.stdout[:200] if result.stdout else ''}"
                    logger.warning("dalfox scan %s failed (cli error): %s", scan_job_id, error_msg)
                elif stdout_bytes > 0 and has_findings:
                    # Exit code 2 with findings is normal for Dalfox - it means vulnerabilities were found
                    # This is NOT an error, it's a success with findings
                    logger.info(
                        "dalfox scan %s completed with exit_code=%s and findings detected (treating as success)",
                        scan_job_id, exit_code
                    )
                    is_error = False
                    error_msg = None
                    # We have output AND findings; dalfox sometimes returns non-zero even on findings.
                    # This is normal - treat as success, don't set error
                    try:
                        findings_count = len(json.loads(normalized_output)) if normalized_output.startswith("[") else 0
                    except (json.JSONDecodeError, ValueError):
                        findings_count = 0
                    logger.info(
                        "dalfox scan %s completed with exit_code=%s but found %d findings (treating as success)",
                        scan_job_id, exit_code, findings_count
                    )
                    is_error = False  # Explicitly clear error flag when we have findings
                    error_msg = None  # Don't show error message when we have findings
                elif stdout_bytes > 0:
                    # We have output but no valid findings (might be malformed JSON or empty)
                    # Try to parse the raw output to see if there's any useful data
                    try:
                        raw_parsed = json.loads(result.stdout) if result.stdout else None
                        if raw_parsed and isinstance(raw_parsed, list) and len(raw_parsed) > 0:
                            # Check if any item has meaningful data
                            has_any_data = any(
                                isinstance(item, dict) and item and 
                                any(v for v in item.values() if v is not None and str(v).strip())
                                for item in raw_parsed
                            )
                            if has_any_data:
                                logger.info(
                                    "dalfox scan %s completed with exit_code=%s and output containing data (treating as success, will parse in ingestion)",
                                    scan_job_id, exit_code
                                )
                                is_error = False
                                error_msg = None
                            else:
                                logger.warning(
                                    "dalfox scan %s completed with exit_code=%s and %d bytes of output but no valid findings",
                                    scan_job_id, exit_code, stdout_bytes
                                )
                                is_error = False
                                error_msg = None
                        else:
                            logger.warning(
                                "dalfox scan %s completed with exit_code=%s and %d bytes of output but no valid findings",
                                scan_job_id, exit_code, stdout_bytes
                            )
                            is_error = False
                            error_msg = None
                    except (json.JSONDecodeError, ValueError) as parse_err:
                        logger.warning(
                            "dalfox scan %s completed with exit_code=%s and %d bytes of non-JSON output: %s",
                            scan_job_id, exit_code, stdout_bytes, str(parse_err)[:100]
                        )
                        # Log raw output for debugging
                        logger.debug("Dalfox raw output (first 500 chars): %s", result.stdout[:500] if result.stdout else "")
                        is_error = False
                        error_msg = None
                elif result.stderr:
                    stderr_lower = result.stderr.lower()
                    if any(keyword in stderr_lower for keyword in ["error", "failed", "fatal", "cannot", "not found"]):
                        is_error = True
                        error_msg = f"dalfox exited with code {exit_code}: {result.stderr[:200]}"
                        logger.warning("dalfox scan %s failed: %s", scan_job_id, error_msg)
                    else:
                        logger.info(
                            "dalfox scan %s completed with exit_code=%s (no XSS found, treating as success)",
                            scan_job_id, exit_code
                        )
                        is_error = False
                        error_msg = None
                else:
                    logger.info(
                        "dalfox scan %s completed with exit_code=%s and no output (no XSS found, treating as success)",
                        scan_job_id, exit_code
                    )
                    is_error = False
                    error_msg = None
            
            if is_error:
                return {
                    "tool_name": "dalfox",
                    "output": normalized_output,
                    "exit_code": exit_code,
                    "error": error_msg,
                    "command": " ".join(cmd),
                    "timed_out": False,
                    "success": False,
                    "targets_count": len(all_urls),
                    "meta": {
                        "harvested_requests": harvester_stats.get("total_requests", 0),
                        "total_parameters": harvester_stats.get("total_parameters", 0),
                        "crawler_urls": len(parameterized_urls),
                    },
                }
            
            # Mark as successful if we have findings or if exit code is 0
            # Dalfox may return non-zero even with findings, so check output
            return {
                "tool_name": "dalfox",
                "output": normalized_output,
                "exit_code": exit_code,
                "command": " ".join(cmd),
                "timed_out": False,
                "success": has_findings or exit_code == 0,  # Success if we have findings or exit code is 0
                "execution_time": exec_duration,  # Accurate subprocess-only execution time
                "targets_count": len(all_urls),  # Number of URLs scanned
                "meta": {
                    "harvested_requests": harvester_stats.get("total_requests", 0),
                    "total_parameters": harvester_stats.get("total_parameters", 0),
                    "crawler_urls": len(parameterized_urls),
                },
            }
        except subprocess.TimeoutExpired as exc:
            logger.warning("dalfox scan %s timed out after %d seconds. Results may be partial.", scan_job_id, timeout)
            return {
                "tool_name": "dalfox",
                "output": "[]",
                "exit_code": None,
                "error": f"Tool execution timed out after {timeout} seconds",
                "command": " ".join(cmd),
                "timed_out": True,
            }
        except Exception as e:
            logger.error(f"dalfox execution error for scan {scan_job_id}: {e}", exc_info=True)
            return {
                "tool_name": "dalfox",
                "output": "",
                "exit_code": -1,
                "error": f"dalfox execution failed: {str(e)}",
                "command": " ".join(cmd),
                "timed_out": False,
            }
    
    # TODO: Vulnerability classes covered by sqlmap:
    # - SQL Injection (SQLi) - primary focus
    # - Database fingerprinting (MySQL, PostgreSQL, Oracle, MSSQL, etc.)
    # - Database enumeration (tables, columns, data extraction)
    # Note: sqlmap is specifically designed for SQL injection detection and exploitation
    async def _run_zap(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run OWASP ZAP scans (passive, active, ajax spider) via ZAP API.
        
        Optional kwargs:
            mode_id: "passive_spider", "active_scan", "ajax_spider"
            max_depth: for spider
            max_children: for spider
            policy: for active scan
            max_duration: for active scan
        """
        import requests
        import time
        import subprocess
        from urllib.parse import urlparse
        from datetime import datetime, timezone
        import json
        
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        mode_id = kwargs.get("mode_id", "passive_spider")
        timeout_seconds = kwargs.get("timeout_seconds", 300)  # Default to 5 minutes
        
        logger.info(f"Starting ZAP scan {scan_job_id} for {target_url} with mode {mode_id}")
        
        # ZAP API URL from environment variable
        # Default to zap hostname (Docker network DNS resolution)
        # In Fly.io, use .internal DNS (same as other services like brain, backend)
        zap_api_url = os.getenv("ZAP_API_URL", "http://thandev-zap.internal:8090")
        
        logger.info(f"ZAP API URL from environment: {zap_api_url}")
        
        # If using hostname, try to resolve it first, fallback to alternative DNS
        # Try .internal first (standard for Fly.io private networking), then .flycast as fallback
        zap_api_urls_to_try = [zap_api_url]
        if "thandev-zap.internal" in zap_api_url:
            # Add .flycast fallback (though .internal should work)
            zap_api_urls_to_try.append(zap_api_url.replace(".internal", ".flycast"))
        elif "thandev-zap.flycast" in zap_api_url:
            # Add .internal fallback (preferred)
            zap_api_urls_to_try.insert(0, zap_api_url.replace(".flycast", ".internal"))
        
        if "zap:" in zap_api_url or "thandev-zap" in zap_api_url:
            for url_to_try in zap_api_urls_to_try:
                try:
                    import socket
                    from urllib.parse import urlparse
                    parsed = urlparse(url_to_try)
                    hostname = parsed.hostname
                    if hostname:
                        zap_ip = socket.gethostbyname(hostname)
                        logger.info(f"Resolved ZAP hostname {hostname} to IP: {zap_ip}")
                        zap_api_url = url_to_try  # Use the working URL
                        break
                except (socket.gaierror, Exception) as e:
                    logger.debug(f"Could not resolve ZAP hostname {hostname} ({e}), trying next URL...")
                    continue
            else:
                # All DNS resolutions failed, will retry in connection attempts
                logger.warning(f"Could not resolve ZAP hostname for any URL, will retry connection attempts")
                import time
                time.sleep(2)  # Give DNS a moment to catch up
        
        # Ensure ZAP is running and accessible - retry with backoff
        # Note: ZAP API may require apikey parameter even if disabled, so we add it as empty
        # CRITICAL: ZAP container may need time to fully start, so we increase retries and delays
        health_check_url = f"{zap_api_url}/JSON/core/view/version/?apikey="
        max_retries = 10  # Increased from 5 to 10 for better reliability
        retry_delay = 5  # Increased from 3 to 5 seconds
        zap_accessible = False
        http_session = None
        
        for attempt in range(max_retries):
            try:
                http_session = requests.Session()
                http_session.mount('http://', requests.adapters.HTTPAdapter(max_retries=1))
                # Increased timeout to 30s for better reliability on slow networks
                response = await asyncio.to_thread(http_session.get, health_check_url, timeout=30)
                response.raise_for_status()
                logger.info(f"ZAP API is accessible: {response.json().get('version')}")
                zap_accessible = True
                break
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"ZAP connection error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.3, 20)  # Cap at 20s max delay
                else:
                    error_msg = f"ZAP API connection failed at {zap_api_url} after {max_retries} attempts: {e}. Check if ZAP service is running."
                    logger.error(error_msg)
                    return {
                        "tool_name": "zap",
                        "output": "[]",
                        "exit_code": -1,
                        "error": error_msg,
                        "command": f"ZAP API call to {health_check_url}",
                        "success": False,
                    }
            except requests.exceptions.Timeout as e:
                if attempt < max_retries - 1:
                    logger.warning(f"ZAP timeout (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.3, 20)
                else:
                    error_msg = f"ZAP API timeout at {zap_api_url} after {max_retries} attempts: {e}. ZAP may be overloaded or unreachable."
                    logger.error(error_msg)
                    return {
                        "tool_name": "zap",
                        "output": "[]",
                        "exit_code": -1,
                        "error": error_msg,
                        "command": f"ZAP API call to {health_check_url}",
                        "success": False,
                    }
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"ZAP health check attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.3, 20)
                else:
                    error_msg = f"ZAP API not accessible at {zap_api_url} after {max_retries} attempts: {e}. ZAP is not deployed to Fly.io - skipping ZAP scan."
                    logger.warning(error_msg)
                    # Return empty results instead of failing - ZAP is optional in Fly.io deployment
                    return {
                        "tool_name": "zap",
                        "output": "[]",
                        "exit_code": -1,
                        "error": error_msg,
                        "command": f"ZAP API call to {health_check_url}",
                        "success": False,
                    }
        
        if not zap_accessible or not http_session:
            return {
                "tool_name": "zap",
                "output": "[]",
                "exit_code": -1,
                "error": "ZAP API not accessible after retries",
                "command": f"ZAP API call to {health_check_url}",
                "success": False,
            }
        
        # CRITICAL FIX: Don't create a new session for each scan
        # Creating a new session clears the scan tree, preventing URLs from accumulating
        # ZAP's spider discovers URLs but they're only added to scan tree when accessed through proxy
        # Since proxy is not accessible, we need URLs to accumulate across scans in the same session
        # We'll use the default session and not create a new one
        logger.info("Using default ZAP session (not creating new session to preserve scan tree)")
        
        # CRITICAL ISSUE: ZAP's proxy (port 8080) is not accessible in daemon mode
        # This means URLs cannot be added to scan tree via proxy access
        # ZAP spider discovers URLs but doesn't automatically add them to scan tree
        # WORKAROUND: Don't create new session, let URLs accumulate if spider somehow adds them
        # Also try accessing URLs directly via ZAP's internal HTTP client if available
        logger.warning("ZAP proxy (port 8080) is not accessible - using workaround: no new session, relying on spider")
        
        # Set target context
        # CRITICAL: Include both the target URL and base URL in context
        # This ensures spider can work with base URL even if target is a specific page
        from urllib.parse import urlparse
        target_parsed = urlparse(target_url)
        base_url = f"{target_parsed.scheme}://{target_parsed.netloc}/"
        
        context_name = f"context_{scan_job_id}"
        await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/context/action/newContext/?contextName={context_name}&apikey=", timeout=10)
        
        # Include base URL in context (for spider starting from root)
        # Escape special regex characters in URLs (., /, etc.)
        import re
        base_url_escaped = re.escape(base_url)
        await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/context/action/includeInContext/?contextName={context_name}&regex={base_url_escaped}.*&apikey=", timeout=10)
        # Also include specific target URL if different from base
        if target_url != base_url:
            target_url_escaped = re.escape(target_url)
            await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/context/action/includeInContext/?contextName={context_name}&regex={target_url_escaped}.*&apikey=", timeout=10)
        
        logger.info(f"Created ZAP context '{context_name}' for target {target_url} (base: {base_url})")
        
        # Enable all passive scanners by default
        await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/pscan/action/enableAllScanners/?apikey=", timeout=10)
        
        # CRITICAL: Configure ZAP to accept invalid SSL certificates for HTTPS targets
        # This is necessary when ZAP cannot validate certificates due to networking issues
        try:
            await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/network/action/setUseClientSockets/?useClientSockets=true&apikey=", timeout=10)
            logger.info("Configured ZAP to use client sockets for better HTTPS support")
        except Exception as socket_config_error:
            logger.debug(f"Failed to configure ZAP client sockets (non-critical): {socket_config_error}")
        
        # Try to configure ZAP to accept invalid certificates (if API available)
        try:
            # This API may not exist in all ZAP versions, so we catch and continue
            await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/network/action/setValidateServerCertificates/?validate=false&apikey=", timeout=10)
            logger.info("Configured ZAP to accept invalid SSL certificates")
        except Exception as cert_config_error:
            logger.debug(f"Failed to configure ZAP certificate validation (API may not exist): {cert_config_error}")
        
        # CRITICAL: Access the target URL through ZAP proxy BEFORE spidering
        # This ensures the URL is in ZAP's scan tree and passive scanners can analyze it
        # ZAP only adds URLs to scan tree when they're accessed through the proxy
        # Try both 8080 and 8090 as proxy ports (8090 might work if proxy chain is configured)
        proxy_ports_to_try = [8080, 8090]
        proxy_accessed = False
        for proxy_port in proxy_ports_to_try:
            try:
                # With host network mode, use localhost instead of zap hostname
                if "localhost" in zap_api_url or "127.0.0.1" in zap_api_url:
                    proxy_url = f"http://localhost:{proxy_port}"
                else:
                    proxy_url = zap_api_url.replace("/JSON", "").replace(":8090", f":{proxy_port}")
                logger.info(f"Attempting to access {target_url} via ZAP proxy {proxy_url} to add to scan tree...")
                
                # #region agent log
                try:
                    debug_log_path = "/app/data/debug.log"
                    with open(debug_log_path, "a") as f:
                        import json as json_lib
                        import time
                        f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H2","location":"tools.py:2190","message":"Before proxy access","data":{"target_url":target_url,"proxy_url":proxy_url,"proxy_port":proxy_port},"timestamp":int(time.time()*1000)})+"\n")
                except: pass
                # #endregion
                
                # Use requests directly for proxy access (this is the proper way to add URLs to scan tree)
                import requests
                proxy_dict = {"http": proxy_url, "https": proxy_url}
                try:
                    proxy_response = requests.get(target_url, proxies=proxy_dict, timeout=10, allow_redirects=True, verify=False)
                    logger.info(f"Successfully accessed {target_url} via ZAP proxy on port {proxy_port}, status: {proxy_response.status_code}")
                    proxy_accessed = True
                    
                    # #region agent log
                    try:
                        debug_log_path = "/app/data/debug.log"
                        with open(debug_log_path, "a") as f:
                            import json as json_lib
                            import time
                            f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H2","location":"tools.py:2210","message":"After proxy access success","data":{"target_url":target_url,"proxy_url":proxy_url,"status_code":proxy_response.status_code},"timestamp":int(time.time()*1000)})+"\n")
                    except: pass
                    # #endregion
                except Exception as proxy_err:
                    # #region agent log
                    try:
                        debug_log_path = "/app/data/debug.log"
                        with open(debug_log_path, "a") as f:
                            import json as json_lib
                            import time
                            f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H2","location":"tools.py:2223","message":"Proxy access failed","data":{"target_url":target_url,"proxy_url":proxy_url,"error":str(proxy_err),"error_type":type(proxy_err).__name__},"timestamp":int(time.time()*1000)})+"\n")
                    except: pass
                    # #endregion
                    error_str = str(proxy_err)
                    # Check if this is a network connectivity issue
                    if "Connection refused" in error_str or "Failed to connect" in error_str or "Name or service not known" in error_str:
                        logger.error(
                            f"CRITICAL: Cannot access {target_url} via ZAP proxy on port {proxy_port}: {proxy_err}. "
                            f"This indicates ZAP container cannot make outbound HTTPS connections. "
                            f"This is a WSL2/Docker networking or Java TLS configuration issue. "
                            f"ZAP may still work for HTTP targets or if networking is configured correctly."
                        )
                    else:
                        logger.warning(f"Failed to access {target_url} via ZAP proxy on port {proxy_port}: {proxy_err}")
                    continue
                
                # Wait for ZAP to process and add to scan tree
                await asyncio.sleep(3)
                
                # Verify target URL is now in scan tree
                try:
                    urls_check = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/view/urls/?apikey=", timeout=10)
                    urls_in_tree = urls_check.json().get("urls", [])
                    target_in_tree = any(target_url in url for url in urls_in_tree)
                    logger.info(f"After proxy access on port {proxy_port}: scan tree contains {len(urls_in_tree)} URLs, target in tree: {target_in_tree}")
                    if target_in_tree:
                        break  # Success - URL is in scan tree
                except Exception as check_error:
                    logger.debug(f"Failed to check URLs after proxy access: {check_error}")
                break  # If we got a response (even if not 200), the proxy is working
            except requests.exceptions.ProxyError as proxy_error:
                logger.debug(f"Proxy on port {proxy_port} not accessible: {proxy_error}")
                continue  # Try next port
            except Exception as proxy_error:
                logger.warning(f"Error accessing URL via ZAP proxy on port {proxy_port}: {proxy_error}")
                # If we got a response (even error), proxy might be working, so break
                if "status_code" in str(proxy_error) or "502" in str(proxy_error) or "503" in str(proxy_error):
                    proxy_accessed = True
                    break
                continue  # Try next port
        
        if not proxy_accessed:
            logger.warning(f"Could not access URL via ZAP proxy on any port (tried {proxy_ports_to_try}) - will try spider")
            # Continue - spider will discover URLs (but won't add them to scan tree without proxy)
        
        # Start spidering (always do a basic spider first to discover URLs)
        # CRITICAL: For better spider results, use base URL if target is a specific page
        # ZAP spider works better when starting from the root of a site
        from urllib.parse import urlparse
        target_parsed = urlparse(target_url)
        spider_start_url = target_url
        # If target is a specific page (has path beyond root), try using base URL for spider
        # Check if path has more than just the root (e.g., /login.php has 2 parts: ['', 'login.php'])
        if target_parsed.path and target_parsed.path != "/" and len([p for p in target_parsed.path.split("/") if p]) > 0:
            base_url = f"{target_parsed.scheme}://{target_parsed.netloc}/"
            logger.info(f"Target is a specific page ({target_url}), using base URL for spider: {base_url}")
            spider_start_url = base_url
        
        spider_id = None
        try:
            logger.info(f"Starting ZAP spider for {spider_start_url} (original target: {target_url})...")
            max_depth = kwargs.get("max_depth", 5)
            max_children = kwargs.get("max_children", 50)
            # CRITICAL: Always run spider WITH context to ensure discovered URLs are added to scan tree
            # URLs discovered by spider without context may not be added to scan tree automatically
            # Using context ensures URLs are in scope and will be added to scan tree
            spider_response = None
            spider_id = None
            try:
                # Run spider WITH context to ensure URLs are added to scan tree
                spider_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/spider/action/scan/?url={spider_start_url}&contextName={context_name}&maxDepth={max_depth}&maxChildren={max_children}&apikey=", timeout=timeout_seconds)
                spider_result = spider_response.json()
                if "code" in spider_result and spider_result.get("code") != "OK":
                    # If context fails, try without context as fallback
                    logger.warning(f"Spider with context failed ({spider_result}), trying without context...")
                    spider_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/spider/action/scan/?url={spider_start_url}&maxDepth={max_depth}&maxChildren={max_children}&apikey=", timeout=timeout_seconds)
                    spider_result = spider_response.json()
                    if "code" in spider_result and spider_result.get("code") != "OK":
                        raise ValueError(f"Failed to start ZAP spider (tried with and without context): {spider_result}")
                spider_id = spider_result.get("scan")
            except Exception as spider_start_error:
                raise ValueError(f"Failed to start ZAP spider: {spider_start_error}")
            
            if not spider_id:
                raise ValueError(f"Failed to start ZAP spider: {spider_response.text if spider_response else 'No response'}")
            
            # Poll spider status
            start_time = time.time()
            while True:
                status_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/spider/view/status/?scanId={spider_id}&apikey=", timeout=10)
                status_result = status_response.json()
                status_percent = int(status_result.get("status", "0"))
                
                # Also check results count to see if spider is finding URLs
                try:
                    results_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/spider/view/results/?scanId={spider_id}&apikey=", timeout=10)
                    results = results_response.json().get("results", [])
                    logger.debug(f"ZAP Spider status: {status_percent}%, URLs found so far: {len(results)}")
                except:
                    logger.debug(f"ZAP Spider status: {status_percent}%")
                
                if status_percent >= 100:
                    break
                if time.time() - start_time > timeout_seconds:
                    raise subprocess.TimeoutExpired(cmd="ZAP Spider", timeout=timeout_seconds)
                await asyncio.sleep(5)
            
            # Check final spider results
            spider_urls = []
            try:
                final_results_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/spider/view/results/?scanId={spider_id}&apikey=", timeout=10)
                final_results = final_results_response.json().get("results", [])
                spider_urls = final_results
                logger.info(f"ZAP Spider completed for {target_url}. Found {len(spider_urls)} URLs via spider results API")
                
                # #region agent log
                try:
                    debug_log_path = "/app/data/debug.log"
                    with open(debug_log_path, "a") as f:
                        import json as json_lib
                        import time
                        f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H4","location":"tools.py:2320","message":"Spider results","data":{"target_url":target_url,"spider_urls_count":len(spider_urls),"spider_urls_sample":spider_urls[:5]},"timestamp":int(time.time()*1000)})+"\n")
                except: pass
                # #endregion
            except Exception as spider_results_error:
                logger.warning(f"Failed to get spider results: {spider_results_error}")
                logger.info(f"ZAP Spider completed for {target_url}")
            
            # CRITICAL: Wait a moment for ZAP to process spider results and add URLs to scan tree
            # Spider results API returns URLs found, but they need time to be added to scan tree
            if spider_urls:
                logger.info(f"Waiting 3 seconds for ZAP to process {len(spider_urls)} spider-discovered URLs into scan tree...")
                await asyncio.sleep(3)
            
            # DEBUG: Check how many URLs are in scan tree after waiting
            urls_in_tree = []
            try:
                urls_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/view/urls/?apikey=", timeout=10)
                urls_in_tree = urls_response.json().get("urls", [])
                logger.info(f"ZAP scan tree now contains {len(urls_in_tree)} URLs after spidering (spider found {len(spider_urls)}). Sample URLs: {urls_in_tree[:5]}")
                # #region agent log
                try:
                    debug_log_path = "/app/data/debug.log"
                    with open(debug_log_path, "a") as f:
                        import json as json_lib
                        import time
                        f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H8","location":"tools.py:2238","message":"After spider - URLs in scan tree","data":{"spider_urls_count":len(spider_urls),"scan_tree_urls_count":len(urls_in_tree),"sample_urls":urls_in_tree[:5]},"timestamp":int(time.time()*1000)})+"\n")
                except: pass
                # #endregion
            except Exception as url_check_error:
                logger.warning(f"Failed to check URLs after spider: {url_check_error}")
            
            # CRITICAL: Access discovered URLs through ZAP proxy to ensure they're in scan tree
            # Spider discovers URLs but doesn't automatically add them - they must be accessed through proxy
            # Use spider_urls if available (even if not in scan tree yet), otherwise use urls_in_tree
            urls_to_access = spider_urls if spider_urls else urls_in_tree
            if urls_to_access and len(urls_in_tree) == 0:
                # Only access URLs if they're not already in scan tree
                logger.info(f"Accessing {min(10, len(urls_to_access))} discovered URLs via ZAP proxy to add to scan tree...")
                accessed_count = 0
                failed_count = 0
                import requests
                # Try both 8080 and 8090 as proxy ports
                proxy_ports_to_try = [8080, 8090]
                working_proxy_port = None
                for proxy_port in proxy_ports_to_try:
                    try:
                        test_proxy_url = zap_api_url.replace("/JSON", "").replace(":8090", f":{proxy_port}")
                        test_proxy_dict = {"http": test_proxy_url, "https": test_proxy_url}
                        # Test if proxy works
                        test_response = requests.get("http://testphp.vulnweb.com/", proxies=test_proxy_dict, timeout=3, verify=False)
                        working_proxy_port = proxy_port
                        logger.info(f"Found working ZAP proxy on port {proxy_port}")
                        break
                    except:
                        continue
                
                if working_proxy_port:
                    proxy_url = zap_api_url.replace("/JSON", "").replace(":8090", f":{working_proxy_port}")
                    proxy_dict = {"http": proxy_url, "https": proxy_url}
                    for url in urls_to_access[:10]:  # Limit to first 10 URLs to avoid timeout
                        try:
                            # Access URL through ZAP proxy (this is the proper way to add URLs to scan tree)
                            proxy_response = requests.get(url, proxies=proxy_dict, timeout=5, allow_redirects=True, verify=False)
                            accessed_count += 1
                            logger.debug(f"Successfully accessed {url} via ZAP proxy on port {working_proxy_port}, status: {proxy_response.status_code}")
                        except Exception as proxy_error:
                            failed_count += 1
                            logger.debug(f"Exception accessing {url} via proxy: {proxy_error}")
                    logger.info(f"Accessed {accessed_count} URLs via ZAP proxy on port {working_proxy_port} (failed: {failed_count})")
                else:
                    logger.warning(f"Could not find working ZAP proxy on ports {proxy_ports_to_try} - URLs will not be added to scan tree")
                # #region agent log
                try:
                    debug_log_path = "/app/data/debug.log"
                    with open(debug_log_path, "a") as f:
                        import json as json_lib
                        import time
                        f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H11","location":"tools.py:2294","message":"After proxy access of spider URLs","data":{"accessed_count":accessed_count,"failed_count":failed_count,"urls_attempted":min(10, len(urls_to_access))},"timestamp":int(time.time()*1000)})+"\n")
                except: pass
                # #endregion
                # Wait for URLs to be processed and passive scanners to analyze
                await asyncio.sleep(5)
                
                # Verify URLs are now in scan tree
                try:
                    verify_urls_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/view/urls/?apikey=", timeout=10)
                    verify_urls = verify_urls_response.json().get("urls", [])
                    logger.info(f"After proxy access: scan tree now contains {len(verify_urls)} URLs")
                    # #region agent log
                    try:
                        debug_log_path = "/app/data/debug.log"
                        with open(debug_log_path, "a") as f:
                            import json as json_lib
                            import time
                            f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H11","location":"tools.py:2315","message":"Scan tree after proxy access","data":{"urls_count":len(verify_urls),"sample_urls":verify_urls[:5]},"timestamp":int(time.time()*1000)})+"\n")
                    except: pass
                    # #endregion
                except Exception as verify_error:
                    logger.debug(f"Failed to verify URLs after proxy access: {verify_error}")
            elif len(urls_in_tree) > 0:
                logger.info(f"URLs already in scan tree ({len(urls_in_tree)}), skipping proxy access")
        except Exception as e:
            logger.warning(f"ZAP Spider failed or timed out for {target_url}: {e}", exc_info=True)
            # Continue with passive scan even if spider fails
        
        # Passive Scan (always runs implicitly as ZAP proxies traffic)
        # CRITICAL: The proxy on port 8090 returns 502 errors, which means ZAP isn't seeing actual HTTP responses
        # Without real responses, passive scanners can't analyze them and generate alerts
        # WORKAROUND: Use ZAP's accessUrl API to manually access URLs in scan tree
        # This should trigger passive scanning on those URLs even if proxy isn't working
        try:
            urls_check = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/view/urls/?apikey=", timeout=10)
            urls_in_tree = urls_check.json().get("urls", [])
            if len(urls_in_tree) > 0:
                logger.info(f"Found {len(urls_in_tree)} URLs in scan tree - accessing them via ZAP API to trigger passive scanning...")
                accessed_count = 0
                for url in urls_in_tree[:10]:  # Limit to first 10 URLs
                    try:
                        # Use ZAP's accessUrl API to access the URL - this should trigger passive scanning
                        access_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/action/accessUrl/?url={url}&followRedirects=true&apikey=", timeout=10)
                        access_result = access_response.json()
                        if access_result.get("Result") == "OK":
                            accessed_count += 1
                            logger.debug(f"Successfully accessed {url} via ZAP accessUrl API")
                        else:
                            logger.debug(f"Failed to access {url}: {access_result}")
                    except Exception as access_error:
                        logger.debug(f"Exception accessing {url}: {access_error}")
                logger.info(f"Accessed {accessed_count} URLs via ZAP accessUrl API to trigger passive scanning")
                # Wait for passive scanners to process the newly accessed URLs
                # CRITICAL: Increase wait time for passive scanners to analyze and generate alerts
                await asyncio.sleep(10)  # Increased from 5s to 10s for better alert generation
                
                # Check records to scan - if there are pending records, wait longer
                try:
                    records_to_scan = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/pscan/view/recordsToScan/?apikey=", timeout=10)
                    records_count = records_to_scan.json().get("recordsToScan", 0)
                    if records_count > 0:
                        logger.info(f"ZAP has {records_count} records pending passive scan - waiting additional 5s...")
                        await asyncio.sleep(5)
                except Exception as records_error:
                    logger.debug(f"Failed to check records to scan: {records_error}")
            else:
                logger.warning("ZAP has 0 URLs in scan tree - passive scanners have nothing to analyze")
                # CRITICAL: If no URLs in scan tree, try to add target URL directly
                try:
                    logger.info(f"Attempting to add target URL {target_url} to scan tree via accessUrl API...")
                    access_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/action/accessUrl/?url={target_url}&followRedirects=true&apikey=", timeout=10)
                    access_result = access_response.json()
                    if access_result.get("Result") == "OK":
                        logger.info(f"Successfully added {target_url} to scan tree via accessUrl API")
                        await asyncio.sleep(5)  # Wait for passive scanning
                    else:
                        logger.warning(f"Failed to add URL via accessUrl API: {access_result}")
                except Exception as add_url_error:
                    logger.warning(f"Failed to add URL to scan tree: {add_url_error}")
        except Exception as url_access_error:
            logger.warning(f"Failed to access URLs via ZAP API: {url_access_error}")
        
        # Wait for passive scan to finish processing alerts
        logger.info("Waiting for ZAP Passive Scan to complete processing alerts...")
        start_time = time.time()
        max_wait_time = 60  # Maximum 60 seconds for passive scan to process
        while True:
            records_to_scan = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/pscan/view/recordsToScan/?apikey=", timeout=10)
            records_count = int(records_to_scan.json().get("recordsToScan", "0"))
            logger.debug(f"ZAP Passive Scan: {records_count} records remaining to scan")
            if records_count == 0:
                break
            if time.time() - start_time > max_wait_time:
                logger.warning(f"ZAP Passive Scan timeout after {max_wait_time}s, {records_count} records still pending")
                break
            await asyncio.sleep(5)
        logger.info("ZAP Passive Scan completed processing alerts.")
        
        # CRITICAL: Wait additional time after passive scan completes to ensure alerts are fully processed
        # ZAP may need a moment to finalize alert generation after recordsToScan reaches 0
        # Also check if we have URLs in scan tree - if not, passive scanners might not have analyzed anything
        logger.info("Waiting additional 10 seconds for ZAP to finalize alert processing...")
        await asyncio.sleep(10)
        
        # DEBUG: Check scan tree one more time to see if URLs were added
        try:
            final_urls_check = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/view/urls/?apikey=", timeout=10)
            final_urls = final_urls_check.json().get("urls", [])
            logger.info(f"Final check: ZAP scan tree contains {len(final_urls)} URLs after passive scan completion")
        except Exception as final_check_error:
            logger.debug(f"Failed to check final URLs: {final_check_error}")
        
        # CRITICAL WORKAROUND: For passive_spider mode, if we have URLs in scan tree but 0 alerts FOR THIS TARGET,
        # it means passive scanning isn't working (likely due to proxy issues).
        # In this case, fall back to active scanning which doesn't require a working proxy.
        if mode_id == "passive_spider":
            # Check if we have URLs but no alerts FOR THE CURRENT TARGET - if so, passive scanning isn't working
            try:
                alerts_check = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/view/alerts/?apikey=", timeout=10)
                all_alerts = alerts_check.json().get("alerts", [])
                urls_check = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/view/urls/?apikey=", timeout=10)
                current_urls = urls_check.json().get("urls", [])
                
                # Filter alerts by target domain to check if we have alerts FOR THIS SPECIFIC TARGET
                # This prevents false positives from previous scans in the same ZAP session
                from urllib.parse import urlparse
                target_parsed = urlparse(target_url)
                target_domain = target_parsed.netloc or target_parsed.hostname
                
                target_alerts = []
                for alert in all_alerts:
                    alert_url = alert.get("url", "")
                    if alert_url:
                        alert_parsed = urlparse(alert_url)
                        alert_domain = alert_parsed.netloc or alert_parsed.hostname
                        # Match if same domain OR if alert URL starts with target URL
                        if alert_domain == target_domain or alert_url.startswith(target_url):
                            target_alerts.append(alert)
                
                if len(current_urls) > 0 and len(target_alerts) == 0:
                    logger.warning(
                        f"ZAP has {len(current_urls)} URLs in scan tree but 0 alerts for target {target_domain}. "
                        f"Passive scanning isn't working (likely proxy issue). "
                        f"Falling back to active scanning as workaround."
                    )
                    # Fall through to active scan logic below
                    mode_id = "active_scan"
                    logger.info("Switching to active scan mode as workaround for passive scanning failure")
            except Exception as fallback_check_error:
                logger.debug(f"Failed to check for fallback to active scan: {fallback_check_error}")
                # Continue with passive_spider mode
        
        # Conditional Active Scan or AJAX Spider
        if mode_id == "active_scan":
            logger.info(f"Starting ZAP Active Scan for {target_url}...")
            max_duration = kwargs.get("max_duration", 0)  # 0 means no limit
            
            # CRITICAL: Ensure URLs are in scan tree before starting active scan
            # Active scan requires URLs to be in scan tree, so verify they're there
            try:
                urls_check = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/view/urls/?apikey=", timeout=10)
                urls_in_tree = urls_check.json().get("urls", [])
                target_in_tree = any(target_url in url or url in target_url for url in urls_in_tree)
                logger.info(f"Before active scan: scan tree has {len(urls_in_tree)} URLs, target in tree: {target_in_tree}")
                
                # If target is not in scan tree, try to add it using ZAP's accessUrl API
                if not target_in_tree:
                    logger.warning(f"Target URL {target_url} not in scan tree - attempting to add it via accessUrl API")
                    try:
                        access_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/action/accessUrl/?url={target_url}&followRedirects=true&apikey=", timeout=10)
                        access_result = access_response.json()
                        if access_result.get("Result") == "OK":
                            logger.info(f"Successfully added {target_url} to scan tree via accessUrl API")
                            await asyncio.sleep(2)  # Wait for URL to be processed
                        else:
                            logger.warning(f"Failed to add URL via accessUrl API: {access_result}")
                    except Exception as access_error:
                        logger.warning(f"Failed to add URL via accessUrl API: {access_error}")
                    
                    # Verify URL is now in scan tree
                    urls_check2 = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/view/urls/?apikey=", timeout=10)
                    urls_in_tree2 = urls_check2.json().get("urls", [])
                    target_in_tree2 = any(target_url in url or url in target_url for url in urls_in_tree2)
                    logger.info(f"After accessUrl: scan tree has {len(urls_in_tree2)} URLs, target in tree: {target_in_tree2}")
            except Exception as url_check_error:
                logger.debug(f"Failed to check URLs before active scan: {url_check_error}")
            
            # Start active scan - URL should now be in scan tree
            # CRITICAL: Use recurse=true to scan all URLs in the scan tree, not just the target URL
            # This ensures all discovered URLs are scanned, not just the entry point
            # CRITICAL: Use inScopeOnly=false to scan all URLs, not just those in scope
            # This ensures all discovered URLs are scanned
            active_scan_url = f"{zap_api_url}/JSON/ascan/action/scan/?url={target_url}&recurse=true&inScopeOnly=false"
            if context_name:
                active_scan_url += f"&contextName={context_name}"
            if max_duration > 0:
                active_scan_url += f"&maxDuration={max_duration}"
            active_scan_url += "&apikey="
            
            logger.info(f"ZAP Active Scan URL: {active_scan_url.replace('apikey=', 'apikey=***')}")
            
            active_scan_response = await asyncio.to_thread(http_session.get, active_scan_url, timeout=timeout_seconds)
            active_scan_result = active_scan_response.json()
            
            logger.info(f"ZAP Active Scan API response: {active_scan_result}")
            
            # Check for error in response
            active_scan_id = None
            if "code" in active_scan_result:
                error_code = active_scan_result.get("code")
                if error_code != "OK":
                    error_msg = active_scan_result.get("message", "Unknown error")
                    logger.warning(f"ZAP Active Scan failed with code {error_code}: {error_msg}")
                    # If URL still not found, the spider may not have completed or URL format is wrong
                    if error_code == "url_not_found":
                        # Try using just the base URL without path
                        from urllib.parse import urlparse
                        parsed = urlparse(target_url)
                        base_url = f"{parsed.scheme}://{parsed.netloc}"
                        logger.warning(f"URL not in scan tree, trying base URL: {base_url}")
                        base_scan_url = f"{zap_api_url}/JSON/ascan/action/scan/?url={base_url}&apikey="
                        base_scan_response = await asyncio.to_thread(http_session.get, base_scan_url, timeout=timeout_seconds)
                        base_scan_result = base_scan_response.json()
                        logger.info(f"ZAP Active Scan base URL API response: {base_scan_result}")
                        if base_scan_result.get("code") == "OK":
                            active_scan_id = base_scan_result.get("scan")
                            logger.info(f"Started ZAP Active Scan using base URL: {base_url}, scanId: {active_scan_id}")
                        else:
                            logger.error(f"Failed to start ZAP Active Scan with base URL: {base_scan_result}")
                            raise ValueError(f"Failed to start ZAP Active Scan: {error_msg} (code: {error_code}). URL may not be accessible or spider didn't complete.")
                    else:
                        logger.error(f"ZAP Active Scan failed: {error_msg} (code: {error_code})")
                        raise ValueError(f"Failed to start ZAP Active Scan: {error_msg} (code: {error_code})")
                else:
                    active_scan_id = active_scan_result.get("scan")
                    logger.info(f"Started ZAP Active Scan for {target_url}, scanId: {active_scan_id}")
            else:
                active_scan_id = active_scan_result.get("scan")
                if active_scan_id:
                    logger.info(f"Started ZAP Active Scan for {target_url}, scanId: {active_scan_id}")
                else:
                    logger.warning(f"ZAP Active Scan response missing scanId: {active_scan_result}")
            
            if not active_scan_id:
                logger.error(f"Failed to start ZAP Active Scan: No scanId in response. Response: {active_scan_response.text}")
                raise ValueError(f"Failed to start ZAP Active Scan: {active_scan_response.text}")
            
            # Poll active scan status
            logger.info(f"Polling ZAP Active Scan status for scanId: {active_scan_id}")
            start_time = time.time()
            poll_count = 0
            
            # CRITICAL: Wait a moment after starting the scan before checking status
            # ZAP needs time to initialize the scan and start making requests
            # Also verify the scan actually started by checking if it's in the scans list
            await asyncio.sleep(3)
            
            # Verify scan actually started
            try:
                verify_scans_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/ascan/view/scans/?apikey=", timeout=10)
                verify_scans = verify_scans_response.json().get("scans", [])
                verify_scan = next((s for s in verify_scans if s.get("id") == str(active_scan_id)), None)
                if verify_scan:
                    initial_req_count = int(verify_scan.get("reqCount", "0"))
                    initial_state = verify_scan.get("state", "UNKNOWN")
                    initial_progress = verify_scan.get("progress", "0")
                    logger.info(f"Verified active scan {active_scan_id} started: state={initial_state}, progress={initial_progress}%, reqCount={initial_req_count}")
                    if initial_state == "FINISHED" and initial_req_count == 0:
                        logger.error(
                            f"Active scan {active_scan_id} finished immediately with 0 requests - ZAP cannot access URLs to test them. "
                            f"This indicates a network/configuration issue. ZAP container may not be able to reach external URLs. "
                            f"Target: {target_url}"
                        )
                        # CRITICAL: Since active scan can't access URLs, we should still try to get any alerts that might exist
                        # from passive scanning or previous scans
                        try:
                            # Get all alerts and filter by target
                            alerts_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/view/alerts/?baseurl={target_url}&apikey=", timeout=10)
                            alerts_data = alerts_response.json()
                            all_alerts = alerts_data.get("alerts", [])
                            logger.info(f"Retrieved {len(all_alerts)} total alerts from ZAP (may include alerts from other targets)")
                            
                            # Filter alerts by target domain
                            from urllib.parse import urlparse
                            target_parsed = urlparse(target_url)
                            target_domain = target_parsed.netloc or target_parsed.hostname
                            
                            target_alerts = []
                            for alert in all_alerts:
                                alert_url = alert.get("url", "")
                                if alert_url:
                                    alert_parsed = urlparse(alert_url)
                                    alert_domain = alert_parsed.netloc or alert_parsed.hostname
                                    if alert_domain == target_domain or alert_url.startswith(target_url):
                                        target_alerts.append(alert)
                            
                            if len(target_alerts) > 0:
                                logger.info(f"Found {len(target_alerts)} alerts for target {target_domain} despite active scan failure")
                            else:
                                logger.warning(f"No alerts found for target {target_domain} - ZAP cannot access this URL")
                        except Exception as alerts_error:
                            logger.debug(f"Failed to get alerts after active scan failure: {alerts_error}")
                        
                        # Try to get more details about why the scan failed
                        try:
                            scan_progress_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/ascan/view/scanProgress/?scanId={active_scan_id}&apikey=", timeout=10)
                            scan_progress = scan_progress_response.json()
                            logger.error(f"Active scan progress details: {json.dumps(scan_progress, indent=2)[:500]}")
                        except Exception as progress_error:
                            logger.debug(f"Failed to get scan progress: {progress_error}")
                else:
                    logger.warning(f"Active scan {active_scan_id} not found in scans list after 3 seconds")
            except Exception as verify_error:
                logger.debug(f"Failed to verify scan start: {verify_error}")
            
            while True:
                poll_count += 1
                status_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/ascan/view/status/?scanId={active_scan_id}&apikey=", timeout=10)
                status_result = status_response.json()
                status_percent = int(status_result.get("status", "0"))
                
                # Also check scan details to see if it's actually running
                try:
                    scans_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/ascan/view/scans/?apikey=", timeout=10)
                    scans_data = scans_response.json().get("scans", [])
                    current_scan = next((s for s in scans_data if s.get("id") == str(active_scan_id)), None)
                    if current_scan:
                        req_count = int(current_scan.get("reqCount", "0"))
                        alert_count = int(current_scan.get("alertCount", "0"))
                        state = current_scan.get("state", "UNKNOWN")
                        # Log status every 5 polls (every ~25 seconds) or on first poll, or if reqCount changes
                        if poll_count == 1 or poll_count % 5 == 0 or req_count > 0:
                            logger.info(f"ZAP Active Scan status (poll {poll_count}): {status_percent}%, state={state}, reqCount={req_count}, alertCount={alert_count}")
                        
                        # If scan is finished but made no requests, this is suspicious
                        if state == "FINISHED" and req_count == 0 and poll_count == 1:
                            logger.warning(f"ZAP Active Scan finished immediately with 0 requests - scan may not have run properly")
                    else:
                        logger.warning(f"ZAP Active Scan {active_scan_id} not found in scans list")
                except Exception as scan_detail_error:
                    logger.debug(f"Failed to get scan details: {scan_detail_error}")
                    # Fall back to simple status logging
                    if poll_count == 1 or poll_count % 5 == 0:
                        logger.info(f"ZAP Active Scan status (poll {poll_count}): {status_percent}%")
                
                if status_percent >= 100:
                    logger.info(f"ZAP Active Scan reached 100% after {poll_count} polls ({time.time() - start_time:.1f}s)")
                    break
                if time.time() - start_time > timeout_seconds:
                    logger.warning(f"ZAP Active Scan timeout after {timeout_seconds}s (status: {status_percent}%)")
                    raise subprocess.TimeoutExpired(cmd="ZAP Active Scan", timeout=timeout_seconds)
                await asyncio.sleep(5)
            logger.info(f"ZAP Active Scan completed for {target_url} (total time: {time.time() - start_time:.1f}s)")
            
        elif mode_id == "ajax_spider":
            logger.info(f"Starting ZAP AJAX Spider for {target_url}...")
            max_depth = kwargs.get("max_depth", 10)
            max_children = kwargs.get("max_children", 100)
            
            # AJAX Spider API - contextName is optional
            ajax_spider_url = f"{zap_api_url}/JSON/ajaxSpider/action/scan/?url={target_url}&maxDepth={max_depth}&maxChildren={max_children}&apikey="
            
            ajax_spider_response = await asyncio.to_thread(http_session.get, ajax_spider_url, timeout=timeout_seconds)
            ajax_spider_result = ajax_spider_response.json()
            
            # ZAP AJAX Spider API returns {"Result":"OK"} on success, not {"code":"OK"}
            # Check for both formats
            if "Result" in ajax_spider_result:
                if ajax_spider_result.get("Result") != "OK":
                    raise ValueError(f"Failed to start ZAP AJAX Spider: {ajax_spider_result}")
                # Success - continue
            elif "code" in ajax_spider_result and ajax_spider_result.get("code") != "OK":
                raise ValueError(f"Failed to start ZAP AJAX Spider: {ajax_spider_result}")
            
            # AJAX Spider doesn't return a scan ID like active scan
            # It runs immediately and we poll the status
            ajax_spider_id = None  # AJAX Spider doesn't use scan IDs
            
            # Poll AJAX spider status (no scanId needed for AJAX Spider)
            start_time = time.time()
            while True:
                # AJAX Spider status endpoint doesn't require scanId
                status_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/ajaxSpider/view/status/?apikey=", timeout=10)
                status_result = status_response.json()
                # Status can be in "status" field or "Result" field
                status_text = status_result.get("status", status_result.get("Result", "running"))
                logger.debug(f"ZAP AJAX Spider status: {status_text}")
                if status_text in ["stopped", "OK"]:
                    break
                if time.time() - start_time > timeout_seconds:
                    raise subprocess.TimeoutExpired(cmd="ZAP AJAX Spider", timeout=timeout_seconds)
                await asyncio.sleep(5)
            logger.info(f"ZAP AJAX Spider completed for {target_url}")
        
        # Retrieve alerts - try without baseurl first to get all alerts, then filter
        # ZAP's baseurl filter can be too restrictive, so we get all alerts and filter client-side
        try:
            # #region agent log
            try:
                debug_log_path = "/app/data/debug.log"
                with open(debug_log_path, "a") as f:
                    import json as json_lib
                    import time
                    f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H7","location":"tools.py:2333","message":"Before retrieving ZAP alerts","data":{"target_url":target_url,"mode_id":mode_id,"scan_job_id":scan_job_id},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            
            # Retry alert retrieval with exponential backoff (ZAP connection can be flaky)
            max_retries = 5
            retry_delay = 2
            all_alerts = []
            for attempt in range(max_retries):
                try:
                    alerts_response = await asyncio.to_thread(http_session.get, f"{zap_api_url}/JSON/core/view/alerts/?apikey=", timeout=30)
                    alerts_response.raise_for_status()
                    all_alerts = alerts_response.json().get("alerts", [])
                    logger.info(f"Successfully retrieved {len(all_alerts)} alerts from ZAP (attempt {attempt + 1})")
                    break
                except (requests.exceptions.ConnectionError, requests.exceptions.ProtocolError, requests.exceptions.Timeout) as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Failed to retrieve ZAP alerts (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, 10)  # Exponential backoff, max 10s
                        # Recreate session if connection was closed
                        http_session = requests.Session()
                        http_session.mount('http://', requests.adapters.HTTPAdapter(max_retries=1))
                    else:
                        logger.error(f"Failed to retrieve ZAP alerts after {max_retries} attempts: {e}")
                        raise
            
            # #region agent log
            try:
                debug_log_path = "/app/data/debug.log"
                with open(debug_log_path, "a") as f:
                    import json as json_lib
                    import time
                    f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H7","location":"tools.py:2338","message":"Retrieved all alerts from ZAP","data":{"total_alerts":len(all_alerts),"sample_alert_urls":[a.get("url","")[:100] for a in all_alerts[:3]]},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            
            # Filter alerts by target URL (check if alert URL starts with target_url)
            from urllib.parse import urlparse
            target_parsed = urlparse(target_url)
            target_domain = target_parsed.netloc or target_parsed.hostname
            target_base = f"{target_parsed.scheme}://{target_parsed.netloc}"
            
            # CRITICAL FIX: For Pro/Advanced scans, be more lenient with alert filtering
            # ZAP may find alerts on related URLs (subdomains, different paths) that are still relevant
            # Include ALL alerts from the same base domain (scheme + netloc) regardless of path
            alerts = []
            filtered_out = []
            for alert in all_alerts:
                alert_url = alert.get("url", "")
                if alert_url:
                    try:
                        alert_parsed = urlparse(alert_url)
                        alert_domain = alert_parsed.netloc or alert_parsed.hostname
                        alert_base = f"{alert_parsed.scheme}://{alert_parsed.netloc}" if alert_parsed.scheme and alert_parsed.netloc else None
                        
                        # Match if:
                        # 1. Same domain (most common case)
                        # 2. Same base URL (scheme + netloc) - includes all paths
                        # 3. Alert URL starts with target URL (for specific page scans)
                        # 4. Target URL starts with alert base (for reverse matching)
                        if (alert_domain == target_domain or 
                            alert_base == target_base or
                            alert_url.startswith(target_url) or
                            target_url.startswith(alert_base or "")):
                            alerts.append(alert)
                        else:
                            filtered_out.append({"url": alert_url[:100], "domain": alert_domain, "base": alert_base})
                    except Exception as parse_err:
                        # If URL parsing fails, include the alert anyway (better to show than hide)
                        logger.debug(f"Failed to parse alert URL {alert_url[:100]}: {parse_err}, including alert anyway")
                        alerts.append(alert)
                else:
                    # Alert has no URL - include it anyway (might be a general finding)
                    alerts.append(alert)
            
            logger.info(
                f"Retrieved {len(alerts)} ZAP alerts for {target_url} "
                f"(total alerts: {len(all_alerts)}, scan_job_id: {scan_job_id}, target_domain: {target_domain}, target_base: {target_base})"
            )
            
            # #region agent log
            try:
                debug_log_path = "/app/data/debug.log"
                with open(debug_log_path, "a") as f:
                    import json as json_lib
                    import time
                    f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H7","location":"tools.py:2365","message":"After filtering alerts","data":{"total_alerts":len(all_alerts),"filtered_alerts":len(alerts),"target_domain":target_domain,"target_base":target_base,"filtered_out_sample":filtered_out[:3]},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            
            # DEBUG: Log if we're filtering out alerts
            if len(all_alerts) > 0 and len(alerts) == 0:
                logger.warning(
                    f"ZAP found {len(all_alerts)} total alerts but filtered to 0 for {target_url}. "
                    f"Target domain: {target_domain}, target_base: {target_base}. "
                    f"Sample alert domains: {[urlparse(a.get('url', '')).netloc for a in all_alerts[:3]]}. "
                    f"Sample filtered out: {filtered_out[:3]}"
                )
                # CRITICAL: If we have alerts but filtered to 0, include at least some alerts to avoid 0 results
                # This ensures ZAP results are shown even if domain matching is slightly off
                if len(all_alerts) > 0:
                    logger.info(f"Including first {min(5, len(all_alerts))} alerts as fallback to avoid 0 results")
                    alerts = all_alerts[:5]  # Include first 5 alerts as fallback
        except Exception as e:
            logger.error(f"Failed to retrieve ZAP alerts: {e}", exc_info=True)
            alerts = []
        
        # Convert ZAP alerts to findings format
        findings = []
        for alert in alerts:
            # Map ZAP severity to Thandev severity
            severity_map = {
                "0": "info",      # Informational
                "1": "low",       # Low
                "2": "medium",    # Medium
                "3": "high",      # High
                "4": "critical",  # Critical
            }
            severity = severity_map.get(alert.get("riskcode"), "info")
            
            findings.append({
                "tool_id": "zap",
                "title": alert.get("alert"),
                "severity": severity,
                "description": alert.get("description"),
                "evidence": alert.get("solution"),
                "url": alert.get("url"),
                "host": urlparse(alert.get("url")).hostname,
                "port": urlparse(alert.get("url")).port,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "raw": json.dumps(alert),
            })
        
        # Return findings as JSON string
        # CRITICAL: Always return findings array, even if empty, so parser can process it
        findings_json = json.dumps(findings)
        logger.info(
            f"ZAP scan {scan_job_id} completed: {len(findings)} findings generated. "
            f"Output length: {len(findings_json)} bytes"
        )
        return {
            "tool_name": "zap",
            "output": findings_json,
            "exit_code": 0,
            "command": f"ZAP API calls for {mode_id}",
            "success": True,
        }

    async def _run_sqlmap(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run sqlmap SQL injection scanner
        
        Optional kwargs:
            timeout_seconds: timeout in seconds (default: 900 for 15 minutes)
            profile: profile name (e.g., "sqli_light") - currently not used but available
        """
        from app.utils.param_harvester import ParamHarvester, create_fallback_targets
        
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        mode_id = kwargs.get("mode_id", "sqli_light")
        scan_job_dir = kwargs.get("scan_job_dir")
        logger.info(f"Checking sqlmap availability for scan {scan_job_id}, mode={mode_id}")
        
        # 1. Harvest parameterized requests from ZAP/crawler outputs first
        logger.info(f"Harvesting parameterized endpoints for SQLMap scan {scan_job_id}: {target_url}")
        harvester = ParamHarvester(job_dir=scan_job_dir)
        
        # Try to harvest from job directory (ZAP output, etc.)
        parameterized_urls = []
        harvested_requests = []
        if scan_job_dir:
            harvested_count = harvester.harvest_from_job_dir()
            logger.info(f"SQLMap scan {scan_job_id}: Harvested {harvested_count} parameterized requests from job dir")
            harvested_requests = harvester.get_all_requests()
        
        # 2. Also crawl to get additional endpoints (only if in generic scan mode)
        if mode_id in ["sqli_light", "sqli_get_basic"]:
            logger.info(f"Crawling target for SQLMap scan {scan_job_id}...")
            try:
                _, parameterized_urls = await self._crawl_target(target_url, scan_job_id, scan_level)
                logger.info(f"SQLMap found {len(parameterized_urls)} parameterized URLs from crawler")
                
                # Add crawler results to harvester
                if parameterized_urls:
                    crawler_count = harvester.harvest_from_crawler_output(parameterized_urls)
                    logger.info(f"SQLMap scan {scan_job_id}: Added {crawler_count} URLs from crawler")
            except Exception as crawl_error:
                logger.warning(f"SQLMap crawler failed for {scan_job_id}: {crawl_error}. Will test target URL directly.")
                parameterized_urls = []
        
        # Get all harvested parameterized URLs
        harvested_param_urls = harvester.get_parameterized_urls()
        
        # Combine all sources
        combined_urls = set(parameterized_urls)
        combined_urls.update(harvested_param_urls)
        parameterized_urls = list(combined_urls)
        
        # Always include the target URL if it's a login page or has parameters
        # For login pages, we MUST test them even if crawler found nothing
        if target_url not in parameterized_urls:
            # Check if it's a login page (common patterns)
            if 'login' in target_url.lower() or 'signin' in target_url.lower() or 'auth' in target_url.lower():
                parameterized_urls.append(target_url)
                logger.info(f"SQLMap: Added login page {target_url} to parameterized URLs (will test with --forms)")
            elif '?' in target_url:
                parameterized_urls.append(target_url)
        
        # If still no URLs, create fallback targets with common parameters
        if not parameterized_urls:
            logger.warning(
                f"SQLMap scan {scan_job_id}: No parameterized URLs found from harvester or crawler! "
                f"Creating fallback test parameters."
            )
            fallback_urls = create_fallback_targets(target_url)
            parameterized_urls.extend(fallback_urls)
            logger.info(f"SQLMap scan {scan_job_id}: Added {len(fallback_urls)} fallback parameterized URLs")
        
        # Get stats
        harvester_stats = harvester.get_stats()
        logger.info(
            f"SQLMap scan {scan_job_id}: Will test {len(parameterized_urls)} URLs total "
            f"({harvester_stats['total_requests']} from harvester with {harvester_stats['total_parameters']} params)."
        )
        
        # Try to find sqlmap in common locations (container installation first)
        sqlmap_path = None
        possible_paths = [
            "/opt/sqlmap/sqlmap.py",  # Container installation (baked into image)
            "sqlmap",  # In PATH
            str(Path.home() / ".local" / "bin" / "sqlmap"),  # User local bin
            "/usr/local/bin/sqlmap",  # System local
            "/usr/bin/sqlmap",  # System bin
        ]
        
        for path in possible_paths:
            try:
                check_result = await asyncio.to_thread(subprocess.run,
                    [path, "--version"],
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                if check_result.returncode == 0:
                    sqlmap_path = path
                    logger.info(f"sqlmap binary found at {path} for scan {scan_job_id}: {check_result.stdout.strip()[:50]}")
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
                continue
        
        if not sqlmap_path:
            error_msg = "sqlmap binary not found. Please install sqlmap: pip install sqlmap or download from https://github.com/sqlmapproject/sqlmap"
            logger.error(f"sqlmap binary not found for scan {scan_job_id}")
            return {
                "tool_name": "sqlmap",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "sqlmap --version",
                "timed_out": False,
            }
        
        # Get timeout from kwargs or default to 900 seconds (15 minutes)
        # Increase timeout if we have many URLs
        base_timeout = kwargs.get("timeout_seconds", 300)
        timeout = base_timeout
        if parameterized_urls:
            timeout = max(base_timeout, len(parameterized_urls) * 60) # 1 min per URL minimum
        
        # Get output directory from kwargs (scan_job_dir)
        # This should be the same job_dir used by other tools (backend/data/jobs/scan_job_id)
        scan_job_dir = kwargs.get("scan_job_dir")
        if not scan_job_dir:
            # Fallback: try to infer from scan_job_id or create temp directory
            # Use same canonical path as other tools: backend/data/jobs/scan_job_id
            scan_job_dir = Path(os.getenv("JOBS_DIR", "/tmp/jobs")) / scan_job_id
            logger.warning(
                f"SQLMap scan_job_dir not provided, using inferred path: {scan_job_dir} "
                f"(scan_job_id: {scan_job_id})"
            )
        else:
            scan_job_dir = Path(scan_job_dir)
        
        # Ensure job directory exists (canonical path for all tools)
        scan_job_dir.mkdir(parents=True, exist_ok=True)
        
        # Create sqlmap output directory (sqlmap creates subdirectory for its output)
        sqlmap_output_dir = scan_job_dir / "sqlmap"
        sqlmap_output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"SQLMap output directory for scan {scan_job_id}: {sqlmap_output_dir} "
            f"(job_dir: {scan_job_dir})"
        )
        
        # Get mode-specific parameters
        level = kwargs.get("level", 2)
        risk = kwargs.get("risk", 1)
        
        # For Advanced scans, force stronger checks if not specified
        if scan_level == "advanced":
            level = max(level, 5)
            risk = max(risk, 3)
            
        request_timeout = 120  # Increased from 60 to 120 for slow/unstable connections
        
        # Build sqlmap command based on mode
        cmd = [sqlmap_path, "--batch"]
        
        # Mode-specific command building
        # CRITICAL: For login pages, always use --forms directly, don't use bulk mode
        is_login_page = 'login' in target_url.lower() or 'signin' in target_url.lower() or 'auth' in target_url.lower()
        
        if is_login_page and mode_id in ["sqli_light", "sqli_get_basic"]:
            # For login pages, test directly with --forms (POST parameters)
            cmd.extend(["-u", target_url, "--forms"])
            logger.info(f"SQLMap: Testing login form at {target_url} directly with --forms (bypassing bulk mode)")
        elif parameterized_urls and mode_id in ["sqli_light", "sqli_get_basic"] and not is_login_page:
            # Use bulk mode only for non-login pages with multiple URLs
            bulk_file = sqlmap_output_dir / "bulk_targets.txt"
            with open(bulk_file, "w") as f:
                f.write("\n".join(parameterized_urls))
            
            cmd.extend(["-m", str(bulk_file)])
            # Use smart heuristics
            cmd.extend(["--smart"])
            
            logger.info(f"Using bulk mode for SQLMap with {len(parameterized_urls)} targets")
            
        elif mode_id == "sqli_raw_request":
            # Use raw request file (-r)
            raw_request_ref = kwargs.get("raw_request_ref")
            if not raw_request_ref:
                raise ValueError("sqli_raw_request mode requires raw_request_ref parameter")
            
            # Check if it's a file path or inline request
            raw_request_path = Path(raw_request_ref)
            if not raw_request_path.exists():
                # Assume it's inline request text, save it to a file
                raw_request_path = sqlmap_output_dir / "request.txt"
                with open(raw_request_path, 'w', encoding='utf-8') as f:
                    f.write(raw_request_ref)
                logger.info(f"Saved inline raw request to {raw_request_path}")
            
            cmd.extend(["-r", str(raw_request_path)])
            
        elif mode_id == "sqli_forms_login":
            # For login forms, prefer raw request method for reliability
            use_raw_request = kwargs.get("use_raw_request", True)
            
            if use_raw_request:
                # Build raw request from login form
                # Note: request_recorder not available in runner, use --forms instead
                logger.warning(f"use_raw_request=True for sqli_forms_login but request_recorder not available in runner, falling back to --forms")
                cmd.extend(["-u", target_url, "--forms", "--crawl=0"])
            else:
                # Use --forms for form-based SQL injection testing
                cmd.extend(["-u", target_url, "--forms", "--crawl=0"])
                
        elif mode_id == "sqli_post_data":
            # Use --data for POST requests
            post_data = kwargs.get("post_data")
            if not post_data:
                raise ValueError("sqli_post_data mode requires post_data parameter")
            
            cmd.extend(["-u", target_url, "--data", post_data])
            
            # Add cookie if provided
            cookie = kwargs.get("cookie")
            if cookie:
                cmd.extend(["--cookie", cookie])
            
            # Test specific parameters if provided
            param_names = kwargs.get("param_names")
            if param_names:
                cmd.extend(["-p", ",".join(param_names)])
                
        elif mode_id == "sqli_get_basic":
            # Basic GET request with URL (fallback if no params found or logic above skipped)
            cmd.extend(["-u", target_url])
            
            # Test specific parameters if provided
            param_names = kwargs.get("param_names")
            if param_names:
                cmd.extend(["-p", ",".join(param_names)])
                
        else:
            # Legacy mode: sqli_light (fallback)
            # For login pages, use --forms to test form parameters
            # Don't use --crawl=1 if we already crawled (it causes connection issues)
            if parameterized_urls:
                # Use bulk mode with crawled URLs
                bulk_file = sqlmap_output_dir / "bulk_targets.txt"
                with open(bulk_file, "w") as f:
                    f.write("\n".join(parameterized_urls))
                cmd.extend(["-m", str(bulk_file), "--smart"])
            else:
                # Test the target URL directly with forms
                # For login pages, use --forms to test POST parameters
                # CRITICAL: Don't use --crawl=0 as it might prevent form testing
                is_login_page = 'login' in target_url.lower() or 'signin' in target_url.lower() or 'auth' in target_url.lower()
                if is_login_page:
                    # For login pages, explicitly test forms (POST parameters)
                    cmd.extend(["-u", target_url, "--forms"])
                    logger.info(f"SQLMap: Testing login form at {target_url} with --forms flag (no --crawl to avoid connection issues)")
                else:
                    # For other pages, test URL directly with forms
                    cmd.extend(["-u", target_url, "--forms", "--crawl=0"])
        
        # Add common flags
        cmd.extend([
            "--risk", str(risk),
            "--level", str(level),
            "--timeout", str(request_timeout),
            "--time-sec", "5",  # Time-based injection delay
            "--retries", "3",  # Retry failed requests up to 3 times
            "--random-agent",
            "--technique", "BEUSTQ",  # Test all techniques
            "--fresh-queries",
            "--threads", "2",  # Slightly more threads
            "-v", "3",  # Verbosity level 3
            "--output-dir", str(sqlmap_output_dir),
        ])
        
        # Safe defaults - no destructive flags
        # DO NOT add: --os-shell, --file-write, --sql-shell, etc.
        
        logger.info(
            "sqlmap command for scan %s: %s (output_dir: %s)",
            scan_job_id, " ".join(cmd), sqlmap_output_dir
        )
        
        try:
            # Track execution start time
            import time
            exec_start_time = time.time()

            # Use asyncio.to_thread to prevent blocking event loop
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            exec_duration = time.time() - exec_start_time
            stdout_bytes = len(result.stdout.encode("utf-8")) if result.stdout else 0
            stderr_bytes = len(result.stderr.encode("utf-8")) if result.stderr else 0
            exit_code = result.returncode
            
            logger.info(
                "sqlmap scan %s completed: exit_code=%s, stdout=%d bytes, stderr=%d bytes, output_dir=%s",
                scan_job_id, exit_code, stdout_bytes, stderr_bytes, sqlmap_output_dir
            )
            
            # Check if output directory has artifacts
            artifacts = list(sqlmap_output_dir.rglob("*")) if sqlmap_output_dir.exists() else []
            logger.info(
                "sqlmap scan %s: output_dir exists=%s, artifacts found=%d",
                scan_job_id, sqlmap_output_dir.exists(), len(artifacts)
            )
            
            # sqlmap may exit with non-zero even when it finds SQLi issues
            # Consider it successful if we have output or if output directory has result files
            is_error = False
            error_msg = None
            
            # Check if sqlmap found SQL injection (look in stdout)
            # sqlmap outputs detection results to stdout with patterns like:
            # - "GET parameter 'X' is vulnerable"
            # - "sqlmap identified the following injection point(s)"
            has_results = False
            
            if result.stdout:
                stdout_lower = result.stdout.lower()
                # Check for key detection phrases
                detection_phrases = [
                    "is vulnerable",
                    "injection point",
                    "is '",
                    "appears to be '",
                    "injectable",
                ]
                for phrase in detection_phrases:
                    if phrase in stdout_lower:
                        has_results = True
                        logger.info("sqlmap detected SQL injection in stdout for scan %s (phrase: %s)", scan_job_id, phrase)
                        break
                
                # Also check for the detailed injection point section
                if "sqlmap identified the following injection point" in stdout_lower:
                    has_results = True
                    logger.info("sqlmap found detailed injection points for scan %s", scan_job_id)
            
            # Also check log files in output directory
            if not has_results:
                log_files = list(sqlmap_output_dir.glob("*.log")) + list(sqlmap_output_dir.glob("*.txt"))
                for log_file in log_files:
                    try:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            log_content = f.read().lower()
                            if any(phrase in log_content for phrase in ["is vulnerable", "injection point", "injectable"]):
                                has_results = True
                                logger.info("sqlmap detected SQL injection in log file %s for scan %s", log_file, scan_job_id)
                                break
                    except Exception as e:
                        logger.debug("Failed to read log file %s: %s", log_file, e)
            
            # Also check for CSV files (in case --dump was used or sqlmap created them)
            result_files = list(sqlmap_output_dir.glob("*.csv")) + list(sqlmap_output_dir.glob("*.json"))
            if result_files:
                has_results = True
            
            if exit_code != 0:
                if has_results or stdout_bytes > 0:
                    # We have results, so the scan found some SQLi issues
                    logger.info(
                        "sqlmap scan %s completed with exit_code=%s but produced results (treating as success)",
                        scan_job_id, exit_code
                    )
                elif result.stderr:
                    stderr_lower = result.stderr.lower()
                    if any(keyword in stderr_lower for keyword in ["error", "failed", "fatal", "cannot", "not found"]):
                        is_error = True
                        error_msg = f"sqlmap exited with code {exit_code}: {result.stderr[:200]}"
                        logger.warning("sqlmap scan %s failed: %s", scan_job_id, error_msg)
                    else:
                        logger.info(
                            "sqlmap scan %s completed with exit_code=%s (no SQLi found, treating as success)",
                            scan_job_id, exit_code
                        )
                else:
                    logger.info(
                        "sqlmap scan %s completed with exit_code=%s and no results (no SQLi found, treating as success)",
                        scan_job_id, exit_code
                    )
            
            if is_error:
                return {
                    "tool_name": "sqlmap",
                    "output": result.stdout,  # Still return any partial output
                    "exit_code": exit_code,
                    "error": error_msg,
                    "command": " ".join(cmd),
                    "timed_out": False,
                    "output_dir": str(sqlmap_output_dir),
                    "execution_time": exec_duration,  # Accurate subprocess-only execution time
                    "targets_count": len(parameterized_urls),
                    "meta": {
                        "harvested_requests": harvester_stats.get("total_requests", 0),
                        "total_parameters": harvester_stats.get("total_parameters", 0),
                        "mode_id": mode_id,
                    },
                }
            
            # Success case - log findings status
            # Note: We don't claim "SQLi detected" here - that's determined by the ingestor
            # We only log that the scan completed and produced output
            if has_results:
                logger.info(
                    "sqlmap scan %s completed: stdout indicates potential SQLi (will be confirmed by ingestor)",
                    scan_job_id
                )
            elif stdout_bytes > 0:
                logger.info("sqlmap scan %s completed: stdout produced but no clear SQLi markers", scan_job_id)
            else:
                logger.info("sqlmap scan %s completed: no output produced", scan_job_id)
            
            return {
                "tool_name": "sqlmap",
                "output": result.stdout,
                "exit_code": exit_code,
                "command": " ".join(cmd),
                "timed_out": False,
                "output_dir": str(sqlmap_output_dir),
                "stderr": result.stderr[:4000] if result.stderr else None,
                "success": True,  # Always mark as success if we got here (even if no SQLi found)
                "execution_time": exec_duration,  # Accurate subprocess-only execution time
                "targets_count": len(parameterized_urls),  # Number of URLs tested
                "meta": {
                    "harvested_requests": harvester_stats.get("total_requests", 0),
                    "total_parameters": harvester_stats.get("total_parameters", 0),
                    "mode_id": mode_id,
                },
            }
        except subprocess.TimeoutExpired as exc:
            # Calculate execution time even on timeout
            exec_duration = time.time() - exec_start_time
            logger.warning("sqlmap scan %s timed out after %d seconds (%d minutes, actual: %.2fs). Checking for partial results...", 
                          scan_job_id, timeout, timeout // 60, exec_duration)
            logger.warning("  Command: %s", " ".join(cmd))
            
            # Check for partial results even on timeout
            result_files = list(sqlmap_output_dir.glob("*.csv")) + list(sqlmap_output_dir.glob("*.json")) + list(sqlmap_output_dir.glob("*.txt"))
            has_results = len(result_files) > 0
            
            # Try to read any output that was captured
            partial_output = ""
            if hasattr(exc, 'stdout') and exc.stdout:
                partial_output = exc.stdout.decode('utf-8', errors='ignore') if isinstance(exc.stdout, bytes) else exc.stdout
            
            if has_results:
                logger.info("sqlmap scan %s timed out but found partial results: %d files", scan_job_id, len(result_files))
                return {
                    "tool_name": "sqlmap",
                    "output": partial_output,
                    "exit_code": None,  # None indicates timeout
                    "error": f"Tool execution timed out after {timeout} seconds, but partial results found",
                    "command": " ".join(cmd),
                    "timed_out": True,
                    "output_dir": str(sqlmap_output_dir),
                    "success": True,  # Mark as success if we have results
                    "execution_time": exec_duration,  # Actual time before timeout
                }
            else:
                return {
                    "tool_name": "sqlmap",
                    "output": partial_output,
                    "exit_code": None,  # None indicates timeout
                    "error": f"Tool execution timed out after {timeout} seconds ({timeout // 60} minutes)",
                    "command": " ".join(cmd),
                    "timed_out": True,
                    "output_dir": str(sqlmap_output_dir),
                    "execution_time": exec_duration,  # Actual time before timeout
                }
        except Exception as e:
            logger.error(f"sqlmap execution error for scan {scan_job_id}: {e}", exc_info=True)
            logger.error(f"  Command: {' '.join(cmd)}")
            logger.error(f"  Target URL: {target_url}")
            return {
                "tool_name": "sqlmap",
                "output": "",
                "exit_code": -1,
                "error": f"sqlmap execution failed: {str(e)}",
                "command": " ".join(cmd),
                "timed_out": False,
                "output_dir": str(sqlmap_output_dir),
            }
    
    async def _run_sslscan(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """Run SSL/TLS scanner"""
        from urllib.parse import urlparse
        
        parsed = urlparse(target_url)
        hostname = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        
        if not hostname:
            raise ValueError(f"Invalid URL: {target_url}")
        
        target = f"{hostname}:{port}"
        
        # Note: sslscan doesn't support --json flag, it outputs text with ANSI colors
        cmd = ["sslscan", target]
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            
            return {
                "tool_name": "sslscan",
                "output": result.stdout,
                "exit_code": result.returncode,
                "command": " ".join(cmd),
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "sslscan",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out",
            }
        except FileNotFoundError:
            # Fallback to openssl if sslscan not available
            logger.warning("sslscan not found, using openssl fallback")
            return await self._run_openssl_fallback(hostname, port)
    
    async def _run_openssl_fallback(self, hostname: str, port: int) -> Dict:
        """Fallback SSL check using openssl"""
        cmd = [
            "openssl", "s_client",
            "-connect", f"{hostname}:{port}",
            "-showcerts",
        ]
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                input="",  # Close connection immediately
            )
            
            return {
                "tool_name": "openssl",
                "output": result.stdout,
                "exit_code": result.returncode,
                "command": " ".join(cmd),
            }
        except Exception as e:
            return {
                "tool_name": "openssl",
                "output": "",
                "exit_code": -1,
                "error": str(e),
            }
    
    # TODO: Vulnerability classes covered by httpx:
    # - HTTP Surface Discovery (identifies endpoints, status codes, technologies)
    # - Content Discovery (via response analysis)
    # Note: httpx is primarily a reconnaissance tool, not a vulnerability scanner
    async def _run_httpx(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run httpx HTTP surface scanner (ProjectDiscovery httpx)
        
        Optional kwargs:
            intensity: "low", "medium", "high" (from tool config, currently not used but available)
        """
        # Check if ProjectDiscovery httpx is installed
        # Note: Python httpx library also has a CLI, so we need to verify it's the right one
        # Python httpx errors on -u flag, ProjectDiscovery httpx supports it
        httpx_binary = None
        
        # Try common locations for ProjectDiscovery httpx
        # Check ~/go/bin first (most common location) before PATH to avoid Python httpx
        # Also check ~/.local/bin which is common in user installations
        possible_paths = [
            os.path.expanduser("~/go/bin/httpx"),  # Go bin directory (check first!)
            os.path.expanduser("~/.local/bin/httpx"),  # User local bin (common location)
            "/usr/local/bin/httpx",
            "/usr/local/bin/httpx-projectdiscovery",
            "/usr/bin/httpx",  # System bin
            "httpx",  # In PATH (check last to avoid Python httpx)
        ]
        
        for binary_path in possible_paths:
            try:
                test_cmd = [binary_path, "-u", "https://example.com", "-silent", "-json"]
                test_result = await asyncio.to_thread(subprocess.run,
                    test_cmd,
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                # Python httpx will error with "No such option: -u" or "required dependencies"
                # ProjectDiscovery httpx will either succeed or fail with different error
                stderr_lower = test_result.stderr.lower()
                if ("no such option" not in stderr_lower and 
                    "error: no such option" not in stderr_lower and
                    "required dependencies" not in stderr_lower and
                    "could not run" not in stderr_lower):
                    httpx_binary = binary_path
                    logger.info(f"Detected ProjectDiscovery httpx binary at: {binary_path}")
                    break
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.debug(f"httpx detection test failed for {binary_path}: {e}")
                continue
        
        if not httpx_binary:
            error_msg = "ProjectDiscovery httpx binary not found. The system has Python httpx (HTTP client) installed, but we need ProjectDiscovery httpx (security scanner). Install with: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest (or download from https://github.com/projectdiscovery/httpx/releases). After installation, ensure ~/go/bin is in your PATH."
            logger.error(f"httpx binary not found: {error_msg}")
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "httpx -u <url> -json",
                "success": False,
            }
        
        # httpx (ProjectDiscovery) command flags:
        # -u: target URL (required)
        # -json: output JSON format (one JSON object per line)
        # -follow-redirects: follow HTTP redirects
        # -status-code: include HTTP status code in output
        # -title: extract page title
        # -tech-detect: detect web technologies
        # -tls-probe: probe TLS/SSL information
        # -silent: suppress non-JSON output
        cmd = [
            httpx_binary,
            "-u", target_url,
            "-json",
            "-follow-redirects",
            "-status-code",
            "-title",
            "-tech-detect",
            "-tls-probe",
            "-silent",
        ]
        
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        logger.info("httpx command for scan %s: %s", scan_job_id, " ".join(cmd))
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            
            exit_code = result.returncode
            stdout_bytes = len(result.stdout.encode("utf-8")) if result.stdout else 0
            stderr_bytes = len(result.stderr.encode("utf-8")) if result.stderr else 0
            
            logger.info(
                "httpx completed for scan %s: exit_code=%s, stdout_bytes=%d, stderr_bytes=%d",
                scan_job_id, exit_code, stdout_bytes, stderr_bytes
            )
            
            # httpx may exit with non-zero even when it successfully probes URLs
            # Consider it successful if we have output OR if exit code is just a warning
            # Only treat as error if exit_code is non-zero AND we have no output AND stderr indicates failure
            is_error = False
            error_msg = None
            
            if exit_code != 0:
                # Check if we have useful output despite non-zero exit
                if stdout_bytes > 0:
                    # We have output, so the scan was partially successful
                    logger.info(
                        "httpx scan %s completed with exit_code=%s but produced %d bytes of output (treating as success)",
                        scan_job_id, exit_code, stdout_bytes
                    )
                elif result.stderr:
                    # Check stderr for actual errors vs warnings
                    stderr_lower = result.stderr.lower()
                    if any(keyword in stderr_lower for keyword in ["error", "failed", "fatal", "cannot"]):
                        is_error = True
                        error_msg = f"httpx exited with code {exit_code}: {result.stderr[:200]}"
                        logger.warning("httpx scan %s failed: %s", scan_job_id, error_msg)
                    else:
                        # Likely just a warning, not a fatal error
                        logger.info(
                            "httpx scan %s completed with exit_code=%s (likely no reachable URLs, treating as success)",
                            scan_job_id, exit_code
                        )
                else:
                    # No output and no stderr - might be unreachable target
                    logger.warning(
                        "httpx scan %s completed with exit_code=%s and no output (target unreachable). Skipping as success.",
                        scan_job_id, exit_code
                    )
                    return {
                        "tool_name": "httpx",
                        "output": "[]",
                        "exit_code": 0,
                        "command": " ".join(cmd),
                        "timed_out": False,
                        "error": "Target unreachable (no output from httpx)",
                        "success": True 
                    }
            
            if is_error:
                return {
                    "tool_name": "httpx",
                    "output": result.stdout,  # Still return any partial output
                    "exit_code": exit_code,
                    "error": error_msg,
                    "command": " ".join(cmd),
                    "success": False,
                }
            
            # Success case (even with non-zero exit if we have output)
            if stdout_bytes > 0:
                logger.info(
                    "httpx scan %s successful: found %d bytes of output",
                    scan_job_id, stdout_bytes
                )
            else:
                logger.info("httpx scan %s completed: no output (target may be unreachable or no URLs found)", scan_job_id)
            
            return {
                "tool_name": "httpx",
                "output": result.stdout,
                "exit_code": exit_code,  # Return actual exit code even if we treat as success
                "command": " ".join(cmd),
                "success": True,  # Explicitly mark as successful
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out after 10 minutes",
                "command": " ".join(cmd),
                "success": False,
                "timed_out": True,
            }
        except Exception as e:
            logger.error(f"httpx execution error: {e}", exc_info=True)
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": f"httpx execution failed: {str(e)}",
                "command": " ".join(cmd),
                "success": False,
            }
    
    # TODO: Vulnerability classes covered by ffuf:
    # - Content Discovery (finds hidden files, directories, endpoints)
    # - Information Disclosure (via discovered paths like .git, .env, backup files)
    # Note: ffuf is a content discovery tool, findings may reveal attack surface for other vulnerability classes
    async def _run_ffuf(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run ffuf content discovery scanner
        
        Optional kwargs:
            wordlist: wordlist filename from tool config (e.g., "ffuf-pro.txt", "ffuf-advanced.txt")
                     If provided, will use wordlists/{wordlist} instead of default
            timeout_seconds: timeout in seconds (default: 900 for 15 minutes)
        """
        # Check if ffuf is installed
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        logger.info(f"Checking ffuf availability for scan {scan_job_id}")
        
        # Try common locations for ffuf (in order of preference)
        ffuf_binary = None
        possible_paths = [
            os.path.expanduser("~/go/bin/ffuf"),  # Go bin directory (most common)
            os.path.expanduser("~/.local/thandev-tools/bin/ffuf"),  # Local tools directory
            "/usr/local/bin/ffuf",
            "ffuf",  # In PATH
        ]
        
        for binary_path in possible_paths:
            try:
                expanded_path = os.path.expanduser(binary_path) if binary_path.startswith("~") else binary_path
                if os.path.isabs(expanded_path) or expanded_path.startswith("/"):
                    if os.path.exists(expanded_path) and os.access(expanded_path, os.X_OK):
                        ffuf_binary = expanded_path
                        logger.info(f"Found ffuf binary at: {ffuf_binary}")
                        break
                else:
                    # Check if command exists in PATH
                    check_result = await asyncio.to_thread(subprocess.run,
                        ["which", binary_path],
                        capture_output=True,
                        timeout=2,
                        text=True
                    )
                    if check_result.returncode == 0:
                        ffuf_binary = check_result.stdout.strip()
                        logger.info(f"Found ffuf binary at: {ffuf_binary}")
                        break
            except Exception:
                continue
        
        if not ffuf_binary:
            error_msg = "ffuf binary not found. Please install ffuf: go install -v github.com/ffuf/ffuf/v2@latest (ensure ~/go/bin is in PATH)"
            logger.error(f"ffuf binary not found for scan {scan_job_id}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "ffuf -V",
                "timed_out": False,
            }
        
        # Verify ffuf works
        try:
            check_result = await asyncio.to_thread(subprocess.run,
                [ffuf_binary, "-V"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if check_result.returncode != 0:
                error_msg = f"ffuf command failed with exit code {check_result.returncode}: {check_result.stderr}"
                logger.error(f"ffuf binary check failed for scan {scan_job_id}: {error_msg}")
                raise FileNotFoundError("ffuf command failed")
            logger.info(f"ffuf binary verified for scan {scan_job_id}: {check_result.stdout.strip()}")
        except FileNotFoundError:
            error_msg = "ffuf binary not found in PATH. Please install ffuf: go install -v github.com/ffuf/ffuf/v2@latest"
            logger.error(f"ffuf binary not found for scan {scan_job_id}. Check PATH or install ffuf.")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "ffuf -V",
                "timed_out": False,
            }
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            error_msg = f"ffuf binary check failed: {str(e)}"
            logger.error(f"ffuf binary check error for scan {scan_job_id}: {error_msg}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "ffuf -V",
                "timed_out": False,
            }
        
        # ffuf command flags:
        # -u: target URL with FUZZ placeholder
        # -w: wordlist file path
        # -mc: match status codes (200, 204, 301, 302, 307, 401, 403)
        # -json: output JSON format
        # 
        # Wordlist path configuration:
        # - Can be specified via tool config (kwargs["wordlist"]) or env var
        # - Default: repo_root/wordlists/ffuf-small.txt
        # - Priority: tool config > env var > default
        wordlist_filename = kwargs.get("wordlist", None)
        if wordlist_filename:
            # Use wordlist from tool config (e.g., "ffuf-pro.txt" -> wordlists/ffuf-pro.txt)
            wordlist_path = os.path.join(os.getenv("WORDLISTS_DIR", "/opt/thandev/wordlists"), wordlist_filename)
            logger.info(f"Using wordlist from tool config: {wordlist_filename}")
        else:
            # Fall back to env var or default
            wordlist_path = os.getenv(
                "THANDEV_FFUF_WORDLIST",
                os.path.join(os.getenv("WORDLISTS_DIR", "/opt/thandev/wordlists"), "ffuf-small.txt"),
            )
        
        # Verify wordlist exists before running ffuf
        if not os.path.exists(wordlist_path):
            error_msg = f"Wordlist not found: {wordlist_path}. Please ensure the wordlist exists or set THANDEV_FFUF_WORDLIST environment variable."
            logger.error(f"ffuf wordlist not found for scan {scan_job_id}: {wordlist_path}")
            logger.error(f"  Expected location: {wordlist_path}")
            logger.error(f"  BASE_DIR: {BASE_DIR}")
            logger.error(f"  Wordlist filename from config: {wordlist_filename}")
            logger.error(f"  THANDEV_FFUF_WORDLIST env var: {os.getenv('THANDEV_FFUF_WORDLIST', 'not set')}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": f"ffuf -u {target_url}/FUZZ -w <wordlist>",
                "timed_out": False,
            }
        
        logger.info(f"ffuf wordlist verified for scan {scan_job_id}: {wordlist_path} ({os.path.getsize(wordlist_path)} bytes)")
        
        # PR-4C: Baseline detection to filter out 404/wildcard responses
        baseline = None
        try:
            import random
            import string
            import requests
            
            # Generate random baseline path
            random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            baseline_path = f"/THANDEV-BASELINE-{random_suffix}"
            baseline_url = f"{target_url.rstrip('/')}{baseline_path}"
            
            logger.info(f"Performing baseline request for ffuf: {baseline_url}")
            
            # Make baseline request
            baseline_resp = requests.get(
                baseline_url,
                timeout=10,
                allow_redirects=True,
                headers={"User-Agent": "Thandev-Baseline/1.0"},
            )
            
            # Calculate baseline signature
            response_text = baseline_resp.text
            baseline = {
                "status_code": baseline_resp.status_code,
                "content_length": len(baseline_resp.content),
                "word_count": len(response_text.split()),
                "line_count": len(response_text.splitlines()),
                "content_hash": hash(response_text[:1000]),  # Hash first 1000 chars
            }
            
            logger.info(
                f"Baseline signature for {target_url}: status={baseline['status_code']}, "
                f"size={baseline['content_length']}, words={baseline['word_count']}, "
                f"lines={baseline['line_count']}"
            )
        except Exception as e:
            logger.warning(f"Failed to establish baseline for ffuf: {e}. Will filter by status code only.")
            baseline = None
        
        # Get timeout from config (default: 5 minutes)
        default_timeout = 300  # 5 minutes
        timeout = kwargs.get("timeout_seconds", default_timeout)
        
        # PR-4C: Add filters to exclude baseline and 404
        cmd = [
            ffuf_binary,  # Use the found binary path
            "-u", f"{target_url}/FUZZ",
            "-w", wordlist_path,
            "-mc", "200,204,301,302,307,401,403",  # Only allow relevant status codes
            "-json",
        ]
        
        # Add size filter if baseline available
        if baseline:
            # Exclude responses matching baseline size (with small tolerance)
            baseline_size = baseline["content_length"]
            if baseline_size > 0:
                # Exclude responses within 5% of baseline size
                tolerance = max(10, int(baseline_size * 0.05))
                min_size = baseline_size - tolerance
                max_size = baseline_size + tolerance
                cmd.extend(["-fs", f"{min_size}-{max_size}"])  # Filter by size
                logger.info(f"Added size filter to exclude baseline: {min_size}-{max_size} bytes")
        
        logger.info("ffuf command for scan %s: %s (timeout: %d seconds, wordlist: %s)", 
                   scan_job_id, " ".join(cmd), timeout, wordlist_path)
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            exit_code = result.returncode
            stdout_bytes = len(result.stdout.encode("utf-8")) if result.stdout else 0
            stderr_bytes = len(result.stderr.encode("utf-8")) if result.stderr else 0
            
            logger.info(
                "ffuf completed for scan %s: exit_code=%s, stdout_bytes=%d, stderr_bytes=%d",
                scan_job_id, exit_code, stdout_bytes, stderr_bytes
            )
            
            # ffuf may exit with non-zero even when it finds paths
            # Consider it successful if we have output
            is_error = False
            error_msg = None
            
            if exit_code != 0:
                if stdout_bytes > 0:
                    # We have output, so the scan found some paths
                    logger.info(
                        "ffuf scan %s completed with exit_code=%s but produced %d bytes of output (treating as success)",
                        scan_job_id, exit_code, stdout_bytes
                    )
                elif result.stderr:
                    stderr_lower = result.stderr.lower()
                    if any(keyword in stderr_lower for keyword in ["error", "failed", "fatal", "cannot", "not found"]):
                        is_error = True
                        error_msg = f"ffuf exited with code {exit_code}: {result.stderr[:200]}"
                        logger.warning("ffuf scan %s failed: %s", scan_job_id, error_msg)
                    else:
                        logger.info(
                            "ffuf scan %s completed with exit_code=%s (no paths found, treating as success)",
                            scan_job_id, exit_code
                        )
                else:
                    logger.info(
                        "ffuf scan %s completed with exit_code=%s and no output (no paths found, treating as success)",
                        scan_job_id, exit_code
                    )
            
            if is_error:
                return {
                    "tool_name": "ffuf",
                    "output": result.stdout,  # Still return any partial output
                    "exit_code": exit_code,
                    "error": error_msg,
                    "command": " ".join(cmd),
                    "timed_out": False,
                }
            
            # Success case
            if stdout_bytes > 0:
                logger.info(
                    "ffuf scan %s successful: found %d bytes of output (paths discovered)",
                    scan_job_id, stdout_bytes
                )
            else:
                logger.info("ffuf scan %s completed: no paths discovered (exit_code=%s, stderr_bytes=%d)", 
                           scan_job_id, exit_code, stderr_bytes)
            
            return {
                "tool_name": "ffuf",
                "output": result.stdout,
                "exit_code": exit_code,
                "command": " ".join(cmd),
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            logger.warning("ffuf scan %s timed out after %d seconds (%d minutes). Results may be partial.", 
                          scan_job_id, timeout, timeout // 60)
            logger.warning("  Command: %s", " ".join(cmd))
            logger.warning("  Wordlist: %s", wordlist_path)
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": None,  # None indicates timeout (not a normal exit code)
                "error": f"Tool execution timed out after {timeout} seconds ({timeout // 60} minutes)",
                "command": " ".join(cmd),
                "timed_out": True,
            }
        except Exception as e:
            logger.error(f"ffuf execution error for scan {scan_job_id}: {e}", exc_info=True)
            logger.error(f"  Command: {' '.join(cmd)}")
            logger.error(f"  Wordlist: {wordlist_path}")
            logger.error(f"  Target URL: {target_url}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": f"ffuf execution failed: {str(e)}",
                "command": " ".join(cmd),
                "timed_out": False,
            }
    

    async def _run_sslscan(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """Run SSL/TLS scanner"""
        from urllib.parse import urlparse
        
        parsed = urlparse(target_url)
        hostname = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        
        if not hostname:
            raise ValueError(f"Invalid URL: {target_url}")
        
        target = f"{hostname}:{port}"
        
        # Note: sslscan doesn't support --json flag, it outputs text with ANSI colors
        cmd = ["sslscan", target]
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            
            return {
                "tool_name": "sslscan",
                "output": result.stdout,
                "exit_code": result.returncode,
                "command": " ".join(cmd),
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "sslscan",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out",
            }
        except FileNotFoundError:
            # Fallback to openssl if sslscan not available
            logger.warning("sslscan not found, using openssl fallback")
            return await self._run_openssl_fallback(hostname, port)
    
    async def _run_openssl_fallback(self, hostname: str, port: int) -> Dict:
        """Fallback SSL check using openssl"""
        cmd = [
            "openssl", "s_client",
            "-connect", f"{hostname}:{port}",
            "-showcerts",
        ]
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                input="",  # Close connection immediately
            )
            
            return {
                "tool_name": "openssl",
                "output": result.stdout,
                "exit_code": result.returncode,
                "command": " ".join(cmd),
            }
        except Exception as e:
            return {
                "tool_name": "openssl",
                "output": "",
                "exit_code": -1,
                "error": str(e),
            }
    
    # TODO: Vulnerability classes covered by httpx:
    # - HTTP Surface Discovery (identifies endpoints, status codes, technologies)
    # - Content Discovery (via response analysis)
    # Note: httpx is primarily a reconnaissance tool, not a vulnerability scanner
    async def _run_httpx(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run httpx HTTP surface scanner (ProjectDiscovery httpx)
        
        Optional kwargs:
            intensity: "low", "medium", "high" (from tool config, currently not used but available)
        """
        # Check if ProjectDiscovery httpx is installed
        # Note: Python httpx library also has a CLI, so we need to verify it's the right one
        # Python httpx errors on -u flag, ProjectDiscovery httpx supports it
        httpx_binary = None
        
        # Try common locations for ProjectDiscovery httpx
        # Check ~/go/bin first (most common location) before PATH to avoid Python httpx
        # Also check ~/.local/bin which is common in user installations
        possible_paths = [
            os.path.expanduser("~/go/bin/httpx"),  # Go bin directory (check first!)
            os.path.expanduser("~/.local/bin/httpx"),  # User local bin (common location)
            "/usr/local/bin/httpx",
            "/usr/local/bin/httpx-projectdiscovery",
            "/usr/bin/httpx",  # System bin
            "httpx",  # In PATH (check last to avoid Python httpx)
        ]
        
        for binary_path in possible_paths:
            try:
                test_cmd = [binary_path, "-u", "https://example.com", "-silent", "-json"]
                test_result = await asyncio.to_thread(subprocess.run,
                    test_cmd,
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                # Python httpx will error with "No such option: -u" or "required dependencies"
                # ProjectDiscovery httpx will either succeed or fail with different error
                stderr_lower = test_result.stderr.lower()
                if ("no such option" not in stderr_lower and 
                    "error: no such option" not in stderr_lower and
                    "required dependencies" not in stderr_lower and
                    "could not run" not in stderr_lower):
                    httpx_binary = binary_path
                    logger.info(f"Detected ProjectDiscovery httpx binary at: {binary_path}")
                    break
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.debug(f"httpx detection test failed for {binary_path}: {e}")
                continue
        
        if not httpx_binary:
            error_msg = "ProjectDiscovery httpx binary not found. The system has Python httpx (HTTP client) installed, but we need ProjectDiscovery httpx (security scanner). Install with: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest (or download from https://github.com/projectdiscovery/httpx/releases). After installation, ensure ~/go/bin is in your PATH."
            logger.error(f"httpx binary not found: {error_msg}")
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "httpx -u <url> -json",
                "success": False,
            }
        
        # httpx (ProjectDiscovery) command flags:
        # -u: target URL (required)
        # -json: output JSON format (one JSON object per line)
        # -follow-redirects: follow HTTP redirects
        # -status-code: include HTTP status code in output
        # -title: extract page title
        # -tech-detect: detect web technologies
        # -tls-probe: probe TLS/SSL information
        # -silent: suppress non-JSON output
        cmd = [
            httpx_binary,
            "-u", target_url,
            "-json",
            "-follow-redirects",
            "-status-code",
            "-title",
            "-tech-detect",
            "-tls-probe",
            "-silent",
        ]
        
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        logger.info("httpx command for scan %s: %s", scan_job_id, " ".join(cmd))
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            
            exit_code = result.returncode
            stdout_bytes = len(result.stdout.encode("utf-8")) if result.stdout else 0
            stderr_bytes = len(result.stderr.encode("utf-8")) if result.stderr else 0
            
            logger.info(
                "httpx completed for scan %s: exit_code=%s, stdout_bytes=%d, stderr_bytes=%d",
                scan_job_id, exit_code, stdout_bytes, stderr_bytes
            )
            
            # httpx may exit with non-zero even when it successfully probes URLs
            # Consider it successful if we have output OR if exit code is just a warning
            # Only treat as error if exit_code is non-zero AND we have no output AND stderr indicates failure
            is_error = False
            error_msg = None
            
            if exit_code != 0:
                # Check if we have useful output despite non-zero exit
                if stdout_bytes > 0:
                    # We have output, so the scan was partially successful
                    logger.info(
                        "httpx scan %s completed with exit_code=%s but produced %d bytes of output (treating as success)",
                        scan_job_id, exit_code, stdout_bytes
                    )
                elif result.stderr:
                    # Check stderr for actual errors vs warnings
                    stderr_lower = result.stderr.lower()
                    if any(keyword in stderr_lower for keyword in ["error", "failed", "fatal", "cannot"]):
                        is_error = True
                        error_msg = f"httpx exited with code {exit_code}: {result.stderr[:200]}"
                        logger.warning("httpx scan %s failed: %s", scan_job_id, error_msg)
                    else:
                        # Likely just a warning, not a fatal error
                        logger.info(
                            "httpx scan %s completed with exit_code=%s (likely no reachable URLs, treating as success)",
                            scan_job_id, exit_code
                        )
                else:
                    # No output and no stderr - might be unreachable target
                    logger.info(
                        "httpx scan %s completed with exit_code=%s and no output (target may be unreachable, treating as success)",
                        scan_job_id, exit_code
                    )
            
            if is_error:
                return {
                    "tool_name": "httpx",
                    "output": result.stdout,  # Still return any partial output
                    "exit_code": exit_code,
                    "error": error_msg,
                    "command": " ".join(cmd),
                    "success": False,
                }
            
            # Success case (even with non-zero exit if we have output)
            if stdout_bytes > 0:
                logger.info(
                    "httpx scan %s successful: found %d bytes of output",
                    scan_job_id, stdout_bytes
                )
            else:
                logger.info("httpx scan %s completed: no output (target may be unreachable or no URLs found)", scan_job_id)
            
            return {
                "tool_name": "httpx",
                "output": result.stdout,
                "exit_code": exit_code,  # Return actual exit code even if we treat as success
                "command": " ".join(cmd),
                "success": True,  # Explicitly mark as successful
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out after 10 minutes",
                "command": " ".join(cmd),
                "success": False,
                "timed_out": True,
            }
        except Exception as e:
            logger.error(f"httpx execution error: {e}", exc_info=True)
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": f"httpx execution failed: {str(e)}",
                "command": " ".join(cmd),
                "success": False,
            }
    
    # TODO: Vulnerability classes covered by ffuf:
    # - Content Discovery (finds hidden files, directories, endpoints)
    # - Information Disclosure (via discovered paths like .git, .env, backup files)
    # Note: ffuf is a content discovery tool, findings may reveal attack surface for other vulnerability classes
    async def _run_ffuf(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run ffuf content discovery scanner
        
        Optional kwargs:
            wordlist: wordlist filename from tool config (e.g., "ffuf-pro.txt", "ffuf-advanced.txt")
                     If provided, will use wordlists/{wordlist} instead of default
            timeout_seconds: timeout in seconds (default: 900 for 15 minutes)
        """
        # Check if ffuf is installed
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        logger.info(f"Checking ffuf availability for scan {scan_job_id}")
        
        # Try common locations for ffuf (in order of preference)
        ffuf_binary = None
        possible_paths = [
            os.path.expanduser("~/go/bin/ffuf"),  # Go bin directory (most common)
            os.path.expanduser("~/.local/thandev-tools/bin/ffuf"),  # Local tools directory
            "/usr/local/bin/ffuf",
            "ffuf",  # In PATH
        ]
        
        for binary_path in possible_paths:
            try:
                expanded_path = os.path.expanduser(binary_path) if binary_path.startswith("~") else binary_path
                if os.path.isabs(expanded_path) or expanded_path.startswith("/"):
                    if os.path.exists(expanded_path) and os.access(expanded_path, os.X_OK):
                        ffuf_binary = expanded_path
                        logger.info(f"Found ffuf binary at: {ffuf_binary}")
                        break
                else:
                    # Check if command exists in PATH
                    check_result = await asyncio.to_thread(subprocess.run,
                        ["which", binary_path],
                        capture_output=True,
                        timeout=2,
                        text=True
                    )
                    if check_result.returncode == 0:
                        ffuf_binary = check_result.stdout.strip()
                        logger.info(f"Found ffuf binary at: {ffuf_binary}")
                        break
            except Exception:
                continue
        
        if not ffuf_binary:
            error_msg = "ffuf binary not found. Please install ffuf: go install -v github.com/ffuf/ffuf/v2@latest (ensure ~/go/bin is in PATH)"
            logger.error(f"ffuf binary not found for scan {scan_job_id}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "ffuf -V",
                "timed_out": False,
            }
        
        # Verify ffuf works
        try:
            check_result = await asyncio.to_thread(subprocess.run,
                [ffuf_binary, "-V"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if check_result.returncode != 0:
                error_msg = f"ffuf command failed with exit code {check_result.returncode}: {check_result.stderr}"
                logger.error(f"ffuf binary check failed for scan {scan_job_id}: {error_msg}")
                raise FileNotFoundError("ffuf command failed")
            logger.info(f"ffuf binary verified for scan {scan_job_id}: {check_result.stdout.strip()}")
        except FileNotFoundError:
            error_msg = "ffuf binary not found in PATH. Please install ffuf: go install -v github.com/ffuf/ffuf/v2@latest"
            logger.error(f"ffuf binary not found for scan {scan_job_id}. Check PATH or install ffuf.")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "ffuf -V",
                "timed_out": False,
            }
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            error_msg = f"ffuf binary check failed: {str(e)}"
            logger.error(f"ffuf binary check error for scan {scan_job_id}: {error_msg}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "ffuf -V",
                "timed_out": False,
            }
        
        # ffuf command flags:
        # -u: target URL with FUZZ placeholder
        # -w: wordlist file path
        # -mc: match status codes (200, 204, 301, 302, 307, 401, 403)
        # -json: output JSON format
        # 
        # Wordlist path configuration:
        # - Can be specified via tool config (kwargs["wordlist"]) or env var
        # - Default: repo_root/wordlists/ffuf-small.txt
        # - Priority: tool config > env var > default
        wordlist_filename = kwargs.get("wordlist", None)
        if wordlist_filename:
            # Use wordlist from tool config (e.g., "ffuf-pro.txt" -> wordlists/ffuf-pro.txt)
            wordlist_path = os.path.join(os.getenv("WORDLISTS_DIR", "/opt/thandev/wordlists"), wordlist_filename)
            logger.info(f"Using wordlist from tool config: {wordlist_filename}")
        else:
            # Fall back to env var or default
            wordlist_path = os.getenv(
                "THANDEV_FFUF_WORDLIST",
                os.path.join(os.getenv("WORDLISTS_DIR", "/opt/thandev/wordlists"), "ffuf-small.txt"),
            )
        
        # Verify wordlist exists before running ffuf
        if not os.path.exists(wordlist_path):
            error_msg = f"Wordlist not found: {wordlist_path}. Please ensure the wordlist exists or set THANDEV_FFUF_WORDLIST environment variable."
            logger.error(f"ffuf wordlist not found for scan {scan_job_id}: {wordlist_path}")
            logger.error(f"  Expected location: {wordlist_path}")
            logger.error(f"  BASE_DIR: {BASE_DIR}")
            logger.error(f"  Wordlist filename from config: {wordlist_filename}")
            logger.error(f"  THANDEV_FFUF_WORDLIST env var: {os.getenv('THANDEV_FFUF_WORDLIST', 'not set')}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": f"ffuf -u {target_url}/FUZZ -w <wordlist>",
                "timed_out": False,
            }
        
        logger.info(f"ffuf wordlist verified for scan {scan_job_id}: {wordlist_path} ({os.path.getsize(wordlist_path)} bytes)")
        
        # PR-4C: Baseline detection to filter out 404/wildcard responses
        baseline = None
        try:
            import random
            import string
            import requests
            
            # Generate random baseline path
            random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            baseline_path = f"/THANDEV-BASELINE-{random_suffix}"
            baseline_url = f"{target_url.rstrip('/')}{baseline_path}"
            
            logger.info(f"Performing baseline request for ffuf: {baseline_url}")
            
            # Make baseline request
            baseline_resp = requests.get(
                baseline_url,
                timeout=10,
                allow_redirects=True,
                headers={"User-Agent": "Thandev-Baseline/1.0"},
            )
            
            # Calculate baseline signature
            response_text = baseline_resp.text
            baseline = {
                "status_code": baseline_resp.status_code,
                "content_length": len(baseline_resp.content),
                "word_count": len(response_text.split()),
                "line_count": len(response_text.splitlines()),
                "content_hash": hash(response_text[:1000]),  # Hash first 1000 chars
            }
            
            logger.info(
                f"Baseline signature for {target_url}: status={baseline['status_code']}, "
                f"size={baseline['content_length']}, words={baseline['word_count']}, "
                f"lines={baseline['line_count']}"
            )
        except Exception as e:
            logger.warning(f"Failed to establish baseline for ffuf: {e}. Will filter by status code only.")
            baseline = None
        
        # Get timeout from config (default: 5 minutes)
        default_timeout = 300  # 5 minutes
        timeout = kwargs.get("timeout_seconds", default_timeout)
        
        # PR-4C: Add filters to exclude baseline and 404
        cmd = [
            ffuf_binary,  # Use the found binary path
            "-u", f"{target_url}/FUZZ",
            "-w", wordlist_path,
            "-mc", "200,204,301,302,307,401,403",  # Only allow relevant status codes
            "-json",
        ]
        
        # Add size filter if baseline available
        if baseline:
            # Exclude responses matching baseline size (with small tolerance)
            baseline_size = baseline["content_length"]
            if baseline_size > 0:
                # Exclude responses within 5% of baseline size
                tolerance = max(10, int(baseline_size * 0.05))
                min_size = baseline_size - tolerance
                max_size = baseline_size + tolerance
                cmd.extend(["-fs", f"{min_size}-{max_size}"])  # Filter by size
                logger.info(f"Added size filter to exclude baseline: {min_size}-{max_size} bytes")
        
        logger.info("ffuf command for scan %s: %s (timeout: %d seconds, wordlist: %s)", 
                   scan_job_id, " ".join(cmd), timeout, wordlist_path)
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            exit_code = result.returncode
            stdout_bytes = len(result.stdout.encode("utf-8")) if result.stdout else 0
            stderr_bytes = len(result.stderr.encode("utf-8")) if result.stderr else 0
            
            logger.info(
                "ffuf completed for scan %s: exit_code=%s, stdout_bytes=%d, stderr_bytes=%d",
                scan_job_id, exit_code, stdout_bytes, stderr_bytes
            )
            
            # ffuf may exit with non-zero even when it finds paths
            # Consider it successful if we have output
            is_error = False
            error_msg = None
            
            if exit_code != 0:
                if stdout_bytes > 0:
                    # We have output, so the scan found some paths
                    logger.info(
                        "ffuf scan %s completed with exit_code=%s but produced %d bytes of output (treating as success)",
                        scan_job_id, exit_code, stdout_bytes
                    )
                elif result.stderr:
                    stderr_lower = result.stderr.lower()
                    if any(keyword in stderr_lower for keyword in ["error", "failed", "fatal", "cannot", "not found"]):
                        is_error = True
                        error_msg = f"ffuf exited with code {exit_code}: {result.stderr[:200]}"
                        logger.warning("ffuf scan %s failed: %s", scan_job_id, error_msg)
                    else:
                        logger.info(
                            "ffuf scan %s completed with exit_code=%s (no paths found, treating as success)",
                            scan_job_id, exit_code
                        )
                else:
                    logger.info(
                        "ffuf scan %s completed with exit_code=%s and no output (no paths found, treating as success)",
                        scan_job_id, exit_code
                    )
            
            if is_error:
                return {
                    "tool_name": "ffuf",
                    "output": result.stdout,  # Still return any partial output
                    "exit_code": exit_code,
                    "error": error_msg,
                    "command": " ".join(cmd),
                    "timed_out": False,
                }
            
            # Success case
            if stdout_bytes > 0:
                logger.info(
                    "ffuf scan %s successful: found %d bytes of output (paths discovered)",
                    scan_job_id, stdout_bytes
                )
            else:
                logger.info("ffuf scan %s completed: no paths discovered (exit_code=%s, stderr_bytes=%d)", 
                           scan_job_id, exit_code, stderr_bytes)
            
            return {
                "tool_name": "ffuf",
                "output": result.stdout,
                "exit_code": exit_code,
                "command": " ".join(cmd),
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            logger.warning("ffuf scan %s timed out after %d seconds (%d minutes). Results may be partial.", 
                          scan_job_id, timeout, timeout // 60)
            logger.warning("  Command: %s", " ".join(cmd))
            logger.warning("  Wordlist: %s", wordlist_path)
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": None,  # None indicates timeout (not a normal exit code)
                "error": f"Tool execution timed out after {timeout} seconds ({timeout // 60} minutes)",
                "command": " ".join(cmd),
                "timed_out": True,
            }
        except Exception as e:
            logger.error(f"ffuf execution error for scan {scan_job_id}: {e}", exc_info=True)
            logger.error(f"  Command: {' '.join(cmd)}")
            logger.error(f"  Wordlist: {wordlist_path}")
            logger.error(f"  Target URL: {target_url}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": f"ffuf execution failed: {str(e)}",
                "command": " ".join(cmd),
                "timed_out": False,
            }
    

    async def _run_sslscan(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """Run SSL/TLS scanner"""
        from urllib.parse import urlparse
        
        parsed = urlparse(target_url)
        hostname = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        
        if not hostname:
            raise ValueError(f"Invalid URL: {target_url}")
        
        target = f"{hostname}:{port}"
        
        # Note: sslscan doesn't support --json flag, it outputs text with ANSI colors
        cmd = ["sslscan", target]
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            
            return {
                "tool_name": "sslscan",
                "output": result.stdout,
                "exit_code": result.returncode,
                "command": " ".join(cmd),
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "sslscan",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out",
            }
        except FileNotFoundError:
            # Fallback to openssl if sslscan not available
            logger.warning("sslscan not found, using openssl fallback")
            return await self._run_openssl_fallback(hostname, port)
    
    async def _run_openssl_fallback(self, hostname: str, port: int) -> Dict:
        """Fallback SSL check using openssl"""
        cmd = [
            "openssl", "s_client",
            "-connect", f"{hostname}:{port}",
            "-showcerts",
        ]
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                input="",  # Close connection immediately
            )
            
            return {
                "tool_name": "openssl",
                "output": result.stdout,
                "exit_code": result.returncode,
                "command": " ".join(cmd),
            }
        except Exception as e:
            return {
                "tool_name": "openssl",
                "output": "",
                "exit_code": -1,
                "error": str(e),
            }
    
    # TODO: Vulnerability classes covered by httpx:
    # - HTTP Surface Discovery (identifies endpoints, status codes, technologies)
    # - Content Discovery (via response analysis)
    # Note: httpx is primarily a reconnaissance tool, not a vulnerability scanner
    async def _run_httpx(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run httpx HTTP surface scanner (ProjectDiscovery httpx)
        
        Optional kwargs:
            intensity: "low", "medium", "high" (from tool config, currently not used but available)
        """
        # Check if ProjectDiscovery httpx is installed
        # Note: Python httpx library also has a CLI, so we need to verify it's the right one
        # Python httpx errors on -u flag, ProjectDiscovery httpx supports it
        httpx_binary = None
        
        # Try common locations for ProjectDiscovery httpx
        # Check ~/go/bin first (most common location) before PATH to avoid Python httpx
        # Also check ~/.local/bin which is common in user installations
        possible_paths = [
            os.path.expanduser("~/go/bin/httpx"),  # Go bin directory (check first!)
            os.path.expanduser("~/.local/bin/httpx"),  # User local bin (common location)
            "/usr/local/bin/httpx",
            "/usr/local/bin/httpx-projectdiscovery",
            "/usr/bin/httpx",  # System bin
            "httpx",  # In PATH (check last to avoid Python httpx)
        ]
        
        for binary_path in possible_paths:
            try:
                test_cmd = [binary_path, "-u", "https://example.com", "-silent", "-json"]
                test_result = await asyncio.to_thread(subprocess.run,
                    test_cmd,
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                # Python httpx will error with "No such option: -u" or "required dependencies"
                # ProjectDiscovery httpx will either succeed or fail with different error
                stderr_lower = test_result.stderr.lower()
                if ("no such option" not in stderr_lower and 
                    "error: no such option" not in stderr_lower and
                    "required dependencies" not in stderr_lower and
                    "could not run" not in stderr_lower):
                    httpx_binary = binary_path
                    logger.info(f"Detected ProjectDiscovery httpx binary at: {binary_path}")
                    break
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.debug(f"httpx detection test failed for {binary_path}: {e}")
                continue
        
        if not httpx_binary:
            error_msg = "ProjectDiscovery httpx binary not found. The system has Python httpx (HTTP client) installed, but we need ProjectDiscovery httpx (security scanner). Install with: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest (or download from https://github.com/projectdiscovery/httpx/releases). After installation, ensure ~/go/bin is in your PATH."
            logger.error(f"httpx binary not found: {error_msg}")
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "httpx -u <url> -json",
                "success": False,
            }
        
        # httpx (ProjectDiscovery) command flags:
        # -u: target URL (required)
        # -json: output JSON format (one JSON object per line)
        # -follow-redirects: follow HTTP redirects
        # -status-code: include HTTP status code in output
        # -title: extract page title
        # -tech-detect: detect web technologies
        # -tls-probe: probe TLS/SSL information
        # -silent: suppress non-JSON output
        cmd = [
            httpx_binary,
            "-u", target_url,
            "-json",
            "-follow-redirects",
            "-status-code",
            "-title",
            "-tech-detect",
            "-tls-probe",
            "-silent",
        ]
        
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        logger.info("httpx command for scan %s: %s", scan_job_id, " ".join(cmd))
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            
            exit_code = result.returncode
            stdout_bytes = len(result.stdout.encode("utf-8")) if result.stdout else 0
            stderr_bytes = len(result.stderr.encode("utf-8")) if result.stderr else 0
            
            logger.info(
                "httpx completed for scan %s: exit_code=%s, stdout_bytes=%d, stderr_bytes=%d",
                scan_job_id, exit_code, stdout_bytes, stderr_bytes
            )
            
            # httpx may exit with non-zero even when it successfully probes URLs
            # Consider it successful if we have output OR if exit code is just a warning
            # Only treat as error if exit_code is non-zero AND we have no output AND stderr indicates failure
            is_error = False
            error_msg = None
            
            if exit_code != 0:
                # Check if we have useful output despite non-zero exit
                if stdout_bytes > 0:
                    # We have output, so the scan was partially successful
                    logger.info(
                        "httpx scan %s completed with exit_code=%s but produced %d bytes of output (treating as success)",
                        scan_job_id, exit_code, stdout_bytes
                    )
                elif result.stderr:
                    # Check stderr for actual errors vs warnings
                    stderr_lower = result.stderr.lower()
                    if any(keyword in stderr_lower for keyword in ["error", "failed", "fatal", "cannot"]):
                        is_error = True
                        error_msg = f"httpx exited with code {exit_code}: {result.stderr[:200]}"
                        logger.warning("httpx scan %s failed: %s", scan_job_id, error_msg)
                    else:
                        # Likely just a warning, not a fatal error
                        logger.info(
                            "httpx scan %s completed with exit_code=%s (likely no reachable URLs, treating as success)",
                            scan_job_id, exit_code
                        )
                else:
                    # No output and no stderr - might be unreachable target
                    logger.info(
                        "httpx scan %s completed with exit_code=%s and no output (target may be unreachable, treating as success)",
                        scan_job_id, exit_code
                    )
            
            if is_error:
                return {
                    "tool_name": "httpx",
                    "output": result.stdout,  # Still return any partial output
                    "exit_code": exit_code,
                    "error": error_msg,
                    "command": " ".join(cmd),
                    "success": False,
                }
            
            # Success case (even with non-zero exit if we have output)
            if stdout_bytes > 0:
                logger.info(
                    "httpx scan %s successful: found %d bytes of output",
                    scan_job_id, stdout_bytes
                )
            else:
                logger.info("httpx scan %s completed: no output (target may be unreachable or no URLs found)", scan_job_id)
            
            return {
                "tool_name": "httpx",
                "output": result.stdout,
                "exit_code": exit_code,  # Return actual exit code even if we treat as success
                "command": " ".join(cmd),
                "success": True,  # Explicitly mark as successful
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out after 10 minutes",
                "command": " ".join(cmd),
                "success": False,
                "timed_out": True,
            }
        except Exception as e:
            logger.error(f"httpx execution error: {e}", exc_info=True)
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": f"httpx execution failed: {str(e)}",
                "command": " ".join(cmd),
                "success": False,
            }
    
    # TODO: Vulnerability classes covered by ffuf:
    # - Content Discovery (finds hidden files, directories, endpoints)
    # - Information Disclosure (via discovered paths like .git, .env, backup files)
    # Note: ffuf is a content discovery tool, findings may reveal attack surface for other vulnerability classes
    async def _run_ffuf(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run ffuf content discovery scanner
        
        Optional kwargs:
            wordlist: wordlist filename from tool config (e.g., "ffuf-pro.txt", "ffuf-advanced.txt")
                     If provided, will use wordlists/{wordlist} instead of default
            timeout_seconds: timeout in seconds (default: 900 for 15 minutes)
        """
        # Check if ffuf is installed
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        logger.info(f"Checking ffuf availability for scan {scan_job_id}")
        
        # Try common locations for ffuf (in order of preference)
        ffuf_binary = None
        possible_paths = [
            os.path.expanduser("~/go/bin/ffuf"),  # Go bin directory (most common)
            os.path.expanduser("~/.local/thandev-tools/bin/ffuf"),  # Local tools directory
            "/usr/local/bin/ffuf",
            "ffuf",  # In PATH
        ]
        
        for binary_path in possible_paths:
            try:
                expanded_path = os.path.expanduser(binary_path) if binary_path.startswith("~") else binary_path
                if os.path.isabs(expanded_path) or expanded_path.startswith("/"):
                    if os.path.exists(expanded_path) and os.access(expanded_path, os.X_OK):
                        ffuf_binary = expanded_path
                        logger.info(f"Found ffuf binary at: {ffuf_binary}")
                        break
                else:
                    # Check if command exists in PATH
                    check_result = await asyncio.to_thread(subprocess.run,
                        ["which", binary_path],
                        capture_output=True,
                        timeout=2,
                        text=True
                    )
                    if check_result.returncode == 0:
                        ffuf_binary = check_result.stdout.strip()
                        logger.info(f"Found ffuf binary at: {ffuf_binary}")
                        break
            except Exception:
                continue
        
        if not ffuf_binary:
            error_msg = "ffuf binary not found. Please install ffuf: go install -v github.com/ffuf/ffuf/v2@latest (ensure ~/go/bin is in PATH)"
            logger.error(f"ffuf binary not found for scan {scan_job_id}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "ffuf -V",
                "timed_out": False,
            }
        
        # Verify ffuf works
        try:
            check_result = await asyncio.to_thread(subprocess.run,
                [ffuf_binary, "-V"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if check_result.returncode != 0:
                error_msg = f"ffuf command failed with exit code {check_result.returncode}: {check_result.stderr}"
                logger.error(f"ffuf binary check failed for scan {scan_job_id}: {error_msg}")
                raise FileNotFoundError("ffuf command failed")
            logger.info(f"ffuf binary verified for scan {scan_job_id}: {check_result.stdout.strip()}")
        except FileNotFoundError:
            error_msg = "ffuf binary not found in PATH. Please install ffuf: go install -v github.com/ffuf/ffuf/v2@latest"
            logger.error(f"ffuf binary not found for scan {scan_job_id}. Check PATH or install ffuf.")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "ffuf -V",
                "timed_out": False,
            }
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            error_msg = f"ffuf binary check failed: {str(e)}"
            logger.error(f"ffuf binary check error for scan {scan_job_id}: {error_msg}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": "ffuf -V",
                "timed_out": False,
            }
        
        # ffuf command flags:
        # -u: target URL with FUZZ placeholder
        # -w: wordlist file path
        # -mc: match status codes (200, 204, 301, 302, 307, 401, 403)
        # -json: output JSON format
        # 
        # Wordlist path configuration:
        # - Can be specified via tool config (kwargs["wordlist"]) or env var
        # - Default: repo_root/wordlists/ffuf-small.txt
        # - Priority: tool config > env var > default
        wordlist_filename = kwargs.get("wordlist", None)
        if wordlist_filename:
            # Use wordlist from tool config (e.g., "ffuf-pro.txt" -> wordlists/ffuf-pro.txt)
            wordlist_path = os.path.join(os.getenv("WORDLISTS_DIR", "/opt/thandev/wordlists"), wordlist_filename)
            logger.info(f"Using wordlist from tool config: {wordlist_filename}")
        else:
            # Fall back to env var or default
            wordlist_path = os.getenv(
                "THANDEV_FFUF_WORDLIST",
                os.path.join(os.getenv("WORDLISTS_DIR", "/opt/thandev/wordlists"), "ffuf-small.txt"),
            )
        
        # Verify wordlist exists before running ffuf
        if not os.path.exists(wordlist_path):
            error_msg = f"Wordlist not found: {wordlist_path}. Please ensure the wordlist exists or set THANDEV_FFUF_WORDLIST environment variable."
            logger.error(f"ffuf wordlist not found for scan {scan_job_id}: {wordlist_path}")
            logger.error(f"  Expected location: {wordlist_path}")
            logger.error(f"  BASE_DIR: {BASE_DIR}")
            logger.error(f"  Wordlist filename from config: {wordlist_filename}")
            logger.error(f"  THANDEV_FFUF_WORDLIST env var: {os.getenv('THANDEV_FFUF_WORDLIST', 'not set')}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": error_msg,
                "command": f"ffuf -u {target_url}/FUZZ -w <wordlist>",
                "timed_out": False,
            }
        
        logger.info(f"ffuf wordlist verified for scan {scan_job_id}: {wordlist_path} ({os.path.getsize(wordlist_path)} bytes)")
        
        # PR-4C: Baseline detection to filter out 404/wildcard responses
        baseline = None
        try:
            import random
            import string
            import requests
            
            # Generate random baseline path
            random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            baseline_path = f"/THANDEV-BASELINE-{random_suffix}"
            baseline_url = f"{target_url.rstrip('/')}{baseline_path}"
            
            logger.info(f"Performing baseline request for ffuf: {baseline_url}")
            
            # Make baseline request
            baseline_resp = requests.get(
                baseline_url,
                timeout=10,
                allow_redirects=True,
                headers={"User-Agent": "Thandev-Baseline/1.0"},
            )
            
            # Calculate baseline signature
            response_text = baseline_resp.text
            baseline = {
                "status_code": baseline_resp.status_code,
                "content_length": len(baseline_resp.content),
                "word_count": len(response_text.split()),
                "line_count": len(response_text.splitlines()),
                "content_hash": hash(response_text[:1000]),  # Hash first 1000 chars
            }
            
            logger.info(
                f"Baseline signature for {target_url}: status={baseline['status_code']}, "
                f"size={baseline['content_length']}, words={baseline['word_count']}, "
                f"lines={baseline['line_count']}"
            )
        except Exception as e:
            logger.warning(f"Failed to establish baseline for ffuf: {e}. Will filter by status code only.")
            baseline = None
        
        # Get timeout from config (default: 5 minutes)
        default_timeout = 300  # 5 minutes
        timeout = kwargs.get("timeout_seconds", default_timeout)
        
        # PR-4C: Add filters to exclude baseline and 404
        cmd = [
            ffuf_binary,  # Use the found binary path
            "-u", f"{target_url}/FUZZ",
            "-w", wordlist_path,
            "-mc", "200,204,301,302,307,401,403",  # Only allow relevant status codes
            "-json",
        ]
        
        # Add size filter if baseline available
        if baseline:
            # Exclude responses matching baseline size (with small tolerance)
            baseline_size = baseline["content_length"]
            if baseline_size > 0:
                # Exclude responses within 5% of baseline size
                tolerance = max(10, int(baseline_size * 0.05))
                min_size = baseline_size - tolerance
                max_size = baseline_size + tolerance
                cmd.extend(["-fs", f"{min_size}-{max_size}"])  # Filter by size
                logger.info(f"Added size filter to exclude baseline: {min_size}-{max_size} bytes")
        
        logger.info("ffuf command for scan %s: %s (timeout: %d seconds, wordlist: %s)", 
                   scan_job_id, " ".join(cmd), timeout, wordlist_path)
        
        try:
            result = await asyncio.to_thread(subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            exit_code = result.returncode
            stdout_bytes = len(result.stdout.encode("utf-8")) if result.stdout else 0
            stderr_bytes = len(result.stderr.encode("utf-8")) if result.stderr else 0
            
            logger.info(
                "ffuf completed for scan %s: exit_code=%s, stdout_bytes=%d, stderr_bytes=%d",
                scan_job_id, exit_code, stdout_bytes, stderr_bytes
            )
            
            # ffuf may exit with non-zero even when it finds paths
            # Consider it successful if we have output
            is_error = False
            error_msg = None
            
            if exit_code != 0:
                if stdout_bytes > 0:
                    # We have output, so the scan found some paths
                    logger.info(
                        "ffuf scan %s completed with exit_code=%s but produced %d bytes of output (treating as success)",
                        scan_job_id, exit_code, stdout_bytes
                    )
                elif result.stderr:
                    stderr_lower = result.stderr.lower()
                    if any(keyword in stderr_lower for keyword in ["error", "failed", "fatal", "cannot", "not found"]):
                        is_error = True
                        error_msg = f"ffuf exited with code {exit_code}: {result.stderr[:200]}"
                        logger.warning("ffuf scan %s failed: %s", scan_job_id, error_msg)
                    else:
                        logger.info(
                            "ffuf scan %s completed with exit_code=%s (no paths found, treating as success)",
                            scan_job_id, exit_code
                        )
                else:
                    logger.info(
                        "ffuf scan %s completed with exit_code=%s and no output (no paths found, treating as success)",
                        scan_job_id, exit_code
                    )
            
            if is_error:
                return {
                    "tool_name": "ffuf",
                    "output": result.stdout,  # Still return any partial output
                    "exit_code": exit_code,
                    "error": error_msg,
                    "command": " ".join(cmd),
                    "timed_out": False,
                }
            
            # Success case
            if stdout_bytes > 0:
                logger.info(
                    "ffuf scan %s successful: found %d bytes of output (paths discovered)",
                    scan_job_id, stdout_bytes
                )
            else:
                logger.info("ffuf scan %s completed: no paths discovered (exit_code=%s, stderr_bytes=%d)", 
                           scan_job_id, exit_code, stderr_bytes)
            
            return {
                "tool_name": "ffuf",
                "output": result.stdout,
                "exit_code": exit_code,
                "command": " ".join(cmd),
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            logger.warning("ffuf scan %s timed out after %d seconds (%d minutes). Results may be partial.", 
                          scan_job_id, timeout, timeout // 60)
            logger.warning("  Command: %s", " ".join(cmd))
            logger.warning("  Wordlist: %s", wordlist_path)
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": None,  # None indicates timeout (not a normal exit code)
                "error": f"Tool execution timed out after {timeout} seconds ({timeout // 60} minutes)",
                "command": " ".join(cmd),
                "timed_out": True,
            }
        except Exception as e:
            logger.error(f"ffuf execution error for scan {scan_job_id}: {e}", exc_info=True)
            logger.error(f"  Command: {' '.join(cmd)}")
            logger.error(f"  Wordlist: {wordlist_path}")
            logger.error(f"  Target URL: {target_url}")
            return {
                "tool_name": "ffuf",
                "output": "",
                "exit_code": -1,
                "error": f"ffuf execution failed: {str(e)}",
                "command": " ".join(cmd),
                "timed_out": False,
            }
    

