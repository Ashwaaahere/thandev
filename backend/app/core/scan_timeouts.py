"""
Scan timeout configuration per scan level and per tool.

This module provides timeout settings for different scan levels (basic, pro, advanced)
and per-tool timeouts. These timeouts are enforced during tool execution to prevent
scans from running indefinitely.
"""
import os
from typing import Dict, Optional
from app.models.scan import ScanLevel

# Per-scan-level timeout configuration
# Structure: {scan_level: {"max_total_seconds": int, "per_tool": {tool_name: int}}}
SCAN_TIMEOUTS: Dict[str, Dict] = {
    "basic": {
        "max_total_seconds": 600,  # 10 minutes total
        "per_tool": {
            "httpx": 30,  # 30 seconds
            "sslscan": 180,  # 3 minutes (increased from 120 for slow SSL connections)
            "zap": 300,  # 5 minutes (passive scan + short spider)
            "nuclei": 180,  # 3 minutes (safe tags, low rate)
        }
    },
    "pro": {
        "max_total_seconds": 2400,  # 40 minutes total (increased to accommodate longer tool runs)
        "per_tool": {
            "httpx": 30,  # 30 seconds
            "nuclei": 1500,  # 25 minutes (increased from 20min - comprehensive scanning needs more time)
            "nmap": 600,  # 10 minutes (increased from 5min - port scans can take longer)
            "ffuf": 300,  # 5 minutes
            "sslscan": 90,  # 90 seconds (normally 30s, 3x safety buffer)
            "zap": 1200,  # 20 minutes (increased from 15min - active scans need more time)
            "dalfox": 1200,  # 20 minutes (increased from 15min - XSS testing needs more time)
        }
    },
    "advanced": {
        "max_total_seconds": 5400,  # 1.5 hours total (increased for complex targets)
        "per_tool": {
            "httpx": 30,  # 30 seconds
            "nuclei": 1800,  # 30 minutes (comprehensive template scanning - increased from 15min)
            "nmap": 1800,  # 30 minutes (comprehensive port scan)
            "ffuf": 600,  # 10 minutes
            "sslscan": 180,  # 3 minutes (normally 30s, 6x safety buffer for thorough scan)
            "dalfox": 2400,  # 40 minutes (thorough XSS testing - increased from 20min)
            "sqlmap": 2400,  # 40 minutes (thorough SQLi testing - increased from 20min)
            "zap": 1200,  # 20 minutes (passive + active + ajax spider)
        }
    }
}

# Parallelism control per scan level
# Maximum number of tools to run concurrently
SCAN_PARALLELISM: Dict[str, Dict] = {
    "basic": {
        "max_concurrent": 5,  # Lightweight, can run all basic tools in parallel
    },
    "pro": {
        "max_concurrent": 10,  # Run all Pro tools in parallel (including ZAP's 2 modes)
    },
    "advanced": {
        "max_concurrent": 10,  # Run all Advanced tools in parallel (including ZAP's 2 modes + SQLMap)
    }
}


def get_tool_timeout(scan_level: str, tool_name: str, default: int = 300) -> int:
    """
    Get the timeout for a specific tool at a given scan level.
    
    Args:
        scan_level: Scan level ("basic", "pro", or "advanced")
        tool_name: Tool name (e.g., "nuclei", "nmap")
        default: Default timeout if not configured (default: 300 seconds)
        
    Returns:
        Timeout in seconds
    """
    scan_level_lower = scan_level.lower()
    tool_name_lower = tool_name.lower()
    
    timeout = default
    if scan_level_lower in SCAN_TIMEOUTS:
        per_tool = SCAN_TIMEOUTS[scan_level_lower].get("per_tool", {})
        if tool_name_lower in per_tool:
            timeout = per_tool[tool_name_lower]
    
    # Scale down timeouts in fast test mode (for faster manual integration tests)
    if os.getenv("THANDEV_FAST_MANUAL") == "1":
        # Reduce timeouts by 70% (0.3x) for faster tests
        timeout = int(timeout * 0.3)
        # But ensure minimum 10 seconds
        timeout = max(timeout, 10)
    
    return timeout


def get_max_scan_timeout(scan_level: str, default: int = 3600) -> int:
    """
    Get the maximum total timeout for a scan level.
    
    Args:
        scan_level: Scan level ("basic", "pro", or "advanced")
        default: Default timeout if not configured (default: 3600 seconds)
        
    Returns:
        Maximum total scan timeout in seconds
    """
    scan_level_lower = scan_level.lower()
    
    if scan_level_lower in SCAN_TIMEOUTS:
        return SCAN_TIMEOUTS[scan_level_lower].get("max_total_seconds", default)
    
    return default


def get_max_parallelism(scan_level: str, default: int = 5) -> int:
    """
    Get the maximum number of tools to run concurrently for a scan level.
    
    Args:
        scan_level: Scan level ("basic", "pro", or "advanced")
        default: Default parallelism if not configured (default: 5)
        
    Returns:
        Maximum number of concurrent tools
    """
    scan_level_lower = scan_level.lower()
    
    if scan_level_lower in SCAN_PARALLELISM:
        return SCAN_PARALLELISM[scan_level_lower].get("max_concurrent", default)
    
    return default

