"""
Security scanning tools service
Handles execution of various security scanning tools
"""
import logging
import subprocess
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

# Ensure PATH includes common tool locations when module loads
# This helps subprocess.find_executable() and subprocess.run() find tools
_home_dir = os.path.expanduser("~")
_go_bin = os.path.join(_home_dir, "go", "bin")
_local_tools = os.path.join(_home_dir, ".local", "thandev-tools", "bin")
# Base directory: project root (services/thandev-runner/app/services/tools.py -> project root)
# parents[0] = services/thandev-runner/app/services, parents[1] = services/thandev-runner/app, 
# parents[2] = services/thandev-runner, parents[3] = services, parents[4] = project root
_BASE_DIR = Path(__file__).resolve().parents[4]
_current_path = os.environ.get("PATH", "")
if _go_bin not in _current_path or _local_tools not in _current_path:
    _new_path = f"{_local_tools}:{_go_bin}:{_current_path}"
    os.environ["PATH"] = _new_path
    logger = logging.getLogger(__name__)
    logger.debug(f"Updated PATH to include tool directories: {_go_bin}, {_local_tools}")

# Base directory: project root (services/thandev-runner/app/services/tools.py -> project root)
# parents[0] = services/thandev-runner/app/services, parents[1] = services/thandev-runner/app,
# parents[2] = services/thandev-runner, parents[3] = services, parents[4] = project root
BASE_DIR = Path(__file__).resolve().parents[4]

# Initialize logger after PATH setup
if 'logger' not in locals():
    logger = logging.getLogger(__name__)

# Nuclei profile to tags mapping
# Maps profile names from tool_matrix to Nuclei -tags CLI argument
NUCLEI_PROFILE_TAGS = {
    "basic_web": ["cves", "misconfig", "exposed-panels", "exposures"],
    "pro_web": [
        "cves", "misconfig", "exposed-panels", "exposures",
        "xss", "sqli", "ssrf", "ssti", "xxe", "lfi", "rfi", "path-traversal",
        "cmdi", "idor", "csrf", "cors", "cors-misconfig"
    ],
    "advanced_web": [
        "cves", "misconfig", "exposed-panels", "exposures",
        "xss", "sqli", "ssrf", "ssti", "xxe", "lfi", "rfi", "path-traversal",
        "cmdi", "idor", "csrf", "cors", "cors-misconfig"
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
    if normalized_for_check in ["{}", "[{}]", "[]"] or output_stripped in ["{}", "[{}]", "[]"]:
        return "[]"
    
    # Try parsing as JSON to check for empty objects
    # This handles cases like "[\n{}\n]" where newlines are inside brackets
    try:
        parsed = json.loads(output_stripped)
        
        # If it's a list, filter out empty dicts
        if isinstance(parsed, list):
            # Filter out empty dicts (dicts with no keys or all None/empty values)
            filtered = []
            for item in parsed:
                if isinstance(item, dict):
                    # Check if dict has any non-empty values
                    if item and any(v for v in item.values() if v is not None and str(v).strip()):
                        filtered.append(item)
                    # Empty dict {} is skipped
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
        
        # Valid output, return as-is (re-serialize to ensure clean formatting)
        return json.dumps(parsed) if not isinstance(parsed, str) else output_stripped
        
    except json.JSONDecodeError:
        # Not valid JSON, return as-is (might be error message or other text)
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
            "ffuf": self._run_ffuf,
            "dalfox": self._run_dalfox,
            "sqlmap": self._run_sqlmap,
        }
        
        # Load catalog for tool_id/mode_id mapping
        if catalog_path is None:
            catalog_path = BASE_DIR / "services" / "thandev-brain" / "catalog" / "catalog.json"
        
        self.catalog_path = catalog_path
        self._catalog = self._load_catalog()
        self._tool_mode_map = self._build_tool_mode_map()
    
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
                
                # Go tools (nuclei, httpx, ffuf, dalfox) are typically in ~/go/bin
                if tool_id in ["nuclei", "httpx", "ffuf", "dalfox"]:
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
                
                # Ensure additionalProperties is false for strict validation
                strict_schema = dict(params_schema)
                if "additionalProperties" not in strict_schema:
                    strict_schema["additionalProperties"] = False
                
                validator = Draft202012Validator(strict_schema)
                validator.validate(params)
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
        
        # Add metadata
        if scan_job_id:
            internal_kwargs["scan_job_id"] = scan_job_id
        if job_dir:
            internal_kwargs["scan_job_dir"] = job_dir
        
        # Determine scan_level from mode_id (for backward compatibility)
        # This is a temporary mapping until we fully remove scan_level dependency
        scan_level = self._infer_scan_level_from_mode(mode_id)
        
        logger.info(f"Executing tool_id={tool_id}, mode_id={mode_id} on {target_url}")
        
        # Track execution time (like run_tool does)
        start_time = datetime.utcnow()
        
        try:
            # Call internal tool runner
            tool_runner = self.supported_tools[tool_id]
            result = await tool_runner(target_url, scan_level, **internal_kwargs)
            
            # Calculate and add execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            result["execution_time"] = execution_time
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
        
        # Pass through timeout if specified in constraints
        constraints = mode_config.get("constraints", {})
        if "max_timeout_sec" in constraints:
            internal["timeout_seconds"] = constraints["max_timeout_sec"]
        
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
        # Check if nuclei is installed
        # Try common locations for nuclei (in order of preference)
        nuclei_binary = None
        possible_paths = [
            os.path.expanduser("~/go/bin/nuclei"),  # Go bin directory (most common)
            os.path.expanduser("~/.local/thandev-tools/bin/nuclei"),  # Local tools directory
            "/usr/local/bin/nuclei",
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
                    # Check if command exists in PATH
                    check_result = subprocess.run(
                        ["which", binary_path],
                        capture_output=True,
                        timeout=2,
                        text=True
                    )
                    if check_result.returncode == 0:
                        nuclei_binary = check_result.stdout.strip()
                        logger.info(f"Found nuclei binary at: {nuclei_binary}")
                        break
            except Exception:
                continue
        
        if not nuclei_binary:
            return {
                "tool_name": "nuclei",
                "output": "",
                "exit_code": -1,
                "error": "Nuclei binary not found or not executable. Please install nuclei: go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest (ensure ~/go/bin is in PATH)",
                "command": "nuclei -version",
            }
        
        try:
            check_result = subprocess.run(
                [nuclei_binary, "-version"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if check_result.returncode != 0:
                raise FileNotFoundError("nuclei command failed")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return {
                "tool_name": "nuclei",
                "output": "",
                "exit_code": -1,
                "error": "Nuclei binary not found or not executable. Please install nuclei: go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
                "command": "nuclei -version",
            }
        
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
            tags_map = {
                "basic": "cve,vulnerability,exposure",
                "pro": "cve,vulnerability,exposure,misconfig,default-login",
                "advanced": "cve,vulnerability,exposure,misconfig,default-login,tech,ssl",
            }
            template_tags = tags_map.get(scan_level, tags_map["basic"])
            if profile:
                logger.warning(f"Nuclei profile '{profile}' not found in NUCLEI_PROFILE_TAGS, falling back to scan_level-based tags")
        
        # Nuclei v3.4.10 command flags:
        # -u: target URL (required)
        # -severity: filter by severity levels
        # -tags: filter by template tags (cve, vulnerability, etc.) - only if tags are available
        # -jsonl: output JSON Lines format (one JSON object per line)
        # -silent: suppress non-JSON output (logs go to stderr)
        # -rate-limit: limit requests per second (avoid overwhelming target)
        # -timeout: timeout per request in seconds
        # -retries: number of retries for failed requests
        # DO NOT use -json (not supported in v3.4.10)
        # DO NOT use -t with template paths (causes template update output)
        cmd = [
            nuclei_binary,  # Use the found binary path
            "-u", target_url,
            "-severity", severity_levels,
            "-jsonl",
            "-silent",
            "-rate-limit", "50",  # 50 requests per second
            "-timeout", "10",  # 10 second timeout per request
            "-retries", "1",  # Retry once on failure
        ]
        
        # Add -tags argument only if we have tags
        if template_tags:
            cmd.extend(["-tags", template_tags])
        
        # Get scan job ID from kwargs if available for better logging
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        
        logger.info("Nuclei v3.4.10 command for scan %s: %s", scan_job_id, " ".join(cmd))
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
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
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "nuclei",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out after 30 minutes",
                "command": " ".join(cmd),
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
        scan_map = {
            "basic": ["--top-ports", "100", "-sT", "-Pn", "-sV"],
            "pro": ["-sT", "-Pn", "-sV", "-sC", "--top-ports", "1000"],
            "advanced": ["-sT", "-Pn", "-sV", "-sC", "-A", "-p-"],
        }
        
        scan_args = scan_map.get(scan_level, scan_map["basic"])
        
        cmd = ["nmap", "-oX", "-"] + scan_args + [hostname]
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            
            return {
                "tool_name": "nmap",
                "output": result.stdout or "",
                "exit_code": result.returncode,
                "command": " ".join(cmd),
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            logger.warning(f"nmap execution timed out after {timeout_seconds} seconds for {hostname}")
            return {
                "tool_name": "nmap",
                "output": "",
                "exit_code": -1,
                "error": f"Tool execution timed out after {timeout_seconds} seconds",
                "command": " ".join(cmd),
                "timed_out": True,
                "success": False,
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
        
        cmd = ["sslscan", "--json", target]
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = subprocess.run(
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
            result = subprocess.run(
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
        possible_paths = [
            os.path.expanduser("~/go/bin/httpx"),  # Go bin directory (check first!)
            "/usr/local/bin/httpx",
            "/usr/local/bin/httpx-projectdiscovery",
            "httpx",  # In PATH (check last to avoid Python httpx)
        ]
        
        for binary_path in possible_paths:
            try:
                test_cmd = [binary_path, "-u", "https://example.com", "-silent", "-json"]
                test_result = subprocess.run(
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
            logger.warning("ProjectDiscovery httpx not found. System has Python httpx (HTTP client), not ProjectDiscovery httpx (security scanner)")
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": "ProjectDiscovery httpx binary not found. The system has Python httpx (HTTP client) installed, but we need ProjectDiscovery httpx (security scanner). Install with: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest (or download from https://github.com/projectdiscovery/httpx/releases). After installation, ensure ~/go/bin is in your PATH.",
                "command": "httpx -u <url> -json",
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
            result = subprocess.run(
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
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out after 10 minutes",
                "command": " ".join(cmd),
            }
        except Exception as e:
            logger.error(f"httpx execution error: {e}")
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": f"httpx execution failed: {str(e)}",
                "command": " ".join(cmd),
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
                    check_result = subprocess.run(
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
            check_result = subprocess.run(
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
            result = subprocess.run(
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
        # Check if dalfox is installed
        scan_job_id = kwargs.get("scan_job_id", "unknown")
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
                    check_result = subprocess.run(
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
        
        # Get timeout from config (default: 900 for Pro, 1800 for Advanced)
        default_timeout = 300  # 5 minutes for all scan levels
        timeout = kwargs.get("timeout_seconds", default_timeout)
        
        # Dalfox command flags:
        # url: target URL (required)
        # --silence: suppress banner and non-essential output
        # --format json: output JSON format (one JSON object per line)
        # --mining-dict: use parameter mining dictionary
        # --mining-dom: enable DOM-based parameter mining
        # --follow-redirects: follow HTTP redirects
        # --deep-domxss: enable deep DOM XSS analysis
        # --detailed-analysis: perform detailed parameter analysis
        # --grep: filter results by grep patterns (common XSS indicators)
        # --only-poc: only show findings with proof-of-concept (more reliable findings)
        # --waf-evasion: use WAF evasion techniques
        # --user-agent: set custom user agent to avoid blocking
        
        # Check if URL has query parameters - if not, Dalfox will use mining-dict to discover them
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(target_url)
        has_query_params = bool(parse_qs(parsed_url.query))
        
        # Build comprehensive Dalfox command with all XSS testing options
        cmd = [
            dalfox_binary,
            "url", target_url,
            "--silence",
            "--format", "json",
            "--mining-dict",  # Dictionary-based parameter mining
            "--mining-dom",  # DOM-based parameter mining for better discovery
            "--follow-redirects",
            "--deep-domxss",  # Deep DOM XSS analysis
            "--detailed-analysis",  # Detailed parameter analysis
            "--context-aware",  # Context-aware payload selection for better detection
            # Note: --grep expects a file path, not a string, so we skip it
            # Dalfox has built-in grepping that will detect XSS indicators
            "--only-poc", "g,v",  # Only show findings with proof-of-concept (grep + verified)
            "--waf-evasion",  # Use WAF evasion techniques
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",  # Avoid blocking
            "--remote-payloads", "portswigger,payloadbox",  # Use comprehensive payload lists from PortSwigger and PayloadBox
            "--worker", "50",  # Use 50 parallel workers for faster scanning
        ]
        
        # Add custom payload file if it exists
        payload_file = Path(os.getenv("PAYLOADS_DIR", "/opt/thandev/payloads")) / "xss-payloads.txt"
        if payload_file.exists():
            cmd.extend(["--custom-payload", str(payload_file)])
            logger.debug(
                "Using custom XSS payload file",
                extra={"scan_job_id": scan_job_id, "payload_file": str(payload_file)}
            )
        
        # If URL has no query parameters, add common parameter hints
        # Dalfox will still discover parameters, but this helps with sites that need specific params
        if not has_query_params:
            logger.debug(
                "Target URL has no query parameters, Dalfox will use parameter mining to discover them",
                extra={"scan_job_id": scan_job_id, "target_url": target_url}
            )
        
        logger.info("dalfox command for scan %s: %s (timeout: %d seconds)", 
                   scan_job_id, " ".join(cmd), timeout)
        
        try:
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"tools.py:1436","message":"Dalfox command execution start","data":{"scan_job_id":scan_job_id,"cmd":" ".join(cmd),"timeout":timeout},"timestamp":int(datetime.now().timestamp()*1000)})+'\n')
            # #endregion
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            exit_code = result.returncode
            stdout_bytes = len(result.stdout.encode("utf-8")) if result.stdout else 0
            stderr_bytes = len(result.stderr.encode("utf-8")) if result.stderr else 0
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"tools.py:1443","message":"Dalfox command execution result","data":{"scan_job_id":scan_job_id,"exit_code":exit_code,"stdout_length":stdout_bytes,"stderr_length":stderr_bytes,"stdout_preview":result.stdout[:200] if result.stdout else "","stderr_preview":result.stderr[:200] if result.stderr else ""},"timestamp":int(datetime.now().timestamp()*1000)})+'\n')
            # #endregion
            
            logger.info(
                "Dalfox scan completed",
                extra={
                    "scan_job_id": scan_job_id,
                    "exit_code": exit_code,
                    "stdout_bytes": stdout_bytes,
                    "stderr_bytes": stderr_bytes,
                    "target_url": target_url,
                    "has_query_params": has_query_params,
                    "stdout_preview": result.stdout[:500] if result.stdout else None,
                    "stderr_preview": result.stderr[:500] if result.stderr else None,
                }
            )
            
            # Dalfox may exit with non-zero even when it finds XSS issues
            # Consider it successful if we have output
            is_error = False
            error_msg = None
            
            if exit_code != 0:
                if stdout_bytes > 0:
                    # We have output, so the scan found some XSS issues
                    logger.info(
                        "dalfox scan %s completed with exit_code=%s but produced %d bytes of output (treating as success)",
                        scan_job_id, exit_code, stdout_bytes
                    )
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
                else:
                    logger.info(
                        "dalfox scan %s completed with exit_code=%s and no output (no XSS found, treating as success)",
                        scan_job_id, exit_code
                    )
            
            # Normalize Dalfox output before returning (for all cases)
            # This ensures empty placeholder outputs are converted to [] before file writing
            normalized_output = _normalize_dalfox_output(result.stdout) if result.stdout else "[]"
            
            # #region agent log
            with open('/home/ashwath/thandev/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"tools.py:1565","message":"Dalfox output normalization in tools.py","data":{"scan_job_id":scan_job_id,"stdout_length":len(result.stdout) if result.stdout else 0,"stdout_preview":repr(result.stdout[:100]) if result.stdout else "","normalized_length":len(normalized_output),"normalized_preview":repr(normalized_output[:100])},"timestamp":int(datetime.now().timestamp()*1000)})+'\n')
            # #endregion
            
            if is_error:
                return {
                    "tool_name": "dalfox",
                    "output": normalized_output,  # Normalized output
                    "exit_code": exit_code,
                    "error": error_msg,
                    "command": " ".join(cmd),
                    "timed_out": False,
                }
            
            # Success case
            if stdout_bytes > 0:
                logger.info(
                    "dalfox scan %s successful: found %d bytes of output (XSS issues detected)",
                    scan_job_id, stdout_bytes
                )
            else:
                logger.info("dalfox scan %s completed: no XSS issues detected (exit_code=%s, stderr_bytes=%d)", 
                           scan_job_id, exit_code, stderr_bytes)
            
            return {
                "tool_name": "dalfox",
                "output": normalized_output,
                "exit_code": exit_code,
                "command": " ".join(cmd),
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            logger.warning("dalfox scan %s timed out after %d seconds (%d minutes). Results may be partial.", 
                          scan_job_id, timeout, timeout // 60)
            logger.warning("  Command: %s", " ".join(cmd))
            return {
                "tool_name": "dalfox",
                "output": "[]",  # Normalized empty output
                "exit_code": None,  # None indicates timeout (not a normal exit code)
                "error": f"Tool execution timed out after {timeout} seconds ({timeout // 60} minutes)",
                "command": " ".join(cmd),
                "timed_out": True,
            }
        except Exception as e:
            logger.error(f"dalfox execution error for scan {scan_job_id}: {e}", exc_info=True)
            logger.error(f"  Command: {' '.join(cmd)}")
            logger.error(f"  Target URL: {target_url}")
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
    async def _run_sqlmap(self, target_url: str, scan_level: str, **kwargs) -> Dict:
        """
        Run sqlmap SQL injection scanner
        
        Optional kwargs:
            timeout_seconds: timeout in seconds (default: 900 for 15 minutes)
            profile: profile name (e.g., "sqli_light") - currently not used but available
        """
        # Check if sqlmap is installed
        scan_job_id = kwargs.get("scan_job_id", "unknown")
        mode_id = kwargs.get("mode_id", "sqli_light")
        logger.info(f"Checking sqlmap availability for scan {scan_job_id}, mode={mode_id}")
        
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
                check_result = subprocess.run(
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
        timeout = kwargs.get("timeout_seconds", 300)
        
        # Get output directory from kwargs (scan_job_dir)
        # This should be the same job_dir used by other tools (backend/data/jobs/scan_job_id)
        scan_job_dir = kwargs.get("scan_job_dir")
        if not scan_job_dir:
            # Fallback: try to infer from scan_job_id or create temp directory
            scan_job_id = kwargs.get("scan_job_id", "unknown")
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
        timeout_sec = kwargs.get("timeout_seconds", 300)
        request_timeout = min(60, timeout_sec // 5)  # Request timeout, max 60s
        
        # Build sqlmap command based on mode
        cmd = [sqlmap_path, "--batch"]
        
        # Mode-specific command building
        if mode_id == "sqli_raw_request":
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
            # Basic GET request with URL
            cmd.extend(["-u", target_url])
            
            # Test specific parameters if provided
            param_names = kwargs.get("param_names")
            if param_names:
                cmd.extend(["-p", ",".join(param_names)])
                
        else:
            # Legacy mode: sqli_light (uses --forms)
            cmd.extend(["-u", target_url, "--forms", "--crawl=1"])
        
        # Add common flags
        cmd.extend([
            "--risk", str(risk),
            "--level", str(level),
            "--timeout", str(request_timeout),
            "--time-sec", "5",  # Time-based injection delay
            "--random-agent",
            "--technique", "BEUSTQ",  # Test all techniques
            "--fresh-queries",
            "--threads", "1",  # Single thread
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
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
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
            }
        except subprocess.TimeoutExpired as exc:
            logger.warning("sqlmap scan %s timed out after %d seconds (%d minutes). Checking for partial results...", 
                          scan_job_id, timeout, timeout // 60)
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
        
        cmd = ["sslscan", "--json", target]
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = subprocess.run(
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
            result = subprocess.run(
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
        possible_paths = [
            os.path.expanduser("~/go/bin/httpx"),  # Go bin directory (check first!)
            "/usr/local/bin/httpx",
            "/usr/local/bin/httpx-projectdiscovery",
            "httpx",  # In PATH (check last to avoid Python httpx)
        ]
        
        for binary_path in possible_paths:
            try:
                test_cmd = [binary_path, "-u", "https://example.com", "-silent", "-json"]
                test_result = subprocess.run(
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
            logger.warning("ProjectDiscovery httpx not found. System has Python httpx (HTTP client), not ProjectDiscovery httpx (security scanner)")
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": "ProjectDiscovery httpx binary not found. The system has Python httpx (HTTP client) installed, but we need ProjectDiscovery httpx (security scanner). Install with: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest (or download from https://github.com/projectdiscovery/httpx/releases). After installation, ensure ~/go/bin is in your PATH.",
                "command": "httpx -u <url> -json",
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
            result = subprocess.run(
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
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out after 10 minutes",
                "command": " ".join(cmd),
            }
        except Exception as e:
            logger.error(f"httpx execution error: {e}")
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": f"httpx execution failed: {str(e)}",
                "command": " ".join(cmd),
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
                    check_result = subprocess.run(
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
            check_result = subprocess.run(
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
            result = subprocess.run(
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
        
        cmd = ["sslscan", "--json", target]
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = subprocess.run(
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
            result = subprocess.run(
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
        possible_paths = [
            os.path.expanduser("~/go/bin/httpx"),  # Go bin directory (check first!)
            "/usr/local/bin/httpx",
            "/usr/local/bin/httpx-projectdiscovery",
            "httpx",  # In PATH (check last to avoid Python httpx)
        ]
        
        for binary_path in possible_paths:
            try:
                test_cmd = [binary_path, "-u", "https://example.com", "-silent", "-json"]
                test_result = subprocess.run(
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
            logger.warning("ProjectDiscovery httpx not found. System has Python httpx (HTTP client), not ProjectDiscovery httpx (security scanner)")
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": "ProjectDiscovery httpx binary not found. The system has Python httpx (HTTP client) installed, but we need ProjectDiscovery httpx (security scanner). Install with: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest (or download from https://github.com/projectdiscovery/httpx/releases). After installation, ensure ~/go/bin is in your PATH.",
                "command": "httpx -u <url> -json",
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
            result = subprocess.run(
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
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out after 10 minutes",
                "command": " ".join(cmd),
            }
        except Exception as e:
            logger.error(f"httpx execution error: {e}")
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": f"httpx execution failed: {str(e)}",
                "command": " ".join(cmd),
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
                    check_result = subprocess.run(
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
            check_result = subprocess.run(
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
            result = subprocess.run(
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
        
        cmd = ["sslscan", "--json", target]
        
        # Get timeout from kwargs (set by scan_orchestrator based on scan level)
        timeout_seconds = kwargs.get("timeout_seconds", 300)
        
        try:
            result = subprocess.run(
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
            result = subprocess.run(
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
        possible_paths = [
            os.path.expanduser("~/go/bin/httpx"),  # Go bin directory (check first!)
            "/usr/local/bin/httpx",
            "/usr/local/bin/httpx-projectdiscovery",
            "httpx",  # In PATH (check last to avoid Python httpx)
        ]
        
        for binary_path in possible_paths:
            try:
                test_cmd = [binary_path, "-u", "https://example.com", "-silent", "-json"]
                test_result = subprocess.run(
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
            logger.warning("ProjectDiscovery httpx not found. System has Python httpx (HTTP client), not ProjectDiscovery httpx (security scanner)")
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": "ProjectDiscovery httpx binary not found. The system has Python httpx (HTTP client) installed, but we need ProjectDiscovery httpx (security scanner). Install with: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest (or download from https://github.com/projectdiscovery/httpx/releases). After installation, ensure ~/go/bin is in your PATH.",
                "command": "httpx -u <url> -json",
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
            result = subprocess.run(
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
            }
        except subprocess.TimeoutExpired:
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": "Tool execution timed out after 10 minutes",
                "command": " ".join(cmd),
            }
        except Exception as e:
            logger.error(f"httpx execution error: {e}")
            return {
                "tool_name": "httpx",
                "output": "",
                "exit_code": -1,
                "error": f"httpx execution failed: {str(e)}",
                "command": " ".join(cmd),
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
                    check_result = subprocess.run(
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
            check_result = subprocess.run(
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
            result = subprocess.run(
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
    

