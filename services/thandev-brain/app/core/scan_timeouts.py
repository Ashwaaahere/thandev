"""
Scan timeout configuration for brain service
Mirrors backend/app/core/scan_timeouts.py to ensure consistency
"""
from typing import Dict

# Scan timeouts by level and tool
# These should match backend/app/core/scan_timeouts.py
SCAN_TIMEOUTS: Dict[str, Dict] = {
    "basic": {
        "max_total_seconds": 600,
        "per_tool": {
            "httpx": 30,
            "sslscan": 180,  # Increased from 120 to 180 for slow SSL connections
            "zap": 300,  # Passive scan + short spider
            "nuclei": 180,  # Safe tags, low rate
        }
    },
    "pro": {
        "max_total_seconds": 3600,  # 60 minutes total (increased for medium-sized web apps)
        "per_tool": {
            "httpx": 30,
            "sslscan": 300,  # 5 minutes (increased from 90s - SSL scans need more time for thorough analysis)
            "nmap": 600,  # 10 minutes (port scans can take longer on medium-sized apps)
            "zap": 1800,  # 30 minutes (increased from 20min - active scans need more time for medium-sized apps)
            "nuclei": 1800,  # 30 minutes (increased for comprehensive scanning of medium-sized apps)
            "dalfox": 1500,  # 25 minutes (increased from 20min - XSS testing needs more time for medium-sized apps)
        }
    },
    "advanced": {
        "max_total_seconds": 5400,  # 1.5 hours total (increased for complex targets)
        "per_tool": {
            "httpx": 30,
            "sslscan": 180,  # 3 minutes (normally 30s, 6x safety buffer)
            "nmap": 1800,  # 30 minutes (comprehensive scan)
            "zap": 2700,  # 45 minutes (increased from 20min - advanced scans run ajax_spider + active_scan, needs more time for comprehensive testing)
            "nuclei": 1800,  # 30 minutes (comprehensive template scanning - increased from 15min)
            "dalfox": 2400,  # 40 minutes (thorough XSS testing - increased from 20min)
            "sqlmap": 2400,  # 40 minutes (thorough SQLi testing - increased from 20min)
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


def get_tool_timeout(scan_level: str, tool_id: str) -> int:
    """
    Get timeout for a specific tool at a given scan level.
    
    Args:
        scan_level: Scan level ("basic", "pro", "advanced")
        tool_id: Tool identifier (e.g., "nuclei", "dalfox")
        
    Returns:
        Timeout in seconds (default: 300 if not found)
    """
    scan_level_lower = scan_level.lower()
    
    if scan_level_lower not in SCAN_TIMEOUTS:
        return 300  # Default timeout
    
    tool_timeouts = SCAN_TIMEOUTS[scan_level_lower].get("per_tool", {})
    return tool_timeouts.get(tool_id, 300)  # Default to 300s if tool not found


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

