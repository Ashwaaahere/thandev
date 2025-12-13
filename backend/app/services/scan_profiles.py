"""
Scan profiles configuration
Defines which tools to run for each scan level

This module now uses the tool_matrix as the single source of truth for tool selection.
It provides backward-compatible functions that convert tool_matrix data into the
legacy profile format used by some parts of the codebase.

Scan Level Philosophy:
- basic: Fast, lightweight safety scan using nuclei. Non-invasive HTTP vulnerability
  scanning focused on critical and high-severity issues. Minimal impact on target.
- pro: Deeper reconnaissance combining nuclei vulnerability scanning with nmap for
  host and service discovery. Provides network-level visibility and service enumeration.
- advanced: Most comprehensive scan with all available tools (nuclei, nmap, sslscan).
  Slower but more thorough, including SSL/TLS configuration analysis. Best for
  comprehensive security assessments.
"""
from typing import Dict, List, Any
import logging

from app.core.tool_matrix import get_tools_for_level, get_enabled_tool_keys
from app.models.scan import ScanLevel

logger = logging.getLogger(__name__)

# Valid tool identifiers that ToolExecutor supports
# These must match the keys in ToolExecutor.supported_tools
VALID_TOOLS = ["nuclei", "nmap", "sslscan"]

# Scan profile descriptions (metadata only, tool selection comes from tool_matrix)
SCAN_PROFILE_DESCRIPTIONS: Dict[str, str] = {
    "basic": "Fast, lightweight safety scan using nuclei basic HTTP scan (fast, non-invasive)",
    "pro": "Deeper recon using nuclei and nmap for host/service discovery",
    "advanced": "Most comprehensive scan with multiple tools; slower, more thorough",
}

# Legacy SCAN_PROFILES dict - now generated from tool_matrix for backward compatibility
def _build_scan_profiles() -> Dict[str, Dict[str, Any]]:
    """Build SCAN_PROFILES dict from tool_matrix"""
    profiles = {}
    for level in ScanLevel:
        level_str = level.value
        tool_configs = get_tools_for_level(level)
        tools = [
            {
                "name": tool_cfg["key"],
                "config": {}  # Tool-specific config can be added here in the future
            }
            for tool_cfg in tool_configs
            if tool_cfg.get("enabled", True)
        ]
        profiles[level_str] = {
            "description": SCAN_PROFILE_DESCRIPTIONS.get(level_str, ""),
            "tools": tools
        }
    return profiles

SCAN_PROFILES: Dict[str, Dict[str, Any]] = _build_scan_profiles()


def get_profile(scan_level: str) -> Dict[str, Any]:
    """
    Get the scan profile for a given scan level.
    
    This function provides backward compatibility by converting tool_matrix data
    into the legacy profile format. The actual tool selection comes from tool_matrix.
    
    Args:
        scan_level: Scan level string ("basic", "pro", or "advanced")
        
    Returns:
        Dictionary containing the profile configuration with tools list
        
    Raises:
        ValueError: If scan_level is not a valid scan level
        
    Example:
        >>> profile = get_profile("basic")
        >>> tools = profile["tools"]
        >>> # Returns: [{"name": "nuclei", "config": {}}]
    """
    scan_level_lower = scan_level.lower()
    
    if scan_level_lower not in SCAN_PROFILES:
        valid_levels = ", ".join(SCAN_PROFILES.keys())
        raise ValueError(
            f"Invalid scan level: '{scan_level}'. "
            f"Allowed values are: {valid_levels}"
        )
    
    profile = SCAN_PROFILES[scan_level_lower]
    
    # Validate that all tools in the profile are supported
    for tool_config in profile["tools"]:
        tool_name = tool_config.get("name")
        if tool_name not in VALID_TOOLS:
            logger.warning(
                f"Profile '{scan_level_lower}' references unsupported tool: '{tool_name}'. "
                f"Valid tools are: {', '.join(VALID_TOOLS)}"
            )
    
    logger.debug(f"Retrieved profile for scan level '{scan_level_lower}': {len(profile['tools'])} tools")
    return profile


def get_tool_names(scan_level: str) -> List[str]:
    """
    Get the list of tool names to run for a given scan level.
    
    This function now uses tool_matrix as the source of truth.
    
    Args:
        scan_level: Scan level string ("basic", "pro", or "advanced")
        
    Returns:
        List of tool name strings
        
    Raises:
        ValueError: If scan_level is not a valid scan level
    """
    from app.models.scan import ScanLevel
    from app.core.tool_matrix import get_enabled_tool_keys
    
    # Convert string to ScanLevel enum
    try:
        level_enum = ScanLevel(scan_level.lower())
    except ValueError:
        valid_levels = ", ".join([l.value for l in ScanLevel])
        raise ValueError(
            f"Invalid scan level: '{scan_level}'. "
            f"Allowed values are: {valid_levels}"
        )
    
    return get_enabled_tool_keys(level_enum)


def validate_tool_name(tool_name: str) -> bool:
    """
    Check if a tool name is valid and supported
    
    Args:
        tool_name: Name of the tool to validate
        
    Returns:
        True if tool is valid, False otherwise
    """
    return tool_name in VALID_TOOLS
