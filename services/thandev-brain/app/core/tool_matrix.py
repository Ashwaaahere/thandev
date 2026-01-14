"""
Tool Matrix Configuration for Brain Service
Defines which tools MUST run for each scan level.
"""
from typing import List, Dict, Any

# Tool matrix: Maps scan levels to required tools
# Brain planner MUST include all these tools, though it can adjust parameters/modes
TOOL_MATRIX: Dict[str, List[Dict[str, Any]]] = {
    "basic": [
        {"tool_id": "httpx", "mode_id": "low"},
        {"tool_id": "nuclei", "mode_id": "basic_web"},
        {"tool_id": "zap", "mode_id": "passive_spider"},
    ],
    "pro": [
        {"tool_id": "httpx", "mode_id": "medium"},
        {"tool_id": "nuclei", "mode_id": "pro_web"},
        {"tool_id": "nmap", "mode_id": "top_ports"},           # REQUIRED for Pro
        {"tool_id": "sslscan", "mode_id": "standard"},         # REQUIRED for Pro
        {"tool_id": "dalfox", "mode_id": "standard"},          # REQUIRED for Pro
        {"tool_id": "zap", "mode_id": "passive_spider"},
        {"tool_id": "zap", "mode_id": "active_scan"},
    ],
    "advanced": [
        {"tool_id": "httpx", "mode_id": "high"},
        {"tool_id": "nuclei", "mode_id": "advanced_web"},
        {"tool_id": "dalfox", "mode_id": "standard"},
        {"tool_id": "nmap", "mode_id": "full_ports_scripts"},
        {"tool_id": "sslscan", "mode_id": "standard"},
        {"tool_id": "sqlmap", "mode_id": "sqli_light"},
        {"tool_id": "zap", "mode_id": "ajax_spider"},
        {"tool_id": "zap", "mode_id": "active_scan"},
    ],
}


def get_required_tools_for_level(scan_level: str) -> List[Dict[str, Any]]:
    """
    Get the list of required tools for a scan level.
    
    Args:
        scan_level: Scan level ("basic", "pro", "advanced")
        
    Returns:
        List of tool configurations with tool_id and mode_id
    """
    scan_level_lower = scan_level.lower()
    return TOOL_MATRIX.get(scan_level_lower, [])


def is_tool_required(tool_id: str, scan_level: str) -> bool:
    """
    Check if a tool is required for a scan level.
    
    Args:
        tool_id: Tool identifier (e.g., "nmap", "dalfox")
        scan_level: Scan level
        
    Returns:
        True if tool is required, False otherwise
    """
    required_tools = get_required_tools_for_level(scan_level)
    return any(t["tool_id"] == tool_id for t in required_tools)
