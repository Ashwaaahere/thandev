"""
Tool Matrix Configuration
Single source of truth for which tools run at each scan level.

This module defines the tool matrix that maps scan levels to the tools that should
be executed. This centralizes tool selection logic and makes it easy to add new
tools or modify existing tool configurations.

To add a new tool:
1. Implement the tool runner in app/services/tools.py (ToolExecutor)
2. Add a ToolConfig entry for the desired scan levels in TOOL_MATRIX
3. Extend the orchestration routing logic if needed
"""
from __future__ import annotations

from typing import TypedDict, List
from enum import Enum

from app.models.scan import ScanLevel


class ToolConfig(TypedDict, total=False):
    """Configuration for a single tool in the scan matrix"""
    key: str  # Tool identifier (e.g., "nuclei", "nmap", "sslscan")
    enabled: bool  # Whether this tool is enabled for this scan level
    # Optional tool-specific configuration fields
    intensity: str  # For httpx: "low", "medium", "high"
    profile: str  # For nuclei/nmap: profile name (e.g., "basic_web", "pro_web", "advanced_web", "top_ports", "full_ports_scripts")
    wordlist: str  # For ffuf: wordlist filename (e.g., "ffuf-pro.txt", "ffuf-advanced.txt")
    timeout_seconds: int  # Optional timeout override


# Tool Matrix: Maps scan levels to list of tools to run
# This is the single source of truth for tool selection per scan level
TOOL_MATRIX: dict[ScanLevel, List[ToolConfig]] = {
    ScanLevel.BASIC: [
        {"key": "httpx", "enabled": True, "intensity": "low"},
        {"key": "nuclei", "enabled": True, "profile": "basic_web"},
        {"key": "zap", "enabled": True, "mode": "passive_spider", "timeout_seconds": 300},
    ],
    ScanLevel.PRO: [
        {"key": "httpx", "enabled": True, "intensity": "medium"},
        {"key": "nuclei", "enabled": True, "profile": "pro_web"},
        {"key": "nmap", "enabled": True, "profile": "top_ports"},
        {"key": "sslscan", "enabled": True},
        {"key": "dalfox", "enabled": True, "timeout_seconds": 1500},  # 25 minutes for PRO scans
        {"key": "zap", "enabled": True, "mode": "active_scan", "timeout_seconds": 1800},  # 30 minutes for PRO scans (matches scan_timeouts.py)
    ],
    ScanLevel.ADVANCED: [
        {"key": "httpx", "enabled": True, "intensity": "high"},
        {"key": "nuclei", "enabled": True, "profile": "advanced_web"},
        {"key": "dalfox", "enabled": True, "aggressiveness": "high"},
        {"key": "nmap", "enabled": True, "profile": "full_ports_scripts"},
        {"key": "sslscan", "enabled": True},
        {"key": "sqlmap", "enabled": True, "timeout_seconds": 2400},  # 40 minutes for thorough SQLi testing
        {"key": "zap", "enabled": True, "mode": "ajax_spider", "timeout_seconds": 600},  # AJAX spider first
        {"key": "zap", "enabled": True, "mode": "active_scan", "timeout_seconds": 1800},  # Then active scan (increased timeout)
        # NOTE: Future/experimental tools removed from active matrix
        # These tools are not yet fully wired or stable:
        # - xss_experimental (Playwright-based XSS checks)
        # - ssrf_oob (OOB SSRF interaction testing)
        # - cmdi_oob (OOB Command Injection testing)
        # - subfinder (subdomain enumeration)
        # - gitleaks (secret scanning)
        # - nikto, amass, gobuster, crt.sh, sslyze (referenced in presets but not in main tool matrix)
    ],
}


def get_tools_for_level(level: ScanLevel | str) -> List[ToolConfig]:
    """
    Get the list of tool configurations for a given scan level.
    
    Args:
        level: ScanLevel enum or string representation ("basic", "pro", "advanced")
        
    Returns:
        List of ToolConfig dictionaries for the scan level
        
    Raises:
        ValueError: If level is not a valid ScanLevel
        
    Example:
        >>> tools = get_tools_for_level(ScanLevel.BASIC)
        >>> # Returns: [{"key": "nuclei", "enabled": True}]
        >>> 
        >>> tools = get_tools_for_level("pro")
        >>> # Returns: [{"key": "nuclei", "enabled": True}, {"key": "nmap", "enabled": True}]
    """
    # Handle string input (for backward compatibility)
    if isinstance(level, str):
        level_lower = level.lower()
        try:
            level = ScanLevel(level_lower)
        except ValueError:
            valid_levels = ", ".join([l.value for l in ScanLevel])
            raise ValueError(
                f"Invalid scan level: '{level}'. "
                f"Allowed values are: {valid_levels}"
            )
    
    if level not in TOOL_MATRIX:
        valid_levels = ", ".join([l.value for l in TOOL_MATRIX.keys()])
        raise ValueError(
            f"Scan level '{level.value}' not found in tool matrix. "
            f"Valid levels: {valid_levels}"
        )
    
    return TOOL_MATRIX[level]


def get_enabled_tool_keys(level: ScanLevel | str) -> List[str]:
    """
    Get the list of enabled tool keys (names) for a given scan level.
    
    Args:
        level: ScanLevel enum or string representation
        
    Returns:
        List of tool key strings (e.g., ["nuclei", "nmap"])
        
    Example:
        >>> keys = get_enabled_tool_keys(ScanLevel.PRO)
        >>> # Returns: ["nuclei", "nmap"]
    """
    tools = get_tools_for_level(level)
    return [tool["key"] for tool in tools if tool.get("enabled", True)]


def is_tool_enabled_for_level(tool_key: str, level: ScanLevel | str) -> bool:
    """
    Check if a specific tool is enabled for a given scan level.
    
    Args:
        tool_key: Tool identifier (e.g., "nuclei", "nmap", "sslscan")
        level: ScanLevel enum or string representation
        
    Returns:
        True if the tool is enabled for this level, False otherwise
        
    Example:
        >>> is_tool_enabled_for_level("nmap", ScanLevel.BASIC)
        False
        >>> is_tool_enabled_for_level("nmap", ScanLevel.PRO)
        True
    """
    tools = get_tools_for_level(level)
    for tool in tools:
        if tool["key"] == tool_key:
            return tool.get("enabled", True)
    return False

