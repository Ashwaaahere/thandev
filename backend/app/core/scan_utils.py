"""
Utilities for scan level normalization and validation

CRITICAL: These functions ensure scan_level is always normalized to ScanLevel enum instances,
which are then properly serialized to database values (lowercase strings) via TypeDecorator.
"""
from typing import Union
from app.models.scan import ScanLevel


def normalize_scan_level(value: Union[str, ScanLevel, None]) -> ScanLevel:
    """
    Normalize scan level input to ScanLevel enum instance.
    
    Accepts:
    - String: "basic", "Basic", "BASIC", "pro", "Pro", "PRO", etc. (case-insensitive)
    - ScanLevel enum: ScanLevel.BASIC, ScanLevel.PRO, ScanLevel.ADVANCED
    - Handles edge cases like "ScanLevel.BASIC" string representation
    
    Returns:
        ScanLevel enum instance (ScanLevel.BASIC, ScanLevel.PRO, or ScanLevel.ADVANCED)
        
    Raises:
        ValueError: If value cannot be normalized to a valid scan level
        
    Example:
        >>> normalize_scan_level("BASIC")
        <ScanLevel.BASIC: 'basic'>
        >>> normalize_scan_level("basic")
        <ScanLevel.BASIC: 'basic'>
        >>> normalize_scan_level(ScanLevel.PRO)
        <ScanLevel.PRO: 'pro'>
    """
    if value is None:
        raise ValueError("scan_level cannot be None")
    
    # If it's already a ScanLevel enum, return as-is
    if isinstance(value, ScanLevel):
        return value
    
    # Convert to string and normalize
    value_str = str(value).strip()
    
    # Handle enum string representation like "ScanLevel.BASIC"
    if value_str.startswith("ScanLevel."):
        # Extract the part after "ScanLevel."
        enum_name = value_str.split(".", 1)[1].strip()
        # Map enum names directly to enum instances
        enum_name_map = {
            "BASIC": ScanLevel.BASIC,
            "PRO": ScanLevel.PRO,
            "ADVANCED": ScanLevel.ADVANCED,
        }
        if enum_name.upper() in enum_name_map:
            return enum_name_map[enum_name.upper()]
        # Fall through to string normalization
    
    # Normalize to lowercase
    value_str = value_str.lower().strip()
    
    # Validate and map to enum
    enum_map = {
        "basic": ScanLevel.BASIC,
        "pro": ScanLevel.PRO,
        "advanced": ScanLevel.ADVANCED,
    }
    
    if value_str not in enum_map:
        valid_levels = sorted(enum_map.keys())
        raise ValueError(
            f"Invalid scan_level: '{value}'. Must be one of: {', '.join(valid_levels)}"
        )
    
    return enum_map[value_str]


def scan_level_to_enum(scan_level_str: str) -> ScanLevel:
    """
    Convert scan level string to ScanLevel enum.
    
    DEPRECATED: Use normalize_scan_level() instead, which handles both strings and enums.
    This function is kept for backward compatibility.
    
    Args:
        scan_level_str: String "basic", "pro", or "advanced" (case-insensitive)
        
    Returns:
        ScanLevel enum value
        
    Raises:
        ValueError: If scan_level_str is not a valid scan level
    """
    return normalize_scan_level(scan_level_str)

