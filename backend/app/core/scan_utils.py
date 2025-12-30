"""
Utilities for scan level normalization and validation
"""
from typing import Union
from app.models.scan import ScanLevel


def normalize_scan_level(value: Union[str, ScanLevel, None]) -> str:
    """
    Normalize scan level input to lowercase string: "basic", "pro", or "advanced".
    
    Accepts:
    - String: "basic", "Basic", "BASIC", "pro", "Pro", "PRO", etc. (case-insensitive)
    - ScanLevel enum: ScanLevel.BASIC, ScanLevel.PRO, ScanLevel.ADVANCED
    - Handles edge cases like "ScanLevel.BASIC" string representation
    
    Returns:
        Lowercase string: "basic", "pro", or "advanced"
        
    Raises:
        ValueError: If value cannot be normalized to a valid scan level
    """
    if value is None:
        raise ValueError("scan_level cannot be None")
    
    # If it's already a ScanLevel enum, use its value
    if isinstance(value, ScanLevel):
        return value.value.lower()
    
    # Convert to string and normalize
    value_str = str(value).strip()
    
    # Handle enum string representation like "ScanLevel.BASIC"
    if value_str.startswith("ScanLevel."):
        # Extract the part after "ScanLevel."
        enum_name = value_str.split(".", 1)[1].strip()
        # Map enum names to values
        enum_to_value = {
            "BASIC": "basic",
            "PRO": "pro",
            "ADVANCED": "advanced",
        }
        value_str = enum_to_value.get(enum_name.upper(), enum_name.lower())
    
    # Normalize to lowercase
    value_str = value_str.lower().strip()
    
    # Validate
    valid_levels = {"basic", "pro", "advanced"}
    if value_str not in valid_levels:
        raise ValueError(
            f"Invalid scan_level: '{value}'. Must be one of: {', '.join(sorted(valid_levels))}"
        )
    
    return value_str


def scan_level_to_enum(scan_level_str: str) -> ScanLevel:
    """
    Convert normalized scan level string to ScanLevel enum.
    
    Args:
        scan_level_str: Lowercase string "basic", "pro", or "advanced"
        
    Returns:
        ScanLevel enum value
        
    Raises:
        ValueError: If scan_level_str is not a valid scan level
    """
    normalized = normalize_scan_level(scan_level_str)
    
    # Map to enum
    enum_map = {
        "basic": ScanLevel.BASIC,
        "pro": ScanLevel.PRO,
        "advanced": ScanLevel.ADVANCED,
    }
    
    return enum_map[normalized]

