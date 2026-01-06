"""
Tool name normalization utilities.

Ensures consistent, canonical tool names across the system.
Tool names are normalized to lowercase for consistency.
"""
import logging

logger = logging.getLogger(__name__)

# Canonical tool name mappings
# Maps common variations to canonical lowercase names
TOOL_NAME_MAPPINGS = {
    "dalfox": "dalfox",
    "Dalfox": "dalfox",
    "DALFOX": "dalfox",
    "nuclei": "nuclei",
    "Nuclei": "nuclei",
    "NUCLEI": "nuclei",
    "nmap": "nmap",
    "Nmap": "nmap",
    "NMAP": "nmap",
    "httpx": "httpx",
    "Httpx": "httpx",
    "HTTPX": "httpx",
    "ffuf": "ffuf",
    "Ffuf": "ffuf",
    "FFUF": "ffuf",
    "sslscan": "sslscan",
    "Sslscan": "sslscan",
    "SSLSCAN": "sslscan",
    "sqlmap": "sqlmap",
    "Sqlmap": "sqlmap",
    "SQLMAP": "sqlmap",
}


def canonical_tool_name(name: str | None) -> str:
    """
    Normalize tool name to canonical lowercase form.
    
    This function ensures consistent tool naming across the system:
    - Normalizes to lowercase
    - Strips whitespace
    - Handles None/empty strings
    - Maps common variations to canonical names
    
    Args:
        name: Tool name (can be None, empty string, or any case variation)
        
    Returns:
        Canonical tool name (lowercase, e.g., "dalfox", "nuclei", "nmap")
        Returns "unknown" if name is None or empty after normalization
    """
    if not name:
        return "unknown"
    
    # Strip whitespace and convert to lowercase
    normalized = str(name).strip().lower()
    
    if not normalized:
        return "unknown"
    
    # Check if we have a direct mapping
    if normalized in TOOL_NAME_MAPPINGS:
        return TOOL_NAME_MAPPINGS[normalized]
    
    # If already lowercase and matches a canonical name, return as-is
    # This handles cases where name is already canonical
    canonical_names = set(TOOL_NAME_MAPPINGS.values())
    if normalized in canonical_names:
        return normalized
    
    # For tool_id format (e.g., "tool-dalfox-v2"), extract the base name
    # This handles brain service tool_id formats
    if "-" in normalized:
        parts = normalized.split("-")
        # Check if any part matches a canonical name
        for part in parts:
            if part in canonical_names:
                return part
    
    # If no mapping found, return normalized lowercase version
    # Log a warning for unknown tool names to help identify new tools
    if normalized not in canonical_names:
        logger.debug(f"Unknown tool name '{name}' normalized to '{normalized}' (not in canonical list)")
    
    return normalized


