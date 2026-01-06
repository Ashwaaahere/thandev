"""
Tool catalog loader
Loads the catalog from JSON file
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any

from app.models import CatalogResponse, ToolDefinition, ModeDefinition

logger = logging.getLogger(__name__)

# Catalog file path (relative to this file)
CATALOG_FILE = Path(__file__).parent.parent / "catalog" / "catalog.json"


def load_catalog() -> Dict[str, Any]:
    """
    Load the tool catalog from JSON file.
    
    Returns:
        Dictionary with tools and metadata
        
    Raises:
        FileNotFoundError: If catalog file doesn't exist
        ValueError: If catalog is invalid
    """
    if not CATALOG_FILE.exists():
        logger.warning(f"Catalog file not found at {CATALOG_FILE}, using empty catalog")
        return {
            "tools": [],
            "metadata": {
                "version": "1.0.0",
                "loaded_at": None,
            }
        }
    
    try:
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            catalog_data = json.load(f)
        
        # Validate structure
        if not isinstance(catalog_data, dict):
            raise ValueError("Catalog must be a JSON object")
        
        if "tools" not in catalog_data:
            catalog_data["tools"] = []
        
        if "metadata" not in catalog_data:
            catalog_data["metadata"] = {}
        
        logger.info(f"Loaded catalog with {len(catalog_data.get('tools', []))} tools")
        return catalog_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse catalog JSON: {e}")
        raise ValueError(f"Invalid catalog JSON: {e}")
    except Exception as e:
        logger.error(f"Failed to load catalog: {e}", exc_info=True)
        raise


def get_tool_definition(tool_id: str) -> Dict[str, Any]:
    """
    Get a specific tool definition from the catalog.
    
    Args:
        tool_id: Tool identifier
        
    Returns:
        Tool definition dictionary
        
    Raises:
        ValueError: If tool not found
    """
    catalog = load_catalog()
    
    for tool in catalog.get("tools", []):
        if tool.get("tool_id") == tool_id:
            return tool
    
    raise ValueError(f"Tool '{tool_id}' not found in catalog")


def get_mode_definition(tool_id: str, mode_id: str) -> Dict[str, Any]:
    """
    Get a specific mode definition from the catalog.
    
    Args:
        tool_id: Tool identifier
        mode_id: Mode identifier
        
    Returns:
        Mode definition dictionary
        
    Raises:
        ValueError: If tool or mode not found
    """
    tool = get_tool_definition(tool_id)
    
    for mode in tool.get("modes", []):
        if mode.get("mode_id") == mode_id:
            return mode
    
    raise ValueError(f"Mode '{mode_id}' not found for tool '{tool_id}'")




